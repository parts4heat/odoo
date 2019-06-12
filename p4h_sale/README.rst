================
P4H Sale
================

Sales & Procurement functionality.
----------------------------------

* Always buy from the cheapest Vendor on a Product

* Manufacturer Lookup on Vendors

* Allow an alternate product to be stored on an order line

* Identify the MIF file used to create a Product Attribute and Product Attribute Value

* Dropship pricing and discounts on Vendor Pricelists

* Exploded Views stored on Models

* Name and Date of each MIF stored and available in Master Data --> Sources Menu

* Model Parts hold a specific part on a specific model

* Model Parts can open the Model parts PDF


Automated Actions:
------------------

* Reorder Vendors on Product based on Vendor Pricelist - cheapest product always the first in the list


Modified Models: 
----------------

* Partners - Manufacturer Lookup 

* Sale Order Lines - Ordered (Product is now the fulfullment product) 

* Products - TBD

* Product Attributes - MIF Source added 

* Product Attribute Values - MIF Source added

* Vendor Pricelists - Drop Shop Cost and Sales Prices, Discount Multiplers, Max Quantities


New Models: 
-----------

* Exploded View - to hold images of Models - Menu via Inventory --> Master Data --> Sources 

* MIF Files - to hold a record of the import - Menu via Inventory --> Master Data --> Sources 

* Model Parts - to hold a record of a specific part listed on a specific Model

* Product Attribute Lines - TBD


Security: 
---------

* Internal Users can read, create, change and delete Product Alternatives, Exploded Views and Model Parts.

* Website Visitors can read Exploded Views and Model Parts.
