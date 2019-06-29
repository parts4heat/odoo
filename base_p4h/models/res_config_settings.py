# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    image_ftp_address = fields.Char(
        string="Image FTP Address",
        related="company_id.image_ftp_address",
        readonly=False,
    )
    image_ftp_user = fields.Char(
        string="Image FTP User", related="company_id.image_ftp_user", readonly=False
    )
    image_ftp_password = fields.Char(
        string="Image FTP Password",
        related="company_id.image_ftp_password",
        readonly=False,
    )
    image_ftp_port = fields.Char(
        string="Image FTP Port", related="company_id.image_ftp_port", readonly=False
    )
    image_ftp_folder = fields.Char(
        string="Image FTP Folder", related="company_id.image_ftp_folder", readonly=False
    )
    image_ftp_last_update = fields.Datetime(
        string="Image FTP Last Update",
        related="company_id.image_ftp_last_update",
        readonly=False,
    )
    image_ftp_type = fields.Selection(
        [("ftp", "FTP"), ("sftp", "SFTP")],
        string="Image FTP Type",
        related="company_id.image_ftp_type",
        readonly=False,
    )
    order_ftp_address = fields.Char(
        string="Order FTP Address",
        related="company_id.order_ftp_address",
        readonly=False,
    )
    order_ftp_user = fields.Char(
        string="Order FTP User", related="company_id.order_ftp_user", readonly=False
    )
    order_ftp_password = fields.Char(
        string="Order FTP Password",
        related="company_id.order_ftp_password",
        readonly=False,
    )
    order_ftp_port = fields.Char(
        string="Order FTP Port", related="company_id.order_ftp_port", readonly=False
    )
    order_ftp_folder = fields.Char(
        string="New Order FTP Folder",
        related="company_id.order_ftp_folder",
        readonly=False,
    )
    order_done_ftp_folder = fields.Char(
        string="Processed Order FTP Folder",
        related="company_id.order_done_ftp_folder",
        readonly=False,
    )
    order_ftp_type = fields.Selection(
        [("ftp", "FTP"), ("sftp", "SFTP")],
        string="Order FTP Type",
        related="company_id.order_ftp_type",
        readonly=False,
    )
    order_default_team = fields.Many2one(
        "crm.team",
        string="Order Default Team",
        related="company_id.order_default_team",
        readonly=False,
    )
    order_default_product = fields.Many2one(
        "product.product",
        string="Order Default Product",
        related="company_id.order_default_product",
        readonly=False,
    )
    order_default_credit_product = fields.Many2one(
        "product.product",
        string="Order Default Credit Product",
        related="company_id.order_default_credit_product",
        readonly=False,
    )
    purchase_ftp_address = fields.Char(
        string="Purchase FTP Address",
        related="company_id.purchase_ftp_address",
        readonly=False,
    )
    purchase_ftp_user = fields.Char(
        string="Purchase FTP User",
        related="company_id.purchase_ftp_user",
        readonly=False,
    )
    purchase_ftp_password = fields.Char(
        string="Purchase FTP Password",
        related="company_id.purchase_ftp_password",
        readonly=False,
    )
    purchase_ftp_port = fields.Char(
        string="Purchase FTP Port",
        related="company_id.purchase_ftp_port",
        readonly=False,
    )
    purchase_ftp_folder = fields.Char(
        string="New Purchase FTP Folder",
        related="company_id.purchase_ftp_folder",
        readonly=False,
    )
    purchase_done_ftp_folder = fields.Char(
        string="Processed Purchase FTP Folder",
        related="company_id.purchase_done_ftp_folder",
        readonly=False,
    )
    purchase_ftp_type = fields.Selection(
        [("ftp", "FTP"), ("sftp", "SFTP")],
        string="Purchase FTP Type",
        related="company_id.purchase_ftp_type",
        readonly=False,
    )
    purchase_default_product = fields.Many2one(
        "product.product",
        string="Purchase Default Product",
        related="company_id.purchase_default_product",
        readonly=False,
    )
    shipstation_key = fields.Char(
        string="SS Key", related="company_id.shipstation_key", readonly=False
    )
    shipstation_secret = fields.Char(
        string="SS Secret", related="company_id.shipstation_secret", readonly=False
    )
    shipstation_root_endpoint = fields.Char(
        string="SS Root Endpoint",
        related="company_id.shipstation_root_endpoint",
        readonly=False,
    )
    shipstation_hook_ids = fields.One2many(
        "shipstation.webhook",
        string="Webhooks",
        related="company_id.shipstation_hook_ids",
        readonly=False,
    )
    target_postback_url = fields.Char(
        string="Postback Target URL",
        placeholder="e.g https://www.odoo.com/shipstation/shipped",
        related="company_id.target_postback_url",
        readonly=False,
    )

    @api.multi
    def get_service(self):
        for record in self:
            record.company_id.get_service()

    @api.multi
    def get_packages(self):
        for record in self:
            record.company_id.get_packages()
