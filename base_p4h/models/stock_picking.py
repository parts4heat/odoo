# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import datetime
import json
import requests


class StockPicking(models.Model):
    _inherit = "stock.picking"

    ss_id = fields.Integer(string="Shipstation ID", copy=False)
    ss_ship_id = fields.Integer(string="Shipment ID", copy=False)
    ss_status = fields.Selection(
        [
            ("awaiting_payment", "Awaiting Payment"),
            ("awaiting_shipment", "Awaiting Shipment"),
            ("shipped", "Shipped"),
            ("on_hold", "On Hold"),
            ("cancelled", "Cancelled"),
        ],
        string="Shipstation Status",
        copy=False,
    )
    ss_address_status = fields.Selection(
        [
            ("Address not yet validated", "Address not Validated"),
            ("Address validated successfully", "Address Validated"),
            ("Address validation warning", "Address Validation Warning"),
            ("Address validation failed", "Address Validation Failed"),
        ],
        string="Shipstation Address",
        copy=False,
    )
    confirmation = fields.Selection(
        [
            ("none", "None"),
            ("delivery", "Delivery"),
            ("signature", "Signature"),
            ("adult_signature", "Adult Signature"),
            ("direct_signature", "Direct Signature"),
        ],
        string="Confirmation method",
        default="none",
        copy=False,
    )
    client_account = fields.Many2one(
        "res.partner.shipping.account", string="Client Shipping Acct"
    )
    delivery_package = fields.Many2one(
        "delivery.shipstation.package", string="Delivery Package"
    )
    delivery_carrier_code = fields.Many2one(
        "delivery.shipstation.carrier",
        string="Carrier Code",
        related="carrier_id.carrier_code",
    )
    delivery_length = fields.Float(string="Length")
    delivery_width = fields.Float(string="Width")
    delivery_height = fields.Float(string="Height")

    @api.constrains("sale_id")
    def add_client_account_if_present(self):
        for record in self:
            if record.sale_id and record.sale_id.client_account:
                record.client_account = record.sale_id.client_account
            if record.sale_id and record.sale_id.delivery_package:
                record.delivery_package = record.sale_id.delivery_package.id
            if record.sale_id:
                record.delivery_length = record.sale_id.delivery_length
                record.delivery_width = record.sale_id.delivery_width
                record.delivery_height = record.sale_id.delivery_height
                record.confirmation = record.sale_id.confirmation
                record.transfer_note = record.sale_id.transfer_note

    @api.multi
    def delete_ssorder(self):
        for record in self:
            company = record.env.user.company_id
            if not record.ss_id:
                raise UserError(
                    _("There is no shipstation order linked to this transfer.")
                )
            url = "%s/orders/%s" % (company.shipstation_root_endpoint, record.ss_id)
            conn = company.shipstation_connection(url, "DELETE", False)
            response = conn[0]
            content = conn[1]
            if response.status_code != requests.codes.ok:
                raise UserError(_("%s\n%s: %s" % (url, response.status_code, content)))
            json_object_str = content.decode("utf-8")
            json_object = json.loads(json_object_str)
            record.write({"ss_status": "cancelled"})
            record.message_post(
                body=_("<b>Shipstation</b> order <b>%s</b> %s")
                % (record.ss_id, json_object["message"])
            )

    @api.multi
    def action_cancel(self):
        super(StockPicking, self).action_cancel()
        for record in self:
            if record.ss_id != 0 and record.ss_status not in ["cancelled", "shipped"]:
                record.delete_ssorder()
            return True

    @api.multi
    def create_update_ssorder(self):
        for record in self:
            company = record.env.user.company_id
            customer = record.partner_id
            nonstandard = False
            if record.sale_id and record.sale_id.client_order_ref:
                ss_name = str(record.sale_id.client_order_ref)
            elif record.sale_id:
                ss_name = str(record.sale_id.name)
            else:
                ss_name = str(record.name)
            selected_email = customer.email
            foreign = False
            if customer.country_id and customer.country_id.code != "US":
                foreign = True
            customer_object = {
                "street1": customer.street,
                "street2": customer.street2 or None,
                "city": customer.city,
                "state": customer.state_id.code,
                "postalCode": customer.zip,
                "country": customer.country_id.code,
                "phone": customer.phone or None,
                "residential": customer.residential,
            }
            if customer.parent_id:
                customer_object.update(
                    {"name": customer.name, "company": customer.parent_id.name}
                )
            else:
                customer_object.update({"name": customer.name})
            url = "%s/orders/createorder" % (company.shipstation_root_endpoint)
            order_item_list = []
            sale_ids_list = []
            packages = []
            # qty_to_use = 0
            # HACK
            component_total = sum(
                [
                    (l.product_id.standard_price * l.product_uom_qty)
                    for l in record.move_lines
                ]
            )
            for p in record.move_lines:
                packages.append(p.package)
                measurement = p.product_id.measurement_ids.filtered(
                    lambda x: x.uom_id == p.product_uom
                )
                if p.product_uom.non_standard:
                    nonstandard = True
                if not measurement:
                    raise UserError(
                        _(
                            "No measurement found for %s for the %s unit of measure."
                            % (p.product_id.name, p.product_uom.name)
                        )
                    )
                if p.sale_line_id:
                    unit_price = p.sale_line_id.price_unit
                    tax_amount = p.sale_line_id.price_reduce_taxinc
                    if (
                        p.sale_line_id.product_id.bom_ids
                        and p.sale_line_id.product_id.bom_ids[0].type == "phantom"
                        and component_total > 0
                    ):
                        share_component = (
                            p.product_id.standard_price * p.product_uom_qty
                        ) / component_total
                        unit_price = round(
                            p.sale_line_id.price_unit * share_component, 2
                        )
                        tax_amount = round(
                            p.sale_line_id.price_reduce_taxinc * share_component, 2
                        )
                    clientref = record.sale_id.client_order_ref
                    sale_ids_list.append(p.sale_line_id.id)
                else:
                    unit_price = p.product_id.product_tmpl_id.list_price
                    clientref = ""
                    tax_amount = 0
                options_dict = [
                    {"name": "Unit of Measure", "value": p.product_uom.name},
                    {"name": "Package #", "value": p.package},
                ]
                if p.sale_line_id:
                    options_dict.append(
                        {"name": "Description", "value": p.sale_line_id.name}
                    )
                name_to_use = p.product_id.display_name
                if foreign:
                    name_to_use = p.product_id.description_comm_invoice
                newitem = {
                    "lineItemKey": str(p.id),
                    # "sku": p.product_id.default_code or p.product_id.name,
                    "name": name_to_use,
                    "weight": {"value": measurement[0].weight_oz, "units": "ounces"},
                    "taxAmount": tax_amount,
                    "quantity": int(p.product_uom_qty),
                    "unitPrice": unit_price,
                    "upc": p.product_id.barcode or None,
                    "options": options_dict,
                }
                # qty_to_use = int(p.product_qty)

                order_item_list.append(newitem)

            if record.sale_id and record.sale_id.hide_source:
                if not record.sale_id.partner_id.shipstation_warehouse_id:
                    raise UserError(
                        _(
                            "There is no shipstation warehouse associated to %s."
                            % (record.sale_id.partner_id)
                        )
                    )
                warehouse = (
                    record.sale_id.partner_id.shipstation_warehouse_id.warehouse_id
                )
            else:
                if not company.partner_id.shipstation_warehouse_id:
                    raise UserError(
                        _(
                            "There is no shipstation warehouse associated to your company %s."
                            % (company.name)
                        )
                    )
                warehouse = company.partner_id.shipstation_warehouse_id.warehouse_id
            add_option = {"warehouseId": warehouse}
            if nonstandard:
                add_option.update({"customField1": "Non-Standard"})
            if record.delivery_package:
                add_option.update({"customField2": record.delivery_package.name})
            num_packages = max([int(l) for l in packages])
            if record.client_account:
                add_option.update(
                    {
                        "billToParty": "third_party",
                        "billToAccount": record.client_account.name,
                        "billToPostalCode": record.client_account.zip,
                        "billToCountryCode": record.partner_id.country_id.code or "US",
                    }
                )
            python_dict = {
                "orderNumber": ss_name,
                "orderKey": str(record.id),
                "orderDate": str(datetime.datetime.now()),
                "billTo": customer_object,
                "shipTo": customer_object,
                "items": order_item_list,
                "orderStatus": record.ss_status or "awaiting_shipment",
                "customerEmail": selected_email,
                "customerNotes": clientref,
                "carrierCode": record.carrier_id.carrier_code.carrier_code,
                "serviceCode": record.carrier_id.service_code,
                "requestedShippingService": record.carrier_id.service_code,
                "confirmation": record.confirmation,
                "internalNotes": "%s Packages" % num_packages,
                "shipByDate": record.scheduled_date,
                "advancedOptions": add_option,
            }
            if (
                record.delivery_package
                and record.delivery_package.created_by_shipstation
            ):
                python_dict.update({"packageCode": record.delivery_package.code})
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

            data_to_post = json.dumps(python_dict)
            conn = company.shipstation_connection(url, "POST", data_to_post)
            response = conn[0]
            content = conn[1]
            if response.status_code != requests.codes.ok:
                raise UserError(_("%s\n%s: %s" % (url, response.status_code, content)))
            json_object_str = content.decode("utf-8")
            json_object = json.loads(json_object_str)
            if record.ss_id == 0:
                record.message_post(
                    body=_(
                        "<b>Shipstation</b> order <b>%s</b> has been <b>created</b> via the API."
                    )
                    % (json_object["orderId"])
                )
            else:
                record.message_post(
                    body=_(
                        "<b>Shipstation</b> order <b>%s</b> has been <b>updated</b> via the API."
                    )
                    % (json_object["orderId"])
                )
            record.write(
                {
                    "ss_id": json_object["orderId"],
                    "ss_status": json_object["orderStatus"],
                    "ss_address_status": json_object["shipTo"]["addressVerified"],
                }
            )

    def get_barcode_view_state(self):
        """ Return the initial state of the barcode view as a dict.
        """
        fields_to_read = self._get_picking_fields_to_read()
        pickings = self.read(fields_to_read)
        for picking in pickings:
            picking["move_line_ids"] = (
                self.env["stock.move.line"]
                .browse(picking.pop("move_line_ids"))
                .read(
                    [
                        "product_id",
                        "location_id",
                        "location_dest_id",
                        "qty_done",
                        "display_name",
                        "product_uom_qty",
                        "product_uom_id",
                        "product_barcode",
                        "owner_id",
                        "lot_id",
                        "lot_name",
                        "package_id",
                        "result_package_id",
                        "dummy_id",
                    ]
                )
            )
            for move_line_id in picking["move_line_ids"]:
                move_line_id["product_id"] = (
                    self.env["product.product"]
                    .browse(move_line_id.pop("product_id")[0])
                    .read(["id", "storage_location_id", "tracking", "barcode"])[0]
                )
                move_line_id["location_id"] = (
                    self.env["stock.location"]
                    .browse(move_line_id.pop("location_id")[0])
                    .read(["id", "display_name"])[0]
                )
                move_line_id["location_dest_id"] = (
                    self.env["stock.location"]
                    .browse(move_line_id.pop("location_dest_id")[0])
                    .read(["id", "display_name"])[0]
                )
                move_line_id["code"] = self.picking_type_code

            picking["location_id"] = (
                self.env["stock.location"]
                .browse(picking.pop("location_id")[0])
                .read(["id", "display_name", "parent_path"])[0]
            )
            picking["location_dest_id"] = (
                self.env["stock.location"]
                .browse(picking.pop("location_dest_id")[0])
                .read(["id", "display_name", "parent_path"])[0]
            )
            picking["group_stock_multi_locations"] = self.env.user.has_group(
                "stock.group_stock_multi_locations"
            )
            picking["group_tracking_owner"] = self.env.user.has_group(
                "stock.group_tracking_owner"
            )
            picking["group_tracking_lot"] = self.env.user.has_group(
                "stock.group_tracking_lot"
            )
            picking["group_production_lot"] = self.env.user.has_group(
                "stock.group_production_lot"
            )
            picking["group_uom"] = self.env.user.has_group("uom.group_uom")
            picking["use_create_lots"] = (
                self.env["stock.picking.type"]
                .browse(picking["picking_type_id"][0])
                .use_create_lots
            )
            picking["use_existing_lots"] = (
                self.env["stock.picking.type"]
                .browse(picking["picking_type_id"][0])
                .use_existing_lots
            )
            picking["show_entire_packs"] = (
                self.env["stock.picking.type"]
                .browse(picking["picking_type_id"][0])
                .show_entire_packs
            )
            picking["actionReportDeliverySlipId"] = self.env.ref(
                "stock.action_report_delivery"
            ).id
            if self.env.user.company_id.nomenclature_id:
                picking["nomenclature_id"] = [
                    self.env.user.company_id.nomenclature_id.id
                ]
        return pickings
