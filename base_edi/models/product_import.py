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
import traceback

from odoo import models, _
from odoo import fields as odoo_fields
_logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)

MAP_HEATER_CODE = {
    1: 'H',
    2: 'DHW',
    3: 'PH',
}


class MifFile(models.Model):
    _inherit = 'mif.file'

    sync_action_id = odoo_fields.Many2one('edi.sync.action', string='Source Action')
    manufacturer = odoo_fields.Many2one(related='sync_action_id.manufacturer', relation='res.partner', readonly=True)


class SyncDocumentType(models.Model):

    _inherit = 'sync.document.type'

    doc_code = odoo_fields.Selection(selection_add=[
        ('import_product', 'Import Product'),
    ])

    def _do_import_product(self, conn, sync_action_id, values):
        self._synch_mif(conn, sync_action_id)
        MifFile = self.env['mif.file']
        # import only 1 mif at a time
        # process inprogress mif first
        MIF = MifFile.search([('sync_action_id', '=', sync_action_id.id), ('state', '=', 'in_progress')], limit=1)
        if not MIF:
            MIF = MifFile.search([('sync_action_id', '=', sync_action_id.id), ('state', '=', 'pending')], limit=1)
        if MIF:
            try:
                # make it inprogress
                self._initialize_mif_variable()
                self._delete_prior_data(MIF)
                self._extract_files_from_subdirectory(conn, sync_action_id, MIF)
                vals = {'state': 'in_progress'}
                if not MIF.processing_start_date:
                    vals['processing_start_date'] = odoo_fields.Datetime.now()
                if self.parts_list_base64:
                    vals['parts_list'] = self.parts_list_base64
                    vals['parts_list_filename'] = self.parts_list_filename
                MIF.write(vals)
                self._cr.commit()
                if self.product_import_file:
                    self._import_products(conn, sync_action_id, MIF.id)
                else:
                    self.state = 'error'
                    self.log_note += '\n\n No Mif file found -> %s' % (self.xlsx_file_path)
            except Exception:
                self.LogErrorMessage()

            MIF.write({'state': self.state, 'log_note': self.log_note, 'processing_end_date': odoo_fields.Datetime.now()})

    def _initialize_mif_variable(self):
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
        self.parts_list_filename = ''
        self.dependancy_label_1 = ''
        self.dependancy_label_2 = ''
        self.dependancy_label_3 = ''
        self.skip_import = False
        self.heater_code = ''
        self.heater_sizes = ''
        self.log_note = ''
        self.state = 'pending'
        self.image_lists = []

    def _extract_files_from_subdirectory(self, conn, sync_action_id, mif):
        directory = mif.mif_directory
        self.mif_path = sync_action_id.dir_path
        self.image_lists = conn.ls(self.mif_path + 'images')
        file_path = os.path.join(sync_action_id.dir_path, directory)
        conn.cd(file_path)
        mif_files = conn.ls()
        for file in mif_files:
            subfile_path = os.path.join(sync_action_id.dir_path + directory, file)
            if file.endswith(".xlsx"):
                self.xlsx_file_path = subfile_path
                self.product_import_file = conn.download_file(self.xlsx_file_path)
                self.miff_file = file
            elif file == directory + ".pdf" and not mif.parts_list:
                image = conn.download_file(subfile_path)
                imgbase64 = base64.encodestring(image)
                self.parts_list_base64 = imgbase64
                self.parts_list_filename = file

            elif '_EXP' in file and (file.endswith(".jpg") or file.endswith(".png")):
                image = conn.download_file(subfile_path)
                imgbase64 = base64.encodestring(image)
                self.product_extra_img_base64.append((0, 0, {'name': 'Exploded View image', 'binary': imgbase64, 'file_name': file}))
            elif '_EXP' in file and file.endswith(".html"):
                image = conn.download_file(subfile_path)
                imgbase64 = base64.encodestring(image)
                self.product_html_base64.append((0, 0, {'name': 'Exploded View HTML', 'binary': imgbase64, 'file_name': file}))
            # pdf = conn.download_file(file_path)

    def _import_products(self, conn, sync_action_id, mif_id):
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
                    'mfg_id': worksheet.cell_value(r, 26) and int(worksheet.cell_value(r, 26)) or False,
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
                application_fields, fields_index, attributes = self._prepare_applications_fields(r, worksheet)
                self._set_dependency_label(worksheet, r)
                break
        heater_codes = self._explode_heater_code(heater_codes, used_in_row)
        attribute_ids = self._get_attributes()
        attribute_data = self._process_attributes(attributes, attribute_ids)
        models_data = self._process_models(heater_codes, used_in_row, attribute_data, application_fields, fields_index, used_in_row_index, mif_id, conn)
        if not self.skip_import:
            parts = self._import_parts(
                conn, row, workbook, worksheet, heater_codes, used_in_row, category_ids, application_fields, fields_index, index_categories_ids, attribute_data, models_data, mif_id)
            self.log_note += '\n\n Success fully imported %s parts' % (parts)
            self.state = 'done'

    def _synch_mif(self, conn, sync_action_id):
        MifFile = self.env['mif.file']
        conn.cd(sync_action_id.dir_path)
        directories = conn.ls()
        all_mifdirectories = MifFile.search([('sync_action_id', '=', sync_action_id.id)]).mapped('mif_directory')
        for directory in filter(lambda d: d not in all_mifdirectories and d != 'images', directories):
            MifFile.with_context(prefetch_fields=False, mail_notrack=True).create({'name': directory, 'mif_directory': directory, 'sync_action_id': sync_action_id.id})
        self.env.cr.commit()

    def _prepare_applications_fields(self, row, worksheet):
        fields = []
        fields_index = []
        attributes = {}

        def setAttributeValue(field, i):
            if '[' in field and ']' in field:
                x = field[field.find("[")+1:field.find("]")]
                x = [c.strip() for c in x.split(",")]
                fields.append(x)
                fields_index.append(i)
                attributes[i] = x

        for i in range(26, 32):
            setAttributeValue(worksheet.cell_value(row, i), i)  # AA to AF
        setAttributeValue(worksheet.cell_value(row, 33), 33)  # AH
        setAttributeValue(worksheet.cell_value(row, 34), 34)  # AI
        setAttributeValue(worksheet.cell_value(row, 37), 37)  # AL
        setAttributeValue(worksheet.cell_value(row, 38), 38)  # AM
        setAttributeValue(worksheet.cell_value(row, 41), 41)  # AP
        # setAttributeValue(worksheet.cell_value(row, 45), 45)  # AT
        return fields, fields_index, attributes

    def _set_dependency_label(self, worksheet, row):
        row_length = worksheet.row_len(row) - 1
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

    def _explode_heater_code(self, heater_codes, used_in_row):
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
        return heater_codes

    def _get_attributes(self):
        attributes = ['FUEL', 'IGNITION TYPE', 'HEAT EXCHANGER', 'CONSTRUCTION', 'ALTITUDE', 'STAGES', 'INDOOR / OUTDOOR', 'LOW NOX', 'PUMP TYPE', 'PRV TYPE', 'HEADER TYPE', 'CONTROL']
        attribute_data = self.env['product.attribute'].search_read([('name', 'in', attributes)], ['name'])
        res = {attr['name']: attr['id'] for attr in attribute_data}
        return res

    def _process_attributes(self, attributes, attribute_ids):
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

        return attributes_data

    def _create_attribute_value(self, attribute_id, values):
        # TODO - late we used DB ID
        attribute_values = {}
        if attribute_id:
            for value in values:
                temp = value
                if temp == '':
                    temp = 'N/A'
                self.env.cr.execute("select id from product_attribute_value where name=%s and attribute_id=%s", (temp, attribute_id))
                value_id = self.env.cr.fetchone()
                value_id = value_id and value_id[0] or False
                if not value_id:
                    self.env.cr.execute('INSERT into product_attribute_value ("name", "attribute_id", "source_doc") VALUES (%s, %s, %s) RETURNING id', (temp, attribute_id, self.miff_file))
                    value_id = self.env.cr.fetchone()[0]
                attribute_values[value] = value_id
        return attribute_values, attribute_id

    def _process_models(self, heater_codes, used_in_row, attribute_data, application_fields, fields_index, used_in_row_index, mif_id, conn):
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
                combinations += self._prepare_additional_model_combination(codes)
            combinations += self._get_possible_combination(code['code'])
            for idx, comb in enumerate(combinations):
                models.append({
                    'name': code['name'],
                    'description': code['description'],
                    #'index_categories': code['index_categories'],
                    'mfg_id': code['mfg_id'],
                    'code': ''.join(str(i) for i in comb)})
        return self._create_models(models, attribute_data, used_in_row_index, mif_id, conn)

    def _get_possible_combination(self, new_heater_codes):
        combinations = []
        items = itertools.product(*new_heater_codes)
        for i in items:
            combinations.append(i)
        return combinations

    def _prepare_additional_model_combination(self, codes):
        model_codes = self.prepare_optional_model_codes_togenerate_combination(codes)
        combinations = []
        for mc in model_codes:
            combinations += self._get_possible_combination(mc)
        return combinations

    def _create_models(self, models, attribute_data, used_in_row_index, mif_id, conn):
        _logger.info('Creating Models')
        ResPartner = self.env['res.partner']
        ProductTemplate = self.env['product.template']
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

            # get rid of = from model name
            model_code = model_code.replace('=', '-')
            model['code'] = model['code'].replace('=', '-')

            # remove model number speprator (**)
            model_code = model_code.replace('@@', '')
            model['code'] = model['code'].replace('@@', '')
            # map category
            #category_id = False
            # for k, v in used_in_row_index.items():
            #     if v and v == model_number:
            #         category_id = model['index_categories'][k]
            #         break
            # if not category_id:
            #     category_input = False
            # else:
            #     category_input = [(4, category_id)]
            model_id = ProductTemplate.search([('default_code', '=', model_code)], limit=1).id
            if not model_id:
                manufacturer_id = False
                if model['mfg_id']:
                    manufacturer_id = ResPartner.search([('mfg_lookup', '=', model['mfg_id'])], limit=1).id
                vals = {
                    'name':  model['name'] + ' - ' + model['description'] if model['name'] not in model['description'] else model['description'],
                    'default_code': model_code,
                    'mif_id': mif_id,
                    'heater_code': self.heater_code,
                    'heater_sizes': self.heater_sizes,
                    'image': self._find_product_image(conn, model_code, self.mif_path, self.image_lists),
                    # 'public_categ_ids': category_input,
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
                model_id = ProductTemplate.with_context(prefetch_fields=False, mail_notrack=True).create(vals).id
            models_data[model_code] = {'code': model['code'], 'db_id': model_id}
        self._cr.commit()
        return models_data

    def _prepare_model_attribute_lines(self, code, attribute_data, field1, field2):
        # TODO - improve logic
        values = re.findall('\{(.*?)\}', code)
        attribute_line_ids = []
        for k, data in attribute_data.items():
            for val in values:
                v, i = val.split('(')
                i = i[:2]  # hope for the best
                if v in data['values'].keys() and int(i) == k:
                    attribute_line_ids.append((0, 0, {field1: data['attribute_id'], field2: [(6, 0, [data['values'][v]])]}))
                    break

        return attribute_line_ids

    def _import_parts(self, conn, row, workbook, worksheet, heater_codes, used_in_row, category_ids, application_fields, fields_index, index_categories_ids, attribute_data, models_data, mif_id):
        datas = self._extract_parts_datas(conn, row, workbook, worksheet, heater_codes, used_in_row, category_ids, application_fields, fields_index, index_categories_ids, attribute_data, mif_id)
        _logger.info('Importing Parts')
        ProductTemplate = self.env['product.template']
        IrModelData = self.env['ir.model.data']
        ModelPart = self.env['model.part']
        images = conn.ls('../images')
        i = 0
        x = 0
        for d in datas:
            # do not create if product is already exists with same internal reference
            product_id = ProductTemplate.search([('default_code', '=', d['default_code'])], limit=1)
            parts_data = d.pop('other_data')

            if product_id:
                # may be later we might need to a search read call
                d.pop('default_code')
                d.pop('name')
                d.pop('public_categ_ids')
                d.pop('attribute_line_ids')
                # overrtie image
                product_id.write(d)
            else:
                d['image'] = self._find_product_image(conn, d['default_code'], self.mif_path, images)
                product_id = self.env['product.template'].with_context(prefetch_fields=False, mail_notrack=True).create(d)

                external_id_vals = {
                    'model': 'product.template',
                    'module': 'p4h',
                    'name': d['default_code'],
                    'res_id': product_id.id,
                }

                if not IrModelData.search_count([('model', '=', 'product.template'), ('module', '=', 'p4h'), ('res_id', '=', product_id.id)]):
                    IrModelData.with_context(prefetch_fields=False, mail_notrack=True).create(external_id_vals)

            # create new model datas
            for model in parts_data['models']:
                for m in model['models'].split(', '):
                    if not m:
                        continue
                    m = m.rstrip()
                    m = m.replace('=', '-')
                    model_id = ProductTemplate.search([('default_code', '=', m)], limit=1)
                    if not model_id:
                        break
                    parts = {
                        'model_id': model_id.id,
                        'callout': parts_data['callout'],
                        'dependency1': parts_data['dependancy1'],
                        'dependency2': parts_data['dependancy2'],
                        'dependency3': parts_data['dependancy3'],
                        'quantity': model['qunatity'],
                        'part_id': product_id.id,
                        'group': parts_data['group'],
                        'name': model_id.name,
                        'source_doc': self.miff_file,
                        'attribute_line_ids': self._prepare_model_attribute_lines(models_data[m]['code'], attribute_data, 'attribute_id', 'value_ids'),
                    }
                    if not ModelPart.search_count([('model_id', '=', model_id.id), ('part_id', '=', product_id.id)]):
                        # This could be done with multi records
                        ModelPart.with_context(prefetch_fields=False, mail_notrack=True).create(parts)

            i += 1
            x += 1
            if x == 10:
                self._cr.commit()
                x = 0

        return i
        _logger.info(str(i) + ' parts imported')

    def _extract_parts_datas(self, conn, row, workbook, worksheet, heater_codes, used_in_row, category_ids, application_fields, fields_index, index_categories_ids, attribute_data, mif_id):
        _logger.info('Preparing Parts Data')
        products = []
        group = ''
        for r in range(row, worksheet.nrows):
            part_no = self.Convert2Str(worksheet.cell(r, 1))  # col 1 -> Part No
            section = worksheet.cell_value(r, 0)
            callout = self.Convert2Str(worksheet.cell(r, 0))
            row_length = worksheet.row_len(row) - 1
            dependancy1 = row_length >= 42 and worksheet.cell_value(r, 42) or False
            dependancy2 = row_length >= 43 and worksheet.cell_value(r, 43) or False
            dependancy3 = row_length >= 45 and worksheet.cell_value(r, 45) or False
            if section and not part_no:
                group = section

            if not part_no:
                continue
            categ_ids = []
            product_name = worksheet.cell_value(r, 2)  # col 2 -> DESCRIPTION

            # for idx, col in enumerate(range(4, 26)):
            #     if worksheet.cell_value(r, col):
            #         categ_ids += filter(None, [ici.get(col) for ici in index_categories_ids])
            # col 3 = Used in. -> we don't need this
            # col 4,5,6,7,8(E,F,G,H,I to Z) are Used in values
            models = self._prepare_models_combinations(r, worksheet, heater_codes, used_in_row, application_fields, fields_index)
            # prepare final dict for product
            res = dict(
                default_code=part_no,
                name=product_name,
                mif_id=mif_id,
                # image=self.product_img_base64,
                type='product',
                product_class='p',
                source_doc=self.miff_file,
                # product_image_ids=self.product_extra_img_base64,
                website_published=True,
                # attribute_line_ids=self._prepare_attribute_lines(r, worksheet, attribute_data),
                attribute_line_ids=False,
                other_data={'callout': callout, 'group': group, 'dependancy1': dependancy1, 'dependancy2': dependancy2, 'dependancy3': dependancy3, 'models': models},
                public_categ_ids=[(4, c_id) for c_id in categ_ids]
            )
            products.append(res)
        return products

    def _prepare_models_combinations(self, row, worksheet, heater_codes, used_in_row, application_fields, fields_index):
        new_heater_codes = copy.deepcopy(heater_codes)  # deep copy
        res = []
        AG_vals = worksheet.cell_value(row, 32).split(',')  # AG
        AG_vals = ['PH' if x == 'P' or x == 'POOL' else x for x in AG_vals]
        for i in range(4, 26):
            used_in = worksheet.cell_value(row, i)
            used_in_val = used_in_row[i - 4]
            if used_in:
                models = ''
                for heater_code in new_heater_codes:
                    if AG_vals and heater_code not in AG_vals:
                        continue
                    temp = copy.deepcopy(new_heater_codes)
                    model_codes = []
                    model_codes.append([item for item in temp[heater_code]['code'] if item != ['*']])
                    model_codes += self.prepare_optional_model_codes_togenerate_combination(temp[heater_code]['code'])
                    for code in model_codes:
                        temp_field_index = fields_index[:]
                        missing_part = {}
                        skip_code = False
                        for idx, af in enumerate(application_fields):
                            if af not in code:
                                missing_part[idx] = af
                        for idx, c in enumerate(code):
                            if not isinstance(c, list):
                                code[idx] = [''.join(c1 for c1 in c)]
                            elif isinstance(c, list):
                                if all(str(x) and str(x) in used_in_row for x in c):
                                    code[idx] = [str(used_in_val)]
                                elif any(c == af for af in application_fields):
                                    i = 0
                                    for z in temp_field_index:
                                        f_v = worksheet.cell_value(row, z)
                                        if f_v:
                                            if isinstance(f_v, float):
                                                f_v = str(int(f_v))
                                            x = f_v.split(',')
                                            if application_fields[i] == c:
                                                x = list(set(c) & set(x))
                                                if len(x):
                                                    code[idx] = x
                                            elif missing_part.get(i) and set(missing_part[i]) & set(x):
                                                skip_code = True
                                        i = i + 1
                        if skip_code:
                            continue
                        combinations = self._get_possible_combination(code)
                        for comb in combinations:
                            models += ''.join(str(i) for i in comb) + ', '
                if isinstance(used_in, float):
                    used_in = int(used_in)
                res.append({
                    'qunatity': used_in,
                    'models': models})
        return res

    def prepare_optional_model_codes_togenerate_combination(self, codes):
        fix_parts = []
        optional_parts = []
        temp_codes = codes[:]
        model_codes = []
        for idx, c in enumerate(temp_codes):
            if c == ['*'] or c == '*':
                optional_parts.append(temp_codes[idx+1])
                temp_codes.remove(temp_codes[idx+1])
            else:
                fix_parts.append(c)

        model_codes.append(fix_parts)
        if len(optional_parts) == 1:
            return model_codes
        for op in optional_parts:
            c = [item for item in codes if item != ['*'] and item != '*' and not (item in optional_parts and item != op)]
            model_codes.append(c)
        return model_codes

    def _find_product_image(self, conn, part, file_path, images):
        if part and file_path:
            images_path = file_path + 'images/'
            part_filename = part + '_2' + '.jpg'
        else:
            return False

        if part_filename not in images:
            part_filename = part + '_2' + '.JPG'
        if part_filename not in images:
            part_filename = part + '_3' + '.jpg'
        if part_filename not in images:
            part_filename = part + '_3' + '.JPG'

        if part_filename not in images:
            return False
        jpg = conn.download_file(images_path + part_filename)
        return base64.encodestring(jpg)

    def _delete_prior_data(self, mif):
        if mif.state == 'pending':
            models_to_delete = self.env['product.template'].search([('source_doc', '=', mif.name), ('product_class', '=', 'm'), ('mif_id', '=', mif.id)])
            self.log_note += '\n\n Deleting Models %s' % (str(models_to_delete.ids))
            _logger.info('Deleting Models' + str(models_to_delete.ids))
            models_to_delete.unlink()
        return True

    # ===================================================
    # Helper MEthods
    # ===================================================

    def LogErrorMessage(self):
        exc_type, exc_obj, exc_tb = sys.exc_info()
        msg = traceback.format_exc()
        _logger.error(msg)
        self.log_note += msg
        self.state = 'error'

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
