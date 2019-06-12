# Part of Odoo. See LICENSE file for full copyright and licensing details.

import xmlrpclib
import os, sys
import xlrd
import base64
import itertools
import copy
import pprint
import re
import shutil
import logging
import ntpath
from string import maketrans
from pathlib2 import Path
from datetime import datetime
pp = pprint.PrettyPrinter(indent=4)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

MAP_HEATER_CODE = {
    1: 'H',
    2: 'DHW',
    3: 'PH',
}

p4h_from="!#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`{|}~"
p4h_to="!z$%&'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxy"
p4h_parts = maketrans(p4h_from,p4h_to)

def setup_logger():
    logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s")
    fh = logging.FileHandler('script.log')
    fh.setFormatter(logFormatter)
    fh.setLevel(logging.DEBUG)  # or any level you want

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    logger.addHandler(fh)
    logger.addHandler(ch)


class OdooConnection():
    def __init__(self, user, password, db_name):
        self.user = user
        self.password = password
        self.db_name = db_name

    def set_connection(self):
        self.common_proxy = xmlrpclib.ServerProxy('http://localhost:8069/xmlrpc/common')
        self.object_proxy = xmlrpclib.ServerProxy('http://localhost:8069/xmlrpc/object')
        self.uid = self.common_proxy.login(self.db_name, self.user, self.password)
        if not self.uid:
            return False
        return True


