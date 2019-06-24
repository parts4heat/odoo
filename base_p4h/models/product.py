# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.addons import decimal_precision as dp
from odoo.tools import float_compare, UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # TODO: Incorporate the quant opening actions
    storage_location_id = fields.Many2one("stock.location", string="Storage Location")
    qty_available_not_res = fields.Float(
        "Quantity On Hand No Res",
        store=False,
        readonly=True,
        compute="_compute_ph_quantities",
        search="_search_quantity_unreserved",
        digits=dp.get_precision("Product Unit of Measure"),
    )
    ph_qty_available = fields.Float(
        "Quantity On Hand (incl. alt)",
        store=False,
        readonly=True,
        compute="_compute_ph_quantities",
        search="_search_ph_qty_available",
        digits=dp.get_precision("Product Unit of Measure"),
    )
    ph_virtual_available = fields.Float(
        "Forecasted Quantity (incl. alt)",
        store=False,
        readonly=True,
        compute="_compute_ph_quantities",
        search="_search_ph_virtual_available",
        digits=dp.get_precision("Product Unit of Measure"),
    )
    ph_incoming_qty = fields.Float(
        "Incoming (incl. alt)",
        store=False,
        readonly=True,
        compute="_compute_ph_quantities",
        search="_search_ph_incoming_qty",
        digits=dp.get_precision("Product Unit of Measure"),
    )
    ph_outgoing_qty = fields.Float(
        "Outgoing (incl. alt)",
        store=False,
        readonly=True,
        compute="_compute_ph_quantities",
        search="_search_ph_outgoing_qty",
        digits=dp.get_precision("Product Unit of Measure"),
    )

    def action_open_quants(self):
        self.env["stock.quant"]._merge_quants()
        self.env["stock.quant"]._unlink_zero_quants()
        products = self.mapped("product_variant_ids")
        products |= (
            self.mapped("alternate_ids")
            .mapped("product_alt_id")
            .mapped("product_variant_ids")
        )
        action = self.env.ref("stock.product_open_quants").read()[0]
        action["domain"] = [("product_id", "in", products.ids)]
        action["context"] = {"search_default_internal_loc": 1}
        return action

    @api.multi
    def _compute_ph_quantities(self):
        res = self._compute_ph_quantities_dict()
        for template in self:
            template.ph_qty_available = res[template.id]["qty_available"]
            template.ph_virtual_available = res[template.id]["virtual_available"]
            template.ph_incoming_qty = res[template.id]["incoming_qty"]
            template.ph_outgoing_qty = res[template.id]["outgoing_qty"]
            template.qty_available_not_res = res[template.id]["qty_available_not_res"]

    def _compute_ph_quantities_dict(self):
        self_variants = self.mapped("product_variant_ids")
        self_variants |= (
            self.mapped("alternate_ids")
            .mapped("product_alt_id")
            .mapped("product_variant_ids")
        )
        variants_available = self_variants._product_available()
        no_res = sum(self_variants.mapped("qty_available_not_res"))
        prod_available = {}
        for template in self:
            qty_available = 0
            virtual_available = 0
            incoming_qty = 0
            outgoing_qty = 0
            for p in variants_available.items():
                qty_available += p[1]["qty_available"]
                virtual_available += p[1]["virtual_available"]
                incoming_qty += p[1]["incoming_qty"]
                outgoing_qty += p[1]["outgoing_qty"]
            prod_available[template.id] = {
                "qty_available": qty_available,
                "virtual_available": virtual_available,
                "incoming_qty": incoming_qty,
                "outgoing_qty": outgoing_qty,
                "qty_available_not_res": no_res,
            }
        return prod_available

    @api.multi
    def action_open_quants_unreserved(self):
        product_ids = self.mapped("product_variant_ids")
        product_ids |= (
            self.mapped("alternate_ids")
            .mapped("product_alt_id")
            .mapped("product_variant_ids")
        )
        product_ids = product_ids.ids
        quants = self.env["stock.quant"].search([("product_id", "in", product_ids)])
        quant_ids = quants.filtered(lambda x: x.quantity > x.reserved_quantity).ids
        result = self.env.ref("stock.product_open_quants").read()[0]
        result["domain"] = [("id", "in", quant_ids)]
        result["context"] = {
            "search_default_locationgroup": 1,
            "search_default_internal_loc": 1,
        }
        return result

    @api.multi
    def action_open_ph_forecast(self):
        product_ids = self.mapped("product_variant_ids")
        product_ids |= (
            self.mapped("alternate_ids")
            .mapped("product_alt_id")
            .mapped("product_variant_ids")
        )
        product_ids = product_ids.ids
        result = self.env.ref(
            "stock.action_stock_level_forecast_report_template"
        ).read()[0]
        result["domain"] = [("product_id", "in", product_ids)]
        result["context"] = {"group_by": ["product_id"]}
        return result

    def _search_quantity_unreserved(self, operator, value):
        domain = [("qty_available_not_res", operator, value)]
        product_variant_ids = self.env["product.product"].search(domain)
        return [("product_variant_ids", "in", product_variant_ids.ids)]

    def _search_ph_qty_available(self, operator, value):
        domain = [("ph_qty_available", operator, value)]
        product_variant_ids = self.env["product.product"].search(domain)
        return [("product_variant_ids", "in", product_variant_ids.ids)]

    def _search_ph_virtual_available(self, operator, value):
        domain = [("ph_virtual_available", operator, value)]
        product_variant_ids = self.env["product.product"].search(domain)
        return [("product_variant_ids", "in", product_variant_ids.ids)]

    def _search_ph_incoming_qty(self, operator, value):
        domain = [("ph_incoming_qty", operator, value)]
        product_variant_ids = self.env["product.product"].search(domain)
        return [("product_variant_ids", "in", product_variant_ids.ids)]

    def _search_ph_outgoing_qty(self, operator, value):
        domain = [("ph_outgoing_qty", operator, value)]
        product_variant_ids = self.env["product.product"].search(domain)
        return [("product_variant_ids", "in", product_variant_ids.ids)]


class ProductProduct(models.Model):
    _inherit = "product.product"

    storage_location_id = fields.Many2one(
        "stock.location",
        string="Storage Location",
        related="product_tmpl_id.storage_location_id",
        store=True,
        readonly=False,
    )

    def _alternate_check_availability(self, line, single=False):
        """
        GFP: Checks to see if there are any alternatives available
        if the product itself is not available.
        """
        if self.type == "product":
            precision = self.env["decimal.precision"].precision_get(
                "Product Unit of Measure"
            )
            product = self.with_context(
                warehouse=line.order_id.warehouse_id.id,
                lang=line.order_id.partner_id.lang or self.env.user.lang or "en_US",
            )
            product_qty = line.product_uom._compute_quantity(
                line.product_uom_qty, self.uom_id
            )
            if (
                float_compare(
                    product.virtual_available, product_qty, precision_digits=precision
                )
                == -1
            ):
                is_available = line._check_routing()
                if is_available:
                    return self
                if (
                    not is_available
                    and self.procurement_method == "list"
                    and not single
                ):
                    if not self.alternate_ids:
                        return UserError(
                            "%s's configuration requires alternates configured."
                        )
                    for alternate in self.alternate_ids.sorted(
                        key=lambda x: x.product_alt_id.product_variant_id.standard_price
                    ):
                        alt_prod = alternate.product_alt_id.product_variant_id
                        returned_prod = alt_prod._alternate_check_availability(
                            line, single=True
                        )
                        if returned_prod:
                            return returned_prod
            else:
                return self
        return False
