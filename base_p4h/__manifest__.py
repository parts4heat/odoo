# -*- coding: utf-8 -*-

###################################################################################
#
#    Copyright (C) 2019 Parts4Heating
#
###################################################################################

{
    "name": "Base Developments for Parts4Heating",
    "category": "Hidden",
    "author": "GFP Solutions LLC",
    "summary": "Custom",
    "version": "3.7",
    "description": """

THIS MODULE IS PROVIDED AS IS - INSTALLATION AT USERS' OWN RISK - AUTHOR OF MODULE DOES NOT CLAIM ANY
RESPONSIBILITY FOR ANY BEHAVIOR ONCE INSTALLED.
        """,
    "depends": [
        "delivery",
        "stock_barcode",
        "sale_management",
        "product",
        "website_sale",
        "sms",
        "delivery",
        "mrp",
        "p4h_sale",  # odoo developed custom module
        "p4h_product_sequence",  # odoo developed custom module
        "stock_available_unreserved",  # odoo developed custom module
    ],
    "data": [
        "views/ir_ui_views.xml",
        "views/ir_action_window.xml",
        "views/ir_ui_menu.xml",
        "data/ir_cron.xml",
        "data/records.xml",
        "data/ir_model_access.xml",
    ],
    "qweb": ["static/src/xml/qweb_templates.xml"],
    "installable": True,
}
