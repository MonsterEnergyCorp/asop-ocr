import json
import logging
import re
import unicodedata
from datetime import datetime
from html.parser import HTMLParser

from apps.html_parser import mappings

BR_MARK = "<<BR>>"  # marks a real <br> tag so name/address lines can be split later


# ---------------------------------------------------------------------------------------------
# Text and date helpers (generic - no template specific text in this file)
# ---------------------------------------------------------------------------------------------
def clean_text(value):
    text = "" if value is None else str(value)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" :")


def month_lookup(languages=None):
    """Merged {month name: number} for the given languages (all configured languages if None)."""
    months = {}
    for language in (languages or list(mappings.MONTH_NAMES)):
        months.update(mappings.MONTH_NAMES.get(language, {}))
    return months


def normalize_date(value, date_formats=None, month_names=None):
    date_text = clean_text(value)
    if not date_text:
        return ""

    iso_text = date_text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_text).strftime("%Y-%m-%d")
    except ValueError:
        pass

    for date_format in (date_formats or mappings.DEFAULT_DATE_FORMATS):
        try:
            return datetime.strptime(date_text, date_format).strftime("%Y-%m-%d")
        except ValueError:
            continue

    normalized_text = unicodedata.normalize("NFKD", date_text)
    normalized_text = normalized_text.encode("ascii", "ignore").decode().lower()
    months = month_names if month_names is not None else month_lookup()
    match = re.fullmatch(r"(\d{1,2})[/\-. ]([a-z]+)[/\-. ]((?:19|20)\d{2})", normalized_text)
    if match:
        day, month_name, year = match.groups()
        month = months.get(month_name)
        if month:
            return datetime(int(year), month, int(day)).strftime("%Y-%m-%d")

    raise ValueError(f"Unsupported date value: {date_text}")


def normalize_header(value):
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def decode_html_bytes(content):
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            return text
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


class TableTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.raw_parts = []  # same as text_parts, but <br> kept as BR_MARK
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
            self.raw_parts.append(BR_MARK)
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
        self.raw_parts.append(data)
        if self.current_cell is not None:
            self.current_cell.append(data)


# ---------------------------------------------------------------------------------------------
# Generic extraction rules (driven by mappings.HTML_TEMPLATES)
# ---------------------------------------------------------------------------------------------
def extract_between(text, start, end):
    # allow up to 3 stray/mangled characters between a label and its colon,
    # since some templates arrive with corrupted accented characters
    # (e.g. "Elaboró :" decoding as "Elabor≤ :")
    pattern = rf"{re.escape(start)}\s*:?\s*(.*?)(?=\s+{re.escape(end)}\S{{0,3}}\s*:|$)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return clean_text(match.group(1)) if match else ""


def extract_regex(text, pattern, group=1):
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(group) if match else ""


def block_lines(raw_text, start, end):
    """Lines (split on <br>) of the text found between two labels."""
    pattern = rf"{re.escape(start)}\s*:?\s*(.*?)(?=\s+{re.escape(end)}\S{{0,3}}\s*:|$)"
    match = re.search(pattern, raw_text, flags=re.IGNORECASE)
    if not match:
        return []
    lines = [clean_text(part) for part in match.group(1).split(BR_MARK)]
    return [line for line in lines if line]


def pick_block_value(lines, selector):
    if not lines:
        return ""
    if selector == "first":
        return lines[0]
    if selector == "rest":
        return " ".join(lines[1:])
    if selector == "all":
        return " ".join(lines)
    if isinstance(selector, int) and -len(lines) <= selector < len(lines):
        return lines[selector]
    return ""


def select_template(full_text):
    """
    Pick the template whose markers are all present in the page text.
    Returns (None, None) when none matches, unless mappings.DEFAULT_TEMPLATE names a fallback template.
    """
    haystack = full_text.lower()
    for name, template in mappings.HTML_TEMPLATES.items():
        markers = template.get("markers", [])
        if markers and all(clean_text(marker).lower() in haystack for marker in markers):
            return name, template
    default_name = mappings.DEFAULT_TEMPLATE
    if default_name and default_name in mappings.HTML_TEMPLATES:
        logging.warning("No HTML template markers matched, using default template %s", default_name)
        return default_name, mappings.HTML_TEMPLATES[default_name]
    return None, None


def extract_header(template, full_text, raw_text):
    header = {}
    date_formats = template.get("date_formats")
    months = month_lookup(template.get("date_languages"))
    for rule in template["header_fields"]:
        kind = rule["rule"]
        if kind == "block":
            lines = block_lines(raw_text, rule["start"], rule["end"])
            for field, selector in rule["fields"].items():
                header[field] = pick_block_value(lines, selector)
            continue
        if kind == "regex":
            value = clean_text(extract_regex(full_text, rule["pattern"], rule.get("group", 1)))
        elif kind == "between":
            value = extract_between(full_text, rule["start"], rule["end"])
        else:
            raise ValueError(f"Unknown HTML header rule: {kind}")
        if not value:
            value = rule.get("default", "")
        elif rule.get("date"):
            value = normalize_date(value, date_formats, months)
        header[rule["field"]] = value
    return header


