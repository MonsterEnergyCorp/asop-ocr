
from hdbcli import dbapi
import logging
import os
from core.config import config

connection = None

hana_address = config.hana_address
hana_port = config.hana_port
hana_user = config.hana_user
hana_password = config.hana_password
 
def connect_to_db():

    logging.info("Connecting to database")

    connection = dbapi.connect(
        address=hana_address,
        port=hana_port,
        user=hana_user,
        password=hana_password,
    )

    logging.info(f"Connected to database {connection.isconnected()}")
    return connection

def close_connection(connection):
    logging.info("Closing the connection.")
    connection.close()
    
