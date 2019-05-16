# -*- coding: utf-8 -*-
# Copyright 2016 Sodexis
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase
from ..hooks import pre_init_hook


class TestProductSequence(TransactionCase):
    """Tests for creating product with and without Product Sequence"""

    def setUp(self):
        super(TestProductSequence, self).setUp()
        self.product_product = self.env['product.template']

    def test_product_create_without_p4h_code(self):
        product_1 = self.product_product.create(dict(
            name="Orange",
            p4h_code='/'))
        self.assertRegexpMatches(str(product_1.p4h_code), r'P*')

    def test_product_copy(self):
        product_2 = self.product_product.create(dict(
            name="Apple",
            p4h_code='PROD02'
        ))
        copy_product_2 = product_2.copy()
        self.assertRegexpMatches(str(copy_product_2.p4h_code), r'P*')

    def test_pre_init_hook(self):
        product_3 = self.product_product.create(dict(
            name="Apple",
            p4h_code='PROD03'
        ))
        self.cr.execute(
            "update product_template set p4h_code='/' where id=%s"
            % (product_3.id,))
        product_3.invalidate_cache()
        self.assertEqual(product_3.p4h_code, '/')
        pre_init_hook(self.cr)
        product_3.invalidate_cache()
        self.assertEqual(product_3.p4h_code, 'P[TBA]%s' % (product_3.id,))

