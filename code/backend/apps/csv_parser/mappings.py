ASOP_NO = "0000000000"
OCR_ITEM_NO_START = 10
REGION = "LATAM"
PODOCTYPE = "CSV"

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
    "tdb": ["AFECTO", "TDB"],
    "description": ["PRODUCTO", "MATDESC", "DESCRIPTION"],
    "quantity": ["CANTIDAD", "QUANTITY"],
    "material": ["CODITEM", "MATERIAL", "MATERIALCODE"],
    "uom": ["UNIDADMEDIDA", "UOM"],
    "ship_city": ["COMUNADESTINO", "SHIPCITY"],
    "destination_city": ["CIUDADDESTINO", "CITYDESTINO"],
    "ship_to": ["DIRECCIONDESTINO", "SHIPTO", "DIRECCIONDESPACHO"]
}

OPTIONAL_COLUMNS = {"ship_city", "destination_city", "ship_to"}

HEADER_OUTPUT_FIELDS = [
    "Identifier for ASOP / Sales Order combination",
    "DlvDate",
    "CustPo",
    "Soldto",
    "TDB (Rene to confirm)",
    "MatDesc",
    "Quantity",
    "Material",
    "UoM",
    "ShipCity",
    "ShipTo"
]