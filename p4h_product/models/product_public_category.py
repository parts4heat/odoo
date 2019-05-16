# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    categ_id = fields.Integer(string='MIF Category ID')

