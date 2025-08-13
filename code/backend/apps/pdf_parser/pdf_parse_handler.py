import json
import requests
import apps.pdf_parser.mappings as mappings
import time
import io
from core.config import config
from core.azure_storage.blob_storage_connection import *
from core.db.connection import *
from core.util import *
import logging


"""
Script to parse the PDF file and extract the data using SAP Document Information Extraction Service
"""
app_id = config.app_id
client_secret = config.client_secret
auth_token_url = config.auth_token_url
schemas_url = config.schemas_url
status_url = config.status_url
doc_upload_url = config.doc_upload_url
get_clients_url = config.get_clients_url
sas_token = config.sas_token
account_url = config.account_url
container_name = config.container_name
db_name = config.db_name
db_collection = config.db_collection
header_data_mapping = mappings.header_data
item_mapping = mappings.line_item_data
ocr_erp_push_url = config.ocr_erp_push_url
metadata_mapping = mappings.metadata


def get_auth_token(application_id, app_secret, get_auth_token_url):
    """
    Function to get the authentication token from SAP using client_id and client_secret
    args - 
    client_id - client id for the application
    client_secret - client secret for the application
    auth_token_url - url to get the authentication token
    return -
    auth_token - authentication token from SAP
    """
    payload = {
    "grant_type": "client_credentials",
    "client_id": application_id,
    "client_secret": app_secret,
    "response_type": "token"
            }
    headers = {"content-type": "application/x-www-form-urlencoded"}
    response = requests.post(get_auth_token_url, data=payload, headers=headers)
    json_response = response.json()
    auth_token = json_response["access_token"]
    return auth_token


def get_clients(auth_token, client_get_url):
    """
    Function to get the list of clients from SAP
    args -
    auth_token - authentication token from SAP
    get_clients_url - url to get the list of clients
    return -
    client_id - client id for the client
    """
    headers = {"Authorization": "Bearer " + auth_token}
    querystring = {"limit":"10"}
    response = requests.get(client_get_url, headers=headers, params=querystring)
    json_response = response.json()
    client_id = json_response["payload"][0]["clientId"]
    return client_id


def upload_document(auth_token, upload_url, schema_id, client_id, pdf_bytes, filename):
    """
    Function to upload the document to SAP Document Information Extraction Service
    args -
    auth_token - authentication token from SAP
    doc_upload_url - url to upload the document
    schema_id - schema id for the schema
    client_id - client id for the client
    return -
    job_id - job id for the document upload
    """
    pdf_file = io.BytesIO(pdf_bytes)
    files = [('file', (filename + '.pdf', pdf_file, 'application/pdf'))]
    options = {
    'clientId': f'{client_id}',
    'documentType': 'purchaseOrder',
    'schemaId': f'{schema_id}',
    'templateId': 'detect'
            }
    payload = { "options": json.dumps(options) }
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = requests.post(upload_url, data=payload, files=files, headers=headers)
    json_response = response.json()
    job_id = json_response["id"]
    return job_id


def document_status(auth_token, get_status_url, job_id, client_id, delete_url):
    """
    Function to get the status of the document uploaded to SAP Document Information Extraction Service
    args -
    auth_token - authentication token from SAP
    status_url - url to get the status of the document
    job_id - job id for the document upload
    return -
    status - status of the document
    """
    payload = "-----011000010111000001101001\r\nContent-Disposition: form-data; name=\"options\"\r\n\r\n{\n  \"clientId\": \"" + f"{client_id}" + "\",\n  \"filter\": \"jobId eq " + f"{job_id}" + "\"\n}\r\n-----011000010111000001101001--\r\n\r\n"
    headers = {
        "Authorization": "Bearer " + auth_token,
        "content-type": "multipart/form-data; boundary=---011000010111000001101001"
    }
    status = "PENDING"
    intervals = [10, 5, 5, 5, 3, 3, 3, 20, 30, 60]  # Intervals in seconds

    for interval in intervals:
        time.sleep(interval)  # Wait for the specified interval
        response = requests.post(get_status_url, data=payload, headers=headers)
        json_response = response.json()
        logging.info(f'FETCH API RESPONSE: {json_response}')
        status = json_response["results"][0]["status"]
        
        if status == "DONE":
            return True

    # If status is still not "DONE" after all intervals, call the DELETE API
    if status != "DONE":
        payload = json.dumps({"value": [job_id]})
        headers = {"Authorization": "Bearer " + auth_token}
        delete_response = requests.delete(delete_url, data=payload, headers=headers)
        if delete_response.status_code == 200:
            logging.info(f"Resource {job_id} deleted successfully.")
        else:
            logging.info(f"Failed to delete resource. Response: {delete_response.text}")
        return False    


