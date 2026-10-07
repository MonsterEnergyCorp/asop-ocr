# CSV/HTML Deployment Runbook

## S4 DEV Public Ingest Endpoint

The `prod_replica_test` ingest chart exposes this exact path in `ocr-s4-dev`:

```text
https://api.nonprod.ocr.monsterenergy.com/s4-dev/ocr/ingest
```

The Deployment passes `ingress.publicPath` as `INGEST_PUBLIC_PATH`. The application
registers it as an additional POST route using the existing handler and validation.
The internal `/dev/ocr/ingest` route remains available. No NGINX rewrite or regex
annotation is used, so this change does not require changing the old DEV/QA paths.
Keep `ingress.publicPath` and the Ingress host's path identical.

Rebuild and push the ingest image from the updated source before upgrading Helm.
If reusing `s4-dev-0606`, ensure the push succeeded before rollout; this overwrites
that tag. A config-only upgrade cannot add the new route to an older image.

The issuer definition at `helm/ocr-ingest-documents/issuer.yaml` is not a Helm
template. It must be applied separately in the new namespace. Review its ACME
contact email with the platform owner first; do not copy TLS private keys from
the old namespace. From a connected PowerShell terminal at the repository root:

```powershell
kubectl apply -n ocr-s4-dev -f .\helm\ocr-ingest-documents\issuer.yaml
kubectl wait -n ocr-s4-dev --for=condition=Ready issuer/ocr-cert-issuer --timeout=180s
helm upgrade aiops-ocr-ingest-documents .\helm\ocr-ingest-documents -n ocr-s4-dev --wait --timeout 5m
kubectl get ingress,certificate,issuer -n ocr-s4-dev
kubectl wait -n ocr-s4-dev --for=condition=Ready certificate/ocr-cert-secret --timeout=300s
```

Ingress authentication remains delegated to the S4 DEV authorizer. Certificate
issuance and live routing must be verified in the cluster. The email automation
owner must configure the new URL and the required authentication headers; changing
the email subject does not route it to this namespace. Do not redirect a shared
mailbox's existing DEV/QA flow without approval. ERP publishing remains enabled.

## Scope

This runbook covers the LATAM CSV and HTML parser services added on branch:

```text
LATAM_TEST_VISHAL_CSV_HTML
```

It explains the files, flags, URLs, Docker/Kyma deployment, DEV/UAT validation, production promotion, and VS Code debugging path.

## 1. What `core/config.py` Does

File:

```text
code/backend/core/config.py
```

`config.py` is the central runtime configuration object. It reads environment variables and exposes them to application code as `config.<field>`.

It does not create HANA, Blob, BTP, or ERP resources. It only reads the values supplied by local environment settings or Kubernetes ConfigMap/Secret injection.

Examples:

```python
config.hana_address
config.account_url
config.ocr_latam_csv_url
config.template_parser_test_mode
```

The values are supplied from:

```text
Local development: environment variables or local .env if approved
Kubernetes/Kyma: ConfigMap and Secret
```

Never commit real passwords, SAS tokens, client secrets, or certificates.

## 2. Important Configuration Files

### Application configuration

```text
code/backend/core/config.py
```

### HANA connection

```text
code/backend/core/db/connection.py
```

### Blob connection

```text
code/backend/core/azure_storage/blob_storage_connection.py
```

### Ingest URL routing

```text
code/backend/apps/ingest_documents/ocr_ingest_doc.py
```

### Kubernetes ConfigMap values

```text
helm/ocr-ingest-documents/templates/configmap.yaml
helm/ocr-ingest-documents/values.yaml
```

### Secrets

The charts reference an external Kubernetes Secret. The actual Secret values are supplied by the client deployment environment and are not stored in Git.

## 3. Flags and Where To Change Them

### Source defaults

File:

```text
code/backend/core/config.py
```

Current defaults:

```python
TEMPLATE_PARSER_TEST_MODE=true
LOCAL_TEST_MODE=false
```

### Kubernetes DEV/UAT values

File:

```text
helm/ocr-ingest-documents/values.yaml
```

Section:

```yaml
test_flags:
  template_parser_test_mode: 'true'
  local_test_mode: 'false'
```

### Rendered ConfigMap

File:

```text
helm/ocr-ingest-documents/templates/configmap.yaml
```

It renders:

```text
TEMPLATE_PARSER_TEST_MODE
LOCAL_TEST_MODE
```

### Flag meanings

```text
LOCAL_TEST_MODE=true
```

Uses local test storage and skips HANA, Azure Blob, and ERP.

