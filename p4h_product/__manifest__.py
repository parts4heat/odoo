# -*- coding: utf-8 -*-
{
    'name': "P4H Product Fields",

    'summary': """Extending the Product Models""",

    'description': """
Product Category:
categ_id - holds the MIF Category ID

Product Template:
manual, manual_filename - holds the PDF for each model
miff_import_details - holds the file that created the model/part

""",

    'author': "Odoo Inc. PS",
    'website': "https://www.odoo.com",
    'category': 'PS Developments',
    'version': '0.1',
    'depends': ['p4h_sale','p4h_product_sequence', 'website_sale', 'document', 'purchase', 'stock_available_unreserved'],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/product_template.xml',
        'views/product_supplier_info.xml',
        'views/product_attributes.xml',
        'views/product_attribute_values.xml',
        'views/model_parts.xml',
        'views/mif_file.xml',
        'views/res_partner.xml',
        'views/exploded_view.xml',
    ],
    'demo': [
    ],
}
