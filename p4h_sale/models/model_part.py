# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ModelPart(models.Model):
    _name = 'model.part'
    _description = "Model Part"

    attribute_line_ids = fields.One2many('product.attribute.line','model_part_id',string='Product Attributes')
    callout = fields.Char(string='Callout')
    dependency1 = fields.Char(string='Dependency 1')
    dependency2 = fields.Char(string='Dependency 2')
    dependency3 = fields.Char(string='Dependency 3')
    group = fields.Char(string='Group')
    image_medium = fields.Binary(string='Image',related='part_id.image_medium')
    list_price = fields.Float(string='Sales Price',related='part_id.list_price')
    mfg_id = fields.Many2one('res.partner', string='Manufacturer')
    model_default_code = fields.Char(string='Model Internal Reference',related='model_id.default_code', store=True)
    model_id = fields.Many2one('product.template',string='Model', ondelete='cascade')
    model_name = fields.Char(string='Model Name', related='model_id.name')
    name = fields.Char(string='Name')
    p4h_code = fields.Char(string='P4H Code',related='part_id.p4h_code')
    part_default_code = fields.Char(string='Part Internal Reference',related='part_id.default_code')
    part_id = fields.Many2one('product.template',string='Part')
    part_name = fields.Char(string='Part Name',related='part_id.name')
    qty_available_not_res = fields.Float(string='Available', related='part_id.qty_available_not_res')
    quantity = fields.Char(string='Quantity Required')
    source_doc = fields.Char(string='MIF Source')
    standard_price = fields.Float(string='Cost Price',related='part_id.standard_price')
    heater_code = fields.Char('Heater Code',related='part_id.heater_code')
    heater_sizes = fields.Char('Heater Sizes', related='part_id.heater_sizes')

    @api.multi
    def action_open_manual(self):
        """
            open manual file which attached to related model
        """
        self.ensure_one()
        if not self.model_id.parts_list:
            raise UserError(_('No Parts List found for this model part'))
        return {
            'type': 'ir.actions.act_url',
            'url':   '/web/content/product.template/%s/parts_list' % (self.model_id.id),
            'target': '_blank',
        }
