import json, pikepdf, requests, os, tempfile, uuid, logging, base64
from datetime import datetime
from fastapi import UploadFile, HTTPException
from core.azure_storage.blob_storage_connection import *
from core.constants import SUPPORTED_FILE_TYPES, PDF_CONTENT, CSV_CONTENT, MIN_FILE_SIZE_BYTES, PROCESSING_STATUS, SUPPORTED_REGIONS
from core.db.query import execute_query
from core.db.connection import *
from core.db import queries
from core.pdf_util import *
import io
from core.config import config
import requests


# Environment variables
sas_token = config.sas_token
blob_account_url = config.account_url
blob_container_name = config.container_name
db_name = config.db_name
db_collection = config.db_collection
ocr_pdf_url = config.ocr_pdf_url
ocr_csv_url = config.ocr_csv_url
env = config.env

class DuplicateException(Exception):
    pass


def upload_invoice_file(data: dict):
    """
    Uploads a PO file and processes it based on its type (PDF or CSV).
    Now also handles eml_data from the new input structure.

    Args:
        data (dict): Dictionary containing file data and metadata.
            For traditional input: Contains file_content, file_type, file_name, etc.
            For new input: Structured as {'data': {...}, 'region': '...'} with eml_data field

    Returns:
        dict: A response dictionary containing the status and message of the operation.
    """

    try:
        # Check if this is the new input structure with data and region keys
        if 'data' in data and 'region' in data and isinstance(data['data'], dict):
            # Extract the nested data and region
            inner_data = data['data']
            region = data['region']
            
            # Create a new data dictionary with the expected structure
            processed_data = inner_data.copy()
            processed_data['region'] = region
            processed_data['region'] = region
            file_id = data.get('file_id','')
            processed_data['file_id'] = file_id
            duplicate_check = check_for_existing_process(file_id)
            if duplicate_check:
                raise DuplicateException

            # Handle eml data if present
            if inner_data.get('eml_data'):
                eml_uuid = str(uuid.uuid4())
                eml_file_name = f"{eml_uuid}.eml"
                eml_file_path = f"{env}/{region}/eml/{eml_file_name}"
                
                # Create temporary file for eml data
                with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tmp_eml_file:
                    tmp_eml_file.write(inner_data['eml_data'].encode('utf-8'))
                    tmp_eml_file.flush()
                    
                    # Push eml file to blob storage
                    eml_blob_path = push_to_blob_storage(
                        file_name=eml_file_path, 
                        tmp_file=tmp_eml_file, 
                        content_type='message/rfc822', 
                        sas_token=sas_token, 
                        account_url=blob_account_url, 
                        container_name=blob_container_name
                    )
                    
                # Add eml path to the data
                processed_data['eml_file_path'] = eml_blob_path
                
                # Remove eml_data to avoid storing large strings in DB
                processed_data.pop('eml_data', None)

            # Continue with standard processing using the processed data
            data = processed_data
        # Continue with existing processing flow
        file_content = decode(data)
        # Get file name, content type and sender email
        sender_email = data.get('sender_email', '')
        file_name = data.get('file_name', '')
            
        file_path = env + '/' + data['region'] + '/' + file_name
            
        # Check content_type
        content_type, data = get_attachment_content_type(data)
        file_type_folder, error_response = get_file_type(content_type)

        if file_type_folder == 'pdf':
            # use file id instead of uuid4
            document_no = data.get('file_id', str(uuid.uuid4()))
            if 'file_id' not in data:
                data['file_id'] = document_no
                
            tmp_file = tempfile.NamedTemporaryFile(mode='w+b')
            tmp_file.write(file_content)
            response = pdf_validate_push_to_storage(document_no, tmp_file, file_path, content_type, data)
            push_to_parsers(ocr_pdf_url, document_no)
            tmp_file.close()


        if file_type_folder == 'csv':
            # Call invoice_template_processor function
            tmp_file = tempfile.NamedTemporaryFile(mode='w+b')
            tmp_file.write(file_content)
            document_no = data.get('file_id', str(uuid.uuid4()))
            if 'file_id' not in data:
                data['file_id'] = document_no
                
            if tmp_file is not None:
                file_path = push_to_blob_storage(file_name=file_path, tmp_file=tmp_file, content_type=content_type, sas_token=sas_token, account_url=blob_account_url, container_name=blob_container_name)
                data.pop('file_content', None)
                data.update({'file_path': file_path})
            response = {
                'message': f'file {file_name} uploaded to blob storage',
                'document_no': document_no
            }
            data=add_audit_fields(data)
            hana_storage_insert(data)
            push_to_parsers(ocr_csv_url, document_no)
            tmp_file.close()

            return {"status_code": 200, "message" : response}
    except DuplicateException:
        logging.info(f"File already ingested in OCR")
        return {"status_code": 400, "message" : "File already ingested in OCR"}
    except Exception as e:
        logging.error('Runtime error: ', e)
        response = {"status_code": 500, "message" : f'Error Processing request - {e}'}

    return response

def push_to_parsers(url, file_id):
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
        response = requests.post(url, data=json.dumps(payload))
        return response
    except Exception as e:
        logging.error(f'Error pushing file to parser: {e}')
        raise HTTPException(status_code=400, detail='Error pushing file to parser')

