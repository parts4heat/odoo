# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError

from odoo.addons import decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class ProductAlternative(models.Model):
    _name = 'product.alternative'
    _description = 'Alternate Product'

    product_tmpl_id = fields.Many2one('product.template', string='Alternate Of')
    product_alt_id = fields.Many2one('product.template', string='Alternate For')

    @api.multi
    def unlink(self):
        for record in self:
          result = self.env.cr.execute('delete from product_alternative where product_tmpl_id = %s or product_alt_id = %s' % (record.product_alt_id.id,record.product_alt_id.id) )
        return super(ProductAlternative, self).unlink()

    @api.model
    def create(self, vals):
        res = super(ProductAlternative, self).create(vals)

        # prevent recursive calls
        if 'stop' in vals:
          return res

        # check for recursive data entry
        if vals['product_tmpl_id'] == vals['product_alt_id']:
            raise UserError("Product cannot be an alternative of itself!")

        # get a list of alternates for the alternate product
        existing_alternates = self.env['product.alternative'].search([('product_tmpl_id','=',vals['product_tmpl_id']),
                                                              ('product_alt_id','!=',vals['product_alt_id'])])

        for alt in existing_alternates:
          #_logger.warning("EXISTING ALTERNATIVE FOUND")
          #_logger.warning("tmpl= "+str(alt.product_tmpl_id.id)+", alt="+ str(alt.product_alt_id.id))
          alt_exists = self.env['product.alternative'].search([('product_tmpl_id','=',alt.product_alt_id.id),
                                                              ('product_alt_id','=',vals['product_alt_id'])])

          if not alt_exists:
            #_logger.warning("ALT DOESNT EXIST")
            #_logger.warning("tmpl= "+str(alt.product_tmpl_id.id)+", alt="+ str(vals['product_alt_id']))
            new_alt={}
            new_alt['product_tmpl_id'] = alt.product_alt_id.id
            new_alt['product_alt_id'] = vals['product_alt_id']
            new_alt['stop'] = True
            res2 = self.create(new_alt)

          alt_inverse_exists = self.env['product.alternative'].search([('product_tmpl_id','=',vals['product_alt_id']),
                                                              ('product_alt_id','=',alt.product_alt_id.id)])
          if not alt_inverse_exists:
            #_logger.warning("ALT INVERSE DOESNT EXIST")
            #_logger.warning("tmpl= "+str(vals['product_alt_id'])+", alt="+ str(alt.product_alt_id.id))
            new_alt_inv={}
            new_alt_inv['product_tmpl_id'] = vals['product_alt_id']
            new_alt_inv['product_alt_id'] = alt.product_alt_id.id
            new_alt_inv['stop'] = True
            res3 = self.create(new_alt_inv)


        # check if the reverse relationship exists
        inverse_exists = self.env['product.alternative'].search([('product_tmpl_id','=',vals['product_alt_id']),
                                                        ('product_alt_id','=',vals['product_tmpl_id'])])

        if not inverse_exists:
          #_logger.warning("CREATING ALTERNATE")
          inverse_product = self.env['product.template'].search([('id','=',vals['product_alt_id'])])
          inverse_product['procurement_method'] = 'list'
          new_inverse = {}
          new_inverse['product_tmpl_id'] = vals['product_alt_id']
          new_inverse['product_alt_id'] = vals['product_tmpl_id']
          new_inverse['stop'] = True
          res4 = self.create(new_inverse)

        return res

class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = 'product.template'

    procurement_method = fields.Selection([
        ('odoo', 'Default (match product)'),
        ('list', 'Alternate (cheapest from list)')], string='Procurement Method',
         compute='_compute_procurement_method')


    @api.depends('alternate_ids')
    def _compute_procurement_method(self):
      for record in self:
        if len(record.alternate_ids) > 0:
          record.procurement_method = 'list'
        else:
          record.procurement_method = 'odoo'

    alternate_ids = fields.One2many('product.alternative','product_tmpl_id','Alternates - Sell as Many')

    # To support import of pricelists
    mult = fields.Float('Discount Multipler',digits=(6,4))
    mult_ds = fields.Float('Discount Multplier (Drop Ship)',digits=(6,4))

    cost_ds = fields.Float('Cost (Drop Ship)',digits=dp.get_precision('Product Price'))
    listPrice_ds = fields.Float('Sales Price (Drop Ship)',digits=dp.get_precision('Product Price'))


