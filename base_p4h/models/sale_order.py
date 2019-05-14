# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    paymentmethod = fields.Char("Volusion Payment Method")
    shipdate = fields.Datetime("Volusion Ship Date")
    shipresidential = fields.Boolean("Volusion Ship Residential")
