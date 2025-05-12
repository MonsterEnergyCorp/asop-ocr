import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import json
import logging
load_dotenv()


class Config(BaseSettings):
    sas_token: str = os.getenv("blob_sas_token") or ''
    account_url: str = os.getenv("blob_container_url") or ''
    container_name: str = os.getenv("blob_container_name") or ''
    db_name: str = os.getenv("HANA_USERNAME") or ''
    db_collection: str = os.getenv("HANA_DB_COLLECTION") or ''
    hana_address: str = os.getenv("HANA_ADDRESS") or ''
    hana_port: str = os.getenv("HANA_PORT") or ''
    hana_user: str = os.getenv("HANA_USERNAME") or ''
    hana_password: str = os.getenv("HANA_PASSWORD") or ''
    app_id: str = os.getenv("pdf_client_id") or ''
    client_secret: str = os.getenv("pdf_client_secret") or ''
    auth_token_url: str = os.getenv("auth_token_url") or ''
    schemas_url: str = os.getenv("schemas_url") or ''
    status_url: str = os.getenv("status_url") or ''
    doc_upload_url: str = os.getenv("doc_upload_url") or ''
    get_clients_url: str = os.getenv("get_clients_url") or ''
    port: int = os.getenv("PORT") or 8000
    ocr_pdf_url: str = os.getenv("ocr_pdf_url") or ''
    ocr_csv_url: str = os.getenv("ocr_csv_url") or ''
    ocr_erp_push_url: str = os.getenv("ocr_erp_push_url") or ''
    api_auth_username: str = os.getenv("api_auth_username", "") or ''
    api_auth_password: str = os.getenv("api_auth_password", "") or ''
    us_pdf_schema_id: str = os.getenv("us_pdf_schema_id") or ''
    emea_pdf_schema_id: str = os.getenv("emea_pdf_schema_id") or '' 
    latam_pdf_schema_id: str = os.getenv("latam_pdf_schema_id") or '' 
    odata_url: str = os.getenv("odata_url") or ''
    odata_username: str = os.getenv("odata_username") or ''
    odata_password: str = os.getenv("odata_pwd") or ''
    env: str = os.getenv("env") or 'dev'
    
config = Config()