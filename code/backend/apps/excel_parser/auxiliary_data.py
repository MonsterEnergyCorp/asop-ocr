# File handling data mappings, anchor fields and other auxiliary items required for data processing and tranformation
data_dimensions={
    "PODate": "date_type",
    "DlvDate": "date_type",
    "CustPo": "possible_singular",
    "BillTo": "listed",
    "ShipTo": "listed",
    "contactname": "multi",
    "CustPhone": "singular",
    "email": "singular",
    "faxordersto:": "singular",
    "e-mailordersto:": "singular",
    "name:": "multi",
    "city": "multi",
    "SoldTo": "singular",
    "Payer": "singular",
    "IncoTerm": "singular",
    "IncoTerm2": "singular",
    "melplant#": "singular",
    "ordertype": "singular",
    "SalesOrg": "singular",
    "itemcategory": "singular",
    "shippingcondition": "singular",
    "deliverylocation:": "singular",
    "podate:": "singular",
    "state/region": "multi",
    "streetnamenumber": "multi",
    "postalcode": "multi",
    "CostCentre": "singular",
    "InternalOrder": "singular",
    "Shipinst": "possible_singular",
    "ShipStreet": "possible_singular",
    "ShipAddress": "possible_singular",
    "SalesDocType": "singular",
    "SoldToName": "singular",
    "ShippingCond": "singular",
    "ItemCat": "singular",
    "Currency": "singular",
    "Podoctype": "singular"
}

data_mapping = {
    "REQUESTEDDELIVERYDATE": "DlvDate",
    "PO#(required)": "CustPo",
    "BILLTO": "BillTo",
    "SHIPTO": "ShipTo",
    "PRODUCTDESCRIPTION": "MatDesc",
    "OrderCode": "Material",
    "#ofCases": "Quantity",
    "Qty": "Quantity",
    "Product": "Material",
    "NumberofCases": "Quantity",
    "Name:": "Name",
    "City": "City",
    "MELSold-To": "SoldTo",
    "MELShip-To": "ShipTo",
    "MELBill-To": "BillTo",
    "IncoTerm:": "IncoTerm",
    "IncoTerm2:": "IncoTerm2",
    "SalesOrg:": "SalesOrg",
    "MELSKU#": "Material",
    "KitDescription": "MatDesc",
    "Quantity(UNITS)": "Quantity",
    "CustomerPONumber": "CustPo",
    "CustomerPO#": "CustPo",
    "StreetNameNumber": "Street",
    "PostalCode": "Zip",
    "ORDERDATE": "PODate",
    "PODate:": "PODate",
    "CS.": "CasesQuantity",
    "EA.": "EachesQuantity",
    "MATERIAL": "Material",
    "DESCRIPTION": "MatDesc",
    "*REQUESTEDDELIVERYDATE(DeliveredbyMEC)": "DlvDate",
    "*SHIPTO/PICKUPADDRESS": "ShipStreet",
    "ITEM#": "Material",
    "ITEMDESCRIPTION": "MatDesc",
    "MATERIAL#": "Material",
    "SALESORG": "SalesOrg",
    "CASES": "Quantity",
    "OrderDate:": "PODate",
    "(FullTimeRemoteEmployeesOnly)ShippingAddress:": "ShipTo",
    "(NottobeusedforCorporateorRialtoWarehouseemployees)ShippingAddress:": "ShipTo",
    "DELIVERYDATE": "DlvDate",
    "ORDERSUBMITDATE": "PODate",
    "SHIPTO/PICKUP-CONTACT&ADDRESS": "ShipAddress",
    "*COSTCENTER/INTERNALORDER#": "CostCentre",
    "COSTCENTER": "CostCentre",
    "INTERNALORDER#": "InternalOrder",
    "SPECIALDELIVERYINSTRUCTIONS": "Shipinst",
    "Phone:": "CustPhone",
    "RequestedDeliveryDate": "DlvDate",
    "SalesOrganisation": "SalesOrg",
    "SoldtoNumber": "SoldTo",
    "CCEPPONumber": "CustPo",
    "ProductDescription": "MatDesc",
    "MonsterSKU": "Material",
    "CasesOrdered": "Quantity",
    "Shipto": "ShipTo",
    "DeliveryDate": "DlvDate",
    "ORDERSUBMITDATE*": "PODate",
    "ORDERTYPE*": "SalesDocType",
    "SOLDTOCUSTOMER": "SoldToName",
    "SHIPTOADDRESS*": "ShipTo",
    "SOLDTO#": "SoldTo",
    "CUSTOMER#": "SoldTo",
    "PACKAGE": "MatDesc",
    "DELIVERYDATE*": "DlvDate",
    "SoldtoName": "SoldToName",
    "ShippingCondition": "ShippingCond",
    "ItemCategory": "ItemCat",
    "REQDELDATE": "DlvDate",
    "RequestedDeliveryDateDD/MM/YYYY": "DlvDate",
    "RequestedDeliveryDateDD-MM-YYYY": "DlvDate",
    "ORDERTYPE": "SalesDocType",
    'CustomerPO': 'CustPo',
    'CustomerPODate': 'PODate',
    'MaterialNumber': 'Material',
    'Qty': 'Quantity',
    'ITEMNUMBER': 'Material',
    'QUANTITY': 'Quantity',
    "LoopID": "TemplateInd",
    "Amount/Price": "UnitPrice",
    "MELPayer:": "Payer",

    "OrderType": "SalesDocType",  #US ZEM
    "SalesOrg": "SalesOrg",
    "OrderDate": "PODate",
    "Podoctype": "Podoctype",  # a Podoctype label in the file overrides the default
    "Podoctype:": "Podoctype"
}

