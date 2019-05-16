================
Product Sequence
================

This module was derived from the original OCA product_sequence module and modified for Parts4Heating.

This module creates a new field for P4H Part Numbers and automatically populates it.
The P4H Part Number (p4h_code) is unique (SQL constrained), readonly via the UI and required.

Installation
============

Prior to installing this module, if you have any existing products you should
ensure they already have a unique reference (or no reference) set.  Products
with a default_code of '/' or empty will automatically be assigned a code of
"P[TBA]" followed by the system id for that product.

Otherwise the setting of the unique constraint will fail and the module will
fail to install.

Usage
=====

#. Works automatically

Credits
=======

Original Module Contributors
----------------------------

* Angel Moya <angel.moya@domatix.com>
* Graeme Gellatly <g@o4sb.com>
* Sodexis <dev@sodexis.com>
* Lois Rilo <lois.rilo@eficent.com>

Original Module Maintainer
--------------------------

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

This module is maintained by the OCA.

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

To contribute to this module, please visit https://odoo-community.org.