def extract_items(tables, asop_no, items_config):
    for table in tables:
        if not table:
            continue
        header_text = " ".join(normalize_header(cell) for cell in table[0])
        if not all(marker in header_text for marker in items_config["header_markers"]):
            continue
        items = []
        for index, row in enumerate(table[1:]):
            if len(row) < items_config.get("min_columns", 1):
                continue
            item = {
                "AsopNo": asop_no,
                "OCRItemno": str(mappings.OCR_ITEM_NO_START + (index * 10)),
            }
            for field in mappings.OUTPUT_ITEM_FIELDS:
                item.setdefault(field, "")
            for field, column in items_config["columns"].items():
                item[field] = row[column] if column < len(row) else ""
            column = items_config["description_column"]
            description = row[column] if column < len(row) else ""
            split = items_config.get("split_description")
            description_match = re.match(split["pattern"], description) if split else None
            if split:
                item[split["code_field"]] = description_match.group(1) if description_match else ""
                item[split["text_field"]] = description_match.group(2) if description_match else description
            else:
                item["MatDesc"] = description
            items.append(item)
        return items
    return []


def default_metadata(file_data, asop_no):
    file_date = file_data.get("created_at") or datetime.now().strftime("%Y-%m-%d")
    try:
        file_date = normalize_date(file_date)
    except ValueError:
        file_date = clean_text(file_date)
    return {
        "AsopNo": asop_no,
        "CustEmail": file_data.get("sender_email", ""),
        "MonsterEmail": "",
        "FileDate": file_date,
        # same as Excel / PDF: the Content sent to ERP is the .eml email, so the name ends in .eml
        "FileName": f'{file_data.get("file_name") or "placeholder"}.eml',
        "MimeType": file_data.get("file_type", "text/html"),
        "Field1": "",
        "Field2": "",
        "Field3": "",
        "Field4": "",
        "Field5": ""
    }


def get_asop_no(file_data):
    return str(file_data.get("AsopNo") or file_data.get("asop_no") or mappings.ASOP_NO)


# ---------------------------------------------------------------------------------------------
# Parser entry points
# ---------------------------------------------------------------------------------------------
def copy_header_to_items(record):
    """Line items get the header value of every ERP field they share with the header, unless the template filled it."""
    for item in record["NavHeadToItem"]:
        for field in mappings.OUTPUT_ITEM_FIELDS:
            if not item.get(field) and record.get(field):
                item[field] = record[field]


def parse_html_po(content, file_data=None):
    """Parse an HTML purchase order with the template it matches (see mappings.HTML_TEMPLATES)."""
    file_data = file_data or {}
    asop_no = get_asop_no(file_data)
    html = decode_html_bytes(content)
    parser = TableTextParser()
    parser.feed(html)
    full_text = clean_text(" ".join(parser.text_parts))
    raw_text = re.sub(r"\s+", " ", " ".join(parser.raw_parts))

    template_name, template = select_template(full_text)
    if template is None:
        logging.warning("HTML EXTRACTION ISSUE: no template in mappings.HTML_TEMPLATES matches this file")
        return failed_record(file_data)
    logging.info("HTML template used: %s", template_name)
    region = str(file_data.get("region") or template.get("region") or mappings.REGION).upper()

    record = {
        "AsopNo": asop_no,
        "Region": region,
        "Podoctype": template.get("podoctype", mappings.PODOCTYPE),
    }
    record.update(extract_header(template, full_text, raw_text))
    for field in mappings.OUTPUT_HEADER_FIELDS:
        record.setdefault(field, "")
    record["NavHeadToItem"] = extract_items(parser.tables, asop_no, template["items"])
    copy_header_to_items(record)
    record["HeadtoMeta"] = [default_metadata(file_data, asop_no)]
    return record


# old name, kept only so scripts written before the rename still run; use parse_html_po
parse_latam_html = parse_html_po


def failed_record(file_data):
    """Record used when a file cannot be read: no data, but the metadata (email) is kept."""
    file_data = file_data or {}
    asop_no = get_asop_no(file_data)
    return {
        "AsopNo": asop_no,
        "CustPo": mappings.UNEXTRACTED_PO,
        "NavHeadToItem": [],
        "HeadtoMeta": [default_metadata(file_data, asop_no)],
    }


def parse_or_fail(content, file_data):
    try:
        return parse_html_po(content, file_data)
    except Exception as exc:
        logging.exception("HTML EXTRACTION ISSUE: %s", exc)
        return failed_record(file_data)


def build_erp_payload(final_output):
    """
    Payload stored in HANA and pushed to ERP.
    Same convention as the Excel parser: a file with no PO number or no items goes to ERP with
    Status 52 and its metadata (the email) under UNEXTRACTED, so the order can be handled manually.
    """
    if final_output.get("CustPo") == mappings.UNEXTRACTED_PO or not final_output.get("NavHeadToItem"):
        return {mappings.UNEXTRACTED_PO: {
            "Status": mappings.FAILURE_STATUS,
            "HeadtoMeta": final_output["HeadtoMeta"],
        }}
    return {final_output["CustPo"]: final_output}


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
        logging.info("HTML ERP PUSH: sending file_id %s to %s", file_id, config.ocr_erp_push_url)
        response = push_to_erp(config.ocr_erp_push_url, file_id)
        logging.info("HTML ERP PUSH: ERP answered %s for file_id %s", response.status_code, file_id)
    else:
        logging.info("HTML ERP PUSH: skipped, TEMPLATE_PARSER_TEST_MODE is on (file_id %s)", file_id)
    return final_output