keys = ['DELIVERYCONTACT-EMAIL*',
 'UNIT/SUITE/APT/BLDG',
 'CASES/PALLET',
 'PACKAGE',
 '*TOTALEACHES/CANS(onlyiforderinglessthanfullcases):',
 'REQUESTEDBY',
 'Product',
 'ORDERSUBMITDATE',
 'PostalCode',
 'ORDERSUBMITDATE*',
 'PACKSIZE',
 'Phone:',
 '*EVENTNAME/SAMPLEREASON',
 'SoldtoNumber',
 'OrderDate:',
 'TypeofProduct',
 'EA.',
 '*PALLETJACKREQUIRED-YESorNO?',
 'CS.',
 'SPECIALDELIVERYINSTRUCTIONS',
 'MELPayer:',
 'REQDELDATE',
 'SOLDTO#',
 'PHONE',
 'MATERIAL#',
 '#ofCases',
 'Name:',
 '*SHIPTO/PICKUPADDRESS',
 'IncoTerm:',
 '*UNIT/SUITE/APT,ETC',
 'DeliveryLocation:',
 'SHIPTO/PICKUP-CONTACT&ADDRESS',
 'KitDescription',
 'Quantity(UNITS)',
 'CustomerPONumber',
 'ITEM#',
 'SALESORG',
 '*LIFTGATEREQUIRED-YESorNO?',
 'StreetNameNumber',
 'MonsterSKU',
 'CUSTOMER#',
 'SoldtoName',
 'REQUESTEDDELIVERYDATE',
 'PO#(required)',
 'MATERIAL',
 'ProductDescription',
 'City',
 'DeliveryDate',
 'CASES',
 'E-MailOrdersTo:',
 'RequestedDeliveryDate',
 'DPSKU#',
 'SOLDTO',
 '*COSTCENTER/INTERNALORDER#',
 'SPECIALDELIVERYINSTRUCTIONS:',
 'SalesOrg:',
 'No.ofLoads',
 'PICKUPDATE*',
 'ItemCategory',
 'EmployeeDept:',
 'ORDERDATE',
 'Qty',
 '*REQUESTEDDELIVERYDATE(DeliveredbyMEC)',
 '*ORDERDATE',
 'Wtw/Pallet',
 '*REQUESTEDPICKUPDATE',
 'PODate:',
 'CasesOrdered',
 'ShippingCondition',
 'ItemCategory',
 'BottlerSKU#',
 'RUSHREQUEST',
 'OrderCode',
 'EmployeeName:',
 'Flavour',
 'REQUESTEDBY*',
 'Shipto',
 'DELIVERDATE',
 '*TOTALCASES:',
 'PRODUCTDESCRIPTION',
 'CSWT',
 'WeekCommencing',
 'DELIVERYDATE*',
 'CONTACTNAME',
 '*RECIPIENTEMAIL',
 'SOLDTOCUSTOMER',
 'Pallets',
 'MELSKU#',
 'Size',
 'Cases/Pallet',
 'BILLTO',
 'ORDERTYPE*',
 'IncoTerm2:',
 '(FullTimeRemoteEmployeesOnly)ShippingAddress:',
 'EACHES',
 'CCEPSKU',
 'MELShip-To',
 'INTERNALORDER#',
 'OrderType',
 'State/Region',
 '(NottobeusedforCorporateorRialtoWarehouseemployees)ShippingAddress:',
 'PICKUPDATE',
 'EMAIL',
 'COSTCENTER',
 'MELBill-To',
 '*REQUESTEDBY',
 'NumberofCases',
 'FaxOrdersTo:',
 'SHIPTO',
 'MELSold-To',
 '*PHONENUMBER',
 'ShiptoLocation',
 'SalesOrganisation',
 'ITEMDESCRIPTION',
 'MELPlant#',
 'DELIVERYDATE',
 'BRAND',
 'CCEPPONumber',
 'OrderWeight',
 'TotalCases',
 'SHIPTOADDRESS*',
 'ORDERTYPE',
 'RequestedDeliveryDateDD/MM/YYYY',
 'RequestedDeliveryDateDD-MM-YYYY',
 'CustomerPO#',
 'Ship-To',
 'Sold-To',
 'DocumentType',
 'CustomerPO',
 'CustomerPODate',
 'Plant',
 'MaterialNumber',
 'Qty',
 'Amount/Price',
 'Department',
 'Email:',
 'Company:',
 'ContactName:',
 'Address:',
 'SalesOrg',
 'ITEMNUMBER',
 'QUANTITY',
 'TOTALPRICE',
 'LoopID',
 'Amount/Price',

 'OrderDate', #ZEM
 'Podoctype',
 'Podoctype:'
 ]

