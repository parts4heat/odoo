# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import os
import pprint
import logging
import ntpath
import re
import base64
import itertools
import copy
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
                self.miff_file = file
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
            attribute_ids = self._create_attribute()
            attribute_data = self._process_attributes(attributes, attribute_ids)
            models_data = self._process_models(heater_codes, used_in_row, attribute_data, application_fields, fields_index, used_in_row_index)
            # if not self.skip_import:
            #     self._import_products(row, workbook, worksheet, heater_codes, used_in_row, category_ids, application_fields, fields_index, index_categories_ids, attribute_data, models_data)
        except Exception as e:
            _logger.error(e)

    def _do_import_product(self, conn, sync_action_id, values):
        # change to directory path
        conn.cd(sync_action_id.dir_path)
        directories = conn.ls()
        for directory in directories:
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

    def _create_attribute(self):
        try:
            # TODO: move this to DATA File
            attributes = ['FUEL', 'IGNITION TYPE', 'HEAT EXCHANGER', 'CONSTRUCTION', 'ALTITUDE', 'STAGES', 'INDOOR / OUTDOOR', 'LOW NOX', 'PUMP TYPE', 'PRV TYPE', 'HEADER TYPE', 'CONTROL']
            res = {}
            for attr in attributes:
                self.env.cr.execute("select id from product_attribute where name=%s", (attr, ))
                attribute_id = self.env.cr.fetchone()
                attribute_id = attribute_id and attribute_id[0] or False
                # TODO: once it move no need of this
                if not attribute_id:
                    self.env.cr.execute('INSERT into product_attribute ("name", "create_variant", "type") VALUES (%s, False, %s) RETURNING id', (attr, 'radio'))
                    attribute_id = self.env.cr.fetchone()[0]
                res[attr] = attribute_id
        except Exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.xlsx_file_path) + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj) + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return res

    def _process_attributes(self, attributes, attribute_ids):
        try:
            attributes_data = {}
            if attributes.get(26):
                """
                Most manufacturers use N for natural gas and P for propane.
                But a couple (Lochinvar being the most notable one) use L for propane.
                For all intents and purposes, L = P.  If a customer selects Propane from the attributes list, L or P are equivalent
                """
                is_notable_lochinvar = False
                if 'L' in attributes[26]:
                    is_notable_lochinvar = True
                    attributes[26] = ['P' if x == 'L' else x for x in attributes[26]]
                attribute_vals, attribute_id = self._create_attribute_value(attribute_ids['FUEL'], attributes.get(26))
                if is_notable_lochinvar:
                    attribute_vals['L'] = attribute_vals.pop('P')
                attributes_data[26] = {'attribute_id': attribute_id, 'values': attribute_vals}

            if attributes.get(27):
                attribute_vals, attribute_id = self._create_attribute_value(attribute_ids['IGNITION TYPE'], attributes.get(27))
                attributes_data[27] = {'attribute_id': attribute_id, 'values': attribute_vals}

            if attributes.get(28):
                attribute_vals, attribute_id = self._create_attribute_value(attribute_ids['HEAT EXCHANGER'], attributes.get(28))
                attributes_data[28] = {'attribute_id': attribute_id, 'values': attribute_vals}

            if attributes.get(29):
                attribute_vals, attribute_id = self._create_attribute_value(attribute_ids['CONSTRUCTION'], attributes.get(29))
                attributes_data[29] = {'attribute_id': attribute_id, 'values': attribute_vals}

            if attributes.get(30):
                attribute_vals, attribute_id = self._create_attribute_value(attribute_ids['ALTITUDE'], attributes.get(30))
                attributes_data[30] = {'attribute_id': attribute_id, 'values': attribute_vals}

            if attributes.get(31):
                attribute_vals, attribute_id = self._create_attribute_value(attribute_ids['STAGES'], attributes.get(31))
                attributes_data[31] = {'attribute_id': attribute_id, 'values': attribute_vals}

            if attributes.get(33):
                attribute_vals, attribute_id = self._create_attribute_value(attribute_ids['INDOOR / OUTDOOR'], attributes.get(33))
                attributes_data[33] = {'attribute_id': attribute_id, 'values': attribute_vals}

            if attributes.get(34):
                attribute_vals, attribute_id = self._create_attribute_value(attribute_ids['LOW NOX'], attributes.get(34))
                attributes_data[34] = {'attribute_id': attribute_id, 'values': attribute_vals}

            if attributes.get(37):
                attribute_vals, attribute_id = self._create_attribute_value(attribute_ids['PUMP TYPE'], attributes.get(37))
                attributes_data[37] = {'attribute_id': attribute_id, 'values': attribute_vals}

            if attributes.get(38):
                attribute_vals, attribute_id = self._create_attribute_value(attribute_ids['PRV TYPE'], attributes.get(38))
                attributes_data[38] = {'attribute_id': attribute_id, 'values': attribute_vals}

            if attributes.get(41):
                attribute_vals, attribute_id = self._create_attribute_value(attribute_ids['HEADER TYPE'], attributes.get(41))
                attributes_data[41] = {'attribute_id': attribute_id, 'values': attribute_vals}

        except Exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.xlsx_file_path) + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj) + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return attributes_data

    def _create_attribute_value(self, attribute_id, values):
        try:
            # TODO - late we used DB ID
            attribute_values = {}
            if attribute_id:
                for value in values:
                    temp = value
                    if temp == '':
                        temp = 'N/A'
                    self.env.cr.execute("select id from product_attribute_value where name=%s and attribute_id=%s", (value, attribute_id))
                    value_id = self.env.cr.fetchone()
                    value_id = value_id and value_id[0] or False
                    if not value_id:
                        self.env.cr.execute('INSERT into product_attribute_value ("name", "attribute_id", "source_doc") VALUES (%s, %d, %s) RETURNING id', (temp, attribute_id, self.miff_file))
                        value_id = self.env.cr.fetchone()[0]
                    attribute_values[value] = value_id
        except Exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.xlsx_file_path) + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj) + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return attribute_values, attribute_id

    def _process_models(self, heater_codes, used_in_row, attribute_data, application_fields, fields_index, used_in_row_index):
        try:
            new_heater_codes = copy.deepcopy(heater_codes)  # deep copy
            models = []
            for heater_code in new_heater_codes:
                code = new_heater_codes[heater_code]
                for idx, c in enumerate(code['code']):
                    if not isinstance(c, list):
                        code['code'][idx] = [''.join(c1 for c1 in c)]
                    elif isinstance(c, list) and all(str(x) and str(x) in used_in_row for x in c):
                        code['code'][idx] = ['@@' + str(r) + '@@' for r in used_in_row if r]
                    elif isinstance(c, list):
                        for i, fields in enumerate(application_fields):
                            if fields == c:
                                code['code'][idx] = ['{' + str(x) + '(' + str(fields_index[i]) + ')' + '}' for x in c]
                                break
                codes = code['code'][:]
                combinations = []
                if ['*'] in codes:
                    code['code'] = [item for item in code['code'] if item != ['*']]
                    combinations += self.prepare_additional_model_combination(codes)
                combinations += self._get_possible_combination(code['code'])
                for idx, comb in enumerate(combinations):
                    models.append({
                        'name': code['name'],
                        'description': code['description'],
                        #'index_categories': code['index_categories'],
                        'mfg_id': code['mfg_id'],
                        'code': ''.join(str(i) for i in comb)})
        except Exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.xlsx_file_path) + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj) + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return self._create_models(models, attribute_data, used_in_row_index)

    def _get_possible_combination(self, new_heater_codes):
        try:
            combinations = []
            items = itertools.product(*new_heater_codes)
            for i in items:
                combinations.append(i)
        except Exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj) + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return combinations

    def prepare_additional_model_combination(self, codes):
        model_codes = self.prepare_optional_model_codes_togenerate_combination(codes)
        combinations = []
        for mc in model_codes:
            combinations += self._get_possible_combination(mc)
        return combinations

    def _create_models(self, models, attribute_data, used_in_row_index):
        try:
            # we can take res_id from the ir model data using xml id
            models_data = {}
            for model in models:
                # code look like 'BWC@@151@@E{L(26)}{V(38)}{G(37)}1P{9(30)}{U(29)}'
                # first remove field index
                model_code = re.sub("[\(\[].*?[\)\]]", "", model['code'])
                # second remove {}
                model_code = re.sub('{|}', '', model_code).rstrip()

                # get model number
                model_number = re.search(r'\@\@(.*?)\@\@', model_code)
                model_number = model_number and model_number.group(1)

                # remove model number speprator (**)
                model_code = model_code.replace('@@', '')
                model['code'] = model['code'].replace('@@', '')
                # map category
                category_id = False
                for k, v in used_in_row_index.iteritems():
                    if v and v == model_number:
                        category_id = model['index_categories'][k]
                        break
                if not category_id:
                    category_input = False
                else:
                    category_input = [(4, category_id)]
                self.env.cr.execute("select id from product_template where default_code=%s", (model_code,))
                model_id = self.env.cr.fetchone()
                model_id = model_id and model_id[0] or False
                if not model_id:
                    manufacturer_id = False
                    if model['mfg_id']:
                        self.env.cr.execute("select id from res_partner where mfg_lookup=%s", (model['mfg_id'],))
                        manufacturer_id = self.env.cr.fetchone()
                        manufacturer_id = manufacturer_id and manufacturer_id[0] or False
                    vals = {
                        'name':  model['name'] + ' - ' + model['description'] if model['name'] not in model['description'] else model['description'],
                        'default_code': model_code,
                        'heater_code': self.heater_code,
                        'heater_sizes': self.heater_sizes,
                        'image': self.product_img_base64,
                        'public_categ_ids': category_input,
                        'product_class': 'm',
                        'description': model_code.replace('-', '').replace(' ', ''),
                        'type': 'consu',
                        'website_published': True,
                        'mfg_id': manufacturer_id,
                        'parts_list': self.parts_list_base64,
                        'manual': self.maual_base64,
                        'manual_filename': self.manual_filename,
                        'source_doc':  self.miff_file,
                        'dependency_1_label': self.dependancy_label_1,
                        'dependency_2_label': self.dependancy_label_2,
                        'dependency_3_label': self.dependancy_label_3,
                        'exploded_views': self.product_extra_img_base64 + self.product_html_base64,
                        'attribute_line_ids': self._prepare_model_attribute_lines(model['code'], attribute_data, 'attribute_id', 'value_ids'),
                    }
                    # TODO prepare model in such way so that it can be used below while creating parts
                    # TODO: use sql query instead; also api.multi???
                    model_id = self.env['product.template'].create(vals).id
                    #model_id = object_proxy.execute(db_name, uid, password, "product.template", "create", vals)
                models_data[model_code] = {'code': model['code'], 'db_id': model_id}
        except Exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj) + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return models_data

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
