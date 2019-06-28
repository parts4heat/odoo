# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    storage_location_id = fields.Many2one(
        "stock.location",
        string="Storage Location",
        related="product_id.storage_location_id",
    )

    @api.constrains("product_id", "location_id")
    def set_true_putaway(self):
        for record in self:
            if (
                record.product_id
                and record.location_id
                and record.location_id.usage == "supplier"
                and record.product_id.storage_location_id
            ):
                record.location_dest_id = record.product_id.storage_location_id


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    storage_location_id = fields.Many2one(
        "stock.location",
        string="Storage Location",
        related="product_id.storage_location_id",
    )
