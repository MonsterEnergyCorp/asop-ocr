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


def normalize_date(value):
    date_text = clean_text(value)
    if not date_text:
        return ""

    iso_text = date_text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_text).strftime("%Y-%m-%d")
    except ValueError:
        pass

    for date_format in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_text, date_format).strftime("%Y-%m-%d")
        except ValueError:
            continue

    normalized_text = unicodedata.normalize("NFKD", date_text)
    normalized_text = normalized_text.encode("ascii", "ignore").decode().lower()
    spanish_months = {
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
    }
    match = re.fullmatch(r"(\d{1,2})/([a-z]+)/((?:19|20)\d{2})", normalized_text)
    if match:
        day, month_name, year = match.groups()
        month = spanish_months.get(month_name)
        if month:
            return datetime(int(year), month, int(day)).strftime("%Y-%m-%d")

    raise ValueError(f"Unsupported date value: {date_text}")


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


def extract_items(tables, asop_no):
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
                "AsopNo": asop_no,
                "OCRItemno": str(mappings.OCR_ITEM_NO_START + (index * 10)),
                "Quantity": row[0],
                "Uom": row[1],
                "Material": description_match.group(1) if description_match else "",
                "MatDesc": description_match.group(2) if description_match else row[2]
            })
        return items
    return []


def default_metadata(file_data, asop_no):
    file_date = file_data.get("created_at") or datetime.now().strftime("%Y-%m-%d")
    return {
        "AsopNo": asop_no,
        "CustEmail": file_data.get("sender_email", ""),
        "MonsterEmail": "",
        "FileDate": normalize_date(file_date),
        "FileName": file_data.get("file_name", ""),
        "MimeType": file_data.get("file_type", "text/html"),
        "Field1": "",
        "Field2": "",
        "Field3": "",
        "Field4": "",
        "Field5": ""
    }


def parse_latam_html(content, file_data=None):
    # Extract only the HTML fields included in the confirmed ERP payload contract.
    file_data = file_data or {}
    asop_no = str(file_data.get("AsopNo") or file_data.get("asop_no") or mappings.ASOP_NO)
    region = str(file_data.get("region") or mappings.REGION).upper()
    html = decode_html_bytes(content)
    parser = TableTextParser()
    parser.feed(html)
    full_text = clean_text(" ".join(parser.text_parts))

    po_match = re.search(r"Orden de compra\s*:?\s*([A-Z0-9-]+)", full_text, flags=re.IGNORECASE)
    date_match = re.search(r"Fecha Orden Compra\s*:?\s*(.*?)(?=\s+Proveedor\s*:)", full_text, flags=re.IGNORECASE)
    po_number = po_match.group(1) if po_match else "UNEXTRACTED"
    record = {
        "AsopNo": asop_no,
        "Region": region,
        "Podoctype": mappings.PODOCTYPE,
        "CustPo": po_number,
        "PODate": normalize_date(date_match.group(1)) if date_match else "",
        "DlvDate": normalize_date(extract_between(full_text, "Fecha Promesa", "Facturar a")),
        "SalesOrg": extract_between(full_text, "Proveedor", "Vendedor"),
        "SoldTo": extract_between(full_text, "Facturar a", "Consignar a"),
        "ShipTo": extract_between(full_text, "Consignar a", "Elabor"),
        "NavHeadToItem": extract_items(parser.tables, asop_no),
        "NavHeadtoMeta": [default_metadata(file_data, asop_no)]
    }
    return record


def update_processed_values(data):
    po_numbers = ",".join(list(data.keys()))
    data_str = json.dumps(data).replace("'", "''")
    return f'"erp_request_payload" = \'{data_str}\' , "po_numbers" = \'{po_numbers}\''


def html_parsing_flow(file_id):
    from core.config import config

    # Local mode is deliberately isolated from client HANA, Blob, and ERP resources.
    if config.local_test_mode:
        from core.local_test_storage import local_erp_data_fetch, local_read_file, local_hana_storage_push
        hana_data = local_erp_data_fetch(file_id)
        content = local_read_file(hana_data["file_path"])
        final_output = parse_latam_html(content, hana_data)
        erp_payload = {final_output["CustPo"]: final_output}
        local_hana_storage_push(file_id, update_processed_values(erp_payload))
        return final_output

    from core.db.connection import close_connection, connect_to_db
    from core.util import erp_data_fetch, hana_storage_push, push_to_erp, read_file_from_object_store

    # Production path: HANA supplies metadata and Blob supplies the original bytes.
    connection = connect_to_db()
    try:
        hana_data = erp_data_fetch(connection, file_id)
        content = read_file_from_object_store(hana_data.get("file_path", ""))
        final_output = parse_latam_html(content, hana_data)
        erp_payload = {final_output["CustPo"]: final_output}
        hana_storage_push(file_id, connection, update_processed_values(erp_payload))
        close_connection(connection)
        # ERP publishing is opt-in after the DEV/UAT payload review.
        if not config.template_parser_test_mode:
            push_to_erp(config.ocr_erp_push_url, file_id)
        return final_output
    except Exception:
        close_connection(connection)
        raise