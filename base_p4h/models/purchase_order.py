# -*- coding: utf-8 -*-

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    carrier_id = fields.Many2one("delivery.carrier", string="Shipping Method")


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    volusion_id = fields.Char("Volusion ID")
