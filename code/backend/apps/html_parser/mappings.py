"""
HTML PO template configuration.

The parser code (html_parse_handler.py) contains NO template specific text. Everything that
differs between HTML templates lives here, in HTML_TEMPLATES - the same idea as the Excel parser's
auxiliary_data.py. To support another HTML template, add one entry to HTML_TEMPLATES (no code change).

HOW A TEMPLATE IS PICKED
  A template is selected when ALL of its "markers" (labels that appear in the page text, any case)
  are found. Templates are tried in the order listed, so put a more specific template BEFORE a more
  general one. If nothing matches, the file is treated as unreadable and goes to ERP with Status 52
  (set DEFAULT_TEMPLATE to a template name only if some template should be tried on every file).

TEMPLATE KEYS
  markers          list of labels that identify the template
  date_languages   languages (keys of MONTH_NAMES) used to read dates such as 30/Junio/2026
  date_formats     optional, overrides DEFAULT_DATE_FORMATS (e.g. to read 03/04/2026 as month-first)
  region           optional, used only when the file has no region of its own (the region of the file
                   comes from the mailbox folder and is stored in HANA, it is not part of the template)
  podoctype        optional, overrides PODOCTYPE
  header_fields    list of rules, applied in order; each rule fills one ERP header field:
        {"field": "CustPo", "rule": "regex",   "pattern": r"...(group 1 is the value)...", "default": "..."}
        {"field": "SalesOrg", "rule": "between", "start": "Label", "end": "Next label"}
        {"rule": "block", "start": "Label", "end": "Next label", "fields": {"SoldTo": "first", "ShipTo": "rest"}}
      add  "date": True  to a regex/between rule to convert the value to YYYY-MM-DD.
      "block" splits the text under a label on its <br> line breaks:
        "first" = first line, "rest" = remaining lines joined, "all" = every line, or a line number.
  items            how the line item table is read:
        header_markers      normalized words (A-Z, 0-9) that must all appear in the table's first row
        min_columns         rows with fewer cells are skipped
        columns             {ERP field: column number}  (first column = 0)
        description_column  column that holds the code + description text
        split_description   {"pattern": regex with 2 groups, "code_field": "Material", "text_field": "MatDesc"}
"""

ASOP_NO = "0000000000"
OCR_ITEM_NO_START = 10
REGION = ""  # last-resort region when neither the file nor the template has one
PODOCTYPE = "HTML"

# Normalized markers identify the line-item and totals tables in the HTML template.
ITEM_HEADER_MARKERS = ("CANTIDAD", "UNIDAD", "DESCRIPC", "PRECIO", "IMPORTE")

# ERP header and line item fields. The response always carries every one of these, set to "" when
# the template does not fill it, so the shape is the same for every HTML template. A template fills a
# header field with a header_fields rule and a line item field with an items columns entry - no code change.
OUTPUT_HEADER_FIELDS = (
    "AsopNo", "ShipRegion", "BillRegion", "Docnum", "SalesOrgCc", "Payer", "DocDate", "DlvDate",
    "Vbeln", "TotalEach", "TotalCase", "Text", "Status", "SoStatus", "SoldZip", "SoldToName",
    "SoldToCc", "SoldTo", "SoldStreet", "SoldRegion", "SoldCity", "ShipZip", "ShipToRegion",
    "ShipToCountry", "ShipToCc", "ShipTo", "ShipStreet", "ShippingCond", "ShipName", "Shipinst",
    "ShipCity", "ShipAddress", "SenderEmail", "SearchTerm", "SapAmount", "SalesZip", "SalesStreet",
    "SalesOrg", "SalesName", "SalesDocType", "SalesCity", "SalesAddress", "Region", "Regio",
    "Podoctype", "PODate", "PayTerm", "OrderReason", "OrderCode", "NewShipToAdd", "ItemCat",
    "InternalOrder", "IncoTerm2", "IncoTerm", "Freight", "ErrorFlag", "DlvLocation", "DlvBlock",
    "DistChan", "CustPoCc", "CustPo", "CustPhone", "CustEmail", "Currency", "CountryTemplate",
    "CostCentre", "ContactName", "ContactAddress", "Consignee", "CommentS", "CarrierInst", "Bsark",
    "Brand", "BillZip", "BillTo", "BillStreet", "BillName", "BillCity", "BillAddress", "Amount",
    "Agent", "AddField5", "AddField4", "AddField3", "AddField2", "AddField1",
)

OUTPUT_ITEM_FIELDS = (
    "AsopNo", "OCRItemno", "Material", "MaterialCC", "MatDesc", "Quantity", "QuantityCC", "Uom",
    "UnitPrice", "ExtPrice", "DlvDate", "Plant", "ItmCat", "AddField1", "AddField2", "AddField3",
    "AddField4", "AddField5", "Size1", "Pallet", "CustPo", "ShipTo", "SapPriceInd", "SalesDocType",
    "SalesOrg", "SoldTo", "PODate", "TemplateInd", "POSTotalCost", "MatTextInd", "CustPOSuffix",
    "POItemNo", "IncoTerm", "IncoTerm2", "ShippingCond",
)

# Same convention as the Excel parser: a file that cannot be read is sent to ERP with Status 52
# and its metadata (which carries the email) under the key UNEXTRACTED.
UNEXTRACTED_PO = "UNEXTRACTED"
FAILURE_STATUS = "52"

DEFAULT_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y")

# Month names, lower case without accents. Add a language here to read dates like 30/Junio/2026.
MONTH_NAMES = {
    "es": {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    },
}

DEFAULT_TEMPLATE = None

HTML_TEMPLATES = {
    # LATAM purchase order (Spanish) - Bepensa Dominicana
    "LATAM_PO_ES": {
        "markers": ["Orden de compra"],
        "region": "LATAM",
        "date_languages": ["es"],
        "header_fields": [
            {"field": "CustPo", "rule": "regex",
             "pattern": r"Orden de compra\s*:?\s*([A-Z0-9-]+)", "default": UNEXTRACTED_PO},
            {"field": "PODate", "rule": "regex",
             "pattern": r"Fecha Orden Compra\s*:?\s*(.*?)(?=\s+Proveedor\s*:)", "date": True},
            {"field": "DlvDate", "rule": "between",
             "start": "Fecha Promesa", "end": "Facturar a", "date": True},
            {"field": "SalesOrg", "rule": "between",
             "start": "Proveedor", "end": "Vendedor"},
            # "Facturar a": first line = customer name (SoldTo), remaining lines = address (ShipTo)
            {"rule": "block", "start": "Facturar a", "end": "Consignar a",
             "fields": {"SoldTo": "first", "ShipTo": "rest"}},
        ],
        "items": {
            "header_markers": ITEM_HEADER_MARKERS,
            "min_columns": 5,
            "columns": {"Quantity": 0, "Uom": 1},
            "description_column": 2,
            "split_description": {"pattern": r"([A-Z0-9-]+)\s+(.*)",
                                  "code_field": "Material", "text_field": "MatDesc"},
        },
    },
}