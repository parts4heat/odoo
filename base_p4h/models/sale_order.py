# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
import requests
import logging


_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    paymentmethod = fields.Char("Volusion Payment Method")
    shipdate = fields.Datetime("Volusion Ship Date")
    shipresidential = fields.Boolean("Volusion Ship Residential")
    hold = fields.Boolean(string="On Hold", default=False)
    hold_message = fields.Html(string="Hold Message")
    model_entered = fields.Char(string="Model Entered")
    model_searched = fields.Char(string="Model Searched")
    referrer = fields.Char(string="Referrer")
    serial_entered = fields.Char(string="Serial Entered")
    score = fields.Integer(string="Model Match Score")
    delivery_carrier_code = fields.Many2one(
        "delivery.shipstation.carrier",
        string="Carrier Code",
        related="carrier_id.carrier_code",
    )
    delivery_package = fields.Many2one(
        "delivery.shipstation.package", string="Delivery Package"
    )
    delivery_length = fields.Float(string="Length")
    delivery_width = fields.Float(string="Width")
    delivery_height = fields.Float(string="Height")
    client_account = fields.Many2one(
        "res.partner.shipping.account", string="Client Shipping Acct"
    )
    confirmation = fields.Selection(
        [
            ("none", "None"),
            ("delivery", "Delivery"),
            ("signature", "Signature"),
            ("adult_signature", "Adult Signature"),
            ("direct_signature", "Direct Signature"),
        ],
        string="Delivery Confirmation",
        default="none",
        copy=False,
    )
    all_shipped = fields.Boolean(
        string="All Shipped", store=True, compute="calc_all_shipped"
    )

    @api.depends("state", "order_line.product_uom_qty", "order_line.qty_delivered")
    def calc_all_shipped(self):
        for record in self:
            record.all_shipped = False
            if all(
                l.qty_delivered == l.product_uom_qty
                for l in record.order_line.filtered(
                    lambda x: x.product_id.type in ["consu", "product"]
                )
            ):
                record.all_shipped = True

    @api.onchange("delivery_package")
    def set_dimensions_on_change(self):
        for record in self:
            length = width = height = 0
            if record.delivery_package:
                length = record.delivery_package.delivery_length
                width = record.delivery_package.delivery_width
                height = record.delivery_package.delivery_height
            record.delivery_length = length
            record.delivery_width = width
            record.delivery_height = height

    @api.onchange("partner_id")
    def onchange_account_partner(self):
        for record in self:
            record.client_account = False
            record.set_customer_shipping_account()

    def set_customer_shipping_account(self):
        for record in self:
            if record.partner_id and record.partner_id.shipping_account_ids:
                shipping_account = record.partner_id.shipping_account_ids[0]
                record.client_account = shipping_account

    @api.onchange("client_account")
    def _filter_carriers(self):
        if self.client_account:
            action = {
                "domain": {
                    "carrier_id": [
                        ("carrier_code", "=", self.client_account.carrier_id.id)
                    ]
                }
            }
            return action
        else:
            action = {"domain": {"carrier_id": []}}
            return action

    @api.multi
    def get_shipstation_rates(self):
        for record in self:
            wiz_id = record.env["sale.order.rate.wizard"].create(
                {"order_id": record.id}
            )
            company = record.env.user.company_id
            # Retrieving Carriers
            carrier_url = "%s/carriers" % (company.shipstation_root_endpoint)
            conn = company.shipstation_connection(carrier_url, "GET", False)
            response = conn[0]
            content = conn[1]
            if response.status_code != requests.codes.ok:
                raise UserError(
                    _("%s\n%s: %s" % (carrier_url, response.status_code, content))
                )
            json_object_str = content.decode("utf-8")
            json_object = json.loads(json_object_str)
            new_lines = record.env["sale.order.rate.wizard.line"]
            order_weight = 0
            package_price = 0
            if record.delivery_package:
                order_weight += record.delivery_package.package_weight
                package_price += record.delivery_package.price
            for l in record.order_line:
                if (
                    l.product_id.type in ["product", "consu"]
                    and not l.route_id.non_delivery
                ):
                    measurement = l.product_id.measurement_ids.filtered(
                        lambda x: x.uom_id.id == l.product_uom.id
                    )
                    if not measurement:
                        raise UserError(
                            _(
                                """No measurement found for this product
                                and unit of measure combination. Please
                                make sure to configure the appropriate measurement."""
                            )
                        )
                    order_weight += measurement[0].weight_oz * l.product_uom_qty

            for c in json_object:
                try:
                    url = "%s/shipments/getrates" % (company.shipstation_root_endpoint)
                    python_dict = {
                        "carrierCode": c["code"],
                        "fromPostalCode": company.zip,
                        "toState": record.partner_shipping_id.state_id.code,
                        "toCountry": record.partner_shipping_id.country_id.code,
                        "toPostalCode": record.partner_shipping_id.zip,
                        "toCity": record.partner_shipping_id.city,
                        "residential": record.partner_shipping_id.residential,
                        "confirmation": record.confirmation or False,
                        "weight": {"value": order_weight, "units": "ounces"},
                    }
                    if (
                        record.delivery_package
                        and record.delivery_package.created_by_shipstation
                    ):
                        python_dict.update(
                            {"packageCode": record.delivery_package.code}
                        )
                        if (
                            record.delivery_length > 0
                            and record.delivery_width > 0
                            and record.delivery_height > 0
                        ):
                            python_dict.update(
                                {
                                    "dimensions": {
                                        "units": "inches",
                                        "length": int(record.delivery_length),
                                        "width": int(record.delivery_width),
                                        "height": int(record.delivery_height),
                                    }
                                }
                            )
                    if (
                        record.delivery_package
                        and not record.delivery_package.created_by_shipstation
                    ):
                        python_dict.update({"packageCode": "package"})
                        python_dict.update(
                            {
                                "dimensions": {
                                    "units": "inches",
                                    "length": int(
                                        record.delivery_package.delivery_length
                                    ),
                                    "width": int(
                                        record.delivery_package.delivery_width
                                    ),
                                    "height": int(
                                        record.delivery_package.delivery_height
                                    ),
                                }
                            }
                        )
                    if (
                        not record.delivery_package
                        and record.delivery_length > 0
                        and record.delivery_width > 0
                        and record.delivery_height > 0
                    ):
                        python_dict.update(
                            {
                                "dimensions": {
                                    "units": "inches",
                                    "length": int(record.delivery_length),
                                    "width": int(record.delivery_width),
                                    "height": int(record.delivery_height),
                                }
                            }
                        )
                    data_to_post = json.dumps(python_dict)
                    conn = company.shipstation_connection(url, "POST", data_to_post)
                    response = conn[0]
                    content = conn[1]
                    if response.status_code != requests.codes.ok:
                        raise UserError(
                            _("%s\n%s: %s" % (url, response.status_code, content))
                        )
                    json_object_str = content.decode("utf-8")
                    json_object = json.loads(json_object_str)
                    if len(json_object) > 0:
                        for rate in json_object:
                            delivery_id = record.env["delivery.carrier"].search(
                                [("service_code", "=", rate["serviceCode"])], limit=1
                            )
                            if delivery_id:
                                loaded_rate = (
                                    rate["shipmentCost"] + rate["otherCost"]
                                ) * (1 + (delivery_id.margin / 100)) + package_price
                            else:
                                loaded_rate = rate["shipmentCost"] + rate["otherCost"]
                            data = {
                                "wizard_id": wiz_id.id,
                                "valid": True,
                                "carrier_id": delivery_id.id or False,
                                "carrier_code": c["code"],
                                "service_code": rate["serviceCode"],
                                "service_name": rate["serviceName"],
                                "rate": rate["shipmentCost"] + rate["otherCost"],
                                "loaded_rate": loaded_rate,
                                "other_cost": rate["otherCost"],
                            }
                            new_line = new_lines.create(data)
                            new_lines += new_line
                    else:
                        raise UserError(
                            _(
                                """Rate was not retrieved from Shipstation.
                                Please make sure the service is
                                possible for the delivery address."""
                            )
                        )
                except Exception as E:
                    print(E)
                    continue
            wiz_id.wizard_line_ids += new_lines
            action_data = record.env.ref(
                "base_p4h.action_sale_order_rate_wizard"
            ).read()[0]
            action_data.update({"res_id": wiz_id.id})
            return action_data

    @api.multi
    def set_rate_on_order(self):
        for record in self:
            if record.wizard_id.auction:
                delivery_id = record.env["delivery.carrier"].search(
                    [("auction_service_code", "=", record.service_code)], limit=1
                )
            else:
                delivery_id = record.env["delivery.carrier"].search(
                    [("service_code", "=", record.service_code)], limit=1
                )
            if not delivery_id:
                raise UserError(
                    _(
                        """This service code is not linked to any Odoo
                        delivery method. Please assocaite this service code
                        to one of the delivery methods."""
                    )
                )
            if record.wizard_id.order_id.client_account:
                set_rate = 0
            elif record.list_rate > 0:
                set_rate = record.list_rate
            else:
                set_rate = record.loaded_rate
            record.wizard_id.order_id.write(
                {"carrier_id": delivery_id.id, "delivery_rate": set_rate}
            )
            record.wizard_id.order_id.write({"delivery_price": set_rate})
            record.wizard_id.order_id.write({"delivery_rating_success": True})

    @api.multi
    def _action_confirm(self):
        """
        GFP: Inheriting base function to select the cheapest alternative if
            a) current product does not have availability
            b) has the 'list' procurement_method
            c) has alternates
            d) any of the alternates have availabilty
        if none of these conditions are met it confirms with the existing product
        """
        for record in self:
            for line in record.order_line:
                selected_prod = line.product_id._alternate_check_availability(line)
                if selected_prod:
                    if selected_prod != line.product_id:
                        line.orig_product_id = line.product_id
                        line.product_id = selected_prod
                        message = """
                        %s has been swapped for %s given the alternate configuration of the product.
                        """ % (
                            line.orig_product_id.display_name,
                            line.product_id.display_name,
                        )
                        self.message_post(body=message)
                elif line.product_id.procurement_method == "list":
                    message = """
                    Order confirmed w/ %s since there is no available qty for any of the alternates.
                    """ % (
                        line.product_id.display_name,
                    )
                    self.message_post(body=message)

        return super(SaleOrder, self)._action_confirm()


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    orig_product_id = fields.Many2one(
        "product.product", string="Original Product Selection"
    )


