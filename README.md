# asop-ocr

Repository for the ASOP OCR solution to parse Purchase Order documents and extract information.

## Overview

This project receives purchase-order files, stores the original document, extracts structured order data, prepares an ERP-ready payload, and optionally publishes the payload to ERP/SAP.

Supported parser areas in this branch:

```text
PDF   -> SAP Document Information Extraction based OCR flow
XLSX  -> openpyxl based workbook parsing flow
CSV   -> LATAM CSV template parsing flow
HTML  -> LATAM HTML template parsing flow
```

## High-Level Flow

```text
Input file / email attachment
	-> ingest service
	-> Azure Blob Storage
	-> HANA metadata row
	-> parser service
	-> HANA erp_request_payload
	-> ERP push service
	-> SAP/ERP OData endpoint
```

For local CSV/HTML parser debugging, Blob Storage, HANA, and ERP can be bypassed with the local debug tools under `tools/`.

## Key Services and Files

### Ingest

```text
code/backend/apps/ingest_documents/server.py
code/backend/apps/ingest_documents/ocr_ingest_doc.py
```

Important functions:

```text
upload_invoice_file(data)
decode(data)
get_file_type(content_type)
hana_storage_insert(data)
push_to_parsers(url, file_id)
```

Execution role:

```text
Receives payload, decodes file_content, saves the file to Blob Storage, creates a HANA metadata row, and calls the correct parser URL with file_id.
```

### PDF Parser

```text
code/backend/apps/pdf_parser/pdf_parse_handler.py
```

Important functions:

```text
pdf_parsing_flow(data)
get_auth_token()
upload_document()
document_status()
parsed_results()
output_formatter()
output_filtering()
metadata_formatter()
```

Execution role:

```text
Uploads PDF content to SAP Document Information Extraction, receives OCR output, maps fields, stores ERP payload in HANA, then triggers ERP push.
```

### Excel Parser

```text
code/backend/apps/excel_parser/excel_parse_handler.py
code/backend/apps/excel_parser/auxiliary_data.py
code/backend/apps/excel_parser/post_processing.py
```

Important functions:

```text
excel_parsing_flow(file_id)
parse_data(wb)
sheet_traversal(sheet, keys)
erp_field_mapping(parsed_data, region)
extract_header_data(data, tabular_keys_instance)
extract_tabular_data(data, tabular_keys_instance)
post_processing_transformations(...)
```

Execution role:

```text
Reads workbook bytes from Blob Storage, parses sheets with openpyxl, applies template and region rules, stores ERP payload in HANA, then triggers ERP push.
```

### CSV Parser

```text
code/backend/apps/csv_parser/server.py
code/backend/apps/csv_parser/csv_parse_handler.py
code/backend/apps/csv_parser/mappings.py
```

Important functions:

```text
csv_parsing_flow(file_id)
parse_latam_csv(content, file_data)
decode_csv_bytes(content)
detect_csv_separator(text)
find_column(fieldnames, aliases, required=True)
transform_csv_rows(reader, columns)
update_processed_values(data)
```

Execution role:

```text
Reads CSV bytes from Blob Storage or local test storage, maps LATAM CSV columns, groups records by TIPO/FOLIO, builds NavHeadToItem/NavHeadtoMeta, and stores erp_request_payload.
```

### HTML Parser

```text
code/backend/apps/html_parser/server.py
code/backend/apps/html_parser/html_parse_handler.py
code/backend/apps/html_parser/mappings.py
```

Important functions:

```text
html_parsing_flow(file_id)
parse_latam_html(content, file_data)
decode_html_bytes(content)
TableTextParser.handle_data(data)
extract_between(text, start, end)
extract_items(tables)
extract_totals(tables)
update_processed_values(data)
```

Execution role:

```text
Reads HTML bytes from Blob Storage or local test storage, extracts purchase-order header values, line items, and totals, then stores erp_request_payload.
```

### ERP Push

```text
code/backend/apps/publish_to_erp/server.py
code/backend/apps/publish_to_erp/publish_to_erp_handler.py
```

Important functions:

```text
publish_to_erp(data)
excel_call_to_erp(payload, content, hana_data)
pdf_call_to_erp(payload, po_no, file_content)
push_to_erp(url, payload)
fetch_xcsrf_token(session, url, authorization)
metadata_formatter(content, file_data)
```

