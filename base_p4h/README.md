_GFP Solutions LLC Custom Module_

# Base Developments for Parts 4 Heat 

**Author:** GFP Solutions LLC 
**Version:** Odoo 12.0+e (Enterprise Edition)

This issue is a continuation of previous developments done for this client: #1 

## DEVELOPED 

### PRODUCT/INVENTORY
* Image script that retrieves images for parts from a SFTP directory
* Reworked image script to create product image as well on the product.template record if there is not image present
* Relabeled volusion fields on the res.partner record to be relevant after volusion change over (i.e. Procurement Vendor ID)
* Reworked barcode main menu screen so that once the package label is scanned, it opens a picking with the package pre-selected for transfer
* Reworked run procurement.group so that it will select the cheapest of the alternates to satisfy requirement (i.e. reordering rules)
* Added warning message on product template mentioning that the part can be made in-house
* Create new Qty Available (incl. alt) computation to also include the alternate products
* Reworked Qty Available No Res (incl. alt) computation to also include the alternate products
* Create new Qty Forecasted Qty (incl. alt) computation to also include the alternate products
* Create new Qty Incoming (incl. alt) computation to also include the alternate products
* Create new Qty Outgoing  (incl. alt) computation to also include the alternate products
* Reworked product template form view to display new computed qty fields values (replacement of base fields)
* Reworked product template actions to open quants, forecasted qty and availabe for current product and all alternatives
* Added new storage location field on the product template
* Reworked desktop stock picking form to include storage location on transfers that are not outgoing
* Reworked mobile barcode stock picking form to include storage location on transfers that are not outgoing

### SALE 
* Sales Order Volusion --> Odoo EDI Script via SFTP

### PURCHASE 
* Purchase Order Volusion --> Odoo EDI Script via SFTP 

### MANUFACTURING
* Added quantity on hand field on bill of materials
* Added per unit cost on the bill of of materials


## ON GOING DEVELOPMENT 

### PRODUCT/INVENTORY
* True Put-away Strategy employing the m2o storage_location_id field
* QoH Calculation error - still not calculating according to a normal odoo environment

### SALES/ECOMMERCE
* Continue development on alternate selection on the sale order line
* What they searched development: tracking of customers to determine which replacement part they need
