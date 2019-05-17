# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class MifFile(models.Model):
    _name = 'mif.file'
    _description = "MIF File"

    name = fields.Char(string='File Name')


