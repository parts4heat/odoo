# -*- coding: utf-8 -*-
{
    'name': "P4H Sales Fields",

    'summary': """Extending the Sales Order Model""",

    'author': "Odoo Inc. PS",
    'website': "https://www.odoo.com",
    'category': 'PS Developments',
    'version': '0.1',
    'depends': ['p4h_product_sequence','sale_management', 'stock_available_unreserved', 'stock','purchase','base_automation'],
    'data': [
        'data/automated_action.xml',
        'data/data.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/web.xml',
        'views/sale_order.xml',
        'views/product.xml',
'views/exploded_view.xml',
'views/mif_file.xml',
'views/model_parts.xml',
'views/product_attributes.xml',
'views/product_attribute_values.xml',
'views/product_supplier_info.xml',
'views/product_template.xml',
'views/res_partner.xml',
    ],
    'demo': [
    ],
}
