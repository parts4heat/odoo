# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.http import request

class P4HWebsiteSale(WebsiteSale):
    def _get_search_domain(self, search, category, attrib_values):
        domain = request.website.sale_product_domain()
        if search:
            # for srch in search.split(" "):
            #     domain += [
            #         '|', '|', '|', ('name', 'ilike', srch), ('description', 'ilike', srch), ('description_sale', 'ilike', 
            # srch), ('product_variant_ids.default_code', '=', srch)] CUSTOM
            search = search.strip().upper()
            search2 = search.replace(' ','').strip()
            search2 = search.replace('-','')
            domain += [
                '|','|','|','|','|',('p4h_code','ilike',search2),('default_code','=',search2),('name','ilike',search2),
                ('description','ilike',search2),
                ('description_sale', 'ilike', search2), ('product_variant_ids.default_code', '=', search2)]
            # CUSTOM END
        if category:
            domain += [('public_categ_ids', 'child_of', int(category))]
        if attrib_values:
            attrib = None
            ids = []
            for value in attrib_values:
                if not attrib:
                    attrib = value[0]
                    ids.append(value[1])
                elif value[0] == attrib:
                    ids.append(value[1])
                else:
                    domain += [('attribute_line_ids.value_ids', 'in', ids)]
                    attrib = value[0]
                    ids = [value[1]]
            if attrib:
                domain += [('attribute_line_ids.value_ids', 'in', ids)]
        return domain
