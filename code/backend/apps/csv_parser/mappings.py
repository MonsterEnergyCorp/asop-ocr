ASOP_NO = "0000000000"
OCR_ITEM_NO_START = 10
REGION = "LATAM"
PODOCTYPE = "CSV"
ADD_FIELD1 = "MASSCREATION"
CUST_EMAIL = "Amit.Nirala@Monsterenergy.com"
CSV_MIME_TYPE = "application/vnd.ms-excel"

# Aliases allow the parser to accept the descriptive LATAM headers and shorter variants.
COLUMN_ALIASES = {
    "tipo": ["TIPO"],
    "folio": ["FOLIO"],
    "secuencia": ["SECUENCIA", "SEQUENCE"],
    "fecha": ["FECHA", "DLVDATE", "RDD"],
    "po": ["RUT", "CUSTPO", "PONUMBER"],
    "company": ["RAZONSOCIAL", "RAZON SOCIAL"],
    "business_activity": ["GIRO"],
    "sold_city": ["COMUNA"],
    "sold_address": ["DIRECCION", "DIRECCION"],
    "description": ["PRODUCTO", "MATDESC", "DESCRIPTION"],
    "quantity": ["CANTIDAD", "QUANTITY"],
    "material": ["CODITEM", "MATERIAL", "MATERIALCODE"],
    "uom": ["UNIDADMEDIDA", "UOM"],
    "ship_city": ["COMUNADESTINO", "SHIPCITY"],
    "destination_city": ["CIUDADDESTINO", "CITYDESTINO"],
    "ship_to": ["DIRECCIONDESTINO", "SHIPTO", "DIRECCIONDESPACHO"]
}

OPTIONAL_COLUMNS = {"ship_city", "destination_city", "ship_to"}
