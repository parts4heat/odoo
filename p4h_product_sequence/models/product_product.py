# Copyright 2004 Tiny SPRL
# Copyright 2016 Sodexis
# Copyright 2018 Eficent Business and IT Consulting Services S.L.
#   (http://www.eficent.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _


class ProductProduct(models.Model):
    _inherit = 'product.product'

    p4h_code = fields.Char(
        string="P4H Part",
        related='product_tmpl_id.p4h_code',
    )

