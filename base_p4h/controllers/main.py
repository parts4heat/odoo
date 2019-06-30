# -*- coding: utf-8 -*-
import logging

from odoo import http, api, _
from odoo.addons.stock_barcode.controllers.main import StockBarcodeController
from odoo.http import request
from datetime import datetime
from odoo import SUPERUSER_ID

_logger = logging.getLogger(__name__)


class ShipstationPortal(http.Controller):
    def _default_request_uid(self):
        return request.session.uid and request.session.uid or SUPERUSER_ID

    @http.route(
        "/shipstation/shipped", type="json", auth="public", csrf=False, cors="*"
    )
    def ship(self, req):
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        url = str(req.jsonrequest.get("resource_url"))
        new_post = env["shipstation.postback"].create({"name": url})
        string = str(new_post.id)
        return string


class StockBarcodeController(StockBarcodeController):
    def try_new_internal_picking(self, barcode):
        """
            GFP: Inheriting base function where we are opening a operation
            with a package if a package is scanned.
        """
        corresponding_package = request.env["stock.quant.package"].search(
            [("name", "=", barcode), ("quant_ids", "!=", False)], limit=1
        )
        if corresponding_package:
            internal_picking_type = request.env["stock.picking.type"].search(
                [("code", "=", "internal")]
            )
            warehouse = corresponding_package.location_id.get_warehouse()
            if warehouse:
                internal_picking_type = internal_picking_type.filtered(
                    lambda r: r.warehouse_id == warehouse
                )
            dest_loc = internal_picking_type[0].default_location_dest_id
            if internal_picking_type:
                record = corresponding_package
                new_moves = record.env["stock.move"]
                picking = request.env["stock.picking"].create(
                    {
                        "picking_type_id": internal_picking_type[0].id,
                        "location_id": corresponding_package.location_id.id,
                        "location_dest_id": dest_loc.id,
                        "immediate_transfer": True,
                    }
                )
                picking.action_confirm()
                for q in record.quant_ids:
                    if (q.quantity - q.reserved_quantity) > 0:
                        move_data = {
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "location_dest_id": record.location_dest_id.id,
                            "location_id": record.location_id.id,
                            "product_uom": q.product_uom_id.id,
                            "product_id": q.product_id.id,
                            "product_uom_qty": (q.quantity - q.reserved_quantity),
                            "name": record.name,
                            "picking_id": picking.id,
                        }
                        new_move = new_moves.create(move_data)
                        new_moves += new_move
                picking.move_lines += new_moves
                picking.state = "confirmed"
                for m in picking.move_lines:
                    m.state = "confirmed"
                picking.action_assign()

                return self.get_action(picking.id)
            else:
                return {
                    "warning": _(
                        "No internal operation type. Please configure one in warehouse settings."
                    )
                }
        corresponding_location = request.env["stock.location"].search(
            [("barcode", "=", barcode), ("usage", "=", "internal")], limit=1
        )
        if corresponding_location:
            internal_picking_type = request.env["stock.picking.type"].search(
                [("code", "=", "internal")]
            )
            warehouse = corresponding_location.get_warehouse()
            if warehouse:
                internal_picking_type = internal_picking_type.filtered(
                    lambda r: r.warehouse_id == warehouse
                )
            dest_loc = corresponding_location
            while dest_loc.location_id and dest_loc.location_id.usage == "internal":
                dest_loc = dest_loc.location_id
            if internal_picking_type:
                # Create and confirm an internal picking
                picking = request.env["stock.picking"].create(
                    {
                        "picking_type_id": internal_picking_type[0].id,
                        "location_id": corresponding_location.id,
                        "location_dest_id": dest_loc.id,
                        "immediate_transfer": True,
                    }
                )
                picking.action_confirm()

                return self.get_action(picking.id)
            else:
                return {
                    "warning": _(
                        "No internal operation type. Please configure one in warehouse settings."
                    )
                }
        return False
