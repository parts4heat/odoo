# -*- coding: utf-8 -*-

from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    shippingmethodid = fields.Char("Volusion Shipping ID")
