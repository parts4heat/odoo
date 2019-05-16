# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    source_doc = fields.Char('MIF Source')