def decode(data):
    """
    Function to decode base64 encoded file content
    args - 
    data - dictionary containing file content
    return -
    decoded_file - file content in bytes
    """
    try:
        po_bytes = base64.b64decode(data['file_content'])
        return po_bytes
    except Exception as e:
        logging.error(f'Error decoding file: {e}')
        raise HTTPException(status_code=400, detail='Error decoding file')


def get_file_type(content_type):
    """
    Function to validate the file type
    args - 
    content_type - content type of the file
    returns -  
    file_type - type of file
    """
    if content_type not in SUPPORTED_FILE_TYPES:
        return content_type, {'message': 'Not a valid file type'}
    if content_type == PDF_CONTENT:
        return 'pdf', None
    if content_type == CSV_CONTENT:
        return 'csv', None

def add_audit_fields(data):
    data["created_by"] = "system"
    data["created_at"] = datetime.now().strftime('%Y-%m-%d')
    data["updated_by"] = "system"
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return data


def pdf_validate_push_to_storage(document_no, tmp_file, file_name, content_type, data):
    
    error_response = None
    current_date = datetime.now()

    # Validate content_type
    file_type, error_response = get_file_type(content_type)

    # Validate file size - Can be enabled if business decides to include upper and lower size limits.
    # if not validate_file_size(tmp_file):
    #     error_response = {'message': 'Blank File Loaded'}
    # logging.info(f"Error response after file size validation: {error_response}")

    # Validate if PDF file is password protected
    error_message = pdf_pw_check(tmp_file, file_name)
    if error_message is not None:
        error_response = {'message': {error_response}}
    logging.info(f"Error response after password check: {error_response}")

    if error_response is not None:
        status_code, error_response = fail_validation(file_name, error_message, data)
        return {"status_code": status_code, "message" : error_response}
    logging.info(f"Error response after failed validation: {error_response}")

    file_path = blob_storage_push(file_name, tmp_file, content_type, data, file_type)
    data.update({'file_path': file_path})
    data.update({'status': PROCESSING_STATUS})
    data.pop('file_content')
    success_response = {
        'message': f'file {file_name} uploaded to blob storage',
        'document_no': document_no
    }
    data=add_audit_fields(data)
    hana_storage_insert(data)

    return {"status_code": 200, "message" : success_response}

def hana_storage_insert(data):
    """ 
    Update audit status: creates new success/failure audit status,
    creates entry in audit table.
    """
    connection = connect_to_db()
    query = queries.INSERT_INTO_DB_QUERY.format(DATABASE_NAME=db_name, COLLECTION_NAME=db_collection, DATA=json.dumps(data))
    result = execute_query(connection, query, query_type="INSERT")
    logging.info(f"Result: {result}")
    logging.info("Saved")
    close_connection(connection)

def check_for_existing_process(file_id):
    connection = connect_to_db()
    query = queries.GET_FILE_ID.format(DATABASE_NAME=db_name, COLLECTION_NAME=db_collection, FIELD_VALUE=file_id)
    result = execute_query(connection, query, query_type="SELECT")
    logging.info(f"Duplicate Check Result: {result}")
    return result    
   

def validate_file_size(tmp_file):
    """
    Function to validate the file size
    args -
    tmp_file - temporary file
    returns -
    boolean - True if file size is greater than MIN_FILE_SIZE_BYTES
    """
    file_size = os.path.getsize(tmp_file.name)
    logging.info(f'file size: {file_size} bytes')
    return file_size > MIN_FILE_SIZE_BYTES


def blob_storage_push(file_name, tmp_file, content_type, data, file_type):
    """ 
    Function triggers when validation succeeds ONLY FOR PDFs
    Push metadata to Azure Blob Storage.
    """
    # push file to Azure Blob Storage 
    logging.info(f"Tags: {data}")
    file_path = push_to_blob_storage(tmp_file=tmp_file, content_type=content_type, sas_token=sas_token, 
    account_url=blob_account_url, container_name=blob_container_name, file_name = file_name)
    logging.info(f"File path: {file_path}")
    return file_path


def fail_validation(file_name, status_message, data):
    """
    Create error status for invoice audit table. Call update_audit_status to insert record into audit table.
    args - 
    file_name - name of the file
    status_message - error message
    data - dictionary containing file content
    return -
    status_code - status code
    status_message - error message
    """

    logging.info(f"Validation Failed!!! Can not process {file_name}")
    status = {
        'status': 'Invalid File',
        'status_message': status_message,
        'status_creation_date': datetime.now()
    }
    data.update({'system_actions': [status]})
    # Replace with error audit to blob storage under a different folder same region, but different sub folder for invalid_files
    # push to blob storage
    # push to hanadb
    
    return 400, status_message


def get_attachment_content_type(data):
    content_type = data.get('file_type','')
    if content_type == 'application/octet-stream':
        file_extension = data.get('file_name', '').lower().split('.')[-1]   
        content_type = PDF_CONTENT if file_extension == 'pdf' else CSV_CONTENT
        data['file_type'] = content_type
    return content_type, data
