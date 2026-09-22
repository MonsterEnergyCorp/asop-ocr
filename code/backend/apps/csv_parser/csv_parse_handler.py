import csv
import io
import json
import mimetypes
import re
import unicodedata
from datetime import datetime

from apps.csv_parser import mappings


def clean_text(value):
    text = "" if value is None else str(value)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" :")


def normalize_header(value):
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def decode_csv_bytes(content):
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            if "\ufffd" not in text:
                return text
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def detect_csv_separator(text):
    try:
        return csv.Sniffer().sniff(text[:8192], delimiters=";,\t|").delimiter
    except csv.Error:
        return ";"


def find_column(fieldnames, aliases, required=True):
    normalized_columns = {normalize_header(column): column for column in fieldnames}
    normalized_aliases = [normalize_header(alias) for alias in aliases]
    for alias in normalized_aliases:
        if alias in normalized_columns:
            return normalized_columns[alias]
    for alias in normalized_aliases:
        for normalized_column, original_column in normalized_columns.items():
            if normalized_column.startswith(alias):
                return original_column
    if required:
        raise ValueError(f"Required column not found. Expected one of: {aliases}")
    return None


def row_value(row, column_name):
    if column_name is None:
        return ""
    return clean_text(row.get(column_name, ""))


def collapse(values):
    values = [clean_text(value) for value in values if clean_text(value)]
    if not values:
        return ""
    if len(values) == 1 or all(value == values[0] for value in values):
        return values[0]
    return values


def get_column_mapping(fieldnames):
    return {
        field: find_column(fieldnames, aliases, field not in mappings.OPTIONAL_COLUMNS)
        for field, aliases in mappings.COLUMN_ALIASES.items()
    }


def default_metadata(file_data, mime_type):
    file_name = file_data.get("file_name") or file_data.get("source_file") or ""
    return {
        "AsopNo": mappings.ASOP_NO,
        "CustEmail": file_data.get("sender_email", ""),
        "MonsterEmail": "",
        "FileDate": file_data.get("created_at", datetime.now().strftime("%Y-%m-%d")),
        "FileName": file_name,
        "MimeType": file_data.get("file_type") or mime_type,
        "Field1": "",
        "Field2": "",
        "Field3": "",
        "Field4": "",
        "Field5": ""
    }


def transform_csv_rows(reader, columns):
    rows = []
    for row in reader:
        tipo = row_value(row, columns["tipo"])
        folio = row_value(row, columns["folio"])
        secuencia = row_value(row, columns["secuencia"])
        ship_city = row_value(row, columns["ship_city"]) or row_value(row, columns["destination_city"])
        rows.append({
            "_tipo": tipo,
            "_folio": folio,
            "_secuencia": int(secuencia) if secuencia.isdigit() else secuencia,
            "Identifier for ASOP / Sales Order combination": f"{tipo};{folio};{secuencia}",
            "DlvDate": row_value(row, columns["fecha"]),
            "CustPo": row_value(row, columns["po"]),
            "Soldto": ";".join([
                row_value(row, columns["company"]),
                row_value(row, columns["business_activity"]),
                row_value(row, columns["sold_city"]),
                row_value(row, columns["sold_address"])
            ]),
            "TDB (Rene to confirm)": row_value(row, columns["tdb"]),
            "MatDesc": row_value(row, columns["description"]),
            "Quantity": row_value(row, columns["quantity"]),
            "Material": row_value(row, columns["material"]),
            "UoM": row_value(row, columns["uom"]),
            "ShipCity": ship_city,
            "ShipTo": row_value(row, columns["ship_to"])
        })
    return rows


def parse_latam_csv(content, file_data=None):
    file_data = file_data or {}
    text = decode_csv_bytes(content)
    reader = csv.DictReader(io.StringIO(text), delimiter=detect_csv_separator(text))
    if not reader.fieldnames:
        raise ValueError("The CSV file does not contain a header row.")

    rows = transform_csv_rows(reader, get_column_mapping(reader.fieldnames))
    if not rows:
        raise ValueError("The CSV file does not contain any records.")

    rows.sort(key=lambda item: (item["_tipo"], item["_folio"], item["_secuencia"]))
    grouped = {}
    for row in rows:
        grouped.setdefault((row["_tipo"], row["_folio"]), []).append(row)

    output = {}
    for (_, folio), group in grouped.items():
        record = {"AsopNo": mappings.ASOP_NO, "Region": mappings.REGION, "Podoctype": mappings.PODOCTYPE}
        for field in mappings.HEADER_OUTPUT_FIELDS:
            record[field] = collapse(row[field] for row in group)
        record["NavHeadToItem"] = [
            {
                "AsopNo": mappings.ASOP_NO,
                "OCRItemno": str(mappings.OCR_ITEM_NO_START + (index * 10)),
                "MatDesc": row["MatDesc"],
                "Quantity": row["Quantity"],
                "Material": row["Material"],
                "Uom": row["UoM"]
            }
            for index, row in enumerate(group)
        ]
        mime_type = mimetypes.guess_type(file_data.get("file_name", ""))[0] or "text/csv"
        record["NavHeadtoMeta"] = [default_metadata(file_data, mime_type)]
        output[folio] = record
    return output


def update_processed_values(data):
    po_numbers = ",".join(list(data.keys()))
    data_str = json.dumps(data).replace("'", "''")
    return f'"erp_request_payload" = \'{data_str}\' , "po_numbers" = \'{po_numbers}\''


def csv_parsing_flow(file_id):
    from core.config import config

    if config.local_test_mode:
        from core.local_test_storage import local_erp_data_fetch, local_read_file, local_hana_storage_push
        hana_data = local_erp_data_fetch(file_id)
        content = local_read_file(hana_data["file_path"])
        final_output = parse_latam_csv(content, hana_data)
        local_hana_storage_push(file_id, update_processed_values(final_output))
        return final_output

    from core.db.connection import close_connection, connect_to_db
    from core.util import erp_data_fetch, hana_storage_push, push_to_erp, read_file_from_object_store

    connection = connect_to_db()
    try:
        hana_data = erp_data_fetch(connection, file_id)
        content = read_file_from_object_store(hana_data.get("file_path", ""))
        final_output = parse_latam_csv(content, hana_data)
        hana_storage_push(file_id, connection, update_processed_values(final_output))
        close_connection(connection)
        if not config.template_parser_test_mode:
            push_to_erp(config.ocr_erp_push_url, file_id)
        return final_output
    except Exception:
        close_connection(connection)
        raise