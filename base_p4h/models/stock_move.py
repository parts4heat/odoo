# -*- coding: utf-8 -*-

from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    storage_location_id = fields.Many2one(
        "stock.location",
        string="Storage Location",
        related="product_id.storage_location_id",
    )


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    storage_location_id = fields.Many2one(
        "stock.location",
        string="Storage Location",
        related="product_id.storage_location_id",
    )
