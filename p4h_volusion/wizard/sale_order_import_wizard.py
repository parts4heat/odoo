# -*- coding: utf-8 -*-
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import base64
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
from xlrd import open_workbook
import pytz
from datetime import datetime

class SaleOrderImportWizard(models.TransientModel):
    _name = 'sale.order.import.wizard'
    _description = 'Sale Order Import Wizard'

    reference = fields.Char(string='Import Reference')
    file = fields.Binary(string='Import File')
    file_name = fields.Char("File Name")

    def action_import_orders(self):
        self.ensure_one()
        if self.file:
            if self.file_name[-3:] != 'xls' and self.file_name[-4:] != 'xlsm' and self.file_name[-4:] != 'xlsx':
               raise ValidationError("FATAL ERROR: Only Excel Files are supported.")

            file = self.file_name
            decoded_file = base64.b64decode(self.file)

            if not self.env.user.tz:
               raise ValidationError("FATAL ERROR: You have no TimeZone set, please do this in User Preferences.")

            user_tz = self.env.user.tz
            local = pytz.timezone(user_tz)
            tz_time = datetime.now(tz=local)

            #raise ValidationError("INFO: Import with Reference '" + self.reference + "' started " + \
            #                       tz_time.strftime('%m-%d-%Y %H:%M') +'.')

            wb = open_workbook(file_contents = base64.decodestring(self.file))

            import_vals = {
                           'name': self.reference,
                           'file_name': self.file_name,
                           'date': tz_time.strftime('%m-%d-%Y %H:%M'),
                          }

            self.env['sale.order.import'].create(import_vals)
            #if len(wb.sheet_names()) > 1:
            #    raise ValidationError("WARNING: Multiple Sheets found - using '" + wb.sheet_names()[0] +"' Sheet.")

            tz_time = datetime.now(tz=local)
            raise ValidationError("INFO: Import with Reference '" + self.file_name + ":" + self.reference + "' finished at " + \
                                   tz_time.strftime('%H:%M') +'.')

        return {'type': 'ir.actions.act_window_close'}
