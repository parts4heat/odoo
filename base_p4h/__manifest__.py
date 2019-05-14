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
    "version": "1.0",
    "description": """

THIS MODULE IS PROVIDED AS IS - INSTALLATION AT USERS' OWN RISK - AUTHOR OF MODULE DOES NOT CLAIM ANY
RESPONSIBILITY FOR ANY BEHAVIOR ONCE INSTALLED.
        """,
    "depends": ["sale_management", "product", "website_sale", "sms", "delivery"],
    "data": ["views/ir_ui_views.xml", "data/ir_cron.xml", "data/records.xml"],
    "installable": True,
}