Execution role:

```text
Reads erp_request_payload from HANA, enriches metadata/content, then posts to the configured SAP/ERP OData endpoint.
```

## HANA, Blob, and Runtime Config

Core configuration:

```text
code/backend/core/config.py
code/backend/core/db/connection.py
code/backend/core/db/queries.py
code/backend/core/util.py
```

Important HANA/Blob functions:

```text
connect_to_db()
erp_data_fetch(connection, file_id)
read_file_from_object_store(file_path)
hana_storage_push(file_id, connection, update_values)
```

Kubernetes injects values through Helm ConfigMap and Secret references:

```text
helm/*/templates/deployment.yaml
helm/ocr-ingest-documents/templates/configmap.yaml
```

## CSV/HTML Runtime Flags

```text
LOCAL_TEST_MODE=true
```

Uses local test storage and skips HANA, Blob Storage, and ERP.

```text
LOCAL_TEST_MODE=false
```

Uses real HANA and Blob Storage configuration.

```text
TEMPLATE_PARSER_TEST_MODE=true
```

Parses and stores payload, but does not trigger ERP push.

```text
TEMPLATE_PARSER_TEST_MODE=false
```

Parses, stores payload, and triggers ERP push.

Recommended first DEV/UAT setting:

```text
LOCAL_TEST_MODE=false
TEMPLATE_PARSER_TEST_MODE=true
```

## Local Setup

Use Python 3.12, matching the Dockerfiles.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r code\dependencies\requirements.txt
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

## Local CSV/HTML Debug Commands

Sample files are stored under:

```text
sample_inputs/latam/html/OCBD0125252.html
sample_inputs/latam/csv/Cargas Masivas_20-07-2026_Loginsa.csv
```

Debug HTML parser:

```powershell
.\.venv\Scripts\python.exe tools\debug_parse_local.py --type html --file "sample_inputs\latam\html\OCBD0125252.html"
```

Debug CSV parser:

```powershell
.\.venv\Scripts\python.exe tools\debug_parse_local.py --type csv --file "sample_inputs\latam\csv\Cargas Masivas_20-07-2026_Loginsa.csv"
```

Save outputs:

```powershell
.\.venv\Scripts\python.exe tools\debug_parse_local.py --type html --file "sample_inputs\latam\html\OCBD0125252.html" > html-output.json
.\.venv\Scripts\python.exe tools\debug_parse_local.py --type csv --file "sample_inputs\latam\csv\Cargas Masivas_20-07-2026_Loginsa.csv" > csv-output.json
```

Run local full-flow simulation:

```powershell
.\.venv\Scripts\python.exe tools\run_local_flow.py --type html --file "sample_inputs\latam\html\OCBD0125252.html"
.\.venv\Scripts\python.exe tools\run_local_flow.py --type csv --file "sample_inputs\latam\csv\Cargas Masivas_20-07-2026_Loginsa.csv"
```

Local full-flow output is written under:

```text
tools/local_test_storage/
```

## VS Code Debugging

Debug configurations are stored in:

```text
.vscode/launch.json
```

Use Run and Debug (`Ctrl+Shift+D`) and choose:

```text
Debug: LATAM CSV parser (local file)
Debug: LATAM HTML parser (local file)
Debug: LATAM parser unit tests
```

Recommended CSV breakpoints:

```text
parse_latam_csv()
detect_csv_separator()
find_column()
transform_csv_rows()
csv_parsing_flow()
```

Recommended HTML breakpoints:

```text
parse_latam_html()
TableTextParser.handle_data()
extract_between()
extract_items()
extract_totals()
html_parsing_flow()
```

## Deployment Notes

CSV/HTML parser logic is present, but deployment packaging still needs dedicated Docker/Helm work before Kubernetes deployment:

```text
build/Dockerfile.csv-parser
build/Dockerfile.html-parser
helm/ocr-csv-parser/
helm/ocr-html-parser/
```

For safe DEV/UAT rollout, keep ERP push disabled first:

```text
TEMPLATE_PARSER_TEST_MODE=true
```

After payload approval, ERP push can be enabled by setting:

```text
TEMPLATE_PARSER_TEST_MODE=false
```

## Detailed Guide

Full implementation and testing notes are available in:

```text
docs/csv_html_testing_and_debug_guide.md
```
