from core.azure_storage.blob_storage_connection import *
from core.db.connection import *
from core.db.query import execute_query
from core.db import queries
import json, pikepdf
from core.config import config
import base64
import requests
from fastapi import HTTPException

db_name = config.db_name
db_collection = config.db_collection
sas_token = config.sas_token
account_url = config.account_url
container_name = config.container_name


def pdf_pw_check(tmp_file, generated_file_name):
    """
    Function to check if a PDF file is password protected
    args -
    tmp_file - temporary file
    generated_file_name - name of the file
    returns -
    error_message - error message if file is password protected
    """
    error_message = None
    try:
        pdf = pikepdf.open(tmp_file)
    except pikepdf.PasswordError as e:
        logging.error('Runtime error: ', e)
        logging.error(f'{generated_file_name} is Password protected!')
        error_message = 'File is Password Protected'
    except Exception as e:
        logging.error('Runtime error: ', e)
        logging.error(f'{generated_file_name} error reading file!')
        error_message = 'Error reading file'
    return error_message


def file_name_fetch(connection, file_id):
    """ 
    Update audit status: creates new success/failure audit status,
    creates entry in audit table.
    """
    query = queries.SELECT_ONE_QUERY.format(projection='"file_path"', DATABASE_NAME=db_name, COLLECTION_NAME=db_collection, FIELD_NAME='"file_id"', FIELD_VALUE=file_id)
    result = execute_query(connection, query, query_type="SELECT")
    logging.info(result)
    file_name = result[0]["file_path"]
    logging.info(f"Result: {result}")
    logging.info("Saved")
    return file_name

def erp_data_fetch(connection, file_id):
    """ 
    Function to fetch erp payload from Hana DB
    args -
    file_id - file id
    returns - erp payload
    """
    query = queries.SELECT_ALL_FROM_QUERY.format(DATABASE_NAME=db_name, COLLECTION_NAME=db_collection, FIELD_NAME='"file_id"', FIELD_VALUE=file_id)
    result = execute_query(connection, query, query_type="SELECT")
    logging.info(f"Result: {result}")
    logging.info("Saved")
    result = result[0].get(config.db_collection, {})
    json_result = json.loads(result)

    return json_result

def update_hana_status(connection, file_id, combined_update_values):
    """ 
    Function to fetch erp payload from Hana DB
    args -
    file_id - file id
    returns - erp payload
    combined_update_values - combined update values
    """
    query = queries.UPDATE_ONE_QUERY.format(SET_VALUES = combined_update_values, DATABASE_NAME=db_name, COLLECTION_NAME=db_collection, FIELD_NAME='"file_id"', FIELD_VALUE=file_id)
    result = execute_query(connection, query, query_type="UPDATE")
    logging.info(f"Result: {result}")
    logging.info("Saved")

    return result

def update_values(status, failures, failed_file_path, failure_stage = "ERP_Publish"):
    """
    Function to update values in Hana DB
    args -
    status - status of the push
    failures - failures if any
    failure_stage - stage of failure
    returns - combined update values
    """
    if failures:
        failure_reason = '"failure_reason" = ' + f"'{json.dumps(failures)}'"
        failure_stage = '"failure_stage" = ' + f"'{failure_stage}'"
    else:
        failure_reason = '"failure_reason" = ' + "'None'"
        failure_stage = '"failure_stage" = ' + "'None'"
    failed_file_path = '"failed_file_path" = ' + f"'{failed_file_path}'"    
    status = '"status" = ' + f"'{status}'"
    combined_update_values = status + ', ' + failure_reason + ', ' + failure_stage + ', ' + failed_file_path
    return combined_update_values
    
def read_file_from_object_store(file_name):
    logging.info(f'FILE NAME: {file_name}')
    container_client = connect_to_blob_storage(sas_token, account_url, container_name)
    file_content = read_from_blob_storage(container_client, file_name)
    decoded_file = base64.b64encode(file_content).decode('utf-8')
    decoded_file = base64.b64decode(decoded_file)
    logging.info(f'DECODED FILE TYPE: {type(decoded_file)}')
    return decoded_file

def hana_storage_push(file_id, connection, ocr_update_values):
    where_condition = '"file_id" =' + f"'{file_id}'"
    query = queries.UPDATE_QUERY_WITH_WHERE_CONDITION.format(DATABASE_NAME=db_name, COLLECTION_NAME=db_collection,SET_VALUES=ocr_update_values,WHERE_CONDITION=where_condition)  
    logging.info(f'PUSH QUERY: {query}')
    result = execute_query(connection, query, query_type="UPDATE")
    logging.info(f'PUSH RESULT:{result}')

def push_to_erp(url, file_id):
    """
    Function to push the file to OCR parsers
    args - 
    url - url of the parser
    file_id - file id
    return - 
    response - response from the parser
    """
    try:
        file_path = file_id
        payload = {"file_id": file_path}
        logging.info(f'Sending payload {payload} to ERP Push')
        response = requests.post(url, data=json.dumps(payload))
        logging.info(f'ERP push response: {response.json()}')
        return response
    except Exception as e:
        logging.error(f'Error pushing file to erp push pod: {e}')
        raise HTTPException(status_code=400, detail='Error pushing file to erp push pod')  

def delete_record_from_hana(connection,file_id):
    query = queries.DELETE_RECORD_FROM_DB.format(DATABASE_NAME=db_name, COLLECTION_NAME=db_collection, FIELD_NAME='"file_id"', FIELD_VALUE=file_id)
    result = execute_query(connection, query, query_type="DELETE")
    logging.info(f"Result: {result}")  


def get_special_templates_data(connection):
    query = queries.GET_SPECIAL_TEMPLATES.format(DATABASE_NAME=db_name) 
    result = execute_query(connection, query, query_type="SELECT")  
    logging.info(f'Special Template Result: {result}')
    processed_result = {i.get("type", ""): i.get("customers",[]).split(',') for i in result}
    return processed_result  
