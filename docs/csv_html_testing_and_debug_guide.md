# CSV/HTML Parser Testing and Debug Guide

## Purpose

This guide explains the current CSV/HTML enhancement work for the ASOP OCR project, how it fits into the existing architecture, how to debug it locally and in the client environment, and how to safely approach UAT or live testing.

The current enhancement is focused on LATAM CSV and HTML purchase-order templates.

## Current Branch

Work is being done on:

```text
LATAM_TEST_VISHAL_CSV_HTML
```

This branch was created from:

```text
origin/feature/latam
```

## Existing Project Flow

The project has multiple parser services:

```text
ingest_documents
pdf_parser
excel_parser
publish_to_erp
archival
security
```

New services added for this enhancement:

```text
csv_parser
html_parser
```

## PDF Flow

PDF files use SAP Document Information Extraction, which is SAP's OCR / AI-based extraction service.

High-level PDF flow:

```text
PDF file
  -> ingest API
  -> Azure Blob Storage
  -> HANA file metadata
  -> PDF parser service
  -> SAP Document Information Extraction API
  -> SAP extraction result
  -> project mapping logic
  -> HANA erp_request_payload
  -> ERP push service
  -> SAP/ERP OData endpoint
```

Important PDF file:

```text
code/backend/apps/pdf_parser/pdf_parse_handler.py
```

Important PDF functions:

```text
pdf_parsing_flow()
get_auth_token()
get_clients()
upload_document()
document_status()
parsed_results()
output_formatter()
output_filtering()
metadata_formatter()
```

## XLSX / Excel Flow

Excel files do not use SAP OCR. They are parsed directly with `openpyxl` and custom business rules.

High-level Excel flow:

```text
Excel file
  -> ingest API
  -> Azure Blob Storage
  -> HANA file metadata
  -> Excel parser service
  -> openpyxl workbook parsing
  -> header and tabular extraction
  -> post-processing / mapping
  -> HANA erp_request_payload
  -> ERP push service
```

Important Excel file:

```text
code/backend/apps/excel_parser/excel_parse_handler.py
```

Important Excel functions:

```text
excel_parsing_flow()
parse_data()
sheet_traversal()
erp_field_mapping()
extract_header_data()
extract_tabular_data()
post_processing_transformations()
```

## New CSV Flow

The CSV parser uses Python's built-in `csv` module instead of pandas.

Reason:

```text
pandas is not currently used by the project requirements.
The built-in csv module is enough for the current LATAM template.
This avoids adding a heavy dependency and keeps deployment risk lower.
```

Important CSV files:

```text
code/backend/apps/csv_parser/csv_parse_handler.py
code/backend/apps/csv_parser/mappings.py
code/backend/apps/csv_parser/server.py
```

CSV parsing flow:

```text
CSV bytes
  -> decode_csv_bytes()
  -> detect_csv_separator()
  -> csv.DictReader
  -> get_column_mapping()
  -> transform_csv_rows()
  -> group by TIPO + FOLIO
  -> build ERP-style payload
  -> NavHeadToItem
  -> NavHeadtoMeta
```

Important CSV functions:

```text
parse_latam_csv()
decode_csv_bytes()
detect_csv_separator()
find_column()
transform_csv_rows()
update_processed_values()
csv_parsing_flow()
```

## New HTML Flow

The HTML parser uses Python's built-in `html.parser` instead of BeautifulSoup.

Reason:

```text
BeautifulSoup is not currently in project requirements.
The current LATAM HTML template can be parsed with the standard library.
This avoids adding a new dependency and reduces deployment risk.
```

Important HTML files:

```text
code/backend/apps/html_parser/html_parse_handler.py
code/backend/apps/html_parser/mappings.py
code/backend/apps/html_parser/server.py
```

HTML parsing flow:

```text
HTML bytes
  -> decode_html_bytes()
  -> TableTextParser
  -> full_text extraction
  -> PO/header extraction
  -> line item table extraction
  -> total table extraction
  -> build ERP-style payload
  -> NavHeadToItem
  -> NavHeadtoMeta
```

Important HTML functions:

