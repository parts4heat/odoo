# -*- coding: utf-8 -*-
{
    'name': "P4H Sales Fields",

    'summary': """Extending the Sales Order Model""",

    'description': """
Sales Order:
referrer - url used to reach page
model_searched, model_entered, serial_entered - model match information
hold, hold_message - manage order holds
score - support automatic validation or orders

""",

    'author': "Odoo Inc. PS",
    'website': "https://www.odoo.com",
    'category': 'PS Developments',
    'version': '0.1',
    'depends': ['p4h_product_sequence','sale_management', 'stock_available_unreserved', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/web.xml',
        'views/sale_order.xml',
        'views/product.xml',
        'views/mif_file.xml',
        'views/model_parts.xml',
        'views/product_template.xml',
        'data/data.xml',
    ],
    'demo': [
    ],
}
