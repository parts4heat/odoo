# -*- coding: utf-8 -*-

import json
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    vendor_id = fields.Char(string="Procurement Vendor")
    customerid = fields.Char(string="Customer ID")
    fax = fields.Char(string="Fax")
    residential = fields.Boolean(string="Residential")
    shipping_account_ids = fields.One2many(
        "res.partner.shipping.account", "partner_id", string="Shipping Accounts"
    )
    shipstation_warehouse_id = fields.Many2one(
        "shipstation.warehouse", string="Shipstation Warehouse"
    )
    attention = fields.Char(string="Attention")

    @api.multi
    def create_shipstation_warehouse_id(self, something=False):
        for record in self:
            isitdefault = False
            if record.id == record.env.user.company_id.partner_id.id:
                isitdefault = True
            company = record.env.user.company_id
            url = "%s/warehouses/createwarehouse" % (company.shipstation_root_endpoint)
            address_object = {
                "name": record.name,
                "street1": record.street,
                "street2": record.street2 or None,
                "city": record.city,
                "state": record.state_id.code,
                "postalCode": record.zip,
                "country": record.country_id.code,
                "phone": record.phone or None,
            }
            python_dict = {
                "warehouseName": record.name,
                "originAddress": address_object,
                "returnAddress": address_object,
                "isDefault": isitdefault,
            }
            data_to_post = json.dumps(python_dict)
            conn = company.shipstation_connection(url, "POST", data_to_post)
            response = conn[0]
            content = conn[1]
            if response.status_code != requests.codes.ok:
                raise UserError(_("%s\n%s: %s" % (url, response.status_code, content)))
            json_object_str = content.decode("utf-8")
            json_object = json.loads(json_object_str)
            vals = {
                "partner_id": record.id,
                "name": json_object["warehouseName"],
                "warehouse_id": json_object["warehouseId"],
                "is_default": json_object["isDefault"],
            }
            shipstation_warehouse = record.env["shipstation.warehouse"].create(vals)
            if record.shipstation_warehouse_id:
                record.shipstation_warehouse_id.unlink()
            record.shipstation_warehouse_id = shipstation_warehouse
