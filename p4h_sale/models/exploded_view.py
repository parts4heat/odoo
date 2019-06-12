# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ExplodedView(models.Model):
    _name = 'exploded.view'
    _description = "Exploded View"

    binary = fields.Binary(string='Blob')
    file_name = fields.Char(string='File Name')
    model_id = fields.Many2one('product.template',string='Model')
    name = fields.Char(string='Name')