class SaleOrderRateWizard(models.TransientModel):
    _name = "sale.order.rate.wizard"
    _description = "Sale Order Rate Wizard"

    order_id = fields.Many2one("sale.order", string="Order")
    wizard_line_ids = fields.One2many(
        "sale.order.rate.wizard.line", "wizard_id", string="Wizard Lines"
    )
    auction = fields.Boolean(string="Auction Inc")


class SaleOrderRateWizardLine(models.TransientModel):
    _name = "sale.order.rate.wizard.line"
    _description = "Sale Order Rate Wizard Line"

    wizard_id = fields.Many2one("sale.order.rate.wizard", string="Wizard")
    valid = fields.Boolean(string="Valid")
    carrier_id = fields.Many2one("delivery.carrier", string="Delivery method")
    carrier_code = fields.Char(string="Carrier Code")
    service_code = fields.Char(string="Service Code")
    service_name = fields.Char(string="Service Name")
    calc_method = fields.Char(string="Calc Method")
    rate = fields.Float(string="Rate")
    loaded_rate = fields.Float(string="Loaded Rate")
    other_cost = fields.Float(string="Other Cost")
    list_rate = fields.Float(string="Public Rate")

    @api.multi
    def set_rate_on_order(self):
        for record in self:
            if record.wizard_id.auction:
                delivery_id = record.env["delivery.carrier"].search(
                    [("auction_service_code", "=", record.service_code)], limit=1
                )
            else:
                delivery_id = record.env["delivery.carrier"].search(
                    [("service_code", "=", record.service_code)], limit=1
                )
            if not delivery_id:
                raise UserError(
                    _(
                        """This service code is not linked to any Odoo
                        delivery method. Please assocaite this service code
                        to one of the delivery methods."""
                    )
                )
            if record.wizard_id.order_id.client_account:
                set_rate = 0
            elif record.list_rate > 0:
                set_rate = record.list_rate
            else:
                set_rate = record.loaded_rate
            record.wizard_id.order_id.write(
                {"carrier_id": delivery_id.id, "delivery_rate": set_rate}
            )
            record.wizard_id.order_id.write({"delivery_price": set_rate})
            record.wizard_id.order_id.write({"delivery_rating_success": True})
