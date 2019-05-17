# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    original_product_id = fields.Many2one(
        'product.product', string='Ordered',
        domain=[('sale_ok', '=', True)],
        readonly=True, states={'draft': [('readonly', False)],
                                              'sent': [('readonly', False)],
                                              'sale': [('readonly', False)]},)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.original_product_id = self.product_id

    @api.model
    def create(self, values):
        if not values.get('original_product_id'):
            values['original_product_id'] = values.get('product_id')
        record = super(SaleOrderLine, self).create(values)
        return record


