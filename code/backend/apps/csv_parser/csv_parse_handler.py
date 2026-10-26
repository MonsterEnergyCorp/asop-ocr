import csv
import io
import json
import logging
import re
import unicodedata
from datetime import datetime

from apps.csv_parser import mappings


# ---------------------------------------------------------------------------------------------
# Text and date helpers (generic - no template specific text in this file)
# ---------------------------------------------------------------------------------------------
def clean_text(value):
    text = "" if value is None else str(value)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" :")


def normalize_date(value, date_formats=None):
    date_text = clean_text(value)
    if not date_text:
        return ""
    try:
        return datetime.fromisoformat(date_text.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        pass
    for date_format in (date_formats or mappings.DEFAULT_DATE_FORMATS):
        try:
            return datetime.strptime(date_text, date_format).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Unsupported CSV date value: {date_text}")


def normalize_header(value):
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def header_key(value):
    # "TIPO (33: Factura electronica)" and "UNIDADMEDIDA(HR, KG)" are matched by their name only
    return normalize_header(str(value).split("(")[0])


def decode_csv_bytes(content):
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            if "�" not in text:
                return text
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def detect_csv_separator(text):
    # The header row decides: the delimiter that splits it into the most columns wins.
    # csv.Sniffer is not used because the commas inside the header legends confuse it.
    header_line = next((line for line in text.splitlines() if line.strip()), "")
    separator, column_count = ";", 0
    for candidate in mappings.CSV_DELIMITERS:
        count = len(next(csv.reader([header_line], delimiter=candidate), []))
        if count > column_count:
            separator, column_count = candidate, count
    return separator


def select_template(fieldnames):
    """
    Pick the template whose markers are all present in the header row.
    Returns (None, None) when none matches, unless mappings.DEFAULT_TEMPLATE names a fallback template.
    """
    header_keys = {header_key(column) for column in fieldnames}
    for name, template in mappings.CSV_TEMPLATES.items():
        markers = template.get("markers", [])
        if markers and all(header_key(marker) in header_keys for marker in markers):
            return name, template
    default_name = mappings.DEFAULT_TEMPLATE
    if default_name and default_name in mappings.CSV_TEMPLATES:
        logging.warning("No CSV template markers matched, using default template %s", default_name)
        return default_name, mappings.CSV_TEMPLATES[default_name]
    return None, None


def find_column(fieldnames, aliases):
    columns = {}
    for column in fieldnames:
        columns.setdefault(header_key(column), column)
    for alias in aliases:
        if header_key(alias) in columns:
            return columns[header_key(alias)]
    return None


def get_column_mapping(fieldnames, template):
    columns = {}
    for field in set(template["columns"]) | mappings.REQUIRED_COLUMNS:
        aliases = template["columns"].get(field, [])
        column = find_column(fieldnames, aliases)
        if column is None and field in mappings.REQUIRED_COLUMNS:
            raise ValueError(f"Required column not found: {field}. Expected one of: {aliases}")
        columns[field] = column
    return columns


def row_value(row, column_name):
    if column_name is None:
        return ""
    return clean_text(row.get(column_name, ""))


def first_value(values, fields):
    return next((values[field] for field in fields if values.get(field)), "")


def get_asop_no(file_data):
    return str(file_data.get("AsopNo") or file_data.get("asop_no") or mappings.ASOP_NO)


def default_metadata(file_data, template, asop_no):
    file_date = file_data.get("created_at") or datetime.now().strftime("%Y-%m-%d")
    try:
        file_date = normalize_date(file_date, template.get("date_formats"))
    except ValueError:
        file_date = clean_text(file_date)
    return {
        "AsopNo": asop_no,
        "CustEmail": file_data.get("sender_email", ""),
        "MonsterEmail": "",
        "FileDate": file_date,
        # same as Excel / PDF / HTML: the Content sent to ERP is the .eml email, so the name ends in .eml
        "FileName": f'{file_data.get("file_name") or "placeholder"}.eml',
        "MimeType": file_data.get("file_type") or mappings.DEFAULT_MIME_TYPE,
        "Field1": "",
        "Field2": "",
        "Field3": "",
        "Field4": "",
        "Field5": ""
    }


# ---------------------------------------------------------------------------------------------
# Parser entry points
# ---------------------------------------------------------------------------------------------
def transform_csv_rows(reader, columns, template):
    rows = []
    for row in reader:
        values = {field: row_value(row, column) for field, column in columns.items()}
        rows.append({
            "CsvNO": ";".join(values.get(field, "") for field in template["csv_no"]),
            "DlvDate": normalize_date(values.get("fecha", ""), template.get("date_formats")),
            "CustPo": values.get("po", ""),
            "SoldTo": ";".join(values.get(field, "") for field in template["sold_to"]),
            "MatDesc": values.get("description", ""),
            "Quantity": values.get("quantity", ""),
            "Material": values.get("material", ""),
            "UoM": values.get("uom", ""),
            "ShipCity": first_value(values, template.get("ship_city", [])),
            "ShipTo": first_value(values, template.get("ship_to", []))
        })
    return rows


def build_line_items(rows, asop_no):
    return [
        {
            "AsopNo": asop_no,
            "CsvNO": row["CsvNO"],
            "OCRItemno": str(mappings.OCR_ITEM_NO_START + (index * 10)),
            "MatDesc": row["MatDesc"],
            "Quantity": row["Quantity"],
            "Material": row["Material"],
            "Uom": row["UoM"],
            "DlvDate": row["DlvDate"],
            "CustPo": row["CustPo"],
            "SoldTo": row["SoldTo"],
            "ShipCity": row["ShipCity"],
            "ShipTo": row["ShipTo"]
        }
        for index, row in enumerate(rows)
    ]


def parse_csv_po(content, file_data=None):
    """Parse a CSV PO file with the template it matches (see mappings.CSV_TEMPLATES)."""
    file_data = file_data or {}
    asop_no = get_asop_no(file_data)
    text = decode_csv_bytes(content)
    reader = csv.DictReader(io.StringIO(text), delimiter=detect_csv_separator(text))
    if not reader.fieldnames:
        raise ValueError("The CSV file does not contain a header row.")

    template_name, template = select_template(reader.fieldnames)
    if template is None:
        logging.warning("CSV EXTRACTION ISSUE: no template in mappings.CSV_TEMPLATES matches this file")
        return failed_record(file_data)
    logging.info("CSV template used: %s", template_name)

    rows = transform_csv_rows(reader, get_column_mapping(reader.fieldnames, template), template)
    if not rows:
        raise ValueError("The CSV file does not contain any records.")

    return {
        "AsopNo": asop_no,
        "AddField1": template.get("add_field1", mappings.ADD_FIELD1),
        "NavHeadToItem": build_line_items(rows, asop_no),
        "NavHeadtoMeta": [default_metadata(file_data, template, asop_no)],
    }


# old name, kept only so scripts written before the rename still run; use parse_csv_po
parse_latam_csv = parse_csv_po


def failed_record(file_data):
    """Record used when a file cannot be read: no data, but the metadata (email) is kept."""
    file_data = file_data or {}
    asop_no = get_asop_no(file_data)
    return {
        "AsopNo": asop_no,
        "AddField1": mappings.ADD_FIELD1,
        "CustPo": mappings.UNEXTRACTED_PO,
        "NavHeadToItem": [],
        "NavHeadtoMeta": [default_metadata(file_data, {}, asop_no)],
    }


def parse_or_fail(content, file_data):
    try:
        return parse_csv_po(content, file_data)
    except Exception as exc:
        logging.exception("CSV EXTRACTION ISSUE: %s", exc)
        return failed_record(file_data)


def build_erp_payload(final_output):
    """
    Payload stored in HANA and pushed to ERP.
    Same convention as the other parsers: a file with no PO data or no items goes to ERP with
    Status 52 and its metadata (the email) under UNEXTRACTED, so the order can be handled manually.
    """
    if final_output.get("CustPo") == mappings.UNEXTRACTED_PO or not final_output.get("NavHeadToItem"):
        return {mappings.UNEXTRACTED_PO: {
            "Status": mappings.FAILURE_STATUS,
            "NavHeadtoMeta": final_output["NavHeadtoMeta"],
        }}
    return {final_output["AddField1"]: final_output}


def po_numbers_of(erp_payload):
    # PO numbers of the file (CustPo of the line items), as the HTML and PDF parsers store them;
    # the payload keys when the file has none.
    po_numbers = []
    for record in erp_payload.values():
        for item in record.get("NavHeadToItem", []):
            if item.get("CustPo") and item["CustPo"] not in po_numbers:
                po_numbers.append(item["CustPo"])
    return ",".join(po_numbers) if po_numbers else ",".join(erp_payload.keys())


def update_processed_values(data):
    po_numbers = po_numbers_of(data).replace("'", "''")
    data_str = json.dumps(data).replace("'", "''")
    return f'"erp_request_payload" = \'{data_str}\' , "po_numbers" = \'{po_numbers}\''


def csv_parsing_flow(file_id):
    from core.config import config

    # Local mode is deliberately isolated from client HANA, Blob, and ERP resources.
    if config.local_test_mode:
        from core.local_test_storage import local_erp_data_fetch, local_read_file, local_hana_storage_push
        hana_data = local_erp_data_fetch(file_id)
        content = local_read_file(hana_data["file_path"])
        final_output = parse_or_fail(content, hana_data)
        local_hana_storage_push(file_id, update_processed_values(build_erp_payload(final_output)))
        return final_output

    from core.db.connection import close_connection, connect_to_db
    from core.util import erp_data_fetch, hana_storage_push, push_to_erp, read_file_from_object_store

    # Production path: HANA supplies metadata and Blob supplies the original bytes.
    connection = connect_to_db()
    try:
        hana_data = erp_data_fetch(connection, file_id)
        content = read_file_from_object_store(hana_data.get("file_path", ""))
        final_output = parse_or_fail(content, hana_data)
        hana_storage_push(file_id, connection, update_processed_values(build_erp_payload(final_output)))
    finally:
        close_connection(connection)
    # ERP publishing is opt-in after the DEV/UAT payload review.
    if not config.template_parser_test_mode:
        push_to_erp(config.ocr_erp_push_url, file_id)
    return final_output
