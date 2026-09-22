import json
import re
import unicodedata
from datetime import datetime
from html.parser import HTMLParser

from apps.html_parser import mappings


def clean_text(value):
    text = "" if value is None else str(value)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" :")


def normalize_header(value):
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def decode_html_bytes(content):
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            if "\ufffd" not in text:
                return text
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


class TableTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.tables = []
        self.current_table = None
        self.current_row = None
        self.current_cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.current_table = []
        elif tag == "tr" and self.current_table is not None:
            self.current_row = []
        elif tag in {"td", "th"} and self.current_row is not None:
            self.current_cell = []
        elif tag == "br":
            self.text_parts.append(" ")
            if self.current_cell is not None:
                self.current_cell.append(" ")

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.current_cell is not None:
            self.current_row.append(clean_text(" ".join(self.current_cell)))
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            if any(self.current_row):
                self.current_table.append(self.current_row)
            self.current_row = None
        elif tag == "table" and self.current_table is not None:
            self.tables.append(self.current_table)
            self.current_table = None

    def handle_data(self, data):
        self.text_parts.append(data)
        if self.current_cell is not None:
            self.current_cell.append(data)


def extract_between(text, start, end):
    # allow up to 3 stray/mangled characters between a label and its colon,
    # since some LATAM templates arrive with corrupted accented characters
    # (e.g. "Elaboró :" decoding as "Elabor≤ :")
    pattern = rf"{re.escape(start)}\s*:?\s*(.*?)(?=\s+{re.escape(end)}\S{{0,3}}\s*:|$)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return clean_text(match.group(1)) if match else ""


def extract_items(tables):
    for table in tables:
        if not table:
            continue
        header_text = " ".join(normalize_header(cell) for cell in table[0])
        if not all(marker in header_text for marker in mappings.ITEM_HEADER_MARKERS):
            continue
        items = []
        for index, row in enumerate(table[1:]):
            if len(row) < 5:
                continue
            description_match = re.match(r"([A-Z0-9-]+)\s+(.*)", row[2])
            items.append({
                "AsopNo": mappings.ASOP_NO,
                "OCRItemno": str(mappings.OCR_ITEM_NO_START + (index * 10)),
                "Quantity": row[0],
                "Uom": row[1],
                "Material": description_match.group(1) if description_match else "",
                "MatDesc": description_match.group(2) if description_match else row[2],
                "UnitPrice": row[3],
                "Amount": row[4]
            })
        return items
    return []


def extract_totals(tables):
    totals = {}
    for table in tables:
        for row in table:
            if len(row) < 2:
                continue
            label = normalize_header(row[0])
            if label in mappings.TOTAL_LABELS:
                totals[label.title() if label != "IVA" else "IVA"] = row[1]
    return totals


def default_metadata(file_data):
    return {
        "AsopNo": mappings.ASOP_NO,
        "CustEmail": file_data.get("sender_email", ""),
        "MonsterEmail": "",
        "FileDate": file_data.get("created_at", datetime.now().strftime("%Y-%m-%d")),
        "FileName": file_data.get("file_name", ""),
        "MimeType": file_data.get("file_type", "text/html"),
        "Field1": "",
        "Field2": "",
        "Field3": "",
        "Field4": "",
        "Field5": ""
    }


def parse_latam_html(content, file_data=None):
    file_data = file_data or {}
    html = decode_html_bytes(content)
    parser = TableTextParser()
    parser.feed(html)
    full_text = clean_text(" ".join(parser.text_parts))

    po_match = re.search(r"Orden de compra\s*:?\s*([A-Z0-9-]+)", full_text, flags=re.IGNORECASE)
    date_match = re.search(r"Fecha Orden Compra\s*:?\s*(.*?)(?=\s+Proveedor\s*:)", full_text, flags=re.IGNORECASE)
    po_number = po_match.group(1) if po_match else "UNEXTRACTED"
    record = {
        "AsopNo": mappings.ASOP_NO,
        "Region": mappings.REGION,
        "Podoctype": mappings.PODOCTYPE,
        "CustPo": po_number,
        "PODate": clean_text(date_match.group(1)) if date_match else "",
        "DlvDate": extract_between(full_text, "Fecha Promesa", "Facturar a"),
        "SalesOrgDescription": extract_between(full_text, "Proveedor", "Vendedor"),
        "Soldto": extract_between(full_text, "Facturar a", "Consignar a"),
        "ShipTo": extract_between(full_text, "Consignar a", "Elabor"),
        "NavHeadToItem": extract_items(parser.tables),
        "NavHeadtoMeta": [default_metadata(file_data)]
    }
    record.update(extract_totals(parser.tables))
    return {po_number: record}


def update_processed_values(data):
    po_numbers = ",".join(list(data.keys()))
    data_str = json.dumps(data).replace("'", "''")
    return f'"erp_request_payload" = \'{data_str}\' , "po_numbers" = \'{po_numbers}\''


def html_parsing_flow(file_id):
    from core.config import config

    if config.local_test_mode:
        from core.local_test_storage import local_erp_data_fetch, local_read_file, local_hana_storage_push
        hana_data = local_erp_data_fetch(file_id)
        content = local_read_file(hana_data["file_path"])
        final_output = parse_latam_html(content, hana_data)
        local_hana_storage_push(file_id, update_processed_values(final_output))
        return final_output

    from core.db.connection import close_connection, connect_to_db
    from core.util import erp_data_fetch, hana_storage_push, push_to_erp, read_file_from_object_store

    connection = connect_to_db()
    try:
        hana_data = erp_data_fetch(connection, file_id)
        content = read_file_from_object_store(hana_data.get("file_path", ""))
        final_output = parse_latam_html(content, hana_data)
        hana_storage_push(file_id, connection, update_processed_values(final_output))
        close_connection(connection)
        if not config.template_parser_test_mode:
            push_to_erp(config.ocr_erp_push_url, file_id)
        return final_output
    except Exception:
        close_connection(connection)
        raise