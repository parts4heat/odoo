# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MifFile(models.Model):
    _name = 'mif.file'
    _description = "MIF File"
    _order = 'id'

    name = fields.Char(string='File Name')
    log_note = fields.Text()
    mif_directory = fields.Char()
    state = fields.Selection([('pending', 'Pending'), ('in_progress', 'In Progress'), ('done', 'Done'), ('error', 'Error')], default='pending')
    model_counts = fields.Integer(compute='_compute_count')
    part_counts = fields.Integer(compute='_compute_count')
    parts_list = fields.Binary(string='Parts List')
    parts_list_filename = fields.Char()
    processing_start_date = fields.Datetime()
    processing_end_date = fields.Datetime()

    @api.multi
    def _compute_count(self):
        ProductTemplate = self.env['product.template']
        for mif in self:
            mif.model_counts = ProductTemplate.search_count([('mif_id', '=', mif.id), ('product_class', '=', 'm')])
            mif.part_counts = ProductTemplate.search_count([('mif_id', '=', mif.id), ('product_class', '=', 'p')])

    @api.multi
    def action_view_parts(self):
        action = self.env.ref('stock.product_template_action_product').read()[0]
        action['domain'] = [('mif_id', 'in', self.ids), ('product_class', '=', 'p')]
        action['context'] = {}
        return action

    @api.multi
    def action_view_models(self):
        action = self.env.ref('stock.product_template_action_product').read()[0]
        action['domain'] = [('mif_id', 'in', self.ids), ('product_class', '=', 'm')]
        action['context'] = {}
        return action
