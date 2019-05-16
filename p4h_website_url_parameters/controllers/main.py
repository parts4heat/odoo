# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import http
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.http import request
from urllib.parse import urlparse

class WebsiteSale(WebsiteSale):

    @http.route(['/shop/cart'], type='http', auth="public", website=True)
    def cart(self, **post):
        order = request.website.sale_get_order()
        u = urlparse(request.httprequest.referrer)
        order.referrer = u.netloc + u.path
        order.model_searched = u.query
        return super(WebsiteSale, self).cart(**post)
