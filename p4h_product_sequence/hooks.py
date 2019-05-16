# Copyright 2004 Tiny SPRL
# Copyright 2016 Sodexis
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


def pre_init_hook(cr):
    """
    Updates existing codes matching the default '/' or
    empty. Primarily this ensures installation does not
    fail for demo data.
    :param cr: database cursor
    :return: void
    """
    cr.execute(
        "alter table product_template drop column if exists p4h_code; "
        "alter table product_template add column p4h_code varchar; "
        "update product_template set p4h_code = 'P[TBA]' || id where p4h_code is null or p4h_code = '/';"
    )
