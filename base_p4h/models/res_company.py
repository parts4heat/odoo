# -*- coding: utf-8 -*-

import os
import re
import csv
import json
import datetime
import ftplib
import logging
import base64
from html.parser import HTMLParser
from dateutil import parser

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MLstripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return "".join(self.fed)


class ResCompany(models.Model):
    _inherit = "res.company"

    image_ftp_address = fields.Char(string="Image FTP Address")
    image_ftp_user = fields.Char(string="Image FTP User")
    image_ftp_password = fields.Char(string="Image FTP Password")
    image_ftp_port = fields.Char(string="Image FTP Port")
    image_ftp_folder = fields.Char(string="Image FTP Folder")
    image_ftp_last_update = fields.Datetime(string="Image FTP Last Update")
    order_ftp_address = fields.Char(string="Order FTP Address")
    order_ftp_user = fields.Char(string="Order FTP User")
    order_ftp_password = fields.Char(string="Order FTP Password")
    order_ftp_port = fields.Char(string="Order FTP Port")
    order_ftp_folder = fields.Char(string="New Order FTP Folder")
    order_done_ftp_folder = fields.Char(string="Processed Order FTP Folder")
    order_default_team = fields.Many2one("crm.team", string="Order Default Team")
    order_default_product = fields.Many2one(
        "product.product", string="Order Default Product"
    )

    @api.model
    def run_cron_order_processing(self):
        for company in self.env["res.company"].search([]):
            _logger.info("Running Order Processing Cron for %s" % company.name)
            if (
                not company.order_ftp_address
                and not company.order_ftp_user
                and not company.order_ftp_password
                and not company.order_ftp_port
                and not company.order_ftp_folder
                and not company.order_done_ftp_folder
                and not company.order_default_product
            ):
                _logger.warning("FTP configuration not properly set, skipping company.")
                continue

            ip = company.order_ftp_address
            port = int(company.order_ftp_port)
            user = company.order_ftp_user
            pwd = company.order_ftp_password
            path = company.order_ftp_folder
            endpath = company.order_done_ftp_folder

            # Intial FTP configuration
            session = ftplib.FTP()
            session.connect(ip, port)
            session.login(user, pwd)
            path = re.sub("([/]{2,5})+", "/", path)
            endpath = re.sub("([/]{2,5})+", "/", endpath)
            _logger.info("FTP new order path: %s%s" % (ip, path))
            _logger.info("FTP order processed path: %s%s" % (ip, endpath))
            session.cwd(path)

            names = session.nlst()
            names = [k for k in names if ".csv" in k]
            _logger.info("Processing %s file(s)" % (len(names)))
            # Loop through the files and convert them to json dictionaries
            for name in names:
                data = []
                session.retrbinary("RETR " + name, open(name, "wb").write)
                with open(name) as inf:
                    for row in csv.DictReader(inf):
                        data.append(row)
                json_data = json.loads(json.dumps(data))
                orders_processed = company.env["sale.order"]
                payments_processed = company.env["payment.transaction"]
                for l in json_data:

                    order_id = company.env["sale.order"].search(
                        [("name", "=", l["orderid"])]
                    )
                    # Is this the first line in the order?
                    if not order_id:
                        # Look for existing customer, if not found create one
                        partner_id = company.env["res.partner"].search(
                            [("customerid", "=", l["customerid"])], limit=1
                        )
                        partner_shipping_id = False
                        related_co = False
                        if not partner_id:
                            _logger.info(
                                "Creating customer with id  %s" % (l["customerid"])
                            )
                            # Setting blank variables
                            city = country_id = state_id = related_co = False
                            extra_loc_string = ""

                            if l["billingconame"] or l["shipconame"]:
                                if l["shipconame"]:
                                    related_co_name = l["shipconame"]
                                if l["billingconame"]:
                                    related_co_name = l["billingconame"]
                                related_co = company.env["res.partner"].create(
                                    {
                                        "name": related_co_name,
                                        "customer": True,
                                        "supplier": False,
                                        "is_company": True,
                                    }
                                )
                            partner_id_dict = {
                                "name": l["billingfullname2"],
                                "email": l["emailaddress"],
                                "street": l["billingaddress1"],
                                "street2": l["billingaddress2"],
                                "phone": l["billphonenum"],
                                "fax": l["billingfaxnumber"],
                                "zip": l["billingpostalcode"],
                                "customerid": l["customerid"],
                            }
                            city = l["billingcity"]
                            if l["billingcountry"]:
                                country_id = company.env["res.country"].search(
                                    [("name", "ilike", l["billingcountry"])], limit=1
                                )
                                if not country_id:
                                    extra_loc_string = "%s %s" % (
                                        l["billingcountry"],
                                        extra_loc_string,
                                    )
                            if l["billingstate"]:
                                if country_id:
                                    state_id = company.env["res.country.state"].search(
                                        [
                                            ("code", "=", l["billingstate"]),
                                            ("country_id", "=", country_id.id),
                                        ],
                                        limit=1,
                                    )
                                else:
                                    state_id = company.env["res.country.state"].search(
                                        [
                                            ("code", "=", l["billingstate"]),
                                            (
                                                "country_id",
                                                "=",
                                                company.env.ref("base.us").id,
                                            ),
                                        ],
                                        limit=1,
                                    )
                                if not state_id:
                                    extra_loc_string = "%s%s" % (
                                        l["billingstate"],
                                        extra_loc_string,
                                    )
                            if len(extra_loc_string) > 0:
                                city = "%s %s" % (city, extra_loc_string)
                            partner_id_dict.update({"city": city})
                            if state_id:
                                partner_id_dict.update({"state_id": state_id.id})
                            if country_id:
                                partner_id_dict.update({"country_id": country_id.id})
                            if related_co:
                                partner_id_dict.update({"parent_id": related_co.id})
                            partner_id = company.env["res.partner"].create(
                                partner_id_dict
                            )
                        _logger.info(
                            "Odoo res.partner %s selected for customer"
                            % (partner_id.id)
                        )
                        if not related_co:
                            related_co = partner_id

                        # Decide if we should assign a specific delivery address
                        unique_shipping = False
                        if (
                            l["billingfullname2"] != l["shipfullname2"]
                            or l["billingaddress1"] != l["shipaddress1"]
                            or l["billingaddress2"] != l["shipaddress2"]
                            or l["billingcity"] != l["shipcity"]
                            or l["billingstate"] != l["shipstate"]
                            or l["billingcountry"] != l["shipcountry"]
                            or l["billingpostalcode"] != l["shippostalcode"]
                            or l["billphonenum"] != l["shipphonenumber"]
                            or l["billingfaxnumber"] != l["shipfaxnumber"]
                        ):
                            unique_shipping = True
                        if unique_shipping:
                            # Decide to use existing shipping address or create new one
                            ship_ids = related_co.child_ids.filtered(
                                lambda x: x.type == "delivery"
                                and x.street == l["shipaddress1"]
                                and x.street2 == l["shipaddress2"]
                            )
                            if ship_ids:
                                partner_shipping_id = ship_ids[0]
                            else:
                                _logger.info(
                                    "Creating delivery with id  %s" % (l["customerid"])
                                )
                                # Setting blank variables
                                city = country_id = state_id = False
                                extra_loc_string = ""

                                partner_shipping_id_dict = {
                                    "name": l["shipfullname2"],
                                    "street": l["shipaddress1"],
                                    "street2": l["shipaddress2"],
                                    "phone": l["shipphonenumber"],
                                    "fax": l["shipfaxnumber"],
                                    "zip": l["shippostalcode"],
                                    "parent_id": related_co.id,
                                    "type": "delivery",
                                }
                                city = l["shipcity"]
                                if l["shipcountry"]:
                                    country_id = company.env["res.country"].search(
                                        [("name", "ilike", l["shipcountry"])], limit=1
                                    )
                                    if not country_id:
                                        extra_loc_string = "%s %s" % (
                                            l["shipcountry"],
                                            extra_loc_string,
                                        )
                                if l["shipstate"]:
                                    if country_id:
                                        state_id = company.env[
                                            "res.country.state"
                                        ].search(
                                            [
                                                ("code", "=", l["shipstate"]),
                                                ("country_id", "=", country_id.id),
                                            ],
                                            limit=1,
                                        )
                                    else:
                                        state_id = company.env[
                                            "res.country.state"
                                        ].search(
                                            [
                                                ("code", "=", l["shipstate"]),
                                                (
                                                    "country_id",
                                                    "=",
                                                    company.env.ref("base.us").id,
                                                ),
                                            ],
                                            limit=1,
                                        )
                                    if not state_id:
                                        extra_loc_string = "%s%s" % (
                                            l["shipstate"],
                                            extra_loc_string,
                                        )
                                if len(extra_loc_string) > 0:
                                    city = "%s %s" % (city, extra_loc_string)
                                partner_shipping_id_dict.update({"city": city})
                                if state_id:
                                    partner_shipping_id_dict.update(
                                        {"state_id": state_id.id}
                                    )
                                if country_id:
                                    partner_shipping_id_dict.update(
                                        {"country_id": country_id.id}
                                    )
                                partner_shipping_id = company.env["res.partner"].create(
                                    partner_shipping_id_dict
                                )
                        if not partner_shipping_id:
                            partner_shipping_id = partner_id
                        _logger.info(
                            "Odoo res.partner %s selected for delivery"
                            % (partner_shipping_id.id)
                        )
                        # Finding Delivery Method
                        carrier_id = False
                        carrier_id = company.env["delivery.carrier"].search(
                            [("shippingmethodid", "=", l["shippingmethodid"])]
                        )
                        if not carrier_id:
                            carrier_id = company.env.ref(
                                "base_p4h.unmapped_delivery_carrier"
                            )
                        _logger.info(
                            "Odoo delivery.carrier %s selected for shipping method"
                            % (carrier_id.id)
                        )
                        order_dict = {
                            "name": l["orderid"],
                            "partner_id": partner_id.id,
                            "partner_shipping_id": partner_shipping_id.id,
                            "carrier_id": carrier_id.id,
                            "client_order_ref": l["ponum"],
                            "origin": "VOLUSION %s" % (l["order_entry_system"]),
                            "note": "%s\n%s\n%s"
                            % (l["shipdate"], l["order_comments"], l["ordernotes"]),
                            "date_order": l["orderdate"],
                            "shipdate": l["shipdate"],
                            "shipresidential": True
                            if l["shipresidential"] == "Y"
                            else False,
                        }
                        if company.order_default_team:
                            order_dict.update(
                                {"team_id": company.order_default_team.id}
                            )
                        order_id = company.env["sale.order"].create(order_dict)
                        orders_processed |= order_id

                        # Creating Shipping Line
                        deliver_line_dict = {
                            "product_id": carrier_id.product_id.id,
                            "name": l["shippingmethod"],
                            "product_uom_qty": 1,
                            "price_unit": l["totalshippingcost"],
                            "order_id": order_id.id,
                            "tax_id": False,
                        }
                        company.env["sale.order.line"].create(deliver_line_dict)

                        # Creating Payment Transaction
                        tx_ref = "%s\n%s\n%s\n%s" % (
                            l["paymentmethod"],
                            l["pay_details"],
                            l["pay_result"],
                            l["creditcardauthorizationnumber"],
                        )
                        if l["creditcardtransactionid"]:
                            tx_ref = "%s\n%s" % (tx_ref, l["creditcardtransactionid"])
                        payment_tx_dict = {
                            "acquirer_id": company.env.ref(
                                "payment.payment_acquirer_custom"
                            ).id,  # later l['paymentmethodid']
                            "amount": float(l["paymentamount"]),
                            "currency_id": order_id.currency_id.id,
                            "partner_country_id": partner_id.country_id.id,
                            "partner_id": partner_id.id,
                            "reference": l["pay_orderid"],
                            "date": l["pay_authdate"],
                            "state_message": tx_ref,
                            "state": "done",  # pending
                            "type": "form",
                            "sale_order_ids": [(6, 0, [order_id.id])],
                        }
                        payment_id = company.env["payment.transaction"].create(
                            payment_tx_dict
                        )
                        payments_processed |= payment_id

                    # Creating the line

                    # Set the product for the line
                    product_id = company.env["product.product"].search(
                        [("default_code", "ilike", l["productcode"])], limit=1
                    )

                    if not product_id:
                        product_id = company.order_default_product
                    _logger.info(
                        "Odoo product.product %s selected for order line."
                        % (product_id.id)
                    )

                    # Set the name for the line
                    try:
                        # Strip HTML from line name
                        s = MLstripper()
                        s.feed(l["productname"])
                        line_name = s.get_data()
                    except Exception as e:
                        _logger.error(e)
                        line_name = l["productname"]

                    # Set the tax for the line
                    tax_rate = round(float(l["salestaxrate1"]) * 100, 2)
                    tax_id = company.env["account.tax"].search(
                        [("type_tax_use", "=", "sale"), ("amount", "=", tax_rate)],
                        limit=1,
                    )

                    if not tax_id:
                        _logger.info(
                            "Creating a new sales tax for rate %s" % (tax_rate)
                        )
                        tax_id = company.env["account.tax"].create(
                            {
                                "name": "Tax %s%s" % (tax_rate, "%"),
                                "description": "%s%s" % (tax_rate, "%"),
                                "type_tax_use": "sale",
                                "amount_type": "percent",
                                "amount": tax_rate,
                                "tax_group_id": company.env.ref(
                                    "account.tax_group_taxes"
                                ).id,
                            }
                        )
                    _logger.info(
                        "Odoo account.tax %s selected for order line." % (tax_id.id)
                    )

                    order_line_dict = {
                        "product_id": product_id.id,
                        "name": line_name,
                        "product_uom_qty": float(l["quantity"]),
                        "price_unit": float(l["productprice"]),
                        "tax_id": [(6, 0, [tax_id.id])],
                        "order_id": order_id.id,
                    }
                    company.env["sale.order.line"].create(order_line_dict)

                for payment in payments_processed:
                    payment._post_process_after_done()
                os.remove(name)
                session.rename("%s%s" % (path, name), "%s%s" % (endpath, name))

    @api.model
    def run_cron_image_creation(self):
        for company in self.env["res.company"].search([]):
            _logger.info("Running Image Creation Cron for %s" % company.name)
            if (
                not company.image_ftp_address
                and not company.image_ftp_user
                and not company.image_ftp_password
                and not company.image_ftp_port
                and not company.image_ftp_folder
            ):
                _logger.warning("FTP configuration not properly set, skipping company.")
                continue

            ip = company.image_ftp_address
            port = int(company.image_ftp_port)
            user = company.image_ftp_user
            pwd = company.image_ftp_password
            path = company.image_ftp_folder
            last_update = company.image_ftp_last_update

            # Intial FTP configuration
            session = ftplib.FTP()
            session.connect(ip, port)
            session.login(user, pwd)
            path = re.sub("([/]{2,5})+", "/", path)
            _logger.info("FTP path: %s%s" % (ip, path))
            session.cwd(path)

            # Looping through directories
            dir_list = []
            names = session.dir(dir_list.append)
            for line in dir_list:
                try:
                    words = line.split()
                    prod_code = words[8]
                    t = words[7].split(":")
                    ts = (
                        words[5]
                        + "-"
                        + words[6]
                        + "-"
                        + datetime.datetime.now().strftime("%Y")
                        + " "
                        + t[0]
                        + ":"
                        + t[1]
                    )
                    last_mod_directory = datetime.datetime.strptime(
                        ts, "%b-%d-%Y %H:%M"
                    )
                except Exception as e:
                    _logger.error("Error while parsing directory %s" % (line))
                    _logger.error(e)
                    continue

                # Check if there has been an update and a product exists
                if not last_update or (last_mod_directory > last_update):
                    prod = company.env["product.template"].search(
                        [("default_code", "=", prod_code)], limit=1
                    )
                    if prod:
                        session.cwd("%s%s" % (path, prod_code))
                        names = session.nlst()
                        _logger.info("Creating images for %s" % (prod_code))
                        # Loop through the files, check if they have been modidied and then move on
                        for name in names:
                            try:
                                time = session.voidcmd("MDTM " + name)[4:].strip()
                                time = parser.parse(time)
                                if not last_update or (time > last_update):
                                    session.retrbinary(
                                        "RETR " + name, open(name, "wb").write
                                    )
                                    with open(name, "rb") as inf:
                                        data = inf.read()
                                    data = base64.b64encode(data)
                                    company.env["product.image"].create(
                                        {
                                            "image": data,
                                            "name": name,
                                            "product_tmpl_id": prod.id,
                                        }
                                    )
                                    os.remove(name)
                            except Exception as e:
                                _logger.error(
                                    "Error while creating image for %s" % (name)
                                )
                                _logger.error(e)
                                continue

            session.quit()
            company.image_ftp_last_update = datetime.datetime.now()
