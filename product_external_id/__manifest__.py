# -*- coding: utf-8 -*-
{
    'name': "Product External ID Synch",

    'summary': """
        Generate an External automatically for Products
        as they are added via the UI.""",

    'author': "Odoo Inc, PS.",
    'website': "http://www.odoo.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Warehouse',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'stock'],

    # always loaded
    'data': [
        'views/product.xml',
    ],
}