```text
parse_latam_html()
decode_html_bytes()
TableTextParser.handle_data()
extract_between()
extract_items()
extract_totals()
update_processed_values()
html_parsing_flow()
```

## Local Testing Modes

There are two local testing modes.

### 1. Parser-only local testing

This reads a local CSV/HTML file and prints JSON. It does not use HANA, Azure Blob Storage, Kubernetes, or ERP.

Tool:

```text
tools/debug_parse_local.py
```

HTML command:

```powershell
.\.venv\Scripts\python.exe tools\debug_parse_local.py --type html --file "sample_inputs\latam\html\OCBD0125252.html"
```

CSV command:

```powershell
.\.venv\Scripts\python.exe tools\debug_parse_local.py --type csv --file "sample_inputs\latam\csv\Cargas Masivas_20-07-2026_Loginsa.csv"
```

To save output:

```powershell
.\.venv\Scripts\python.exe tools\debug_parse_local.py --type html --file "sample_inputs\latam\html\OCBD0125252.html" > html-output.json

.\.venv\Scripts\python.exe tools\debug_parse_local.py --type csv --file "sample_inputs\latam\csv\Cargas Masivas_20-07-2026_Loginsa.csv" > csv-output.json
```

Expected output files:

```text
html-output.json
csv-output.json
```

### 2. Local full-flow testing

This simulates the `file_id -> metadata -> file -> parser -> output` pattern without real HANA or Blob Storage.

Tool:

```text
tools/run_local_flow.py
```

It uses:

```text
LOCAL_TEST_MODE=true
```

Expected output location:

```text
tools/local_test_storage/manifest.json
tools/local_test_storage/output/local-test-<id>.txt
```

## Sample Input Folder

Tested sample files are stored in the repo under:

```text
sample_inputs/latam/html/OCBD0125252.html
sample_inputs/latam/csv/Cargas Masivas_20-07-2026_Loginsa.csv
```

Future sample templates can be added here:

```text
sample_inputs/latam/pdf/
sample_inputs/latam/xlsx/
sample_inputs/us/
sample_inputs/emea/
```

Keep this folder for sample templates only. Do not store production data or credentials here.

## Runtime Flags

### LOCAL_TEST_MODE

Used by CSV/HTML parser flow functions.

```text
LOCAL_TEST_MODE=true
```

Means:

```text
Use local manifest and local files.
Skip HANA.
Skip Azure Blob Storage.
Skip ERP.
```

```text
LOCAL_TEST_MODE=false
```

Means:

```text
Use real HANA and Azure Blob Storage configuration.
```

### TEMPLATE_PARSER_TEST_MODE

Controls whether CSV/HTML parser service triggers the ERP push service.

```text
TEMPLATE_PARSER_TEST_MODE=true
```

Means:

```text
Parse file and save payload, but do not call ERP push service.
```

```text
TEMPLATE_PARSER_TEST_MODE=false
```

Means:

```text
Parse file, save payload, and trigger ERP push service.
```

Recommended for client DEV/UAT initial testing:

```text
LOCAL_TEST_MODE=false
TEMPLATE_PARSER_TEST_MODE=true
```

Recommended only after payload approval:

```text
LOCAL_TEST_MODE=false
TEMPLATE_PARSER_TEST_MODE=false
```

## Environment Validation

Environment validation means confirming the code works safely in a target environment before enabling ERP publishing.

For DEV/UAT, validate:

```text
1. File reaches ingest API.
2. File is saved to Azure Blob Storage.
3. HANA row is created with file_id, file_path, region and file_type.
4. Parser receives the correct file_id.
5. Parser reads the correct file from Blob Storage.
6. Parser writes erp_request_payload into HANA.
7. po_numbers are populated.
8. ERP push is not called while TEMPLATE_PARSER_TEST_MODE=true.
9. Parser logs do not contain exceptions.
10. Payload is manually reviewed and approved.
```

## Live Testing Guidance

Do not directly test against live production first.

Preferred order:

```text
1. Local parser test.
2. Local full-flow test if possible.
3. DEV Kubernetes deployment with ERP push disabled.
4. UAT deployment with ERP push disabled.
5. Payload review from HANA.
6. UAT test with non-production ERP endpoint if available.
7. Production only after approval.
```

