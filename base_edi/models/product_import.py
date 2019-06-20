# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import os
import pprint
import logging
import ntpath
import base64
import xlrd
from datetime import datetime


from odoo import fields, models, _

_logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)


class SyncDocumentType(models.Model):

    _inherit = 'sync.document.type'

    doc_code = fields.Selection(selection_add=[
        ('import_product', 'Import Product'),
    ])

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

    def extract_files_from_subdirectory(self, conn, sync_action_id, directory):
        file_path = os.path.join(sync_action_id.dir_path, directory)
        conn.cd(file_path)
        mif_files = conn.ls()
        for file in mif_files:
            if file.endswith(".xlsx"):
                self.product_import_file = os.path.join(sync_action_id.dir_path + directory, file)
            elif file == directory + ".pdf":
                file_path = os.path.join(sync_action_id.dir_path + directory, file)
                print(file_path)

    def _import_products(self, conn, sync_action_id):
        logging_time_start = datetime.now()
        _logger.info(datetime.now().strftime("%a, %d %B %Y %H:%M:%S"))
        #_logger.info("%s" % (ntpath.basename(self.prodcut_import_file)))
        try:
            print("\n>>>>>>>>", self.product_import_file)
            xlsx_file = conn.download_file(self.prodcut_import_file)
            print("\n>>>>xlsx_file", xlsx_file)
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
