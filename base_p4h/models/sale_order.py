# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    paymentmethod = fields.Char("Volusion Payment Method")
    shipdate = fields.Datetime("Volusion Ship Date")
    shipresidential = fields.Boolean("Volusion Ship Residential")
    hold = fields.Boolean(string="On Hold", default=False)
    hold_message = fields.Html(string="Hold Message")
    model_entered = fields.Char(string="Model Entered")
    model_searched = fields.Char(string="Model Searched")
    referrer = fields.Char(string="Referrer")
    serial_entered = fields.Char(string="Serial Entered")
    score = fields.Integer(string="Model Match Score")

    @api.multi
    def _action_confirm(self):
        """
        GFP: Inheriting base function to select the cheapest alternative if
            a) current product does not have availability
            b) has the 'list' procurement_method
            c) has alternates
            d) any of the alternates have availabilty
        if none of these conditions are met it confirms with the existing product
        """
        for record in self:
            for line in record.order_line:
                selected_prod = line.product_id._alternate_check_availability(line)
                if selected_prod:
                    if selected_prod != line.product_id:
                        line.orig_product_id = line.product_id
                        line.product_id = selected_prod
                        message = """
                        %s has been swapped for %s given the alternate configuration of the product.
                        """ % (
                            line.orig_product_id.display_name,
                            line.product_id.display_name,
                        )
                        self.message_post(body=message)
                elif line.product_id.procurement_method == "list":
                    message = """
                    Order confirmed w/ %s since there is no available qty for any of the alternates.
                    """ % (
                        line.product_id.display_name,
                    )
                    self.message_post(body=message)

        return super(SaleOrder, self)._action_confirm()


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    orig_product_id = fields.Many2one(
        "product.product", string="Original Product Selection"
    )