If the project documentation provides a testing email ID, that can be useful only if it routes files into a DEV/UAT ingestion pipeline, not directly into production ERP.

Before using the testing email ID, confirm:

```text
1. Which environment does the email feed?
2. Does it create a HANA record?
3. Does it save attachments to Blob Storage?
4. Which parser URL will be called?
5. Is TEMPLATE_PARSER_TEST_MODE=true?
6. Does it point to production ERP or non-production ERP?
7. Who can validate the HANA erp_request_payload?
```

If the email points to production ERP, do not use it for this enhancement until the payload is approved.

## Deployment Readiness

CSV/HTML parser deployment packaging is now present, but client-specific registry, namespace, URL, Secret, and ConfigMap values still need to be supplied before a real Kubernetes deployment.

Existing repo has Dockerfiles and Helm charts for:

```text
pdf parser
excel parser
ingest service
erp push service
archival
authorizer
```

CSV/HTML deployment files now include:

```text
build/Dockerfile.csv-parser
build/Dockerfile.html-parser
helm/ocr-csv-parser/
helm/ocr-html-parser/
```

Also configure these environment variables in Kubernetes ConfigMap/Secret:

```text
ocr_latam_csv_url
ocr_latam_html_url
ocr_latam_template_url
TEMPLATE_PARSER_TEST_MODE
LOCAL_TEST_MODE
```

The default values intentionally leave the CSV/HTML service URLs blank until the client confirms the Kyma namespace and release names. Do not guess or copy production URLs into a test environment.

For deployed environments:

```text
LOCAL_TEST_MODE=false
```

For initial DEV/UAT safety:

```text
TEMPLATE_PARSER_TEST_MODE=true
```

## Debugging in VS Code

Use the Run and Debug panel:

```text
Ctrl + Shift + D
```

Existing local debug configs:

```text
Debug: LATAM CSV parser (local file)
Debug: LATAM HTML parser (local file)
Debug: LATAM parser unit tests
```

### CSV breakpoints

Set breakpoints in:

```text
code/backend/apps/csv_parser/csv_parse_handler.py
```

Recommended functions:

```text
parse_latam_csv()
decode_csv_bytes()
detect_csv_separator()
find_column()
transform_csv_rows()
update_processed_values()
csv_parsing_flow()
```

Watch variables:

```text
text
reader.fieldnames
columns
rows
grouped
record
NavHeadToItem
```

### HTML breakpoints

Set breakpoints in:

```text
code/backend/apps/html_parser/html_parse_handler.py
```

Recommended functions:

```text
parse_latam_html()
decode_html_bytes()
TableTextParser.handle_data()
extract_between()
extract_items()
extract_totals()
update_processed_values()
html_parsing_flow()
```

Watch variables:

```text
html
full_text
parser.tables
items
totals
record
```

### Excel breakpoints

Set breakpoints in:

```text
code/backend/apps/excel_parser/excel_parse_handler.py
```

Recommended functions:

```text
excel_parsing_flow()
parse_data()
sheet_traversal()
erp_field_mapping()
extract_header_data()
extract_tabular_data()
post_processing_transformations()
```

### PDF breakpoints

Set breakpoints in:

```text
code/backend/apps/pdf_parser/pdf_parse_handler.py
```

Recommended functions:

```text
pdf_parsing_flow()
get_auth_token()
get_clients()
upload_document()
document_status()
parsed_results()
output_formatter()
output_filtering()
metadata_formatter()
```

PDF full debugging requires SAP Document Information Extraction credentials and access.

## Client VDI Debugging Without Copilot

On the client VDI, keep this checklist:

```text
1. Confirm Python 3.12 is used.
2. Install requirements.
3. Confirm environment variables.
4. Confirm service URLs.
5. Run parser service locally if needed.
6. Set breakpoints in parser handler.
7. Send a test file through DEV/UAT ingestion.
8. Check parser logs.
9. Check HANA erp_request_payload.
10. Keep ERP disabled until payload is approved.
```

Useful command pattern for service debug:

```powershell
cd code/backend
python -m uvicorn apps.csv_parser.server:app --reload --port 8001
python -m uvicorn apps.html_parser.server:app --reload --port 8002
```

