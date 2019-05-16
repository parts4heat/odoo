# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    mfg_lookup = fields.Integer(string='Manufacturer Lookup')


