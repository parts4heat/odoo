# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    hold = fields.Boolean(string='On Hold',default=False)
    hold_message = fields.Html(string='Hold Message')
    model_entered = fields.Char(string='Model Entered')
    model_searched = fields.Char(string='Model Searched')
    referrer = fields.Char(string='Referrer')
    serial_entered = fields.Char(string='Serial Entered')
    score = fields.Integer(string='Model Match Score')

    @api.onchange('hold')
    def onchange_hold(self):
        if False:
          raise UserError("Can't take this off Hold!")
          record['hold'] = True
        else:
          record['hold'] = False

    @api.multi
    def action_confirm(self):
        # let blocked become True if there is any reason that the order can't be autoconfirmed
        blocked = False
        for record in self:
          if record.hold:
            record.onchange_hold()
          blocked = True
          record.message_post(body="<p style='color:red'>Unable to Confirm Order!</p><ul><li>Didn't feel like it</li><li>Random reason</li></ul>")

        if blocked:
          res = False
        else:
          res = super(SaleOrder, self).action_confirm()
        return res