def parsed_results(upload_url, auth_token, job_id):
    """
    Function to get the parsed results of the document uploaded to SAP Document Information Extraction Service
    args -
    doc_upload_url - url to upload the document
    auth_token - authentication token from SAP
    job_id - job id for the document upload
    return -
    parsed_results - parsed results of the document
    """
    headers = {"Authorization": "Bearer " + auth_token}
    url = upload_url + "/" + job_id
    response = requests.get(url, headers=headers)
    json_response = response.json()
    extracted_data = json_response["extraction"]
    return extracted_data, json_response


def output_formatter(data):
    """
    Function is used to format the data coming from SAP doc info extract into a format similar to excel parser
    args - 
    data (dict) - Parsed data coming from SAP
    returns -
    output (dict) - Formatted output
    """
    # Header formatting
    new_header = {}
    for item in data['headerFields']:
        new_header[item['name']] = str(item['value'])
        if item['name'] in metadata_mapping.keys():
                new_header[metadata_mapping[item['name']]] = str(round(item['confidence']*100, 2))
    # Line item formatting
    line_items = []
    ocritemcount = 0
    for item in range(len(data['lineItems'])):
        temp_item = {}
        for line_item in data['lineItems'][item]:
            temp_item[line_item['name']] = str(line_item['value'])
            if line_item['name'] in metadata_mapping.keys():
                temp_item[metadata_mapping[line_item['name']]] = str(round(line_item['confidence']*100, 2))
            temp_item['AsopNo'] = '0000000000'
            temp_item['OCRItemno'] = str(ocritemcount + 10)
        line_items.append(temp_item)
        ocritemcount += 10
    lines = {'NavHeadToItem': line_items}
    new_header.update(lines)
    return new_header

def handle_customer_material_number(items):
    """
    Removes customerMaterialNumber from all items if any item has a valid materialNumber.
    
    Args:
        items (list): List of line items
    
    Returns:
        list: Processed list of line items
    """
    # First check if any line item has a non-empty materialNumber
    has_valid_material_number = False
    for item in items:
        if "materialNumber" in item and item["materialNumber"]:
            has_valid_material_number = True
            break
    
    # If any item has a valid materialNumber, remove customerMaterialNumber from all items
    if has_valid_material_number:
        for item in items:
            if "customerMaterialNumber" in item:
                item.pop("customerMaterialNumber", None)
    
    return items

def handle_manufact_code(items):
    """
    Discards materialNumber value if ManufactCode is present in line item.
    
    Args:
        items (list): List of line items
    
    Returns:
        list: Processed list of line items
    """
    for item in items:
        if "ManufactCode" in item and item["ManufactCode"] and "materialNumber" in item:
            item.pop("materialNumber", "")
    
    return items
  

def process_region_specific_data(data, region):
    """
    Process region-specific data transformations.
    
    Args:
        data (dict): Data to be processed
        region (str): Region code (e.g., "US", "EMEA")
    
    Returns:
        dict: Processed data
    """
    if region == "US" and isinstance(data, dict):
        # Process US region data
        for key, value in data.items():
            if isinstance(value, list) and key == "NavHeadToItem":
                value = handle_customer_material_number(value)
                value = handle_manufact_code(value)
                data[key] = value
    return data                
      


def output_filtering(data, region):
    """
    Function to filter the output data based on the mapping defined in mappings.py
    args - 
    data (dict) - Formatted output data
    region (str) 
    returns - 
    filtered_output (dict) - Filtered output data
    """
    # Process region-specific data first
    data = process_region_specific_data(data, region)
    
    filtered_output = {}
    filtered_line_items = []

    for key, value in data.items():
        if isinstance(value, list):
            # Process list items
            for item in value:
                temp_lineitem = {
                    item_mapping[line_item]: item[line_item]
                    for line_item in item if line_item in item_mapping
                }
                filtered_line_items.append(temp_lineitem)
            filtered_output['NavHeadToItem'] = filtered_line_items
        else:
            # Process non-list items
            if key in header_data_mapping:
                filtered_output[header_data_mapping[key]] = extraction_cleanups(key,value)
    filtered_output["Region"] = region
    return filtered_output

