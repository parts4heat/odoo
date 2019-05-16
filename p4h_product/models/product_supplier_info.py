# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp


class ProductSupplierInfo(models.Model):
    _inherit = 'product.supplierinfo'

    vendor_rule_id = fields.Integer(string='Vendor Rule ID')
    max_qty = fields.Integer(string='Max Qty')

    # To support import of pricelists
    mult = fields.Float('Disc. Mult.',digits=(6,4))
    mult_ds = fields.Float('Disc. Mult. (DS)',digits=(6,4))

    cost_ds = fields.Float('Cost (DS)',digits=dp.get_precision('Product Price'))
    listPrice = fields.Float('Sell For',digits=dp.get_precision('Product Price'))
    listPrice_ds = fields.Float('Sell For (DS)',digits=dp.get_precision('Product Price'))