```text
LOCAL_TEST_MODE=false
```

Uses real HANA and Azure Blob Storage.

```text
TEMPLATE_PARSER_TEST_MODE=true
```

Parses the document and stores the generated payload, but the CSV/HTML parser does not trigger ERP push.

```text
TEMPLATE_PARSER_TEST_MODE=false
```

Allows the CSV/HTML parser to trigger the ERP push service after parsing.

## 4. URLs That Must Be Supplied

The following values are currently blank by design in the base values file:

```yaml
ocr_latam_csv_url: ''
ocr_latam_html_url: ''
ocr_latam_template_url: ''
```

File:

```text
helm/ocr-ingest-documents/values.yaml
```

They must be set by the client for each environment. Do not guess the namespace or service names.

Expected route shape:

```text
CSV:
http://<csv-service>.<namespace>.svc.cluster.local:8000/<env>/parse/csv

HTML:
http://<html-service>.<namespace>.svc.cluster.local:8000/<env>/parse/html
```

The ingest router selects them in:

```text
code/backend/apps/ingest_documents/ocr_ingest_doc.py
```

```text
CSV  -> ocr_latam_csv_url or ocr_latam_template_url
HTML -> ocr_latam_html_url or ocr_latam_template_url
```

## 5. Input-to-Output Flow

```text
1. Testing email or API sends file to ingest service.
2. ingest_documents validates the content type.
3. File is uploaded to Azure Blob Storage.
4. HANA receives file_id, file_type, region and file_path.
5. Ingest calls the CSV or HTML parser service with file_id.
6. Parser fetches metadata from HANA.
7. Parser reads file bytes from Blob Storage using file_path.
8. Parser creates the normalized ERP-style payload.
9. Parser updates HANA erp_request_payload and po_numbers.
10. ERP push remains disabled while TEMPLATE_PARSER_TEST_MODE=true.
11. After approval, ERP push can be enabled.
```

## 6. Parser Files and Execution Order

### CSV

```text
code/backend/apps/csv_parser/server.py
code/backend/apps/csv_parser/csv_parse_handler.py
code/backend/apps/csv_parser/mappings.py
```

Execution order:

```text
parse_csv()
  -> csv_parsing_flow(file_id)
  -> erp_data_fetch()
  -> read_file_from_object_store()
  -> parse_latam_csv()
  -> update_processed_values()
  -> hana_storage_push()
  -> optional push_to_erp()
```

### HTML

```text
code/backend/apps/html_parser/server.py
code/backend/apps/html_parser/html_parse_handler.py
code/backend/apps/html_parser/mappings.py
```

Execution order:

```text
parse_html()
  -> html_parsing_flow(file_id)
  -> erp_data_fetch()
  -> read_file_from_object_store()
  -> parse_latam_html()
  -> update_processed_values()
  -> hana_storage_push()
  -> optional push_to_erp()
```

## 7. Docker Build Files

```text
build/Dockerfile.csv-parser
build/Dockerfile.html-parser
```

Both images:

```text
1. Use Python 3.12.
2. Install code/dependencies/requirements.txt.
3. Copy the parser package.
4. Copy shared core code.
5. Start code/backend/main.py.
6. Expose port 8000.
```

Build commands depend on the client registry and build context. Example from repository root:

```powershell
docker build -f build/Dockerfile.csv-parser -t <registry>/ocr-csv-parser:<tag> .
docker build -f build/Dockerfile.html-parser -t <registry>/ocr-html-parser:<tag> .
```

Push only to the approved DEV/UAT registry first:

```powershell
docker push <registry>/ocr-csv-parser:<tag>
docker push <registry>/ocr-html-parser:<tag>
```

## 8. Helm Charts

```text
helm/ocr-csv-parser/
helm/ocr-html-parser/
```

Each chart contains:

```text
Chart.yaml
values.yaml
templates/_helpers.tpl
templates/deployment.yaml
templates/service.yaml
templates/serviceaccount.yaml
templates/tests/test-connection.yaml
```

The services are `ClusterIP` services and should be called internally by ingest.

Before deployment, update each environment's values:

```text
image.repository
image.tag
imagePullSecrets
secret.name
configmap.name
env
```

The charts expect the shared HANA/Blob ConfigMap and Secret to exist in the target namespace.

## 9. DEV Deployment

### 9.1 Required client access

Request:

```text
Kyma/Kubernetes namespace
Container registry access
DEV HANA host, port, user and password
DEV HANA collection/schema
DEV Blob account URL
DEV Blob container name
DEV Blob SAS token or service binding
Shared ConfigMap name
Shared Secret name
Testing email routing details
```

