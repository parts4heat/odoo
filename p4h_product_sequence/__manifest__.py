# -*- coding: utf-8 -*-
# Copyright 2004 Tiny SPRL
# Copyright 2016 Sodexis
# Copyright 2018 Eficent Business and IT Consulting Services S.L.
#   (http://www.eficent.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'P4H Product Sequence',
    'version': '0.1',
    'author': "Zikzakmedia SL,Sodexis,Odoo Community Association (OCA),Odoo Inc.",
    'website': 'https://github.com/OCA/product-attribute',
    'license': 'AGPL-3',
    'category': 'Product',
    'depends': [
        'stock',
    ],
    'data': [
        'data/product_sequence.xml',
        'views/product.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'auto_install': False,
    'installable': True,
}
