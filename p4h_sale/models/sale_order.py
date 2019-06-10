# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    hold = fields.Boolean(string='On Hold',default=False)
    hold_message = fields.Html(string='Hold Message')
    model_entered = fields.Char(string='Model Entered')
    model_searched = fields.Char(string='Model Searched')
    referrer = fields.Char(string='Referrer')
    serial_entered = fields.Char(string='Serial Entered')
    score = fields.Integer(string='Model Match Score')

    @api.multi
    def _action_confirm(self):
        for record in self:
            if record.order_line:
                for line in record.order_line:
                    if line.product_id != line.original_product_id:
                        break
                    if line.product_id.procurement_method != 'list':
                        break
                    if line.product_id.default_code:
                        product_name = "'[" + line.product_id.default_code + "] " + line.product_id.name + "'"
                    else:
                        product_name = "'" + line.product_id.name + "'"
                    if len(line.product_id.product_tmpl_id.alternate_ids) == 0:
                        record.message_post(body="Product " + product_name + " is configured for Alternate Procurement " + \
                                        "but has no Alternate Products set! Please correct this by " + \
                                        "changing the Procurement Method or definint a list of Alternate Products.")
                        return True
                    products_in_stock = []
                    for product in line.product_id.product_tmpl_id.alternate_ids:
                        if product.product_alt_id.qty_available_not_res >= line.product_uom_qty:
                            products_in_stock.append(product)
                    if len(products_in_stock) == 0:
                        record.message_post(body="None of the Alternates for Product " + product_name + " are in stock " + \
                                        "or can be made.  Please set this line to Drop Ship or remove it from " + \
                                        "the Order.")
                        return True
                    else:
                        products_in_stock.sort(key=lambda l: l.standard_price)
                        line['product_id'] = products_in_stock[0].id
                        message = 'Replacing ' + product_name + ' with ' + line['product_id'].name + \
                                  ' as this is the cheapest alternate product available in stock.'
                        record.message_post(body=message)

        return super(SaleOrder, self)._action_confirm()