multi_valued = {
    "Product": "multi_valued",
    "Cases/Pallet": "multi_valued",
    "Wtw/Pallet": "multi_valued",
    "NumberofCases": "multi_valued",
    "#ofCases": "multi_valued",
    "CS.": "multi_valued",
    "EA.": "multi_valued",
    "Qty": "multi_valued",
    "CASES": "multi_valued",
    "QUANTITY": "multi_valued"
}

tabular_keys = {
    "EMEA": {"Material": [
        "Material",
        "Quantity",
        "Uom",
        "MatDesc",
        "CustPo",
        "DlvDate",
        "ItemShipTo",
        "ItemSoldTo",
        "ItemDocType",
        "ItemSalesOrg",
        "ItemPODate",
        "TemplateInd",
        "UnitPrice"
    ]},
    "Other": {"Material": [
        "Material",
        "Quantity",
        "Uom",
        "MatDesc",
        "EachesQuantity",
        "CasesQuantity"]}
}

directional_biases = {'EA.': 'below',
 '(FullTimeRemoteEmployeesOnly)ShippingAddress:': 'right',
 '*REQUESTEDDELIVERYDATE(DeliveredbyMEC)': 'below',
 '*SHIPTO/PICKUPADDRESS': 'below',
 '(NottobeusedforCorporateorRialtoWarehouseemployees)ShippingAddress:': 'right',
 '*COSTCENTER/INTERNALORDER#': 'below'}

non_columnar_entry_keys = {'MATERIAL': -1, 'MATERIAL#': -3}

regional_map_lvl1 = {'EMEA': {'Shipto': 'ItemShipTo',
  'Sold-To': 'ItemSoldTo',
  'Ship-To': 'ItemShipTo',
  'DocumentType': 'ItemDocType',
  'SalesOrg': 'ItemSalesOrg',
  'CustomerPODate': 'ItemPODate'}}

regional_map_lvl2 = {'EMEA': {'ItemShipTo': 'ShipTo',
  'ItemSoldTo': 'SoldTo',
  'ItemDocType': 'SalesDocType',
  'ItemSalesOrg': 'SalesOrg',
  'ItemPODate': 'PODate'}}


# ---------------------------------------------------------------------------
# APAC FG PO templates (Macau + China) - parameters only.
# "APAC_FG_PO" is a template profile, not a HANA region: it is switched on only for sheets that
# contain the labels listed in template_region_markers (end of file), whatever region the file
# arrived under. Any other file - including other APAC templates - is processed exactly as before.
# ---------------------------------------------------------------------------

