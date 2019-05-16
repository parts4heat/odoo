# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ProductAttributeLine(models.Model):
    _name = 'product.attribute.line'
    _description = 'Product Attribute Line'

    attribute_id = fields.Many2one('product.attribute',string='Attribute')
    model_part_id = fields.Many2one('model.part',string='Model Part')
    value_ids = fields.Many2many('product.attribute.value',string='Attribute Values')

