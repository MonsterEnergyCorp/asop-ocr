import logging
import datetime
from core.azure_storage.blob_storage_connection import *
from core.db.query import execute_query
from core.db.connection import *
from core.db import queries
from core.config import config

logging.basicConfig(level=logging.INFO)

archival_period_days = config.archival_period_days
db_name = config.db_name
db_collection = config.db_collection

def calculate_archival_cutoff(archival_period_days=None):
    """
    Calculate the cutoff date for archival based on the configured period.
    
    Args:
        archival_period_days (int, optional): Number of days to go back. If None, will use the value from config.
        
    Returns:
        str: Date in YYYY-MM-DD format
    """
    
    current_date = datetime.datetime.now()
    cutoff_date = current_date - datetime.timedelta(days=archival_period_days)
    return cutoff_date.strftime('%Y-%m-%d')

def archive_records(connection, cutoff_date):
    query = queries.DELETE_RECORDS.format(DATABASE_NAME=db_name, COLLECTION_NAME=db_collection, CUTOFF_DATE=cutoff_date)
    result = execute_query(connection, query, query_type="DELETE")
    logging.info(f"Deletion Result: {result}") 

def main():
    connection = connect_to_db()
    archival_cutoff = calculate_archival_cutoff(archival_period_days)
    logging.info(f"ARCHIVAL cutoff at{archival_cutoff}")
    archive_records(connection, archival_cutoff)
    close_connection(connection)    

if __name__ == "__main__":
    main()