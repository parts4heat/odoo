# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ExplodedView(models.Model):
    _name = 'exploded.view'
    _description = "Exploded View"

    binary = fields.Binary(string='Blob')
    model_id = fields.Many2one('product.template')
    name = fields.Char(string='Name')
    file_name = fields.Char()