Then call service endpoint with a valid `file_id` that exists in HANA:

```text
/{env}/parse/csv
/{env}/parse/html
```

Request body:

```json
{
  "file_id": "<existing-file-id>"
}
```

## HANA, Blob, ERP and CronJob Trace

This section tracks the real deployed architecture file-by-file and function-by-function.

### 1. Environment values

Environment variables are read in:

```text
code/backend/core/config.py
```

Important fields:

```text
hana_address
hana_port
hana_user
hana_password
db_name
db_collection
account_url
container_name
sas_token
ocr_pdf_url
ocr_csv_url
ocr_latam_csv_url
ocr_latam_html_url
ocr_erp_push_url
odata_url
TEMPLATE_PARSER_TEST_MODE
LOCAL_TEST_MODE
```

In Kubernetes these are not read from a `.env` file. They are injected through Helm deployment templates:

```text
helm/*/templates/deployment.yaml
```

Each deployment uses:

```yaml
envFrom:
  - configMapRef:
      name: {{ .Values.configmap.name }}
  - secretRef:
      name: {{ .Values.secret.name }}
```

For ingest, ConfigMap keys are defined in:

```text
helm/ocr-ingest-documents/templates/configmap.yaml
```

Current checked values include production-style URLs in:

```text
helm/ocr-ingest-documents/values.yaml
```

Before DEV/UAT deployment for CSV/HTML, add or configure:

```text
ocr_latam_csv_url
ocr_latam_html_url
TEMPLATE_PARSER_TEST_MODE=true
LOCAL_TEST_MODE=false
```

### 2. HANA connection

Connection code:

```text
code/backend/core/db/connection.py
```

Functions:

```text
connect_to_db()
close_connection()
```

Connection values come from `core/config.py`:

```text
HANA_ADDRESS
HANA_PORT
HANA_USERNAME
HANA_PASSWORD
```

### 3. HANA SQL query templates

Query templates are in:

```text
code/backend/core/db/queries.py
```

Important query constants:

```text
INSERT_INTO_DB_QUERY
SELECT_ALL_FROM_QUERY
UPDATE_QUERY_WITH_WHERE_CONDITION
GET_FILE_ID
DELETE_RECORDS
GET_SPECIAL_TEMPLATES
```

Important utility functions are in:

```text
code/backend/core/util.py
```

Functions:

```text
erp_data_fetch(connection, file_id)
hana_storage_push(file_id, connection, ocr_update_values)
read_file_from_object_store(file_name)
push_to_erp(url, file_id)
```

### 4. Ingest and Blob storage

Ingest entry point:

```text
code/backend/apps/ingest_documents/server.py
```

Main ingest implementation:

```text
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

Production algorithm:

```text
1. /{env}/ocr/ingest receives payload.
2. decode() reads base64 file_content.
3. get_file_type() determines pdf / spreadsheet / csv / html.
4. File is pushed to Azure Blob Storage.
5. HANA row is inserted with file metadata and file_path.
6. Parser URL is called with {"file_id": document_no}.
```

CSV/HTML parser URL selection:

```text
csv  -> ocr_latam_csv_url or ocr_latam_template_url
html -> ocr_latam_html_url or ocr_latam_template_url
```

### 5. CSV parser HANA + Blob path

File:

```text
code/backend/apps/csv_parser/csv_parse_handler.py
```

Real environment function:

```text
csv_parsing_flow(file_id)
```

Production algorithm:

```text
1. connect_to_db()
2. erp_data_fetch(connection, file_id)
3. Read hana_data["file_path"]
4. read_file_from_object_store(file_path)
5. parse_latam_csv(content, hana_data)
6. update_processed_values(final_output)
7. hana_storage_push(file_id, connection, update_values)
8. If TEMPLATE_PARSER_TEST_MODE=false, call push_to_erp(ocr_erp_push_url, file_id)
```

Local branch inside the same function:

```text
if config.local_test_mode:
    local_erp_data_fetch(file_id)
    local_read_file(file_path)
    local_hana_storage_push(...)
