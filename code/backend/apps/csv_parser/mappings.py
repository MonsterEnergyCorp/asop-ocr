"""
CSV PO template configuration.

The parser code (csv_parse_handler.py) contains NO template specific text. Everything that
differs between CSV templates lives here, in CSV_TEMPLATES - the same idea as html_parser/mappings.py.
To support another CSV template, add one entry to CSV_TEMPLATES (no code change).

HOW A TEMPLATE IS PICKED
  A template is selected when ALL of its "markers" (header names of the CSV) are found.
  Header names are compared ignoring case, accents, spaces and anything in brackets, so
  "TIPO (33: Factura electronica)" is read as TIPO. Templates are tried in the order listed, so put a
  more specific template BEFORE a more general one. If nothing matches, the file is treated as
  unreadable and goes to ERP with Status 52 (set DEFAULT_TEMPLATE to a template name only if one
  template should be tried on every file).

TEMPLATE KEYS
  markers        header names that identify the template (all must be present)
  add_field1     optional, ERP key of the payload (AddField1), default ADD_FIELD1
  date_formats   optional, overrides DEFAULT_DATE_FORMATS (e.g. to read 03/04/2026 as month-first)
  columns        {logical name: [header names]} - the first header name found is used.
                 A logical column the template does not list is left empty, except the ones in
                 REQUIRED_COLUMNS, which fail the file.
  csv_no         logical columns joined with ";" to build CsvNO
  sold_to        logical columns joined with ";" to build SoldTo
  ship_city      logical columns; the first one with a value is used as ShipCity
  ship_to        logical columns; the first one with a value is used as ShipTo
"""

ASOP_NO = "0000000000"
OCR_ITEM_NO_START = 10
ADD_FIELD1 = "MASSCREATION"
DEFAULT_MIME_TYPE = "text/csv"

# Candidate delimiters; the one that splits the header row into the most columns is used.
CSV_DELIMITERS = ";,\t|"

# Same convention as the other parsers: a file that cannot be read is sent to ERP with Status 52
# and its metadata (which carries the email) under the key UNEXTRACTED.
UNEXTRACTED_PO = "UNEXTRACTED"
FAILURE_STATUS = "52"

DEFAULT_DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%m/%d/%Y")

# Logical columns a template must provide and that must have data in the file, else the file fails.
REQUIRED_COLUMNS = frozenset({
    "tipo", "folio", "secuencia", "fecha", "company", "business_activity", "sold_city",
    "sold_address", "description", "quantity", "material", "uom",
})

DEFAULT_TEMPLATE = None

CSV_TEMPLATES = {
    # LATAM mass creation file (SII "Cargas Masivas" layout). Used by the Loginsa and Ecsa files.
    "LATAM_MASS_CREATION": {
        "markers": ["TIPO", "FOLIO", "SECUENCIA", "RAZONSOCIAL", "CODITEM", "UNIDADMEDIDA"],
        "columns": {
            "tipo": ["TIPO"],
            "folio": ["FOLIO"],
            "secuencia": ["SECUENCIA", "SEQUENCE"],
            "fecha": ["FECHA", "DLVDATE", "RDD"],
            "po": ["RUT", "CUSTPO", "PONUMBER"],
            "company": ["RAZONSOCIAL", "RAZON SOCIAL"],
            "business_activity": ["GIRO"],
            "sold_city": ["COMUNA"],
            "sold_address": ["DIRECCION"],
            "description": ["PRODUCTO", "MATDESC", "DESCRIPTION"],
            "quantity": ["CANTIDAD", "QUANTITY"],
            "material": ["CODITEM", "MATERIAL", "MATERIALCODE"],
            "uom": ["UNIDADMEDIDA", "UOM"],
            "dest_city": ["COMUNADESTINO", "SHIPCITY"],
            "dest_city_alt": ["CIUDADDESTINO", "CITYDESTINO"],
            "dest_address": ["DIRECCIONDESTINO", "SHIPTO", "DIRECCIONDESPACHO"],
        },
        "csv_no": ["tipo", "folio", "secuencia"],
        "sold_to": ["company", "business_activity", "sold_city", "sold_address"],
        "ship_city": ["dest_city", "dest_city_alt"],
        "ship_to": ["dest_address"],
    },
}
