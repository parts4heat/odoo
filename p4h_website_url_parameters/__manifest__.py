# -*- coding: utf-8 -*-

{
    'name': 'P4H URL Parameters',
    'version': '0.1',
    'author': "Odoo Inc. PS",
    'website': "https://www.odoo.com",
    'description': 'Populate the sale.order model fields x_model_searched and x_referrer when items are added to the shopping cart',
    'license': 'AGPL-3',
    'category': 'Website',
    'depends': [
        'website_sale','p4h_sale',
    ],
    'data': [
    ],
    'auto_install': False,
    'installable': True,
}