class ImportMIF():
    def __init__(self, mif_path, odoo_connection):
        self.mif_path = mif_path
        self.connection = odoo_connection

    def initialize_mif_variable(self):
        self.prodcut_import_file = ''
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

    def extract_files_from_subdirectory(self, subdir):
        try:
            full_subdir = self.mif_path + '/' + subdir
            for root, dirs, files in os.walk(full_subdir):
                for file in files:
                    if file.endswith(".xls"):
                        self.prodcut_import_file = full_subdir + '/' + file
                        self.miff_file = file
                    elif file.endswith(".xlsx"):
                        self.prodcut_import_file = full_subdir + '/' + file
                        self.miff_file = file
                    elif file == subdir + ".pdf":
                        self.parts_list_base64 = self._convert_img_to_binary(full_subdir + '/' + file)
                    elif file.endswith("_IMG.png") or file.endswith("_IMG.jpg"):
                        self.product_img_base64 = self._convert_img_to_binary(full_subdir + '/' + file)
                    elif file.endswith("_IOMAN.pdf") or file.endswith("_IOM.pdf"):
                        self.maual_base64 = self._convert_img_to_binary(full_subdir + '/' + file)
                        self.manual_filename = file
                    elif '_EXP' in file and (file.endswith(".jpg") or file.endswith(".png")):
                        imgbase64 = self._convert_img_to_binary(full_subdir + '/' + file)
                        self.product_extra_img_base64.append((0, 0, {'name': 'Exploded View image', 'binary': imgbase64, 'file_name': file}))
                    elif '_EXP' in file and file.endswith(".html"):
                        imgbase64 = self._convert_img_to_binary(full_subdir + '/' + file)
                        self.product_html_base64.append((0, 0, {'name': 'Exploded View HTML', 'binary': imgbase64, 'file_name': file}))
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')

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
                    logger.error('FAILURE! Model range not found in this mif ' + ntpath.basename(self.prodcut_import_file))
                    self.skip_import = True
                    raise ValueError('Model range not found')

                heater_codes[code]['code'] = a
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return heater_codes

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
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')

        try:
            for i in range(26, 32):
                setAttributeValue(worksheet.cell_value(row, i), i)  # AA to AF
            setAttributeValue(worksheet.cell_value(row, 33), 33)  # AH
            setAttributeValue(worksheet.cell_value(row, 34), 34)  # AI
            setAttributeValue(worksheet.cell_value(row, 37), 37)  # AL
            setAttributeValue(worksheet.cell_value(row, 38), 38)  # AM
            setAttributeValue(worksheet.cell_value(row, 41), 41)  # AP
            #setAttributeValue(worksheet.cell_value(row, 45), 45)  # AT
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return fields, fields_index, attributes

    def _get_possible_combination(self, new_heater_codes):
        try:
            combinations = []
            items = itertools.product(*new_heater_codes)
            for i in items:
                combinations.append(i)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return combinations

    def _prepare_model_attribute_lines(self, code, attribute_data, field1, field2):
        # TODO - please improve the logic
        try:
            values = re.findall('\{(.*?)\}', code)
            attribute_line_ids = []
            for k, data in attribute_data.iteritems():
                for val in values:
                    v, i = val.split('(')
                    i = i[:2]  # hope for the best
                    if v in data['values'].keys() and int(i) == k:
                        attribute_line_ids.append((0, 0, {field1: data['attribute_id'], field2: [(6, 0, [data['values'][v]])]}))
                        break
        except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')

        return attribute_line_ids

    def _create_models(self, models, attribute_data, used_in_row_index):
        #logger.info("=======Creating Models.... ======")
        try:
            object_proxy, db_name, uid, password = self._get_connection_items()
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
                model_id = object_proxy.execute(db_name, uid, password, "product.template", "search", [('default_code', "=", model_code)])
                if not model_id:
                    manufacturer_id = False
                    if model['mfg_id']:
                        manufacturer_id = object_proxy.execute(db_name, uid, password, "res.partner", "search", [('mfg_lookup', "=", model['mfg_id'])])
                        manufacturer_id = manufacturer_id and manufacturer_id[0] or False
                    vals = {
                    'name':  model['name'] + ' - ' + model['description'] if model['name'] not in model['description'] else model['description'],
                    'default_code': model_code,
                    'p4h_code': model_code.translate(p4h_parts)
                    'heater_code': self.heater_code,
                    'heater_sizes': self.heater_sizes,
                    'image': self.product_img_base64,
                    'public_categ_ids': category_input,
                    'product_class': 'm',
                    'description': model_code.replace('-','').replace(' ',''),
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
                    model_id = object_proxy.execute(db_name, uid, password, "product.template", "create", vals)
                models_data[model_code] = {'code': model['code'], 'db_id': model_id}
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return models_data

    def _create_attribute(self):
        #logger.info("====Creating Attributes=======")
        try:
            attributes = ['FUEL', 'IGNITION TYPE', 'HEAT EXCHANGER', 'CONSTRUCTION', 'ALTITUDE', 'STAGES', 'INDOOR / OUTDOOR', 'LOW NOX', 'PUMP TYPE', 'PRV TYPE', 'HEADER TYPE', 'CONTROL']
            res = {}
            for attr in attributes:
                object_proxy, db_name, uid, password = self._get_connection_items()
                attribute_id = object_proxy.execute(db_name, uid, password, "product.attribute", "search", [('name', "=", attr)])
                attribute_id = attribute_id and attribute_id[0] or False
                if not attribute_id:
                    attribute_id = object_proxy.execute(db_name, uid, password, "product.attribute", "create", {'source_doc': self.miff_file, 'name': attr, 'create_variant': 'no_variant'})
                res[attr] = attribute_id
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return res

    def _create_attribute_value(self, attribute_id, values):
        try:
            object_proxy, db_name, uid, password = self._get_connection_items()
            #TODO - late we used DB ID
            attribute_values = {}
            if attribute_id:
                for value in values:
                    temp = value
                    if temp == '':
                        temp = 'N/A'
                    value_id = object_proxy.execute(db_name, uid, password, "product.attribute.value", "search", [('name', "=", temp), ('attribute_id', '=', attribute_id)])
                    value_id = value_id and value_id[0] or False
                    if not value_id:
                        value_id = object_proxy.execute(db_name, uid, password, "product.attribute.value", "create", {'name': temp, 'attribute_id': attribute_id, 'source_doc': self.miff_file})
                    attribute_values[value] = value_id
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return attribute_values, attribute_id

    def _process_attributes(self, attributes, attribute_ids):
        #logger.info("=====Processing Attribute Values ========")
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

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return attributes_data

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

    def prepare_additional_model_combination(self, codes):
        model_codes = self.prepare_optional_model_codes_togenerate_combination(codes)
        combinations = []
        for mc in model_codes:
            combinations += self._get_possible_combination(mc)
        return combinations

    def _process_models(self, heater_codes, used_in_row, attribute_data, application_fields, fields_index, used_in_row_index):
        #logger.info("processing models")
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
                    'index_categories': code['index_categories'],
                    'mfg_id': code['mfg_id'],
                    'code': ''.join(str(i) for i in comb)})
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')

        return self._create_models(models, attribute_data, used_in_row_index)

    def _prepare_models_combinations(self, row, worksheet, heater_codes, used_in_row, application_fields, fields_index):
        try:
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
                    if isinstance(used_in,float):
                        used_in = int(used_in)
                    res.append({
                    'qunatity': used_in,
                    'models': models
                    })
        except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return res

    def _convert_img_to_binary(self, file_path):
        with open(file_path, "rb") as file:
            image_base64 = base64.encodestring(file.read())
            return image_base64

    def _get_product_image(self):
        if self.product_image_file:
            return self._convert_img_to_binary(self.product_image_file)
        return False

    def _find_product_image(self, part, file_path):
        try:
            if part and file_path:
                images_path = file_path + 'images/'
                part_filename = part + '_2'
            else:
                return False
            jpg_file = Path(images_path + part_filename + '.jpg')
            if jpg_file.is_file():
                with open(str(jpg_file), "rb") as file:
                    return self._convert_img_to_binary(str(jpg_file))
            JPG_file = Path(images_path + part_filename + '.JPG')
            if JPG_file.is_file():
                with open(str(JPG_file), "rb") as file:
                    return self._convert_img_to_binary(str(JPG_file))
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return False
 
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

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')

    def _prepare_attribute_lines(self, row, worksheet, attribute_data):
        try:
            attribute_line_ids = []
            for idx, col in enumerate(range(26, 44)):
                a_value = worksheet.cell_value(row, col)
                if attribute_data.get(col) and attribute_data.get(col)['values']:
                    #TODO- if value is * (wild card) then set all attribute values
                    value_ids = []
                    if a_value:
                        if isinstance(a_value, float):
                            a_value = str(int(a_value))
                    for v in a_value.split(','):
                        if v in attribute_data.get(col)['values']:
                            value_ids.append(attribute_data.get(col)['values'][v])
                    if value_ids:
                        attribute_line_ids.append((0, 0, {'attribute_id': attribute_data.get(col)['attribute_id'], 'value_ids': [(6, 0, value_ids)]}))
                    else:
                        attribute_line_ids.append((0, 0, {'attribute_id': attribute_data.get(col)['attribute_id'], 'value_ids': [(6, 0, attribute_data.get(col)['values'].values())]}))
        except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')

        return attribute_line_ids

    def _extract_product_datas(self, row, workbook, worksheet, heater_codes, used_in_row, category_ids, application_fields, fields_index, index_categories_ids, attribute_data):
        #logger.info("extracting product data")
        try:
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

                for idx, col in enumerate(range(4, 26)):
                    if worksheet.cell_value(r, col):
                        categ_ids += filter(None, [ici.get(col) for ici in index_categories_ids])
                # col 3 = Used in. -> we don't need this
                # col 4,5,6,7,8(E,F,G,H,I to Z) are Used in values
                models = self._prepare_models_combinations(r, worksheet, heater_codes, used_in_row, application_fields, fields_index)
                # prepare final dict for product
                res = dict(
                    default_code=part_no,
                    p4h_code=part_no.translate(p4h_parts),
                    name=product_name,
                    image=self._find_product_image(part_no, self.mif_path),
                    #image=self.product_img_base64,
                    type='product',
                    product_class='p',
                    source_doc = self.miff_file,
                    #product_image_ids=self.product_extra_img_base64,
                    website_published=True,
                    #attribute_line_ids=self._prepare_attribute_lines(r, worksheet, attribute_data),
                    attribute_line_ids = False,
                    other_data={'callout': callout, 'group': group, 'dependancy1': dependancy1, 'dependancy2': dependancy2, 'dependancy3': dependancy3, 'models': models},
                    public_categ_ids=[(4, c_id) for c_id in categ_ids]
                )
                products.append(res)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return products

    def import_products(self, row, workbook, worksheet, heater_codes, used_in_row, category_ids, application_fields, fields_index, index_categories_ids, attribute_data, models_data):
        datas = self._extract_product_datas(row, workbook, worksheet, heater_codes, used_in_row, category_ids, application_fields, fields_index, index_categories_ids, attribute_data)
        object_proxy, db_name, uid, password = self._get_connection_items()
        #logger.info("=====Creating Products=====")
        try:
            i = 1
            for d in datas:
                # do not create if product is already exists with same internal reference
                fields = ['description']
                product_data = object_proxy.execute(db_name, uid, password, "product.template", "search_read", [('default_code', "=", d['default_code'])], fields)
                parts_data = d.pop('other_data')

                if len(product_data) and product_data[0].get('id'):
                    product_id = product_data[0].get('id')
                    # may be later we might need to a search read call
                    d.pop('default_code')
                    d.pop('name')
                    d.pop('public_categ_ids')
                    d.pop('attribute_line_ids')
                    # overrtie image
                    object_proxy.execute(db_name, uid, password, "product.template", "write", product_id, d)
                else:
                    product_id = object_proxy.execute(db_name, uid, password, "product.template", "create", d)

                    external_id_vals = {
                      'model': 'product.template',
                      'module': 'p4h',
                      'name': d['default_code'],
                      'res_id': product_id,
                    }

                    exid_is_there = object_proxy.execute(db_name, uid, password,"ir.model.data","search",[('model','=','product.template'),('module','=','p4h'),('res_id','=',product_id)])
                    if not exid_is_there:
                        external_id = object_proxy.execute(db_name, uid, password, "ir.model.data","create",external_id_vals)

                # create new model datas
                for model in parts_data['models']:
                    for m in model['models'].split(', '):
                        if not m:
                            continue
                        m = m.rstrip()
                        model_found = object_proxy.execute(db_name, uid, password, "product.template", "search", [('default_code', "=", m)])
                        if not model_found:
                            break 
                        model_data = object_proxy.execute(db_name, uid, password, "product.template", "search_read",[('default_code', "=", m)] , ['name'])[0]
                        parts = {
                        'model_id': model_data.get('id'),
                        'callout': parts_data['callout'],
                        'dependency1': parts_data['dependancy1'],
                        'dependency2': parts_data['dependancy2'],
                        'dependency3': parts_data['dependancy3'],
                        'quantity': model['qunatity'],
                        'part_id': product_id,
                        'group': parts_data['group'],
                        'name': model_data.get('name'),
                        'source_doc': self.miff_file,
                        'attribute_line_ids': self._prepare_model_attribute_lines(models_data[m]['code'], attribute_data, 'attribute_id', 'value_ids'),
                        }
                        is_exist = object_proxy.execute(db_name, uid, password, "model.part", "search_count", [('model_id', "=", model_data.get('id')), ('part_id', '=', product_id)])
                        if not is_exist:
                            object_proxy.execute(db_name, uid, password, "model.part", "create", parts)

                i += 1
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        logger.info(str(i) + ' parts imported' )

    def play_with_xlsx_file(self):
        #logger.info("=====Started Proccessing On File=======")
        logging_time_start = datetime.now()
        logger.info(datetime.now().strftime("%a, %d %B %Y %H:%M:%S"))
        logger.info("%s" % (ntpath.basename(self.prodcut_import_file)))
        try:
            workbook = xlrd.open_workbook(self.prodcut_import_file)
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
                    categories, index_categories = self._process_category(r, worksheet)
                    heater_codes[MAP_HEATER_CODE[r]] = {
                        'name': worksheet.cell_value(r, 1),
                        'description': worksheet.cell_value(r, 2),
                        'code': heater_code,
                        'index_categories': index_categories,
                        'mfg_id': int(worksheet.cell_value(r, 26)),
                    }
                    #category_ids += categories
                    index_categories_ids.append(index_categories)
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
            #print used_in_row
            heater_codes = self.explode_heater_code(heater_codes, used_in_row)
            attribute_ids = self._create_attribute()
            attribute_data = self._process_attributes(attributes, attribute_ids)
            models_data = self._process_models(heater_codes, used_in_row, attribute_data, application_fields, fields_index, used_in_row_index)
            if not self.skip_import:
                self.import_products(row, workbook, worksheet, heater_codes, used_in_row, category_ids, application_fields, fields_index, index_categories_ids, attribute_data, models_data)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')

        #logger.info("=====END Proccessing On File=======")
        #logger.info("%s" % (self.prodcut_import_file))
        logging_time_end = datetime.now()
        logging_time = logging_time_end - logging_time_start
        #logger.info(datetime.now().strftime("%a, %d %B %Y %H:%M:%S"))
        logger.info("time to process was " + str(round((logging_time).total_seconds() / 60.0)) + " minutes")

    # ================================================================
    #                        Category StuFF
    # ================================================================

    def _process_category(self, row, worksheet):
        #logger.info("======Creating Category==========")
        try:
            #TODO simplyfiy this horrible rpc call if possible
            # AF - AD Main Category
            # 31 - 25
            categories = []
            object_proxy, db_name, uid, password = self._get_connection_items()
            prev_categ = False

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')

        def CovertToInt(s):
            try:
                return int(s)
            except ValueError:
                return False

        def create_category(vals):
            return object_proxy.execute(db_name, uid, password, "product.public.category", "create", vals)

        def search_category(name, categ_id):
            domain = [('categ_id', '=', categ_id)]
            if name:
                domain = [('name', '=', name)]
            c_id = object_proxy.execute(db_name, uid, password, "product.public.category", "search", domain)
            return c_id and c_id[0] or False

        def create_or_return_category_id(categ_id):
            categ_id = int(categ_id)
            c_id = search_category(False, categ_id)
            if not c_id:
                c_id = create_category({'categ_id': categ_id, 'name': self.category_datas.get(categ_id), 'parent_id': prev_categ})
            return c_id

        try:
            for col in [31, 30, 27]:
                #column AF, AE, AB

                categ_id = CovertToInt(worksheet.cell_value(row, col))
                if categ_id and self.category_datas.get(categ_id):
                    c_id = create_or_return_category_id(categ_id)
                    prev_categ = c_id

            # #column B -> not a good way to do it
            categ_name = worksheet.cell_value(row, 1)
            c_id = search_category(categ_name, False)
            if not c_id:
                c_id = create_category({'name': categ_name, 'parent_id': prev_categ})
            prev_categ = c_id
            #coulmn B END

            #categories.append(c_id)
            index_categories = {}
            # column E - Z
            # for column E-Z instead of mapping category from category file, we should use model prefix + model range
            # as per the new requirement
            # TODO - some code can be improved after this new requirement, but as of now that is not our priority
            temp_row = row
            for r in range(temp_row, worksheet.nrows):
                name = worksheet.cell_value(r, 0)
                temp_row = temp_row + 1
                if name == 'CALLOUT':
                    for col in range(4, 26):
                        v = self.Convert2Str(worksheet.cell(r, col))
                        if v:
                            code = self.Convert2Str(worksheet.cell(row, 0))
                            code = code.split('[')
                            code = (code and code[0] or '') + v
                            c_id = search_category(code, False)
                            if not c_id:
                                c_id = create_category({'name': code, 'parent_id': prev_categ})
                            index_categories.update({col: c_id})
                            categories.append(c_id)
                    break
        # for idx, col in enumerate(range(4, 26)):
        #     categ_id = CovertToInt(worksheet.cell_value(row, col))
        #     if categ_id and self.category_datas.get(categ_id):
        #         c_id = create_or_return_category_id(categ_id)
        #         index_categories.update({col: c_id})
        #         categories.append(c_id)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.error('\n\n\nFAILURE on ' + ntpath.basename(self.prodcut_import_file) \
                          + '\nTYPE: ' + str(exc_type) + '\nVALUE: ' + str(exc_obj)  \
                          + '\nLINE: ' + str(exc_tb.tb_lineno) + '\n\n\n')
        return categories, index_categories

    def _get_category_file(self, files):
        for file in files:
            if file.startswith('categoryMappings') and file.endswith('.xlsx'):
                return file

    def _extract_category_data_from_worksheet(self, worksheet, workbook):
        res = {}
        for row in range(1, worksheet.nrows):
            res[int(worksheet.cell_value(row, 0))] = worksheet.cell_value(row, 1)
        return res

    def _prepare_category_mapping_data(self):
        workbook = xlrd.open_workbook(self.mif_path + '/' + self.category_file)
        worksheet = workbook.sheet_by_index(0)
        return self._extract_category_data_from_worksheet(worksheet, workbook)

    def create_mif_directories(self):
        mif_directories = ['mif_done', 'mif_error']
        for directory in mif_directories:
            if not os.path.exists(directory):
                os.makedirs(directory, 0777)

    def create_mif_file_entry(self):
        object_proxy, db_name, uid, password = self._get_connection_items()
        object_proxy.execute(db_name, uid, password, "mif.file", "create", {'name': self.miff_file})

    def delete_prior_data(self):
        object_proxy, db_name, uid, password = self._get_connection_items()
        model_ids = object_proxy.execute(db_name, uid, password, "product.template", "search", [('source_doc', '=', self.miff_file), ('product_class', '=', 'm')])
        logger.info('MIF: ' + str(self.miff_file))
        logger.info('Deleting Models' + str(model_ids))
        object_proxy.execute(db_name, uid, password, "product.template", "unlink", model_ids)

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

    def get_immediate_file(self, dir):
        return [file for file in os.listdir(dir) if os.path.isfile(os.path.join(dir, file))]

    def get_immediate_subdirectories(self, dir):
        return [name for name in os.listdir(dir) if os.path.isdir(os.path.join(dir, name))]

    def _get_connection_items(self):
        object_proxy = self.connection.object_proxy
        db_name = self.connection.db_name
        uid = self.connection.uid
        password = self.connection.password
        return object_proxy, db_name, uid, password

    def _move_file_to_mif_directory(self, file, mif_directory):
        shutil.move(file, mif_directory)

    def _remove_file_from_mif_directory(self, mif):
        try:
            shutil.rmtree(mif)
        except:
            pass

    # =================================================
    #             Main Method
    # =================================================

    def start(self):
        # create directory 'mif_done' and 'mif_error'
        self.create_mif_directories()
        # 1 Get all files under the MIF
        files = self.get_immediate_file(self.mif_path)
        self.category_file = self._get_category_file(files)
        self.category_datas = self.category_file and self._prepare_category_mapping_data() or False
        # 2 Get all directory under the MIF
        subdirs = self.get_immediate_subdirectories(self.mif_path)
        for subdir in subdirs:
            # 2 Extract all file from the directory (we are assuiming that we have all files, which mention on task)
            # testing directory = 'CFCHRP04-CopperFin2-CHCF401-751-AfterSerial#L03H00160759'
            if subdir != 'images':
                try:
                    self.initialize_mif_variable()
                    self.extract_files_from_subdirectory(subdir)
                    self.delete_prior_data()
                    if self.prodcut_import_file:
                        self.play_with_xlsx_file()
                        # enable below line if you want to move the successfully imported file to 'mif_done' folder
                        # create mif file entry
                        self.create_mif_file_entry()
                        self._remove_file_from_mif_directory('./mif_done/' + subdir)
                        self._move_file_to_mif_directory('./mif_to_import/' + subdir, './mif_done/')
                except Exception as e:
                    self._remove_file_from_mif_directory('./mif_error/' +subdir)
                    self._move_file_to_mif_directory('./mif_to_import/' + subdir, './mif_error/')

if __name__ == '__main__':
    setup_logger()
    try:
        connection = OdooConnection('admin', 'change*me!', '11.0-mif-imp-test')
        status = connection.set_connection()
        if not status:
            logger.warning("Connection Failed ......")
        else:
            importobj = ImportMIF('/opt/odoo/psus-parts4heating/mif_to_import/', connection)
            importobj.start()
    except Exception as e:
        logger.error('Script stoped with error' + str(e))
