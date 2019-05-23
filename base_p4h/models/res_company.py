# -*- coding: utf-8 -*-
import stat
import os
import re
import csv
import json
import datetime
import ftplib
import logging
import base64
import paramiko
from html.parser import HTMLParser

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
    image_ftp_type = fields.Selection(
        [("ftp", "FTP"), ("sftp", "SFTP")], string="Image FTP Type", default="ftp"
    )
    order_ftp_address = fields.Char(string="Order FTP Address")
    order_ftp_user = fields.Char(string="Order FTP User")
    order_ftp_password = fields.Char(string="Order FTP Password")
    order_ftp_port = fields.Char(string="Order FTP Port")
    order_ftp_folder = fields.Char(string="New Order FTP Folder")
    order_done_ftp_folder = fields.Char(string="Processed Order FTP Folder")
    order_ftp_type = fields.Selection(
        [("ftp", "FTP"), ("sftp", "SFTP")], string="Order FTP Type", default="ftp"
    )
    order_default_team = fields.Many2one("crm.team", string="Order Default Team")
    order_default_product = fields.Many2one(
        "product.product", string="Order Default Product"
    )
    order_default_credit_product = fields.Many2one(
        "product.product", string="Order Default Credit Product"
    )

    def _sftp_helper(self, sftp, files, last_update):
        stats = sftp.listdir_attr(".")
        prod_passing = ""
        prod_passing_id = 0
        for attr in stats:
            if datetime.datetime.fromtimestamp(attr.st_mtime) > last_update:
                if stat.S_ISDIR(attr.st_mode):  # If the file is a directory, recurse it
                    sftp.chdir(attr.filename)
                    self._sftp_helper(sftp, files, last_update)
                    sftp.chdir("..")
                else:
                    file_name = attr.filename
                    prod_image = self.env["product.image"].search(
                        [("name", "=", file_name)], limit=1
                    )
                    if prod_image:
                        continue
                    parsed_file_name = file_name.split(".")
                    prod_code = parsed_file_name[0].split("_")[0]
                    if prod_code != prod_passing:
                        prod = self.env["product.template"].search(
                            [("default_code", "=", prod_code)], limit=1
                        )
                        prod_passing = prod_code
                        prod_passing_id = prod.id

                    if prod:
                        try:
                            _logger.info("Creating image for %s" % (file_name))
                            data = sftp.open(file_name).read()
                            data = base64.b64encode(data)
                            self.env["product.image"].create(
                                {
                                    "image": data,
                                    "name": file_name,
                                    "product_tmpl_id": prod_passing_id,
                                }
                            )
                            sftp.utime(file_name, None)
                        except Exception as e:
                            _logger.error(
                                "Error while creating image for %s" % (file_name)
                            )
                            _logger.error(e)
                            continue

    def filelist_recursive(company, sftp, last_update):
        files = {}
        company._sftp_helper(sftp, files, last_update)
        return files

    @api.model
    def run_cron_order_processing(self):
        for company in self.env["res.company"].search([]):
            _logger.info("Running Order Processing Cron for %s" % company.name)
            if (
                not company.order_ftp_address
                or not company.order_ftp_user
                or not company.order_ftp_password
                or not company.order_ftp_port
                or not company.order_ftp_folder
                or not company.order_done_ftp_folder
                or not company.order_default_product
                or not company.order_default_credit_product
                or not company.order_ftp_type
            ):
                _logger.warning(
                    "(S)FTP configuration not properly set, skipping company."
                )
                continue

            ip = company.order_ftp_address
            port = int(company.order_ftp_port)
            user = company.order_ftp_user
            pwd = company.order_ftp_password
            path = company.order_ftp_folder
            endpath = company.order_done_ftp_folder
            path = re.sub("([/]{2,5})+", "/", path)
            endpath = re.sub("([/]{2,5})+", "/", endpath)

            # Intial (S)FTP configuration
            if company.order_ftp_type == "sftp":
                transport = paramiko.Transport((ip, port))
                transport.connect(None, user, pwd)
                session = paramiko.SFTPClient.from_transport(transport)
                _logger.info("SFTP path: %s%s" % (ip, path))
                _logger.info("SFTP order processed path: %s%s" % (ip, endpath))
                session.chdir(path)
            else:
                session = ftplib.FTP()
                session.connect(ip, port)
                session.login(user, pwd)
                _logger.info("FTP new order path: %s%s" % (ip, path))
                _logger.info("FTP order processed path: %s%s" % (ip, endpath))
                session.cwd(path)

            if company.image_ftp_type == "sftp":
                names = session.listdir_attr(".")
                names = [k for k in names if ".csv" in k.filename]
            else:
                names = session.nlst()
                names = [k for k in names if ".csv" in k]
            _logger.info("Processing %s file(s)" % (len(names)))
            # Loop through the files and convert them to json dictionaries
            for name in names:
                data = []
                if company.image_ftp_type == "sftp":
                    inf = session.open(name.filename)
                    for row in csv.DictReader(inf):
                        data.append(row)
                else:
                    session.retrbinary("RETR " + name, open(name, "wb").write)
                    with open(name) as inf:
                        for row in csv.DictReader(inf):
                            data.append(row)
                json_data = json.loads(json.dumps(data))
                orders_processed = company.env["sale.order"]
                payments_processed = company.env["payment.transaction"]
                for l in json_data:
                    try:
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

                                    related_co = company.env["res.partner"].search(
                                        [
                                            ("name", "ilike", related_co_name),
                                            ("is_company", "=", True),
                                            ("customer", "=", True),
                                        ],
                                        limit=1,
                                    )
                                    if not related_co:
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
                                        [("name", "ilike", l["billingcountry"])],
                                        limit=1,
                                    )
                                    if not country_id:
                                        extra_loc_string = "%s %s" % (
                                            l["billingcountry"],
                                            extra_loc_string,
                                        )
                                if l["billingstate"]:
                                    if country_id:
                                        state_id = company.env[
                                            "res.country.state"
                                        ].search(
                                            [
                                                ("code", "=", l["billingstate"]),
                                                ("country_id", "=", country_id.id),
                                            ],
                                            limit=1,
                                        )
                                    else:
                                        state_id = company.env[
                                            "res.country.state"
                                        ].search(
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
                                    partner_id_dict.update(
                                        {"country_id": country_id.id}
                                    )
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
                                if partner_id.parent_id:
                                    related_co = partner_id.parent_id
                                else:
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
                                        "Creating delivery with id  %s"
                                        % (l["customerid"])
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
                                            [("name", "ilike", l["shipcountry"])],
                                            limit=1,
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
                                    partner_shipping_id = company.env[
                                        "res.partner"
                                    ].create(partner_shipping_id_dict)
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
                            tx_ref = "%s\n%s\n%s" % (
                                l["paymentmethod"],
                                l["pay_details"],
                                l["creditcardauthorizationnumber"],
                            )
                            if l["creditcardtransactionid"]:
                                tx_ref = "%s\n%s" % (
                                    tx_ref,
                                    l["creditcardtransactionid"],
                                )
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

                        # Check to see if its a CREDIT or VOID
                        reduction = False
                        if l["pay_result"] != "DEBIT":
                            reduction = True
                            product_id = company.order_default_credit_product
                        else:
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

                        # Set CREDIT/VOID/DECLINED/FAILED on line name
                        if reduction:
                            line_name = "%s - %s" % (l["pay_result"], line_name)

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

                        price_unit = float(l["productprice"])
                        # Setting it negative if its a credit, etc
                        if reduction:
                            price_unit = price_unit * -1
                        order_line_dict = {
                            "product_id": product_id.id,
                            "name": line_name,
                            "product_uom_qty": float(l["quantity"]),
                            "price_unit": price_unit,
                            "tax_id": [(6, 0, [tax_id.id])],
                            "order_id": order_id.id,
                        }
                        company.env["sale.order.line"].create(order_line_dict)
                    except Exception as e:
                        _logger.error("Error while creating line for %s" % (l))
                        _logger.error(e)
                        continue

                for payment in payments_processed:
                    payment._post_process_after_done()
                if company.image_ftp_type == "sftp":
                    session.rename(
                        "%s%s" % (path, name.filename),
                        "%s%s" % (endpath, name.filename),
                    )
                else:
                    os.remove(name)
                    session.rename("%s%s" % (path, name), "%s%s" % (endpath, name))

    @api.model
    def run_cron_image_creation(self):
        for company in self.env["res.company"].search([]):
            _logger.info("Running Image Creation Cron for %s" % company.name)
            if (
                not company.image_ftp_address
                or not company.image_ftp_user
                or not company.image_ftp_password
                or not company.image_ftp_port
                or not company.image_ftp_folder
                or not company.image_ftp_type
            ):
                _logger.warning(
                    "(S)FTP configuration not properly set, skipping company."
                )
                continue

            ip = company.image_ftp_address
            port = int(company.image_ftp_port)
            user = company.image_ftp_user
            pwd = company.image_ftp_password
            path = company.image_ftp_folder
            last_update = company.image_ftp_last_update

            # Intial (S)FTP configuration
            if company.image_ftp_type == "sftp":
                transport = paramiko.Transport((ip, port))
                transport.connect(None, user, pwd)
                session = paramiko.SFTPClient.from_transport(transport)
                path = re.sub("([/]{2,5})+", "/", path)
                _logger.info("SFTP path: %s%s" % (ip, path))
                session.chdir(path)
            else:
                session = ftplib.FTP()
                session.connect(ip, port)
                session.login(user, pwd)
                path = re.sub("([/]{2,5})+", "/", path)
                _logger.info("FTP path: %s%s" % (ip, path))
                session.cwd(path)

            # Looping through directories
            company.filelist_recursive(session, last_update)

            session.close()
            company.image_ftp_last_update = datetime.datetime.now()
