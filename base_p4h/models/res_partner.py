# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    customerid = fields.Char(string="Volusion Customer ID")
    fax = fields.Char(string="Fax")
