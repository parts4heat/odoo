# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

import logging
#Get the logger
_logger = logging.getLogger(__name__)

# class product_external_id(models.Model):
#     _name = 'product_external_id.product_external_id'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         self.value2 = float(self.value) / 100

class productTemplate(models.Model):
    _inherit = 'product.template'

    external_id = fields.Char('External ID',compute='_retrieve_external_id')

    @api.depends('default_code')
    def _retrieve_external_id(self):
      res = self.get_external_id()
      for record in self:
        record['external_id'] = res.get(record.id)


    @api.onchange('default_code')
    def onchange_default_code(self):
        if self.default_code:
          self.env.cr.execute("SELECT * FROM ir_model_data WHERE module=%s and name=%s",('p4h',self.default_code))
          if self.env.cr.rowcount > 0:
            raise ValidationError('A part with Internal Reference ' + self.default_code + ' already exists!')
          if '.' in self.default_code:
            raise ValidationError('Internal Reference cannot contain a period!')
          if self._origin:
            if self._origin.default_code != self.default_code:
              self.env.cr.execute("DELETE FROM ir_model_data WHERE module=%s and name=%s", ('p4h',self._origin.default_code))
              self.env.cr.execute(""" INSERT INTO ir_model_data (module, name, model, res_id, date_init, date_update)
                                      VALUES (%s, %s, %s, %s, (now() at time zone 'UTC'), (now() at time zone 'UTC')) """,
                                 ('p4h', self.default_code, 'product.template', self._origin.id))


    @api.model
    def create(self, vals):
      res = super(productTemplate, self).create(vals)
      for record in res:
        if record.default_code:
          self.env.cr.execute(""" INSERT INTO ir_model_data (module, name, model, res_id, date_init, date_update)
                                  VALUES (%s, %s, %s, %s, (now() at time zone 'UTC'), (now() at time zone 'UTC')) """,
                              ('p4h', record.default_code, 'product.template', record.id))
      return res

    @api.multi
    def copy(self, default=None):
      if default is None:
        default = {}
      if self.default_code:
        default.update({
          'default_code': self.id + 1,
        })
      return super(productTemplate, self).copy(default)
