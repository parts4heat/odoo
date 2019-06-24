# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ProcurementGroup(models.Model):
    _inherit = "procurement.group"

    @api.model
    def run(
        self, product_id, product_qty, product_uom, location_id, name, origin, values
    ):
        """
        GFP: Inheriting base function so that it selects the cheapest of the alternates on the procurement.
        More specifically, this is aimed at employing the reordering rules
        """
        if not values["sale_line_id"]:
            alternates = product_id.product_tmpl_id.alternate_ids.mapped(
                "product_alt_id"
            ).mapped("product_variant_ids")
            alternates |= product_id
            product_id = alternates.sorted(key=lambda x: x.standard_price)[0]
        values.setdefault(
            "company_id",
            self.env["res.company"]._company_default_get("procurement.group"),
        )
        values.setdefault("priority", "1")
        values.setdefault("date_planned", fields.Datetime.now())
        rule = self._get_rule(product_id, location_id, values)
        if not rule:
            raise UserError(
                _(
                    'No procurement rule found in location "%s" for product "%s".\n Check routes configuration.'
                )
                % (location_id.display_name, product_id.display_name)
            )
        action = "pull" if rule.action == "pull_push" else rule.action
        if hasattr(rule, "_run_%s" % action):
            getattr(rule, "_run_%s" % action)(
                product_id, product_qty, product_uom, location_id, name, origin, values
            )
        else:
            _logger.error(
                "The method _run_%s doesn't exist on the procument rules" % action
            )
        return True