# 1. Labels -> ERP fields (picked up by erp_field_mapping through regional_map_lvl1)
regional_map_lvl1["APAC_FG_PO"] = {
    # Macau FG PO
    "BILLTO:": "BillTo",
    "SHIPTO:": "ShipTo",
    "Soldto": "SoldTo",
    # China FG PO (English + Chinese text in the same cell)
    "ORDERDATE订单日期": "PODate",
    "REQUESTEDDELIVERYDATE要求发货日期": "DlvDate",
    "PO#(required)订单号": "CustPo",
    "SOLDTO#客户号": "SoldTo",
    "BILLTO销售到": "BillTo",
    "SHIPTO运送到": "ShipTo",
    "PRODUCTDESCRIPTION产品描述": "MatDesc",
    "ProductCode产品代码": "Material",
    "#ofCases几个箱": "Quantity",
    "Plant供应源": "Plant",
}

# 2. Extra labels the sheet scan must recognise (also act as stop markers) - only for this region
regional_keys = {
    "APAC_FG_PO": [
        "BILLTO:",
        "SHIPTO:",
        "Soldto",
        "ORDERDATE订单日期",
        "REQUESTEDDELIVERYDATE要求发货日期",
        "PO#(required)订单号",
        "SOLDTO#客户号",
        "BILLTO销售到",
        "SHIPTO运送到",
        "CONTACTNAME联系人",
        "PHONE电话",
        "EMAIL电子邮件",
        "PRODUCTDESCRIPTION产品描述",
        "CO-PACKER提货工厂",
        "Plant供应源",
        "ProductCode产品代码",
        "TypeofProduct产品类型",
        "#ofCases几个箱",
        "NetValue价格",
        "TotalCases总箱",
        "TotalValue(excl.GST)",
        "E-MailOrdersTo发订单到：",
        "CustomerSignature客户签名：",
        "Date日期：",
    ],
}

# 3. Line item columns for this region (existing "Other" columns + Plant)
tabular_keys["APAC_FG_PO"] = {"Material": [*tabular_keys["Other"]["Material"], "Plant"]}

# 4. Behaviour switches read by the handler / post processing (all optional)
#    party_blocks     : BILL TO / SHIP TO block = customer number, then name/address lines (Chinese lines dropped)
#    fill_down_fields : item fields held in one merged cell, copied down to every item row
#    default_uom      : Uom used when the template has no unit column (other regions keep "CS")
#    quantity_thousands: Quantity sent with thousands separators (e.g. 26,000)
#    header_fields    : extra header fields added to the payload
regional_options = {
    "APAC_FG_PO": {
        "party_blocks": True,
        "fill_down_fields": ["Plant"],
        "default_uom": "",
        "quantity_thousands": True,
        "header_fields": {"AsopNo": "0000000000", "Podoctype": "EXCEL", "Region": "APAC"},
    },
    # Chile Andina: the form has no Sold-To, Sales Org or Order Type values, so these stay blank
    "CHILE_ANDINA": {
        "party_blocks": True,  # BillTo/ShipTo = customer number; address lines without it
        "keep_line_spacing": True,  # address text kept as written in the cell
        "header_fields": {"SoldTo": "", "SalesOrg": "", "SalesDocType": ""},
    },
}

# 5. Template recognition. The region on a file comes from the mailbox/blob folder (us / emea / latam),
#    not from the template, so these templates are also recognised by their own labels.
#    A sheet that contains ALL labels of any one list below is processed with that profile's
#    parameters above, whatever region the file arrived under. Other sheets are unaffected.
template_region_markers = {
    "APAC_FG_PO": [
        ["PO#(required)订单号"],                                        # China FG PO
        ["BILLTO:", "SHIPTO:", "Soldto", "OrderType", "SalesOrg"],      # Macau FG PO
    ],
    # Chile Andina FG order form: BILL TO / SHIP TO without colons, no Sold-To label
    "CHILE_ANDINA": [
        ["BILLTO", "SHIPTO", "TypeofProduct", "Cases/Pallet"],
    ],
}

# ---------------------------------------------------------------------------
# Cambodia KIT order form (Monster Energy Concentrate Order Form) - parameters only.
# The layout is the same for every order; only the values change. Recognised by its own labels
# (MEC SKU#, MEC Sold-To, ...), so other sheets are processed exactly as before.
# ---------------------------------------------------------------------------
CAMBODIA_KIT = "CAMBODIA_KIT_ORDER"