### 9.2 Configure safe flags

Use:

```text
LOCAL_TEST_MODE=false
TEMPLATE_PARSER_TEST_MODE=true
```

This tests real HANA and Blob but prevents ERP publishing.

### 9.3 Validate Helm locally

On a machine with Helm installed:

```powershell
helm lint helm/ocr-csv-parser
helm lint helm/ocr-html-parser
helm template csv-parser helm/ocr-csv-parser
helm template html-parser helm/ocr-html-parser
```

### 9.4 Deploy parser services

Use the client-approved namespace and image values:

```powershell
helm upgrade --install ocr-csv-parser helm/ocr-csv-parser -n <namespace> -f <dev-values.yaml>
helm upgrade --install ocr-html-parser helm/ocr-html-parser -n <namespace> -f <dev-values.yaml>
```

Do not place passwords or SAS tokens in the values file. Use the approved Kubernetes Secret.

### 9.5 Set ingest URLs

Set these in the DEV ingest values:

```text
ocr_latam_csv_url
ocr_latam_html_url
```

Then upgrade the ingest chart:

```powershell
helm upgrade --install ocr-ingest-documents helm/ocr-ingest-documents -n <namespace> -f <dev-ingest-values.yaml>
```

## 10. DEV Validation Checklist

```text
1. Check pods are Running.
2. Check parser Services exist.
3. Run Helm smoke tests.
4. Check parser health endpoint `/`.
5. Send a CSV/HTML attachment through the approved testing email.
6. Confirm ingest created file_id.
7. Confirm the Blob object exists at file_path.
8. Confirm the HANA row contains region and file_type.
9. Confirm parser receives file_id.
10. Debug csv_parsing_flow() or html_parsing_flow().
11. Confirm erp_request_payload is written to HANA.
12. Confirm po_numbers is populated.
13. Confirm ERP push was not called.
14. Review payload with the business owner.
```

## 11. UAT Deployment

Repeat the DEV process using UAT-specific:

```text
UAT namespace
UAT registry/image tag
UAT HANA values
UAT Blob values
UAT ConfigMap/Secret
UAT testing email route
```

Keep:

```text
TEMPLATE_PARSER_TEST_MODE=true
```

If the client provides a non-production ERP endpoint, it can be tested only after the payload is approved and the endpoint is confirmed as non-production.

## 12. Production Promotion

Production is not ready merely because the flag is false.

Before production:

```text
1. DEV tests pass.
2. UAT tests pass.
3. CSV and HTML payloads are approved.
4. Image tags are immutable and approved.
5. Helm templates render successfully.
6. Production ConfigMap values are reviewed.
7. Production Secret values are provisioned by the client.
8. Ingest URLs point to production parser Services.
9. Rollback image tag is recorded.
10. Deployment window and owner are agreed.
```

Only after approval set:

```text
LOCAL_TEST_MODE=false
TEMPLATE_PARSER_TEST_MODE=false
```

Then deploy the approved images and charts using the client's production release process.

## 13. Production Smoke Test

After deployment:

```text
1. Check parser pods and Services.
2. Check health endpoints.
3. Send the approved production test document.
4. Verify Blob Storage object path.
5. Verify HANA status and erp_request_payload.
6. Verify ERP response.
7. Check logs for parser/ERP errors.
8. Confirm archival behavior is not deleting test evidence prematurely.
```

## 14. VS Code Debugging

Local parser-only debugging:

```text
.vscode/launch.json
```

Use:

```text
Debug: LATAM CSV parser (local file)
Debug: LATAM HTML parser (local file)
Debug: LATAM parser unit tests
```

Client HANA/Blob debugging uses:

```text
LOCAL_TEST_MODE=false
```

Set breakpoints at:

```text
csv_parsing_flow()
html_parsing_flow()
erp_data_fetch()
read_file_from_object_store()
parse_latam_csv()
parse_latam_html()
hana_storage_push()
push_to_erp()
```

Do not place credentials in `launch.json`. Configure them through the client-approved environment or Kubernetes Secret.

## 15. What `TEMPLATE_PARSER_TEST_MODE=false` Means

Setting it to `false` permits the new CSV/HTML parser flow to call the ERP push service.

It does not prove that:

```text
URLs are correct
HANA is reachable
Blob is reachable
Secrets exist
parser images are deployed
Helm values are correct
ERP endpoint is non-production
payload is approved
```

Therefore the flag should be changed to `false` only as the final controlled step after DEV/UAT validation.
