# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    vendor_id = fields.Char(string="Procurement Vendor")
    customerid = fields.Char(string="Customer ID")
    fax = fields.Char(string="Fax")
