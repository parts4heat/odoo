# -*- coding: utf-8 -*-

from . import delivery_carrier
from . import res_partner
from . import res_company
from . import res_config_settings
from . import sale_order

__all__ = [
    "res_partner",
    "res_company",
    "res_config_settings",
    "delivery_carrier",
    "sale_order",
]
