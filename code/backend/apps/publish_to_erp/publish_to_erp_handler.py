import json
from core.db.connection import *
from core.db.query import *
from core.util import *
from core.config import config
import logging
from core.azure_storage.blob_storage_connection import *
import requests
from fastapi import HTTPException
import random
import apps.publish_to_erp.mappings as mappings
import traceback
import base64
from requests.auth import HTTPBasicAuth

# global vars
success_status = "Success"
failure_status = "Failed"


# Environment variables
sas_token = config.sas_token
account_url = config.account_url
container_name = config.container_name
db_name = config.db_name
db_collection = config.db_collection
metadata_mapping = mappings.metadata

odata_url = config.odata_url
odata_username = config.odata_username
odata_password = config.odata_password

def mock_push_to_erp():
    """
    Mock function for ERP calls
    returns - 
    success - if call is successful
    failure - if call is failed
    """
    return "Success"
    # if random.random() < 0.8:
    #     return "Success"
    # else:
    #     failure_choices = ["failure scenario 1", "failure scenario 2"]
    #     return random.choices(failure_choices)


def push_to_erp(url: str, payload: dict):
    """
    Pushes the payload to the ERP system.

    Args:
        url (str): The URL of the ERP system.
        payload (dict): The payload to be pushed.

    Raises:
        HTTPException: An error occurred while pushing the payload.
    """
    try:
        session = requests.Session()
        authorization = HTTPBasicAuth(odata_username, odata_password)
        xcsrf_token = fetch_xcsrf_token(session, url, authorization)
        headers = {'x-csrf-token': xcsrf_token, 'Content-Type': 'application/json', 'Accept': 'application/json'}
        response = session.post(url, headers=headers, auth=authorization, json=payload)
        logging.info(f'Response from ERP: {response.text}')
        if response.status_code == 201:
            return success_status
        else:
            response_json = response.json()
            error_message = response_json.get('error', {}).get('message', {}).get('value', 'Error pushing to ERP')
            return error_message
    except Exception as e:
        logging.info(f'Error pushing to ERP: {e}')
        raise HTTPException(status_code=400, detail='Error pushing to ERP')

def fetch_xcsrf_token(session: requests.Session, url: str, authorization: HTTPBasicAuth):
    """
    Fetches the X-CSRF token from the ERP system.

    Returns:
        str: The X-CSRF token.
    """
    request_headers = {'x-csrf-token': 'fetch'}
    response = session.get(url, auth=authorization, headers=request_headers)
    xcsrf_token = response.headers.get('x-csrf-token', '')
    return xcsrf_token


def pdf_call_to_erp(payload, po_no, file_content):
    """
    Function to call ERP for PDF files
    args -
    db_data - data fetched from Hana DB
    returns - payload for ERP
    """
    
    status, failures = failure_status, {}
    logging.info(f'payload: {payload}')
    final_payload = metadata_formatter(file_content, payload)
    # Will be passing the payload to the ERP system under here when the SAP OCC endpoint is available
    # JSON Dumps the final payload
    response = push_to_erp(odata_url, payload)
    if response != success_status:
        failures[po_no] = response
        logging.info(f'Failures: {failures}')
    status = "Published" if not failures else status
    return status, failures

def excel_call_to_erp(payload, content, hana_data):
    """
    Function to call ERP for Excel files
    args -
    data - data fetched from Hana DB
    returns - 
    status - status of the push
    failures - failures if any
    """
    failures, status = {}, failure_status
    # Will be passing the payload to the ERP system under here when the SAP OCC endpoint is available
    for k,v in payload.items():
        logging.info(f'Payload for {k}: {v}')
        v = metadata_formatter(content, v)
        response = push_to_erp(odata_url, v)
        if response != success_status:
            failures[k] = response
            logging.info(f'Failures: {failures}')
    status = "Published" if not failures else status
    logging.info(f'\n STATUS: {status}')
    return status, failures


def push_metadata_to_hana(metadata):
    """
    Function to push metadata to Hana DB
    args -
    metadata - metadata to be pushed
    """
    connection = connect_to_db()
    metadata.pop('Content')
    update_data = '"file_metadata" = ' + f"'{json.dumps(metadata)}'"
    hana_storage_push(file_id, connection, update_data)
    close_connection(connection)



def metadata_formatter(content, file_data):
    
    file_data["NavHeadtoMeta"][0]["Content"] = base64.b64encode(content).decode('utf-8')

    return file_data


def publish_to_erp(data: dict):
    """
    Function to publish data to ERP
    args -
    data - data coming from the pdf/csv parsers
    """
    connection = connect_to_db()
    global file_id
    file_id = data['file_id']
    try:
        hana_data = erp_data_fetch(connection, file_id)
        payload = json.loads(hana_data["erp_request_payload"])
        file_path = hana_data["eml_file_path"]
        content = read_file_from_object_store(file_path)
        if hana_data["file_type"] == "application/pdf":
            po_no = hana_data.get("po_numbers")
            status, failures = pdf_call_to_erp(payload, po_no, content)
        elif hana_data["file_type"] in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv']:
            status, failures = excel_call_to_erp(payload, content, hana_data)
        if failures:
            container_client = connect_to_blob_storage(sas_token, account_url, container_name)
            failure_file_path = move_blob_to_failed_folder(container_client, file_path)   
        else:
            failure_file_path = "None"     
    #    combined_status = update_values(status, failures, failure_file_path)
    #    update_hana_status(connection, file_id, combined_status)
        #delete_record_from_hana(connection,file_id)
        close_connection(connection)
    except Exception as e:
        logging.info(f'Error fetching erp payload: {e}')
        logging.info(f'Traceback: {traceback.format_exc()}')
        raise HTTPException(status_code=400, detail='Error fetching erp payload')
    return failures if failures else "Success"


