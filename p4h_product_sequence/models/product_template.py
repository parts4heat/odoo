# Copyright 2004 Tiny SPRL
# Copyright 2016 Sodexis
# Copyright 2018 Eficent Business and IT Consulting Services S.L.
#   (http://www.eficent.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo import exceptions

class ProductProduct(models.Model):
    _inherit = 'product.template'

    p4h_code = fields.Char(
        string="P4H Part",
        required=True,
        default='/',
        help="Set to '/' and save if you want a new internal reference "
             "to be proposed."
    )

    _sql_constraints = [
        ('p4h_code',
         'unique(p4h_code)',
         'P4H Part Numbers must be unique - the one you have chosen has already been used!'),
    ]

    @api.model
    def create(self, vals):
        if 'p4h_code' not in vals or vals['p4h_code'] == '/':
            sequence = self.env.ref('p4h_product_sequence.seq_product_auto')
            vals['p4h_code'] = sequence.next_by_id()
        return super(ProductProduct, self).create(vals)

    @api.multi
    def write(self, vals):
        if ('p4h_code' not in vals or vals['p4h_code'] == '/' ) and not 'alternate_of' in vals:
            sequence = self.env.ref('p4h_product_sequence.seq_product_auto')
            vals['p4h_code'] = sequence.next_by_id()
        return super(ProductProduct, self).write(vals)

    @api.multi
    def copy(self, default=None):
        if default is None:
            default = {}
        if self.p4h_code:
            default.update({
                'p4h_code': _('/'),
            })
        return super(ProductProduct, self).copy(default)
