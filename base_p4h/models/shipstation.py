# -*- coding: utf-8 -*-

import logging
import requests
import json
import base64
from odoo import api, fields, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    service_code = fields.Char(string="Service Code")
    carrier_code = fields.Many2one(
        "delivery.shipstation.carrier", string="Carrier Code"
    )
    domestic = fields.Boolean(string="Domestic")
    international = fields.Boolean(string="International")
    created_by_shipstation = fields.Boolean(string="Created by Shipstation")


class DeliveryShipstationCarrier(models.Model):
    _name = "delivery.shipstation.carrier"
    _description = "Shipstation Carriers"

    name = fields.Char(string="Carrier")
    carrier_code = fields.Char(string="Carrier Code")


class ShipstationWarehouse(models.Model):
    _name = "shipstation.warehouse"
    _description = "Shipstation Warehouse"

    partner_id = fields.Many2one("res.partner", string="Partner")
    name = fields.Char(string="Name")
    warehouse_id = fields.Integer(string="Warehouse ID")
    is_default = fields.Boolean(string="Is Default")


class DeliveryShipstationPackage(models.Model):
    _name = "delivery.shipstation.package"
    _description = "Shipstation Package"

    code = fields.Char(string="Code")
    name = fields.Char(string="Name")
    carrier_code = fields.Many2one(
        "delivery.shipstation.carrier", string="Carrier Code"
    )
    domestic = fields.Boolean(string="Domestic")
    international = fields.Boolean(string="International")
    created_by_shipstation = fields.Boolean(string="Created by Shipstation")
    price = fields.Float(string="Package Price")
    delivery_length = fields.Float(string="Length")
    delivery_width = fields.Float(string="Width")
    delivery_height = fields.Float(string="Height")
    package_weight = fields.Float(string="Package Weight")
    inner_delivery_length = fields.Float(string="Inner Length")
    inner_delivery_width = fields.Float(string="Inner Width")
    inner_delivery_height = fields.Float(string="Inner Height")
    max_package_weight = fields.Float(string="Max Weight")


class ShipstationWebhooks(models.Model):
    _name = "shipstation.webhook"
    _description = "Shipstation Webhook"

    company_id = fields.Many2one("res.company", string="Company")
    name = fields.Char(string="Name")
    url = fields.Char(string="Url")
    hook_type = fields.Char(string="Hook Type")
    web_hook_id = fields.Integer(string="Web Hook Id")
    active = fields.Boolean(string="Active")

    @api.multi
    def delete_webhook(self):
        for record in self:
            company = record.env.user.company_id
            if not record.web_hook_id:
                raise UserError(_("There is no id linked to this webhook."))
            url = "%s/webhooks/%s" % (
                company.shipstation_root_endpoint,
                record.web_hook_id,
            )
            conn = company.shipstation_connection(url, "DELETE", False)
            response = conn[0]
            content = conn[1]
            if response.status_code != requests.codes.ok:
                raise UserError(_("%s\n%s: %s" % (url, response.status_code, content)))
            record.unlink()


class ShipstationPostback(models.Model):
    _name = "shipstation.postback"
    _description = "Shipstation Postback"

    name = fields.Char(string="name")
    success = fields.Boolean(string="Success")
    returned_dictionary = fields.Text(string="Returned Dictionary")
    tracking = fields.Char(string="Tracking")
    cost = fields.Char(string="Cost")
    order_num = fields.Char(string="Order #")
    order_id = fields.Char(string="Order Id")
    order_key = fields.Char(string="Order Key")
    service_code = fields.Char(string="Service Code")
    ship_to = fields.Char(string="Ship To")
    exception = fields.Text(string="Exception")

    @api.model
    def create(self, vals):
        res = super(ShipstationPostback, self).create(vals)
        try:
            res.post_shipstation()
        except Exception as e:
            res["exception"] = e
        return res

    @api.multi
    def post_shipstation(self):
        for record in self:
            company = record.env.user.company_id
            url = record.name
            api_key = company.shipstation_key
            secret = company.shipstation_secret
            auth_string = (
                base64.encodestring(("%s:%s" % (api_key, secret)).encode())
                .decode()
                .replace("\n", "")
            )
            headers = {"Authorization": "Basic %s" % auth_string}
            r = requests.get(url, headers=headers)
            content = r.content
            json_object_str = content.decode("utf-8")
            json_object = json.loads(json_object_str)
            record.returned_dictionary = str(
                json.dumps(json_object, indent=4, sort_keys=True)
            )
            for shipment in json_object["shipments"]:
                picking = record.env["stock.picking"].search(
                    [
                        "|",
                        ("id", "=", int(shipment["orderKey"])),
                        ("ss_id", "=", int(shipment["orderId"])),
                    ]
                )
                if picking and not picking.carrier_tracking_ref:
                    picking.carrier_tracking_ref = shipment["trackingNumber"]
                    picking.ss_status = "shipped"
                    picking.message_post(
                        body=_(
                            """<b>Shipstation</b> order to <b>%s</b> via <b>%s</b>
                                w/ tracking number <b>%s</b> cost <b>%s</b>."""
                        )
                        % (
                            shipment["shipTo"]["name"],
                            shipment["serviceCode"],
                            shipment["trackingNumber"],
                            shipment["shipmentCost"],
                        )
                    )
                    if picking.sale_id:
                        picking.sale_id.message_post(
                            body=_(
                                """<b>Shipstation</b> order to <b>%s</b> via <b>%s</b>
                                    w/ tracking number <b>%s</b> cost <b>%s</b>."""
                            )
                            % (
                                shipment["shipTo"]["name"],
                                shipment["serviceCode"],
                                shipment["trackingNumber"],
                                shipment["shipmentCost"],
                            )
                        )
                    record.success = True


class ResPartnerShippingAccount(models.Model):
    _name = "res.partner.shipping.account"
    _description = "Res Partner Shipping Account"

    carrier_id = fields.Many2one(
        "delivery.shipstation.carrier", required=True, string="Carrier"
    )
    partner_id = fields.Many2one("res.partner", required=True, string="Partner")
    name = fields.Char(string="Account Number", required=True)
    zip = fields.Char(string="Zip")

    @api.multi
    def name_get(self):
        def _name_get(d):
            name = d.get("name", "")
            carrier = d.get("carrier", "")
            name = "%s [Acct #: %s]" % (carrier, name)
            return (d["id"], name)

        self.check_access_rights("read")
        self.check_access_rule("read")

        result = []
        for record in self.sudo():
            mydict = {
                "id": record.id,
                "name": record.name,
                "carrier": record.carrier_id.name,
            }
            result.append(_name_get(mydict))
        return result