# Labels (spaces removed) -> ERP fields
regional_map_lvl1[CAMBODIA_KIT] = {
    "MECSKU#": "Material",
    "SKUDescription": "MatDesc",
    "RequestedDeliveryDateMM/DD/YYYY": "DlvDate",
    "MECSold-To": "SoldTo",
    "MECBill-To": "BillTo",
    "MECShip-To": "ShipTo",
    "OrderType:": "SalesDocType",
    "ItemCategory:": "ItemCat",
    "ShippingCondition:": "ShippingCond",
    "Currency:": "Currency",
}

# Extra labels the sheet scan must recognise (also act as stop markers) - only for this template
regional_keys[CAMBODIA_KIT] = [
    "MECSKU#",
    "SKUDescription",
    "RequestedDeliveryDateMM/DD/YYYY",
    "MECSold-To",
    "MECBill-To",
    "MECShip-To",
    "MECPayer:",
    "OrderType:",
    "ItemCategory:",
    "ShippingCondition:",
    "Currency:",
    "Ship-ToAddress:",
]

# Line item columns: existing "Other" columns + delivery date and customer PO (PO is then taken from the lines)
tabular_keys[CAMBODIA_KIT] = {"Material": [*tabular_keys["Other"]["Material"], "DlvDate", "CustPo"]}

# Template recognition by its own labels
template_region_markers[CAMBODIA_KIT] = [
    ["MECSKU#", "MECSold-To", "MECShip-To", "MECBill-To"],
]

regional_options[CAMBODIA_KIT] = {
    "party_blocks": True,                     # MEC Ship-To / Bill-To: customer number only
    "default_uom": "",                        # the form has no unit column
    "tabular_date_fields": ["DlvDate"],       # Excel dates -> YYYY-MM-DD
    "split_inco_term": True,                  # "CIF Sihanoukvile" -> IncoTerm "CIF", IncoTerm2 "Sihanoukvile"
    "address_block": {                        # Ship-To name and address: the cells to the right of the label
        "label": "Ship-ToAddress:",
        "name_field": "ShipName",
        "address_field": "ShipAddress",
    },
}

# ---------------------------------------------------------------------------
# POS ASOP mass order - flat table: one row per line item, column names in the header row.
# Recognised by its own column names, so other sheets are processed exactly as before.
# The output field list and the column names are configuration, not code.
# ---------------------------------------------------------------------------
POS_ASOP = "POS_ASOP_MASS_ORDER"

template_region_markers[POS_ASOP] = [
    ["ShiptoName", "ShipToStreet", "Material#", "SalesUnitofMeasure"],
]

regional_options[POS_ASOP] = {
    "flat_table": True,
    "region": "EMEA",
    "podoctype": "EXCEL",
    "asop_no": "0000000000",
    "record_fields": {"AddField1": "MASSPOSALL"},      # template indicator, set on the header
    "date_fields": ["PODate", "DlvDate"],
    # column name (see label_key in the handler) -> ERP field
    "flat_columns": {
        "ordertype": "SalesDocType",
        "soldto": "SoldTo",
        "shipto": "ShipTo",
        "payer": "Payer",
        "sales": "SalesOrg",
        "distr": "DistChannel",
        "div": "Division",
        "po": "CustPo",
        "podate": "PODate",
        "shiptoname": "ShipName",
        "shiptostreet": "ShipStreet",
        "shiptohousenum2": "ShipHouse",
        "shiptostreet2": "ShipStreet2",
        "shiptocity": "ShipCity",
        "shiptostate": "ShipState",
        "shiptozip": "ShipZip",
        "shiptoctry": "ShipCountry",
        "shippinginstructions": "ShipInst",
        "requestdeliverydate": "DlvDate",
        "shippingcondition": "ShippingCond",
        "incoterms1": "IncoTerm",
        "material#": "Material",
        "qty": "Quantity",
        "salesunitofmeasure": "Uom",
        "price": "UnitPrice",
        "currency": "Currency",
        "plant": "Plant",
        "internalorder": "InternalOrder",
        "costcenter": "CostCenter",
        "itemcategory": "ItmCat",
    },
    # every field of a line item, in the order of the response; a field not in the file stays ""
    "item_fields": [
        "AsopNo", "OCRItemno", "Material", "MaterialCC", "MatDesc", "Quantity", "QuantityCC", "Uom",
        "UnitPrice", "ExtPrice", "DlvDate", "Plant", "ItmCat", "IncoTerm", "ShippingCond",
        "AddField1", "AddField2", "AddField3", "AddField4", "AddField5", "Size", "Pallet", "CustPo",
        "ShipTo", "SapPriceInd", "SalesDocType", "SalesOrg", "SoldTo", "PODate", "TemplateInd",
        "POSTotalCost", "MatTextInd", "ShipCity", "Payer", "DistChannel", "Division", "ShipName",
        "ShipStreet", "ShipHouse", "ShipStreet2", "ShipState", "ShipZip", "ShipCountry", "ShipInst",
        "Currency", "InternalOrder", "CostCenter", "POItemNo",
    ],
}