```

### 6. HTML parser HANA + Blob path

File:

```text
code/backend/apps/html_parser/html_parse_handler.py
```

Real environment function:

```text
html_parsing_flow(file_id)
```

Production algorithm:

```text
1. connect_to_db()
2. erp_data_fetch(connection, file_id)
3. Read hana_data["file_path"]
4. read_file_from_object_store(file_path)
5. parse_latam_html(content, hana_data)
6. update_processed_values(final_output)
7. hana_storage_push(file_id, connection, update_values)
8. If TEMPLATE_PARSER_TEST_MODE=false, call push_to_erp(ocr_erp_push_url, file_id)
```

### 7. ERP publish service

File:

```text
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

ERP endpoint comes from:

```text
odata_url
```

Important note:

```text
mock_push_to_erp() exists in this file but is not currently wired into the live publish flow.
```

For safe DEV/UAT parser validation, keep:

```text
TEMPLATE_PARSER_TEST_MODE=true
```

This prevents CSV/HTML parser handlers from calling the ERP push service.

### 8. Existing test-related project setup

The repo has Helm chart test manifests such as:

```text
helm/ocr-ingest-documents/templates/tests/test-connection.yaml
helm/ocr-excel-parser/templates/tests/test-connection.yaml
helm/ocr-pdf-parser/templates/tests/test-connection.yaml
helm/ocr-erp-push/templates/tests/test-connection.yaml
```

These are Helm/Kubernetes service connection tests. They are not application-level HANA/Blob parser tests.

Existing project test controls found:

```text
Helm ConfigMap/Secret injection for environment settings
Helm test-connection manifests
publish_to_erp_handler.mock_push_to_erp(), currently unused
```

New test controls added for this CSV/HTML work:

```text
LOCAL_TEST_MODE
TEMPLATE_PARSER_TEST_MODE
tools/debug_parse_local.py
tools/run_local_flow.py
core/local_test_storage.py
tests/test_latam_template_parser.py
```

### 9. Archival CronJob

Archival code and chart:

```text
code/backend/apps/archival/handler.py
helm/archival/templates/cronjob.yaml
helm/archival/values.yaml
```

The chart uses Kubernetes CronJob:

```yaml
apiVersion: batch/v1
kind: CronJob
```

It also receives environment values through ConfigMap and Secret:

```yaml
envFrom:
  - configMapRef:
      name: {{ .Values.configmap.name }}
  - secretRef:
      name: {{ .Values.secret.name }}
```

Before testing in DEV/UAT, confirm whether archival is enabled and what retention period is configured:

```text
ARCHIVE_PERIOD_DAYS
```

### 10. Client-side debug path with testing email

If the testing email ID feeds a DEV/UAT environment, the debug path is:

```text
1. Send CSV/HTML attachment to testing email.
2. Confirm ingest service receives attachment.
3. Confirm Blob file exists.
4. Confirm HANA row exists for file_id.
5. Copy file_id.
6. Set breakpoint in csv_parsing_flow() or html_parsing_flow().
7. Run parser service in VS Code or call existing service endpoint.
8. POST {"file_id": "<file_id>"} to /{env}/parse/csv or /{env}/parse/html.
9. Step through erp_data_fetch(), read_file_from_object_store(), parse function and hana_storage_push().
10. Review HANA erp_request_payload.
```

Use these flags for the first DEV/UAT pass:

```text
LOCAL_TEST_MODE=false
TEMPLATE_PARSER_TEST_MODE=true
```

Do not set `TEMPLATE_PARSER_TEST_MODE=false` until the payload has been approved.

## Current Safe Conclusion

The CSV/HTML parser logic and deployment packaging are present for the provided LATAM samples.

Before production use, complete the client-environment steps in:

```text
docs/csv_html_deployment_runbook.md
```

The remaining work is environment-specific:

```text
1. Set client registry and image tags.
2. Set client Kyma namespace and internal parser URLs.
3. Provision approved HANA and Blob Secrets.
4. Deploy to DEV/UAT with TEMPLATE_PARSER_TEST_MODE=true.
5. Verify HANA payload and Blob flow.
6. Obtain payload approval.
7. Enable ERP push only through the approved release process.
```
