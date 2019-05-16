# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    description_pickingin = fields.Text(string='PutAway', related='product_id.description_pickingin')



