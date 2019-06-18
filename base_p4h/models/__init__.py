# -*- coding: utf-8 -*-

from . import delivery_carrier
from . import res_partner
from . import res_company
from . import res_config_settings
from . import sale_order
from . import mrp_bom
from . import product
from . import stock_move
from . import stock_picking
from . import stock_rule
from . import purchase_order

__all__ = [
    "res_partner",
    "res_company",
    "res_config_settings",
    "delivery_carrier",
    "sale_order",
    "mrp_bom",
    "product",
    "stock_move",
    "stock_picking",
    "stock_rule",
    "purchase_order",
]
