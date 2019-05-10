# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class VolusionOrderImport(models.Model):
    _name = 'sale.order.import'
    _description = 'Volusion Import'

    name = fields.Char("Reference")
    file_name = fields.Char("File Name")
    date = fields.Char("Import Date")
    order_count = fields.Integer("Order Count")
    order_value = fields.Monetary("Order Value")
    messages = fields.Html("Messages")

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Import with this Reference already exists!"),
    ]

