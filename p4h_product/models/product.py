# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.depends('part_ids')
    def _compute_parts_count(self):
        for record in self:
            record.parts_count = len(record.part_ids)


    dependency_1_label = fields.Char(string='Dependency 1 Label')
    dependency_2_label = fields.Char(string='Dependency 2 Label')
    dependency_3_label = fields.Char(string='Dependency 3 Label')
    exploded_views = fields.One2many('exploded.view','model_id',string='Exploded Views')
    parts_list = fields.Binary(string='Parts List')
    manual = fields.Binary(string='Manual')
    manual_filename = fields.Char(string='Manual Filename')
    mfg_id = fields.Many2one('res.partner',string='Manufacturer',domain="[('mfg_lookup','!=',0)]")
    mfg_name = fields.Char(string='Manufacturer Name',related='mfg_id.name')
    part_ids = fields.One2many('model.part','model_id',string='Parts')
    parts_count = fields.Integer(string="Parts Count", compute="_compute_parts_count")
    product_class = fields.Selection(string='Class',selection=[('m', 'Model'),('p','Part'),('s','Standard')], default='s')
    source_doc = fields.Char('MIF Source')
    heater_code = fields.Char('Heater Code')
    heater_sizes = fields.Char('Heater Sizes')

