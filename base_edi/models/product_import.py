# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import os
import pprint
import logging
import ntpath
import base64
import sys
import xlrd
from datetime import datetime


from odoo import fields, models, _

_logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)

MAP_HEATER_CODE = {
    1: 'H',
    2: 'DHW',
    3: 'PH',
}


class SyncDocumentType(models.Model):

    _inherit = 'sync.document.type'

    doc_code = fields.Selection(selection_add=[
        ('import_product', 'Import Product'),
    ])

    def initialize_mif_variable(self):
        self.product_import_file = ''
        self.xlsx_file_path = ''
        self.product_img_base64 = False
        self.product_extra_img_base64 = []
        self.product_html_base64 = []
        self.maual_base64 = False
        self.manual_filename = ''
        self.product_attachment_file = ''
        self.miff_file = ''
        self.parts_list_base64 = []
        self.dependancy_label_1 = ''
        self.dependancy_label_2 = ''
        self.dependancy_label_3 = ''
        self.skip_import = False
        self.heater_code = ''
        self.heater_sizes = ''

    def extract_files_from_subdirectory(self, conn, sync_action_id, directory):
        file_path = os.path.join(sync_action_id.dir_path, directory)
        conn.cd(file_path)
        mif_files = conn.ls()
        for file in mif_files:
            if file.endswith(".xlsx"):
                self.xlsx_file_path = os.path.join(sync_action_id.dir_path + directory, file)
                self.product_import_file = conn.download_file(self.xlsx_file_path)
            elif file == directory + ".pdf":
                file_path = os.path.join(sync_action_id.dir_path + directory, 'P-OB-VerB-PN272437.xlsx')
                #pdf = conn.download_file(file_path)
                #print(pdf)

    def _import_products(self, conn, sync_action_id):
        logging_time_start = datetime.now()
        _logger.info(datetime.now().strftime("%a, %d %B %Y %H:%M:%S"))
        try:
            workbook = xlrd.open_workbook(file_contents=self.product_import_file)
            worksheet = workbook.sheet_by_index(0)
            row = 0
            col = 0
            first_row = []
            for col in range(2):
                first_row.append(worksheet.cell_value(row, col))

            # After HEATER CODE TO HEATER END
            heater_codes = {}
            row = 1
            category_ids = []
            index_categories_ids = []
            for r in range(row, worksheet.nrows):
                row += 1
                heater_code = worksheet.cell_value(r, 0)
                if heater_code == 'HEATER END':
                    break

                if heater_code and heater_code != '#':
                    # process category
                    # categories, index_categories = self._process_category(r, worksheet)
                    heater_codes[MAP_HEATER_CODE[r]] = {
                        'name': worksheet.cell_value(r, 1),
                        'description': worksheet.cell_value(r, 2),
                        'code': heater_code,
                        #'index_categories': index_categories,
                        'mfg_id': int(worksheet.cell_value(r, 26)),
                    }
                    # category_ids += categories
                    # index_categories_ids.append(index_categories)
            used_in_row = []
            used_in_row_index = {}
            application_fields = []
            fields_index = []

            for r in range(row, worksheet.nrows):
                name = worksheet.cell_value(r, 0)
                if name == 'CALLOUT':
                    row += 1
                    for col in range(4, 26):
                        v = self.Convert2Str(worksheet.cell(r, col))
                        used_in_row.append(v)
                        if v:
                            used_in_row_index[col] = str(v)
                    application_fields, fields_index, attributes = self.prepare_applications_fields(r, worksheet)
                    self._set_dependency_label(worksheet, r)
                    break
            # print used_in_row
            heater_codes = self.explode_heater_code(heater_codes, used_in_row)
            # attribute_ids = self._create_attribute()
            # attribute_data = self._process_attributes(attributes, attribute_ids)
            # models_data = self._process_models(heater_codes, used_in_row, attribute_data, application_fields, fields_index, used_in_row_index)
            # if not self.skip_import:
            #     self._import_products(row, workbook, worksheet, heater_codes, used_in_row, category_ids, application_fields, fields_index, index_categories_ids, attribute_data, models_data)

        except Exception as e:
            _logger.error(e)

    def _do_import_product(self, conn, sync_action_id, values):
        # change to directory path
        conn.cd(sync_action_id.dir_path)

        for directory in conn.ls():
            try:
                self.initialize_mif_variable()
                self.extract_files_from_subdirectory(conn, sync_action_id, directory)
                if self.product_import_file:
                    self._import_products(conn, sync_action_id)
            except Exception as e:
                _logger.error(e)
            break

    def prepare_applications_fields(self, row, worksheet):
        fields = []
        fields_index = []
        attributes = {}

        def setAttributeValue(field, i):
            try:
                if '[' in field and ']' in field:
                    x = field[field.find("[")+1:field.find("]")]
                    x = [c.strip() for c in x.split(",")]
                    fields.append(x)
                    fields_index.append(i)
                    attributes[i] = x
            except Exception:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                _logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.xlsx_file_path) + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj) + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')

        try:
            for i in range(26, 32):
                setAttributeValue(worksheet.cell_value(row, i), i)  # AA to AF
            setAttributeValue(worksheet.cell_value(row, 33), 33)  # AH
            setAttributeValue(worksheet.cell_value(row, 34), 34)  # AI
            setAttributeValue(worksheet.cell_value(row, 37), 37)  # AL
            setAttributeValue(worksheet.cell_value(row, 38), 38)  # AM
            setAttributeValue(worksheet.cell_value(row, 41), 41)  # AP
            # setAttributeValue(worksheet.cell_value(row, 45), 45)  # AT
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.xlsx_file_path) + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj) + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return fields, fields_index, attributes

    def _set_dependency_label(self, worksheet, row):
        row_length = worksheet.row_len(row) - 1
        try:
            if row_length >= 42 and any(worksheet.cell_value(r, 42) for r in range((row + 1), worksheet.nrows)):
                self.dependancy_label_1 = worksheet.cell_value(row, 42)
                if self.dependancy_label_1.find("["):
                    self.dependancy_label_1 = self.dependancy_label_1[:self.dependancy_label_1.find("[")].strip(" ")

            if row_length >= 43 and any(worksheet.cell_value(r, 43) for r in range((row + 1), worksheet.nrows)):
                self.dependancy_label_2 = worksheet.cell_value(row, 43)
                if self.dependancy_label_1.find("["):
                    self.dependancy_label_2 = self.dependancy_label_2[:self.dependancy_label_2.find("[")].strip(" ")
            if row_length >= 45 and any(worksheet.cell_value(r, 45) for r in range((row + 1), worksheet.nrows)):
                self.dependancy_label_3 = worksheet.cell_value(row, 45)
                if self.dependancy_label_1.find("["):
                    self.dependancy_label_3 = self.dependancy_label_3[:self.dependancy_label_3.find("[")].strip(" ")

        except Exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.xlsx_file_path) + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj) + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')

    def explode_heater_code(self, heater_codes, used_in_row):
        """
            this function will explode the heater code
            # HTR[150-400]CH[N,P]M[ASME,ASHI,HALT,CAN,CANH]
            # converted something like below
            [HTR, [150,400], CH, [N,P], M, [ASME,ASHI,HALT,CAN,CANH] ]

        """
        for code in heater_codes:
            self.heater_code = self.heater_code + heater_codes[code]['code'] + ' ' + '.........' + ' '
        self.heater_code = self.heater_code[:-10]

        for rowval in used_in_row:
            if len(rowval) > 1:
                self.heater_sizes = self.heater_sizes + rowval + ' ' + '...' + ' '
        self.heater_sizes = self.heater_sizes[:-4]

        try:
            for code in heater_codes:
                a = []
                i = 0
                c = heater_codes[code]['code']
                c = c.replace('*', '[*]')
                while i < len(c):
                    st = ''
                    if c[i] != "[":
                        x = c.find('[', i)
                        if x < 0:
                            x = len(c)
                        st = c[i:x]
                    else:
                        x = c.find(']', i)
                        st = c[i:x+1]
                        x += 1
                    if '[' in st:
                        st = [str(j) if str(j) and str(j) in used_in_row else j.strip() for j in st[1:-1].split(",")]
                    a.append(st)
                    i = x

                # find model range and replace - by comma
                # TODO: replace model range by it alss size like [150-400] to [150,200,300,400]
                filtered_uir = [str(uir) for uir in filter(None, used_in_row)]
                model_range_found = False
                for idx, z in enumerate(a):
                    if isinstance(z, list):
                        if all(str(i) in filtered_uir for i in z[0].split('-')):
                            a[idx] = z[0].split('-')
                            model_range_found = True
                            break
                        elif all(str(i) in filtered_uir for i in z):
                            a[idx] = z
                            model_range_found = True
                            break
                if not model_range_found:
                    _logger.error('FAILURE! Model range not found in this mif ' + ntpath.basename(self.xlsx_file_path))
                    self.skip_import = True
                    raise ValueError('Model range not found')

                heater_codes[code]['code'] = a
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.xlsx_file_path) + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj) + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return heater_codes

    # ===================================================
    # Helper MEthods
    # ===================================================

    def Convert2Str(self, cell):
        if cell.ctype is xlrd.XL_CELL_NUMBER:
            is_float = cell.value % 1 != 0.0
            return str(cell.value) if is_float else str(int(cell.value))
        return cell.value

    def RepresentsInt(self, s):
        try:
            int(s)
            return True
        except ValueError:
            return False
