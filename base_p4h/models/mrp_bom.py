# -*- coding: utf-8 -*-

from odoo import fields, models


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    standard_price = fields.Float(string="Cost", related="product_id.standard_price")
    qty_available = fields.Float(string="QoH", related="product_id.qty_available")
