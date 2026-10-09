# OCR Template and Region Onboarding: Development Through Deployment

Baseline inspected: `prod_replica_test`, 2026-10-08.

This is a standalone handover for adding a customer's template, supporting another
region, or introducing a parser service. It documents the current implementation,
not a promise that every workbook or external integration already works.
The user reports email configuration now works; independently validate each new
template through the acceptance gates below. Historical pod readiness and unit
tests do not establish business acceptance of a new template.

Verification performed while writing this guide:

- All relative file links resolve in this checkout.
- PowerShell examples, JSON examples, and embedded Python syntax were parsed.
- The offline XLSX example ran against a generated two-item workbook for US,
  EMEA, and LATAM, with outbound socket connections blocked. Both material IDs
  and quantities matched the generated input in each case.
- This did not test every customer layout, real email integration, live HANA/Blob,
  Docker builds, TLS provisioning, or SAP ERP acceptance. Deployment and live POST
  examples below are instructions, not operations executed to write this guide.

## Contents

1. [Safety and current environment](#1-safety-and-current-environment)
2. [Architecture and request contract](#2-architecture-and-request-contract)
3. [Decide which change is needed](#3-decide-which-change-is-needed)
4. [Collect the template requirements](#4-collect-the-template-requirements)
5. [Prepare branch and environment](#5-prepare-branch-and-environment)
6. [Add an XLSX template or region](#6-add-an-xlsx-template-or-region)
7. [Add PDF fields](#7-add-pdf-fields)
8. [Extend CSV or HTML](#8-extend-csv-or-html)
9. [Create a genuinely separate service](#9-create-a-genuinely-separate-service)
10. [Run locally without publishing](#10-run-locally-without-publishing)
11. [Debug in VS Code](#11-debug-in-vs-code)
12. [Tests and acceptance gates](#12-tests-and-acceptance-gates)
13. [Commit, build, and push images](#13-commit-build-and-push-images)
14. [Configure and deploy with Helm](#14-configure-and-deploy-with-helm)
15. [Connect Logic Apps and test once](#15-connect-logic-apps-and-test-once)
16. [Trace logs and troubleshoot](#16-trace-logs-and-troubleshoot)
17. [Rollback and handover](#17-rollback-and-handover)

## 1. Safety and Current Environment

- Namespace: `ocr-s4-dev`. Kubernetes context previously used: `sandbox-kmatzhj5`.
- Shared application Secret: `ocr`. Shared ConfigMap: `ocr-configmap`, owned by
  the ingest Helm release. Archival has its own `ocr-archival-configmap`.
- Runtime `env`: `dev`. Namespace name and runtime `env` are different concepts.
- Public ingest: `https://api.nonprod.ocr.monsterenergy.com/s4-dev/ocr/ingest`.
- Internal ingest: `/dev/ocr/ingest`. The public path is an additional route, not
  a replacement for internal routes.
- Public Ingress uses `Exact`: use the public path without a trailing slash.
- Authorizer currently accepts Basic authentication, not a Bearer token. It uses
  `api_auth_username` and `api_auth_password` from the namespace's Secret.
- Old `/dev/ocr/ingest` on the public hostname belongs to namespace `ocr`; the
  public `/qa/ocr/ingest` path belongs to `ocr-qa`. Do not redirect either.
- Current charts use Docker Hub repositories `vishalsunilpatil/*`. The historical
  image tag `s4-dev-0606` was reused during testing. Prefer a new immutable tag for
  every future release, and record the image digest.
- Current existing chart values were intentionally adapted for S4 DEV. Do not
  deploy them unchanged into production. Recheck files before every upgrade.
- A different namespace does NOT isolate a shared HANA collection or Blob
  container. Ensure the Secret points to approved DEV resources. Blob names use
  `env/region/file_name`, not the Kubernetes namespace, and uploads overwrite the
  same Blob name. Use unique test filenames as well as unique file IDs.
- Existing reference documents, email files, kubeconfig files, `.env` files, raw
  logs, and real customer data can contain secrets or personal information. Keep
  them out of commits unless explicitly approved and sanitized. Check ignore
  rules; do not assume every secret-file extension is ignored.
- Never edit `.venv/Lib/site-packages` to fix application behavior.

### Flags: exactly what they do

| Setting | CSV/HTML behavior |
| --- | --- |
| `LOCAL_TEST_MODE=true` | Parser flow uses local manifest/files; no HANA, Blob, or ERP in that branch. |
| `LOCAL_TEST_MODE=false`, `TEMPLATE_PARSER_TEST_MODE=true` | Real HANA and Blob; CSV/HTML skip calling ERP-push. Still writes real data. |
| Both `false` | Real HANA/Blob and CSV/HTML can call ERP-push. |

**PDF, XLSX, and ingest are NOT globally disabled by these flags.** The current PDF
and Excel flows call ERP-push directly. For safe offline XLSX work use section 10's
pure transformation steps or mocks, not `excel_parsing_flow()` with real credentials.
The test flags are not enforced as a global authorization rule by ERP-push itself.

Do not trigger archival as a test: its handler is designed to DELETE old HANA
records. Its debug Deployment sleeps, so a Running archival pod proves very little.
See the specific archival gaps in section 14.

## 2. Architecture and Request Contract

```text
Mailbox -> Logic App -> [optional BTP integration] -> HTTPS Ingress
    -> S4 DEV authorizer checks Basic authentication
    -> ingest API validates MIME type and decodes attachment Base64
    -> original email + attachment uploaded to Azure Blob
    -> HANA metadata row recorded with file_id and storage paths
    -> appropriate parser called with {"file_id": "..."}
    -> parser reads HANA + Blob, extracts/maps fields
    -> normalized ERP payload and PO identifiers saved in HANA
    -> ERP-push reads payload + original email
    -> SAP OData request (including CSRF handling)
```

PDF extraction uses SAP Document Information Extraction (DOX). XLSX uses
`openpyxl`; CSV uses Python `csv`; HTML uses Python `HTMLParser` and template rules.
The latter three do not need a new SAP DOX schema just to recognize source fields.

### Main file ownership

| File | Change here when... |
| --- | --- |
| [ingest server](../code/backend/apps/ingest_documents/server.py) | Changing API admission, public alias registration, or API response handling. |
| [ingest handler](../code/backend/apps/ingest_documents/ocr_ingest_doc.py) | Changing decoding, attachment/email storage, MIME classification, or parser selection. |
| [constants](../code/backend/core/constants.py) | Adding MIME types, extension-related constants, or documented region identifiers. |
| [config](../code/backend/core/config.py) | Adding runtime environment variables needed by code. |
| [Blob helper](../code/backend/core/azure_storage/blob_storage_connection.py) | Changing shared upload/download behavior. Current fix flushes temporary files and rejects empty uploads. |
| [shared utilities](../code/backend/core/util.py) | HANA fetch/update, reading stored bytes, calling ERP-push. |
| [query templates](../code/backend/core/db/queries.py) | SQL query shape changes; review escaping/parameterization and DB schema impact. |
| [ERP publisher](../code/backend/apps/publish_to_erp/publish_to_erp_handler.py) | Dispatching new formats, adapting stored payload shape, attaching email, handling OData responses. |
| [ingest values](../helm/ocr-ingest-documents/values.yaml) | Shared URLs, schemas, flags, environment, public route, image settings. |
| [shared ConfigMap template](../helm/ocr-ingest-documents/templates/configmap.yaml) | Exposing new values as environment variables to services. A values entry alone does not inject it. |

### Email ingest request

This example shows structure only. Replace all example values with approved test
data; do not submit the placeholder strings.

```json
{
  "file_id": "unique-test-id",
  "region": "LATAM",
  "data": {
    "file_name": "unique-test-id.html",
    "file_type": "text/html",
    "file_content": "BASE64_OF_ATTACHMENT_BYTES",
    "sender_email": "approved-test-sender@example.com",
    "eml_data": "RAW_ORIGINAL_EMAIL_TEXT_NOT_BASE64"
  }
}
```

`eml_data` must represent the original MIME email, ideally containing the same
attachment. Do not rename Outlook `.msg` to `.eml`, invent an email path, or send
Base64 in `eml_data`. Ingest creates `eml_file_path`; the ERP publisher requires it.
Handling arbitrary legacy email encodings needs testing because ingest encodes
the supplied email string as UTF-8 before storage.

### Stored payload shape

- PDF stores a single ERP header object.
- XLSX stores an envelope keyed by PO/sheet identifier, with header/item/metadata
  objects inside each entry.
- HTML stores `{CustPo: record}`; CSV currently stores `{MASSCREATION: record}`.
- The existing `excel_call_to_erp()` iterates non-PDF envelope entries and sends
  each record. Do not send the whole envelope as one header object or add an extra
  envelope layer.
- `NavHeadToItem` holds items. `NavHeadtoMeta` holds metadata. Their casing differs
  deliberately; keep the exact ERP field names.
- The publisher adds Base64 email bytes as `NavHeadtoMeta[0].Content`.

## 3. Decide Which Change Is Needed

| Requirement | Preferred change | New service? |
| --- | --- | --- |
| Another XLSX layout with recognizable labels | Existing Excel mapping tables and template-specific transformations | Usually no |
| Existing field appears under another column heading | Add normalized anchor and mapping, scoped to the template/region if ambiguous | No |
| XLSX field changes meaning for one region/customer | Region/template-specific mapping and tests | Usually no |
| New PDF extracted field | SAP DOX schema plus PDF mappings; optional scoped transform | No |
| Another HTML/CSV layout | Deterministic template selection inside existing parser, or explicit rejection | Usually no |
| Different file format or independent dependencies/scaling/ownership | New parser with explicit ingest dispatch, Dockerfile, chart, and tests | Possibly |

**Do not create a Kubernetes namespace or Docker service per customer template by
default.** First extend the existing format parser conservatively.

One MIME type cannot distinguish two XLSX templates. If a separate XLSX service
is genuinely required, add an explicit region/template dispatcher; merely adding
a new URL/chart leaves all spreadsheets routed to the existing `ocr_csv_url`.
Template recognition should use stable sheet names/required headers or an approved
metadata identifier, not a guess based only on filename or the first populated cell.

## 4. Collect the Template Requirements

Get written answers before changing code:

- Region, customer, template identifier/version, and whether existing layouts must
  remain compatible.
- At least two valid source files, original `.eml` examples, and edge-case samples.
- Approved expected JSON for each source, including all lines, types, field casing,
  grouping into purchase orders, metadata, and fields intentionally omitted.
- For every field: exact source label, header or item location, target ERP name,
  required/optional, normalization, default, and failure behavior.
- Whether IDs are text (leading zeros!), dates are day-first/month-first, decimal
  conventions, currency, UOM, quantity, and repeated/merged header behavior.
- Rules for multiple sheets/POs, hidden/summary rows, subtotals, duplicate items,
  blank quantities, formulas, and unsupported layouts.
- Whether `MASSCREATION`, `CountryTemplate`, `SoldTo`, `ShipTo`, price/tax fields,
  and fixed sender metadata are actually required for THIS template.
- Target DEV resources, ERP owner/test permission, and expected OData response.

Example requirement worksheet (illustration, not an implemented rule):

| Source header | Location | ERP field | Scope | Required | Rule |
| --- | --- | --- | --- | --- | --- |
| `Product Code` | Item | `Material` | customer template v2 | Yes | Preserve as text, including leading zeros |
| `Requested Qty` | Item | `Quantity` | customer template v2 | Yes | Confirm decimal/zero behavior |
| `Requested Delivery Date` | Header | `DlvDate` | approved region | Yes | Convert agreed format to YYYY-MM-DD |

Approve the expected JSON BEFORE writing tests; tests that only mirror the code
are not independent proof of correctness.

## 5. Prepare Branch and Environment

### Branch safety (PowerShell, repository root)

```powershell
git status --short --branch
git fetch origin
git branch -r
```

Resolve or preserve uncommitted work deliberately; do not reset it. Agree on the
base branch. `origin/feature/prod` and `origin/prod_replica_test` are NOT equivalent:
the replica contains the added services/fixes and S4 DEV deployment configuration.
Do not merge the entire earlier LATAM branch to pick up a single mapping.

Example after agreeing to extend the existing integration branch:

```powershell
git switch -c feature/new-xlsx-template origin/prod_replica_test
```

### Local Python setup (PowerShell)

Use Python 3.12, matching the Dockerfiles. Some source f-strings need 3.12 syntax;
older Python may fail even before parser logic runs. Prefer an existing `.venv`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\code\dependencies\requirements.txt
.\.venv\Scripts\python.exe --version
```

Run environment creation only if needed, not over an environment you want to keep.
Direct `.venv` executable commands avoid PowerShell activation policy problems.
The current regression tests use `unittest`; pytest is not required.

## 6. Add an XLSX Template or Region

### Step 6.1: Understand this branch, not another branch

Inspect these three files:

- [auxiliary_data.py](../code/backend/apps/excel_parser/auxiliary_data.py)
- [excel_parse_handler.py](../code/backend/apps/excel_parser/excel_parse_handler.py)
- [post_processing.py](../code/backend/apps/excel_parser/post_processing.py)

In the inspected production-based version, `tabular_keys` defines `EMEA` and
`Other`. `regional_map_lvl1` and `regional_map_lvl2` have EMEA overrides.
`region_specific_tabular_transforms()` has an EMEA branch. **Do not assume the
extra LATAM/ARCA/Propimex logic from the older LATAM feature branch is present.**
US and LATAM currently fall back to `Other` for tabular keys unless you extend it.

The actual pipeline is:

```text
excel_parsing_flow(file_id)
  erp_data_fetch -> region from HANA (default US when key absent)
  read_file_from_object_store -> openpyxl.load_workbook(data_only=True)
  parse_data -> sheet_traversal -> erp_field_mapping
  get_tabular_keys_instance -> extract_header_data + extract_tabular_data
  post_processing_transformations -> extract_po_numbers -> apparels_form_check
  update_processed_values -> hana_storage_push -> push_to_erp
```

### Step 6.2: Add source labels and field mappings

In `auxiliary_data.py`, update only the applicable sections:

| Section | What it controls |
| --- | --- |
| `keys` | Recognized source labels/anchors. Unrecognized labels are not traversed. |
| `data_mapping` | Common normalized source label -> ERP/intermediate field name. |
| `data_dimensions` | Header value extraction: `singular`, `possible_singular`, `date_type`, etc. Inspect actual handling before inventing categories. |
| `multi_valued` | Scanning continuation behavior for selected source labels. |
| `directional_biases` | Read right/below for a source label where needed. |
| `non_columnar_entry_keys` | Offset lookup for exceptional layouts; boundary-test any additions. |
| `tabular_keys` | Which mapped fields belong to the line-item table, anchored by `Material`. Other fields can become headers instead. |
| `regional_map_lvl1` | Region override applied BEFORE the common mapping. |
| `regional_map_lvl2` | Mapping used by explicit regional post-processing code; a dictionary entry alone does not activate a new branch. |

`transform_string()` removes spaces and newline characters. It does NOT normalize
case, punctuation, or accents. For example, `Product Code` becomes `ProductCode`,
not `PRODUCTCODE`. Put the actual normalized label in `keys` and mappings.
Adding a mapping without a corresponding recognized anchor may have no effect.

Example intended edits after business approval:

```python
# Illustrative entries to integrate into the existing dictionaries, not replacements.
data_mapping["ProductCode"] = "Material"
data_mapping["RequestedQty"] = "Quantity"
```

Also add `ProductCode` and `RequestedQty` to `keys`. Review scanning rules for the
new quantity label and ensure mapped item fields are in the selected `tabular_keys`.
For region-only semantics, prefer a scoped override over changing a common label
used by existing customers. For customer-only differences WITHIN one region,
region branching alone is insufficient: select a specific template first.

### Step 6.3: Add scoped transformations only if required

In `post_processing.py`, use `region_specific_tabular_transforms(region, item)`
for item rules and the existing header/post-processing functions for header rules.
If adding a new region mapping in `regional_map_lvl2`, add the matching branch in
this function and test that it is invoked. Preserve EMEA and US behavior.

Do not globally reinterpret `Quantity`, `Uom`, or `Material` to fix one customer.
Inspect `special_quantity_transforms()`, `convert_date_format()`, and
`process_bill_and_ship_to()` when those specific outputs are wrong.

### Step 6.4: Check common workbook traps

- `data_only=True` reads cached formula values; openpyxl does not calculate Excel
  formulas. Ask for a workbook recalculated and saved in Excel when caches are absent.
- Material/PO cells stored as numbers may already have lost leading zeros. A
  string cast cannot reliably restore the original identifier without a rule.
- Merged cells generally store a value only in the anchor cell. Test actual layout.
- `extract_tabular_data()` depends on a recognized `Material` anchor and aligned
  field occurrences. Missing anchors or uneven column occurrences can fail.
- Some sheets are skipped and exceptions collected in `failed_sheets`; that list
  is not a robust business failure status. Explicitly check no expected sheet is lost.
- `final_output` is keyed by PO/sheet identifier: test repeated PO keys across
  sheets for overwritten records rather than assuming automatic merging.
- Zero/blank quantity handling and multi-sheet failures need dedicated tests.
- `application/vnd.ms-excel` currently routes to CSV. It is not support for binary
  `.xls`; openpyxl supports `.xlsx`/`.xlsm`, not legacy `.xls` files.

### Step 6.5: Add a truly new region

1. Confirm exact uppercase identifier with the integration owner.
2. Review `SUPPORTED_REGIONS` in `core/constants.py`; updating it alone does NOT
   implement validation or extraction. Trace every consumer.
3. Ensure Logic Apps sends the region into the ingest payload and HANA metadata.
4. Add workbook mappings/transforms and regression cases for that region.
5. Only if PDF is also supported, add its DOX schema/config selection separately.
6. Confirm ERP accepts the region and output fields. Do not assume simply adding
   `Region` to a payload is always required or accepted by the ERP contract.

Usually no API route, Dockerfile, Helm Service, or new namespace is required for
an additional XLSX template. Rebuild the Excel image for its changed source.

## 7. Add PDF Fields

Files:

- [PDF mappings](../code/backend/apps/pdf_parser/mappings.py): `header_data`,
  `line_item_data`, and confidence `metadata` mappings.
- [PDF handler](../code/backend/apps/pdf_parser/pdf_parse_handler.py):
  `get_schema_id()`, `output_formatter()`, `process_region_specific_data()`,
  `output_filtering()`, and `metadata_formatter()`.
- [config](../code/backend/core/config.py), [ingest values](../helm/ocr-ingest-documents/values.yaml),
  and [ConfigMap](../helm/ocr-ingest-documents/templates/configmap.yaml): region
  schema IDs and SAP endpoints.

Sequence:

1. Have the SAP DOX owner configure the field in the correct region schema.
2. Obtain actual `headerFields`/`lineItems` extraction JSON, not guessed names.
3. Map exact names/casing to ERP fields. Examples already added are
   `soldToCountry -> CountryTemplate` and item `itemDeliveryDate -> DlvDate`.
4. Fields absent from mapping tables are dropped by `output_filtering()`.
5. LATAM-only/customer-only rules require explicit scope. Shared mapping tables
   are not automatically limited to LATAM just because that region requested a field.
6. The current special PDF transformation is US-specific. Adding a LATAM branch
   must account for the existing early return for non-US data.
7. Check collisions: `documentDate` and `itemDeliveryDate` both map to item
   `DlvDate`. If both arrive, do not assume the intended precedence without testing.
8. Test raw extraction -> mapped output offline; mock DOX/HANA/Blob/ERP for flow
   tests. Rebuild PDF for code changes. Schema-value-only changes need config rollout,
   not a Python rebuild.

SAP service URLs/schema IDs are external tenant configuration. Changing a
Kubernetes namespace does not create, copy, or grant access to a SAP schema.

## 8. Extend CSV or HTML

| File | Relevant sections |
| --- | --- |
| [CSV mappings](../code/backend/apps/csv_parser/mappings.py) | `COLUMN_ALIASES`, `OPTIONAL_COLUMNS`, mass-creation constants and metadata defaults. |
| [CSV handler](../code/backend/apps/csv_parser/csv_parse_handler.py) | Decode/delimiter/header matching, `transform_csv_rows()`, `parse_latam_csv()`, stored envelope, `csv_parsing_flow()`. |
| [HTML mappings](../code/backend/apps/html_parser/mappings.py) | Item-header markers and defaults. |
| [HTML handler](../code/backend/apps/html_parser/html_parse_handler.py) | Encoding, `TableTextParser`, `extract_between()`, `extract_items()`, `parse_latam_html()`, envelope, `html_parsing_flow()`. |

Do not make every region use LATAM rules merely because the input is CSV/HTML.
Ingest currently routes by file type; the parsers themselves must choose/reject
templates or an approved dispatcher must be added.

Current business decisions to re-confirm for another template:

- CSV creates one `MASSCREATION` record with each source row retained as an item;
  CSV `po_numbers` therefore uses the envelope key, not necessarily actual PO IDs.
- CSV metadata has a fixed `CustEmail` and Excel-style MIME type. This is tested
  behavior, not a universal requirement for every sender/customer.
- HTML omits prices/totals by its current contract and retains formatted quantity
  text. Do not add/remove ERP fields without reviewing the expected payload.
- The current HTML parser can return `UNEXTRACTED` with no items instead of raising
  an error. Tests must reject that as a successful business extraction; add scoped
  validation/failure handling when implementing the next template.
- The exact original HTML attachment tested locally decoded its accents correctly;
  the repository sample contains replacement characters. Do not reconstruct lost
  text by guessing, and do not diagnose file encoding from a chat preview alone.

## 9. Create a Genuinely Separate Service

Only choose this when section 3 justifies it. For a proposed `new_parser`:

1. Create an application package under `code/backend/apps/new_parser/` with a pure
   bytes-to-payload function, format mappings, and an I/O orchestration function.
2. Use [CSV server](../code/backend/apps/csv_parser/server.py) or
   [HTML server](../code/backend/apps/html_parser/server.py) as the local pattern:
   FastAPI POST accepts `file_id`, GET `/` supports probes, `env` defines route prefix.
3. Reuse shared HANA/Blob helpers. Handle connection closure, extraction failures,
   and HTTP failure propagation explicitly; avoid duplicating known defects.
4. Define the stored envelope and ensure the ERP publisher accepts it. Update both
   ingress MIME admission and ERP dispatch for a new format; either alone is incomplete.
5. Add a config URL field, Helm value, and ConfigMap entry. Wire ingest selection
   to that field. For same-MIME templates, define how the dispatcher distinguishes them.
6. Add a Dockerfile under `build/`, starting from the CSV/HTML pattern; copy the
   new package plus `core`, main, logging config, and requirements. Set
   `FAST_API_APP_PATH=apps.new_parser.server:app`. Do not include test data/secrets.
7. Add a chart under `helm/` using a neighboring parser chart: values, Chart,
   helpers, Deployment, Service, service account, and connection test. Ensure all
   helper names/labels/app paths are renamed consistently.
8. Match Service selector labels to pod labels and service `targetPort` to container
   `http`/8000. Render the Service name before using it in an ingest URL.
9. Inject shared Secret/ConfigMap, set correct image/pull secret, and test probes
   against actual routes. Some older servers do not define GET `/`; verify live
   image behavior instead of assuming every older probe is correct.
10. Unit-test parser, API admission, dispatcher, storage envelope, and ERP dispatch.
    Then follow sections 13-15. Do not expose every parser publicly; normally only
    ingest needs the authenticated public endpoint.

The current CSV/HTML helpers always concatenate release name + chart name. That
explains doubled Service names. Older charts avoid duplication when the release
already includes the chart name. Copying a chart without checking this breaks DNS.

## 10. Run Locally Without Publishing

All commands below start from the repository root. Do not use actual customer
files in public output. Local JSON can include personal/order data.

### Pure HTML and CSV parsing (PowerShell)

```powershell
.\.venv\Scripts\python.exe -B tools\debug_parse_local.py --type html --file "sample_inputs\latam\html\OCBD0125252.html"
.\.venv\Scripts\python.exe -B tools\debug_parse_local.py --type csv --file "sample_inputs\latam\csv\Cargas Masivas_20-07-2026_Loginsa.csv"
```

[debug_parse_local.py](../tools/debug_parse_local.py) supports only HTML and CSV.
It calls pure parsers, not HANA/Blob/ERP. A printed JSON object is not automatically
correct: compare every agreed field, type, line count, and identifier to expected JSON.

### Simulated CSV/HTML full flow (PowerShell)

Use a dedicated local terminal and explicitly override inherited flags:

```powershell
$env:LOCAL_TEST_MODE = "true"
$env:TEMPLATE_PARSER_TEST_MODE = "true"
.\.venv\Scripts\python.exe -B tools\run_local_flow.py --type html --file "sample_inputs\latam\html\OCBD0125252.html" --region LATAM
.\.venv\Scripts\python.exe -B tools\run_local_flow.py --type csv --file "sample_inputs\latam\csv\Cargas Masivas_20-07-2026_Loginsa.csv" --region LATAM
```

[run_local_flow.py](../tools/run_local_flow.py) uses `setdefault`, so an already-set
`LOCAL_TEST_MODE=false` would defeat its default. That is why the explicit assignment
above matters. It creates a local manifest/output under `tools/local_test_storage`
unless `LOCAL_TEST_STORAGE_DIR` overrides it. It does not exercise HTTP, Azure, HANA,
or SAP. Close this local test terminal afterward to avoid reusing unintended flags.

### Offline XLSX pipeline (PowerShell; no live flow function)

There is no existing XLSX option in those two CLI tools. This executable inspection
snippet calls only workbook reading and transformation functions. It intentionally
does NOT call `excel_parsing_flow()`, `connect_to_db()`, or `push_to_erp()`.
The region must match your sample; choose a sanitized fixture and compare the result.

```powershell
$env:SAMPLE_XLSX = (Resolve-Path (Read-Host "Path to approved XLSX sample")).Path
$env:SAMPLE_REGION = Read-Host "Region, for example EMEA, US or LATAM"
@'
import json
import os
import sys
from pathlib import Path
import openpyxl

sys.path.insert(0, str(Path.cwd() / "code" / "backend"))
from apps.excel_parser import excel_parse_handler as handler
from apps.excel_parser import post_processing
from apps.excel_parser.auxiliary_data import keys

path = Path(os.environ["SAMPLE_XLSX"])
region = os.environ["SAMPLE_REGION"].strip().upper()
assert path.stat().st_size > 0, "Workbook is empty"
metadata = {
    "file_name": path.name,
    "file_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "sender_email": "offline-test@example.com",
    "created_at": "2026-10-08",
    "region": region,
}
workbook = openpyxl.load_workbook(path, data_only=True)
try:
    workbook_data = handler.parse_data(workbook)
finally:
    workbook.close()
output = {}
for sheet_name, sheet in workbook_data.items():
    parsed = handler.sheet_traversal(sheet, keys)
    if not parsed:
        print("NO RECOGNIZED ANCHORS:", sheet_name)
        continue
    mapped = handler.erp_field_mapping(parsed, region)
    table_keys = handler.get_tabular_keys_instance(region, mapped)
    headers = handler.extract_header_data(mapped, table_keys)
    items = handler.extract_tabular_data(mapped, table_keys)
    headers, items, meta = post_processing.post_processing_transformations(
        headers, items, handler.po_key, metadata, region
    )
    assert items, f"No line items extracted from {sheet_name}"
    po_number = handler.extract_po_numbers(headers, items, sheet_name)
    headers = post_processing.apparels_form_check(sheet_name, region, headers)
    assert po_number not in output, f"Duplicate output key: {po_number}"
    output[po_number] = {**headers, "NavHeadToItem": items, "NavHeadtoMeta": meta}
assert output, "No extractable workbook sheets"
print(json.dumps(output, indent=2, ensure_ascii=True, default=str))
'@ | .\.venv\Scripts\python.exe -B -
```

This inspection wrapper deliberately fails on empty/duplicate output rather than
silently treating it as a success. It is not a replacement production parser.
For repeatable debugging, put this logic into a focused test/helper under the repo's
`tests` or `tools` conventions when you implement the actual new XLSX feature.

### Local API startup (does not itself submit data)

Run only with test-safe configuration in a dedicated terminal:

```powershell
$env:PYTHONPATH = "$PWD\code\backend"
$env:env = "dev"
$env:LOCAL_TEST_MODE = "true"
$env:TEMPLATE_PARSER_TEST_MODE = "true"
.\.venv\Scripts\python.exe -m uvicorn apps.html_parser.server:app --host 127.0.0.1 --port 8001
```

Use `/docs` or `/openapi.json` to inspect routes. The CSV app is
`apps.csv_parser.server:app`. Local flow APIs require a file_id registered in the
local manifest first. Do not POST arbitrary file IDs and expect local files to be
found. Starting PDF/Excel APIs locally does not make their processing safe/offline;
mock I/O or use the pure pipeline above. Stop the server with Ctrl+C.

## 11. Debug in VS Code

1. Open this repository, install/select the Python and Python Debugger extensions.
2. Run `Python: Select Interpreter`; select this repository's `.venv` Python 3.12.
3. Start with `tools/debug_parse_local.py` for HTML/CSV or the new offline XLSX test.
4. Set breakpoints at the owning transformation and inspect input before patching.
5. Use F10 to step over, F11 to enter a function, Shift+F11 to step out, and F5 to continue.

Optional launch configuration to merge into `.vscode/launch.json` if you choose to
create/update it. This guide does not create that file. Keep any existing entries.

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "HTML parser - offline",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/tools/debug_parse_local.py",
      "cwd": "${workspaceFolder}",
      "console": "integratedTerminal",
      "args": ["--type", "html", "--file", "${workspaceFolder}/sample_inputs/latam/html/OCBD0125252.html"],
      "env": {"LOCAL_TEST_MODE": "true", "TEMPLATE_PARSER_TEST_MODE": "true"},
      "justMyCode": true
    },
    {
      "name": "Repository tests - mocked I/O",
      "type": "debugpy",
      "request": "launch",
      "module": "unittest",
      "args": ["discover", "-s", "tests", "-p", "test_*.py"],
      "cwd": "${workspaceFolder}",
      "console": "integratedTerminal",
      "env": {"PYTHONPATH": "${workspaceFolder}/code/backend"},
      "justMyCode": true
    }
  ]
}
```

Suggested breakpoints and watch values:

| Stage | Functions / values to inspect |
| --- | --- |
| XLSX recognition | `transform_string`, `sheet_traversal`; cell text, `keys`, `parsed_data`, sheet name. |
| XLSX mapping | `erp_field_mapping`; `region`, selected regional mapping, `mapped_data`. |
| XLSX extraction | `extract_header_data`, `extract_tabular_data`; selected tabular keys, Material anchor, item counts. |
| XLSX normalization | `post_processing_transformations`; dates, quantities, UOM, header/item PO placement. |
| CSV | Header names, chosen delimiter, resolved column mapping, each source row and output item. |
| HTML | Decoded text, `parser.tables`, header markers, `po_number`, extracted items. |
| Ingest (mocked first) | Decoded `len(file_content)`, normalized MIME, `parser_url`, unique paths. |
| Blob (mocked first) | Flush occurs, on-disk size is nonzero, upload receives all bytes. |
| ERP (mocked first) | HANA envelope, `eml_file_path`, dispatched record, status and failures. |

Never log Secret values, Basic headers, SAS query strings, or full customer documents
in shared debugging output. Inspect lengths/hashes/field names when possible.

## 12. Tests and Acceptance Gates

Current tests:

- [parser contracts](../tests/test_latam_template_parser.py)
- [ingest routes/requests and Blob upload](../tests/test_ingest_parser_request.py)
- [ERP MIME dispatch](../tests/test_publish_to_erp_dispatch.py)

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py"
```

Add focused new XLSX/template tests; current CSV/HTML tests are not Excel coverage.
Use `unittest.mock` for DB, Blob, requests, and OData. Keep a real pure-parser test
with a sanitized workbook so mocks do not hide extraction defects.

Required test matrix:

- Golden expected JSON for approved samples, including every item and field type.
- Existing EMEA/US/LATAM examples remain unchanged where required.
- New template selected correctly; unknown template rejected or reported clearly.
- Empty bytes, missing columns/Material/PO/date, invalid dates, malformed input.
- Multiple sheets/POs, duplicate PO keys, blank/zero quantities, leading-zero IDs,
  merged cells, formulas without cache, alternate encoding/delimiter if applicable.
- Storage envelope matches ERP consumer; original email exists for live publishing.
- Supported MIME aliases and octet-stream extension classification route correctly.
- No ERP call in the CSV/HTML test branch; mocked success/failure in publish mode.
- Parser rejection/ERP failure visible to caller, not just an HTTP 200 assertion.

Gate sequence: pure tests -> mocked flow -> local Docker startup/route check ->
Helm render -> approved DEV full flow -> ERP/business acceptance -> promotion.
Do not skip gates because pods are green or Helm says `deployed`.

## 13. Commit, Build, and Push Images

### Local Windows versus Codespaces

| Task | Shell/location |
| --- | --- |
| Edit, tests, git commit/push | Local PowerShell repository root |
| Docker build/push | Codespaces Bash `/workspaces/asop-ocr`, or a machine with working Docker |
| Helm/kubectl | Connected PowerShell terminal with intended kubeconfig |

Windows working files are NOT automatically available in Codespaces. Commit/push
them, then pull the same branch before building. Do not run `git add .` blindly.

Example for an Excel-only change (adjust explicit files to the actual change):

```powershell
git status --short --branch
git add code/backend/apps/excel_parser/auxiliary_data.py code/backend/apps/excel_parser/post_processing.py
git diff --cached --stat
git diff --cached
git commit -m "Add approved XLSX template mapping"
git push -u origin HEAD
```

Include the relevant new regression tests and approved fixtures explicitly. Do
not include `.venv`, bytecode, local `.eml`/logs, kubeconfig, or unrelated edits.
If `git diff --cached --stat` is empty, check whether changes are already committed
before trying another commit. Preserve any existing staged work deliberately.

### Which images need rebuilding?

| Changed code | Required image(s) |
| --- | --- |
| Excel mappings/handler/post-processing only | Excel |
| PDF mappings/handler only | PDF |
| HTML or CSV parser only | Corresponding parser |
| Ingest dispatch/API/public alias | Ingest |
| ERP MIME dispatch or payload publishing | ERP-push |
| Shared `core` or requirements | Review every consuming image; rebuild all affected consumers. |
| Helm values only | Usually no image rebuild; upgrade chart/restart affected pods as appropriate. |
| Runbook/test-only edits | No runtime image change needed. |

The prior Blob flush hotfix was rolled into ingest because ingest uploads files.
Other images do not automatically receive shared source edits merely because one
image was rebuilt. When releasing a complete consistent stack, rebuild all images
from the same reviewed source commit.

### Codespaces Bash: one changed service

After switching to your actual feature/release branch and confirming a clean tree:

```bash
git pull --ff-only
git status --short --branch
git log -1 --oneline
docker login --username vishalsunilpatil
TAG="s4-dev-$(git rev-parse --short HEAD)"
docker build -f build/Dockerfile.excel-parser -t "vishalsunilpatil/ocr-excel-parser:$TAG" .
docker push "vishalsunilpatil/ocr-excel-parser:$TAG"
docker manifest inspect "vishalsunilpatil/ocr-excel-parser:$TAG" >/dev/null
echo "$TAG"
```

Run each command only after the previous succeeds. For the registry password
prompt, enter a Docker Hub token with write permission directly in the terminal;
never put it in the command, repository, screenshot, or chat.

Repository root `.` is essential: Dockerfiles copy `code/...` relative to that
context, not the `build` folder. Match image architecture to Kubernetes nodes;
specify `--platform linux/amd64` only when those are the target nodes (or build the
required multi-platform image). Do not overwrite a tag used by another deployment.

### Image/build/chart map for all services

| Dockerfile | Docker Hub repository | Chart directory | Expected Helm release |
| --- | --- | --- | --- |
| `build/Dockerfile.ingestdoc` | `vishalsunilpatil/ocr-ingest-doc` | `helm/ocr-ingest-documents` | `aiops-ocr-ingest-documents` |
| `build/Dockerfile.pdfparse` | `vishalsunilpatil/ocr-pdf-parse` | `helm/ocr-pdf-parser` | `aiops-ocr-pdf-parser` |
| `build/Dockerfile.excel-parser` | `vishalsunilpatil/ocr-excel-parser` | `helm/ocr-excel-parser` | `aiops-ocr-excel-parser` |
| `build/Dockerfile.csv-parser` | `vishalsunilpatil/ocr-csv-parser` | `helm/ocr-csv-parser` | `aiops-ocr-csv-parser` |
| `build/Dockerfile.html-parser` | `vishalsunilpatil/ocr-html-parser` | `helm/ocr-html-parser` | `aiops-ocr-html-parser` |
| `build/Dockerfile.erp-push` | `vishalsunilpatil/ocr-erp-push` | `helm/ocr-erp-push` | `aiops-ocr-erp-push` |
| `build/Dockerfile.authorizer` | `vishalsunilpatil/ocr-authorizer` | `helm/authorizer` | `aiops-ocr-authorizer` |
| `build/Dockerfile.archival` | `vishalsunilpatil/ocr-archival` | `helm/archival` | `aiops-ocr-archival` |

To build another service, substitute its Dockerfile/repository in the one-service
commands. Building all eight is unnecessary for an Excel-only mapping change.

If the same tag MUST be reused: confirm no other environment uses it, push first,
then restart only the affected Deployment with `imagePullPolicy: Always`. Helm
may not roll pods if the pod template did not change. Record old/new digests;
rollback by tag is unreliable once that tag is overwritten.

## 14. Configure and Deploy With Helm

### Step 14.1: Connect to the intended cluster

PowerShell; replace the kubeconfig path if your machine differs:

```powershell
$env:KUBECONFIG = "C:\Users\vpatil14\Downloads\kubeconfig.yaml"
kubectl config current-context
kubectl cluster-info
kubectl get namespace ocr-s4-dev
kubectl get secret ocr -n ocr-s4-dev
helm list -n ocr-s4-dev
```

`$env:KUBECONFIG` is per terminal. A new terminal may revert to localhost:8080.
Use `kubectl --kubeconfig "C:\path\kubeconfig.yaml" ...` for explicit one-off commands.
Never share the kubeconfig contents. A context name alone does not prove the
cluster endpoint is correct; confirm ownership with the platform team.

### Step 14.2: Configuration ownership and namespace consistency

Update the appropriate existing `helm/<chart>/values.yaml` as previously requested
for this branch. Keep other environments' deployments untouched. Check these fields:

- `image.repository`, `image.tag`, `image.pullPolicy`, `imagePullSecrets`.
- Service `port`/container named port, expected Service fullname and namespace.
- Secret/ConfigMap names, `env`, URL keys, flags, and replica/resources settings.
- Ingest public path and authenticated TLS Ingress, only if its routing changes.

`imagePullSecrets: []` means the chart does not supply registry credentials. Private
images require an approved pull secret/service-account/node credential setup.
Credentials are namespace-scoped; logging into Docker locally does not authenticate
cluster nodes. Verify the CronJob template separately for pull-secret support.

`env` in most parser chart values is not independently injected; containers use the
shared ConfigMap plus Secret through `envFrom`. Set the runtime environment in the
ingest-owned ConfigMap. Explicit Deployment env settings override envFrom, and a
Secret key can override a ConfigMap key depending on ordering. Never dump all pod
environment variables to troubleshoot; that prints credentials.

Expected internal URLs (all use `http`, port `8000` and `.ocr-s4-dev.svc.cluster.local`):

| Value | Service | Path |
| --- | --- | --- |
| `ocr_pdf_url` | `aiops-ocr-pdf-parser` | `/dev/parse/pdf` |
| `ocr_csv_url` (legacy name means Excel) | `aiops-ocr-excel-parser` | `/dev/parse/excel` |
| `ocr_latam_csv_url` | `aiops-ocr-csv-parser-ocr-csv-parser` | `/dev/parse/csv` |
| `ocr_latam_html_url` | `aiops-ocr-html-parser-ocr-html-parser` | `/dev/parse/html` |
| `ocr_erp_push_url` | `aiops-ocr-erp-push` | `/dev/ocr/erp-push` |
| Ingress auth URL | `aiops-ocr-authorizer` | `/dev/ocr/auth` |

`ocr_latam_template_url` is an optional fallback; blank is intentional when both
dedicated parser URLs are set. The final SAP OData URL comes from `odata_url` in
the Secret, not `ocr_erp_push_url` (which points to our internal publisher).

Some older chart values contain unused external `urls` sections. Inspect templates:
the actual shared runtime configuration comes from ingest's ConfigMap, not every
chart's similarly named defaults. SAP endpoints/region schema IDs require tenant
owner confirmation and are not inferred from namespace naming.

### Step 14.3: Check a changed chart locally

Excel example, after editing its image tag to the newly pushed value:

```powershell
helm lint .\helm\ocr-excel-parser
helm template aiops-ocr-excel-parser .\helm\ocr-excel-parser -n ocr-s4-dev
```

Render ingest too when config/routing changed. Check exact Service names, container
images, ConfigMap references, public alias, auth URL, and duplicate annotations.
Helm lint cannot verify image availability, DB credentials, HTTP routes, or ERP
semantics. Avoid publishing full rendered manifests if future charts contain Secrets.

### Step 14.4: Upgrade only the changed service

```powershell
helm history aiops-ocr-excel-parser -n ocr-s4-dev
helm upgrade aiops-ocr-excel-parser .\helm\ocr-excel-parser -n ocr-s4-dev --wait --timeout 5m
kubectl rollout status deployment/aiops-ocr-excel-parser -n ocr-s4-dev --timeout=5m
kubectl get pods -n ocr-s4-dev -l app.kubernetes.io/instance=aiops-ocr-excel-parser -o custom-columns="NAME:.metadata.name,IMAGE:.spec.containers[0].image,IMAGE-ID:.status.containerStatuses[0].imageID,READY:.status.containerStatuses[0].ready"
```

Use the chart/release table for another service. A mapping-only Excel release does
not require restarting ingest, changing email routing, or upgrading other parsers.

### Step 14.5: Fresh namespace install (only when needed)

Do not rerun a full-stack rollout for every template. For a new isolated stack,
create the approved namespace, provision DEV Secrets/pull credentials, configure
every internal URL, and withhold email/document traffic until dependencies are ready.
Ingest owns `ocr-configmap`, so install it first; it may start before parsers exist.

```powershell
helm upgrade --install aiops-ocr-ingest-documents .\helm\ocr-ingest-documents -n ocr-s4-dev --wait --timeout 5m
helm upgrade --install aiops-ocr-authorizer .\helm\authorizer -n ocr-s4-dev --wait --timeout 5m
helm upgrade --install aiops-ocr-erp-push .\helm\ocr-erp-push -n ocr-s4-dev --wait --timeout 5m
helm upgrade --install aiops-ocr-pdf-parser .\helm\ocr-pdf-parser -n ocr-s4-dev --wait --timeout 5m
helm upgrade --install aiops-ocr-excel-parser .\helm\ocr-excel-parser -n ocr-s4-dev --wait --timeout 5m
helm upgrade --install aiops-ocr-csv-parser .\helm\ocr-csv-parser -n ocr-s4-dev --wait --timeout 5m
helm upgrade --install aiops-ocr-html-parser .\helm\ocr-html-parser -n ocr-s4-dev --wait --timeout 5m
```

Stop at the first failed command. Do not treat the sequence as a script that can
ignore failures. Public DNS and TLS require approved setup before external testing.

**Archival is a separate approval gate**, not part of the normal parser smoke test:

- The inspected handler uses `config.archival_period_days` and `queries.DELETE_RECORDS`,
  but those definitions are absent in the inspected production-based shared modules.
  Resolve and test those dependencies before relying on scheduled archival.
- The debug Deployment uses `sleep infinity`; Running/Ready does not run the handler.
- The inspected CronJob template does not consume a `suspend` value; adding
  `--set suspend=true` alone would not suspend it. Coordinate any suspension with
  the platform owner using an explicit live patch or a reviewed template change.
- The handler deletes by cutoff date in the configured collection. A new namespace
  pointing to the old collection could delete the old environment's records.
- Review CronJob manifest resource placement and pull secrets with server-side
  validation before fresh installation. Do not manually create a Job to see what
  happens against a real collection.

After those issues are resolved and deletion/retention is approved, its install is:

```powershell
helm upgrade --install aiops-ocr-archival .\helm\archival -n ocr-s4-dev --wait --timeout 5m
kubectl get cronjobs,jobs -n ocr-s4-dev
```

### Step 14.6: Ingress and TLS

The S4 DEV alias is configured across these files:

1. [ingest values](../helm/ocr-ingest-documents/values.yaml): `ingress.publicPath`
   and `ingress.hosts[].paths[].path` must agree on `/s4-dev/ocr/ingest`.
2. [Deployment template](../helm/ocr-ingest-documents/templates/deployment.yaml):
   `INGEST_PUBLIC_PATH` injected into the container.
3. [config](../code/backend/core/config.py): reads `ingest_public_path`.
4. [ingest server](../code/backend/apps/ingest_documents/server.py): registers an
   additional POST route to the same handler as the internal path.
5. [Ingress template](../helm/ocr-ingest-documents/templates/ingress.yaml): maps
   the public hostname/path to the Service and uses the S4 DEV authorizer.

There is no NGINX rewrite/regex annotation for this alias. Keep old DEV/QA routes
unchanged. Shared-host rewrite annotations can affect other path matching.

[issuer.yaml](../helm/ocr-ingest-documents/issuer.yaml) sits outside `templates`
and is NOT installed by Helm. Only for a new namespace/issuer, after platform review
of the ACME contact email and existing certificates:

```powershell
kubectl apply -n ocr-s4-dev -f .\helm\ocr-ingest-documents\issuer.yaml
kubectl wait -n ocr-s4-dev --for=condition=Ready issuer/ocr-cert-issuer --timeout=180s
```

After ingest Ingress is installed:

```powershell
kubectl get ingress,certificate,issuer -n ocr-s4-dev
kubectl wait -n ocr-s4-dev --for=condition=Ready certificate/ocr-cert-secret --timeout=300s
```

Do not copy private keys across namespaces or bypass certificate validation. If
issuance fails, inspect issuer/certificate/order/challenge events with the owner.
Ready TLS does not prove the application image contains the new API route.

### Step 14.7: Config-only rollouts

ConfigMap environment variables are read at pod creation/import time. Ingest has a
ConfigMap checksum in its pod template, so its Helm config change triggers rollout.
Other services consuming the shared ConfigMap do not automatically restart just
because ingest changed it. Restart the affected parser/ERP/authorizer Deployments
after a reviewed config-only update, then check rollout status. Do not restart
everything as a substitute for diagnosing an email routing problem.

## 15. Connect Logic Apps and Test Once

### Email integration checklist

1. Identify the Logic App/workflow monitoring the intended test mailbox.
2. Check the email trigger, sender/subject filters, attachment extension/MIME filters,
   region selection, and the HTTP action or intermediate BTP destination.
3. Use a separate approved test branch/workflow; do not enable a second unrestricted
   trigger that processes the same mail twice.
4. Configure POST to the exact S4 DEV public endpoint, JSON content type, and Basic
   authentication in secure settings. If there is a BTP intermediary, change its
   downstream destination while preserving required transformations.
5. Supply attachment Base64, original email text, sender, region, and unique file_id.
6. Save/deploy the workflow change; inspect the EXECUTED run's inputs, not just the
   workflow designer's unsaved configuration.
7. Send one approved test email. Subject is only a label unless the workflow has
   explicit subject rules. A namespace cannot be selected by a subject alone.
8. Trace the same file_id and PO to HANA, parser, ERP-push, and ERP acceptance.

### Optional direct DEV request, only after approval

Port-forwarding can test processing without mailbox routing. It bypasses Ingress
Basic authentication and therefore does not validate the public auth path.
Use a separate terminal and stop/restart the forward after pod rollout:

```powershell
kubectl --kubeconfig "C:\Users\vpatil14\Downloads\kubeconfig.yaml" port-forward -n ocr-s4-dev svc/aiops-ocr-ingest-documents 8000:8000
```

In a second PowerShell terminal, check health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
```

The following PREPARES a request only. It does not send one. Use a genuine `.eml`
export that contains the same attachment; do not rename `.msg` or fabricate content.
This example assumes the email text is valid UTF-8; it fails instead of silently
corrupting another encoding. Confirm/convert the email export with the integration
owner when this assumption is not true.

```powershell
$attachmentPath = (Resolve-Path (Read-Host "Approved attachment path")).Path
$emailPath = (Resolve-Path (Read-Host "Original .eml path")).Path
$region = Read-Host "Approved region (US, EMEA or LATAM)"
$sender = Read-Host "Original sender email address"
$fileId = "s4-dev-test-" + [guid]::NewGuid().ToString()
$extension = [IO.Path]::GetExtension($attachmentPath).ToLowerInvariant()
$types = @{
    ".html" = "text/html"
    ".htm" = "text/html"
    ".csv" = "text/csv"
    ".xlsx" = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ".xlsm" = "application/vnd.ms-excel.sheet.macroenabled.12"
    ".pdf" = "application/pdf"
}
if (-not $types.ContainsKey($extension)) { throw "Unsupported attachment extension" }
if ([IO.Path]::GetExtension($emailPath) -ne ".eml") { throw "Use an original .eml export" }
$attachmentBytes = [IO.File]::ReadAllBytes($attachmentPath)
if ($attachmentBytes.Length -eq 0) { throw "Attachment is empty" }
$strictUtf8 = [Text.UTF8Encoding]::new($false, $true)
$emlText = [IO.File]::ReadAllText($emailPath, $strictUtf8)
if ([string]::IsNullOrWhiteSpace($emlText)) { throw "Email is empty" }
$payload = @{
    file_id = $fileId
    region = $region.Trim().ToUpperInvariant()
    data = @{
        file_name = "$fileId$extension"
        file_type = $types[$extension]
        file_content = [Convert]::ToBase64String($attachmentBytes)
        sender_email = $sender
        eml_data = $emlText
    }
}
$requestJson = $payload | ConvertTo-Json -Depth 10
Write-Host "Prepared file_id=$fileId, attachment bytes=$($attachmentBytes.Length); not submitted."
```

Only after permission to write DEV storage and potentially publish to ERP, run the
following ONCE. A timeout/error does not establish that ERP received nothing.

```powershell
$response = Invoke-RestMethod -Uri http://127.0.0.1:8000/dev/ocr/ingest -Method Post -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($requestJson)) -TimeoutSec 180
$response | ConvertTo-Json -Depth 20
```

Client timeout 180 seconds does not override the current ingest-to-parser 30-second
timeout. Longer PDF/ERP processing may outlive that timeout. Do not retry with a
new file_id until logs and ERP state have been reconciled; it can duplicate orders.
Public-endpoint testing must also cover Basic authentication via the approved
workflow or secure API client; do not hardcode credentials in this snippet.

### Definition of a successful test

- Logic App action actually ran, using the intended URL, method, MIME and region.
- Correct namespace received the request; no duplicate processing by old DEV.
- Attachment byte length/hash matches the source and email metadata exists.
- HANA row contains correct file_id, region, file_type, file_path, eml_file_path.
- Extracted PO/items/addresses/quantity/date match business-approved expectations.
- HANA payload envelope and identifiers are correct; no empty/UNEXTRACTED success.
- ERP-push reads the email and sends the expected record; verify OData success and
  the resulting ERP document/identifier with the ERP owner, not just HTTP 200.
- No unexpected changes to existing templates or other namespaces.

## 16. Trace Logs and Troubleshoot

### Read-only deployment checks (PowerShell)

Set `KUBECONFIG` in EACH connected terminal or use the explicit flag:

```powershell
$env:KUBECONFIG = "C:\Users\vpatil14\Downloads\kubeconfig.yaml"
helm list -n ocr-s4-dev
kubectl get deployments,pods,services,endpointslices -n ocr-s4-dev
kubectl get configmap ocr-configmap -n ocr-s4-dev
kubectl describe secret ocr -n ocr-s4-dev
```

`describe secret` lists key names/lengths, not values. Do not use Secret `-o yaml`,
base64 decoding, or full `printenv` in shared debugging output.

### Trace each layer, across all replicas

```powershell
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --since=2h --tail=-1 --timestamps | Select-String -SimpleMatch "/s4-dev/ocr/ingest"
kubectl logs -n ocr-s4-dev -l app.kubernetes.io/instance=aiops-ocr-authorizer --since=2h --tail=-1 --prefix --timestamps | Select-String -SimpleMatch "/dev/ocr/auth"
kubectl logs -n ocr-s4-dev -l app.kubernetes.io/instance=aiops-ocr-ingest-documents --since=2h --tail=-1 --prefix --timestamps | Select-String -NotMatch '"GET / HTTP'
kubectl logs -n ocr-s4-dev -l app.kubernetes.io/instance=aiops-ocr-excel-parser --since=2h --tail=-1 --prefix --timestamps | Select-String -NotMatch '"GET / HTTP'
kubectl logs -n ocr-s4-dev -l app.kubernetes.io/instance=aiops-ocr-html-parser --since=2h --tail=-1 --prefix --timestamps | Select-String -NotMatch '"GET / HTTP'
kubectl logs -n ocr-s4-dev -l app.kubernetes.io/instance=aiops-ocr-csv-parser --since=2h --tail=-1 --prefix --timestamps | Select-String -NotMatch '"GET / HTTP'
kubectl logs -n ocr-s4-dev -l app.kubernetes.io/instance=aiops-ocr-erp-push --since=2h --tail=-1 --prefix --timestamps | Select-String -NotMatch '"GET / HTTP'
```

For PDF use the same command with instance `aiops-ocr-pdf-parser`. Filter by the
exact file_id afterward to correlate records; HTTP access logs may not contain it,
so also retain nearby timestamps. Timestamps ending in Z are UTC; compare the
Logic App run time in the same timezone.

Save logs locally if needed (contains sensitive data; sanitize before sharing):

```powershell
kubectl logs -n ocr-s4-dev -l app.kubernetes.io/instance=aiops-ocr-excel-parser --since=2h --tail=-1 --prefix --timestamps | Out-File .\excel-parser.log -Encoding utf8
```

`--since=24h` does not recover logs already rotated out or belonging to deleted pods.
Use centralized logging or `kubectl logs POD --previous` for a restarted container
when available. A deployment log command can select only one pod; labels cover all
replicas. For live `-f` streams, stop with Ctrl+C; increase `--max-log-requests` if
following more replicas than allowed by the client.

### Troubleshooting table

| Symptom | Meaning / next discriminating check |
| --- | --- |
| `localhost:8080`, context not set | Kubeconfig is missing in this terminal; set it or pass `--kubeconfig`. Not an ERP error. |
| No matching ingress logs | Inspect the specific Logic App run, filters, executed destination, method, response. Check time window/log retention. Do not assume code failed. |
| GET with Teams/Skype preview user agent, 401 | Link preview without credentials, not the email POST. |
| POST 401/403 at Ingress | Check Basic credentials and S4 DEV authorizer; never disable authentication as a fix. |
| 404 on public path | Check exact path/trailing slash, ingress backend, `INGEST_PUBLIC_PATH`, and image containing route alias. |
| 502/503 | Service/endpoints/readiness, port/selector, DNS/network policy, auth-service reachability. |
| GET `/` 200 repeatedly | Health probes only. Does not prove DB, parser, or ERP functionality. |
| `Content-Length: 0` upload, Blob GET InvalidRange/416 then empty 200 | Empty Blob. Confirm source bytes and running ingest image has temporary-file flush/empty checks. |
| `KeyError: eml_file_path` | Request lacked usable original `eml_data`, or metadata incomplete. Fix email input, not a fabricated storage path. |
| `UNEXTRACTED`, no items | Empty source, unknown layout, encoding/header mismatch, or wrong deployed parser version. Compare source and stored bytes. |
| HTTP 200 but embedded `status_code: 500` | Ingest returns a dictionary error inside a successful API response; inspect body/logs. |
| Parser returns 200 after ERP-push 400 | Shared `core.util.push_to_erp()` currently does not raise on HTTP failure. Downstream acceptance is a separate required check. |
| Parser read timeout around 30 seconds | Current synchronous ingest handoff timeout; processing may continue. Reconcile outcome before retrying. |
| Same file_id rejected | Existing duplicate record; determine prior outcome before a new ID. |
| Same filename affects another run | Blob overwrite collision on `dev/REGION/name`; namespace does not appear in Blob path. |
| XLSX columns missing | Normalized anchor absent from `keys`, mapping missing, wrong tabular group, or formula cache missing. |
| XLSX only partially processed | Check per-sheet exceptions and duplicate PO output keys; no assumption of automatic sheet merging. |
| CountryTemplate/date field missing in PDF | Verify actual SAP extraction names/casing, schema selection, mapping filters and duplicate target fields. |
| ConfigMap updated but pod uses old URL | Env vars require pod replacement; restart affected consumers after reviewing config. |
| ImagePullBackOff | Wrong repository/tag, private image credentials, registry rate limits, or platform mismatch; inspect pod Events. |
| Push token insufficient scopes | Re-login to correct Docker Hub username with authorized write token; no rebuild needed just for login failure. |
| Helm chart path not found | Run at repository root using `.\helm\...`, not `.\ocr-...` unless already inside `helm`. |
| Pod Running but archival fails on schedule | Sleeping debug pod; check handler dependencies and Job logs, not readiness alone. |

Do not fix a failure by replaying all emails, deleting database rows, replacing TLS
keys, disabling auth, or restarting every service. First locate the failing stage
with the file_id, timestamp, and HTTP action result.

## 17. Rollback and Handover

Before deploy, record the source commit, image digest/tag, chart values and Helm
revision. For a regression in one service:

1. Pause the affected test/workflow route with its owner, preventing duplicate sends.
2. Inspect `helm history <release> -n ocr-s4-dev` and choose the known-good revision.
3. Roll back only the affected service; for example, if revision 1 is confirmed good:

```powershell
helm rollback aiops-ocr-excel-parser 1 -n ocr-s4-dev --wait --timeout 5m
kubectl rollout status deployment/aiops-ocr-excel-parser -n ocr-s4-dev --timeout=5m
```

4. If tags were overwritten, use the recorded old digest/version instead; a Helm
   revision referencing the same mutable tag may still pull the faulty new image.
5. Shared ConfigMap rollback can affect multiple services after restart; review its
   dependent consumers instead of blindly rolling all releases back.
6. Rollback does NOT undo Blob writes, HANA inserts, or orders already accepted by
   ERP. Reconcile those with data/business owners before any replay.

### Release checklist

- [ ] Requirement sheet and expected JSON approved for this specific template.
- [ ] Correct branch baseline chosen; unrelated region/service behavior preserved.
- [ ] Offline parser and mocked flow tests pass; existing-template regressions pass.
- [ ] Unknown/empty/invalid templates cannot be mistaken for approved output.
- [ ] SMTP/Logic App MIME, region, email metadata and authentication confirmed.
- [ ] Reviewed commit pushed; Codespaces pulled that exact source before build.
- [ ] Correct platform, repository, immutable tag/digest and pull credentials verified.
- [ ] Helm lint/render pass; live routes, ports and service names agree.
- [ ] DEV Secret uses correct HANA/Blob/ERP; no unintended shared-data operations.
- [ ] Ingest public alias exists in running image; TLS and Basic authentication verified.
- [ ] Single approved email processed once with correct nonempty payload.
- [ ] ERP acceptance/document verified by owner; HTTP 200 alone not sufficient.
- [ ] No unexpected errors/restarts or old DEV/QA behavior changes.
- [ ] Rollback revision/digest and replay precautions recorded.

### Information to leave for the next developer

```text
Template/customer/region/version:
Approved fixtures and expected JSON locations:
Base branch and final source commit:
Modified files and reason for each:
Test commands/results and unverified items:
Image repository:tag and digest:
Namespace/context and Helm release/revision:
Public URL and Logic App/workflow owner (no credentials):
Test file_id / PO / UTC timestamp:
ERP result/document identifier:
Known limitations and rollback revision/digest:
```

Related detailed references: [CSV/HTML deployment runbook](csv_html_deployment_runbook.md)
and [testing/debug guide](csv_html_testing_and_debug_guide.md). Older sections may
refer to the earlier LATAM branch; use the actual current source when deciding
which mappings and flags exist. No source code, Docker image, or cluster resource
is modified merely by following the read-only/documentation parts of this guide.