def extraction_cleanups(key,value):
    if key in ['shipToCity', 'BillToCity']:
        return value.replace(',', '')
    return value


def metadata_formatter(file_data, payload):
    """
    Function to format the metadata for the parsed data
    args -
    file_data - data from the file
    return -
    metadata - formatted metadata for the parsed data
    """
    metadata = {}
    metadata["AsopNo"] = "0000000000"
    metadata["CustEmail"] = file_data.get("sender_email","")
    metadata["MonsterEmail"] = ""
    metadata["FileDate"] = file_data.get("created_at","")
    metadata["FileName"] = f'{file_data.get("file_name","placeholder")}.eml'
    metadata["MimeType"] = file_data.get('file_type',"")
    metadata['Field1'] = ''
    metadata['Field2'] = ''
    metadata['Field3'] = ''
    metadata['Field4'] = ''
    metadata['Field5'] = ''
    payload['NavHeadtoMeta'] = [metadata]
    payload['Podoctype'] = 'PDF'
    return payload


def update_processed_values(data, raw_response, successful_extraction=True):
    """
    Function to write the query set values for the processed data for pdf.
    """
    if successful_extraction:
        data_str = json.dumps(data).replace("'", "''")
        raw_str = json.dumps(raw_response).replace("'", "''")
        ocr_data = '"erp_request_payload" = ' + f"'{data_str}'" + ', "po_numbers" = ' + f"'{data.get('CustPo', '')}'" + ', "ocr_raw_response" = ' + f"'{raw_str}'"
    else:
        ocr_data = '"erp_request_payload" = ' + f"'{json.dumps(data)}'" + ', "ocr_raw_response" = ' + f"'{json.dumps(raw_response)}'"
    return ocr_data

def get_schema_id(region):
    if region == "US":
        schema_id = config.us_pdf_schema_id
    elif region == "EMEA":
        schema_id = config.emea_pdf_schema_id
    elif region == "LATAM":
        schema_id = config.latam_pdf_schema_id
    return schema_id               


def pdf_parsing_flow(data):
    """
    Main function used to get upload pdf file to SAP, get parsed data, format the same and pass it over to SAP OCC
    args - 
    content - pdf file coming from source in byte format
    returns - 
    formatted_output - Formatted parsed output
    """
    connection = connect_to_db()
    file_id = data['file_id']
    # Functions to process the pdf through the SAP OCR
    auth_token = get_auth_token(app_id, client_secret, auth_token_url)
    client_id = get_clients(auth_token, get_clients_url)
    hana_data = erp_data_fetch(connection, file_id)
    file_path = hana_data.get("file_path","")
    region = hana_data.get("region", "US")
    global schema_id
    schema_id = get_schema_id(region)
    content = read_file_from_object_store(file_path)
    job_id = upload_document(auth_token, doc_upload_url, schema_id, client_id, content, file_path)
    if document_status(auth_token, status_url, job_id, client_id, doc_upload_url):
        pdf_output, raw_output = parsed_results(doc_upload_url, auth_token, job_id)
        # Functions to format the output and push to Hana DB
        formatted_output = output_formatter(pdf_output)
        cleaned_output = output_filtering(formatted_output, region)
        hana_data = erp_data_fetch(connection, file_id)
        erp_payload = metadata_formatter(hana_data, cleaned_output)
        # Update the processed values in Hana DB
        logging.info(f"Formatted output: {erp_payload}")
        ocr_update_values = update_processed_values(erp_payload, raw_output)
    else:
        hana_data = erp_data_fetch(connection, file_id)
        erp_payload = metadata_formatter(hana_data, {})
        erp_payload["Status"] = "52"
        logging.info(f"Formatted Metadata output: {erp_payload}")   
        ocr_update_values = update_processed_values(erp_payload, {}, False)
    hana_storage_push(file_id, connection, ocr_update_values)
    logging.info(f"ERP Request payload uploaded to Hana DB")
    close_connection(connection)
    logging.info(f"Connection Closed.")
    push_to_erp(ocr_erp_push_url, file_id)
    logging.info(f"Pushed to ERP")
    return erp_payload