# ---------------------------------------------------------------------------
# POS ASOP mass order - Brazil flat table. Recognised by its own labels (labels are matched with spaces and
# line breaks removed). Its header carries the template indicator AddField1 = MASSPOSBRAZIL.
# ---------------------------------------------------------------------------
POS_ASOP_BRAZIL = "POS_ASOP_MASS_ORDER_BRAZIL"

template_region_markers[POS_ASOP_BRAZIL] = [
    ["GVS_TC_DATA-REC-PARVW(01)", "Taxlaw:ICMS(*)"],
]

regional_options[POS_ASOP_BRAZIL] = {
    "flat_table": True,
    "region": "EMEA",
    "podoctype": "EXCEL",
    "asop_no": "0000000000",
    "record_fields": {"AddField1": "MASSPOSBRAZIL"},   # template indicator, set on the header, not on items
    "one_record_per_sheet": True,                      # all rows of the sheet are line items of one record
    "date_fields": ["PODate", "DlvDate"],
    "excel_serial_dates": True,                        # Request Delivery Date is stored as an Excel serial number
    "price_order_types": ["ZORP"],                     # UnitPrice is only sent for ZORP orders
    "item_defaults": {"ItmCat": "ZBAS", "IncoTerm": "CIF"},  # used when the file leaves these blank
    # column name (see label_key in the handler) -> ERP field
    "flat_columns": {
        "ordertype": "SalesDocType",
        "soldto": "SoldTo",
        "shipto": "ShipTo",
        "sales": "SalesOrg",
        "distr": "DistChannel",
        "div": "Division",
        "po": "CustPo",
        "podate": "PODate",
        "requestdeliverydate": "DlvDate",
        "shippingcondition": "ShippingCond",
        "incoterms1": "IncoTerm",
        "material#": "Material",
        "qty": "Quantity",
        "salesunitofmeasure": "Uom",
        "price": "UnitPrice",
        "plant": "Plant",
        "internalorder": "InternalOrder",
        "costcenter": "CostCenter",
        "itemcategory": "ItmCat",
        "sdtaxcode": "SDTaxCode",
        "cfopcodeandextension": "CFOPCode",
        "taxlawicms": "TaxLawICMS",
        "taxlawipi": "TaxLawIPI",
        "isstaxlaw": "ISSTaxLaw",
        "cofinstaxlaw": "COFINSTaxLaw",
        "pistaxlaw": "PISTaxLaw",
        "mainassetnumber": "AssetNumber",
        "serialnumberx000d": "SerialNumber",
    },
    # every field of a line item, in the order of the response; a field not in the file stays ""
    "item_fields": [
        "AsopNo", "OCRItemno", "Material", "MaterialCC", "MatDesc", "Quantity", "QuantityCC", "Uom",
        "UnitPrice", "ExtPrice", "DlvDate", "Plant", "ItmCat", "IncoTerm", "ShippingCond",
        "AddField1", "AddField2", "AddField3", "AddField4", "AddField5", "Size", "Pallet", "CustPo",
        "ShipTo", "SapPriceInd", "SalesDocType", "SalesOrg", "SoldTo", "PODate", "DistChannel", "Division",
        "InternalOrder", "CostCenter", "CFOPCode", "TaxLawICMS", "TaxLawIPI", "ISSTaxLaw", "COFINSTaxLaw",
        "PISTaxLaw", "AssetNumber", "SerialNumber", "SDTaxCode", "POItemNo",
    ],
}

# Podoctype for every Excel form that does not set its own (a profile can set its own value in its header_fields).
DEFAULT_PODOCTYPE = "EXCEL"
