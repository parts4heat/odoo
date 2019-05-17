# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    source_doc = fields.Char('MIF Source')

