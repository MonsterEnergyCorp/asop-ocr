from core.db.connection import *
import logging

def execute_query(connection, query: str, query_type: str = "SELECT",):
    try:
        # move to codes where connection needed
        cursor = connection.cursor()
        logging.info(f'\n\nExecuting query\n\n: {query}  \n\n')
        cursor.execute(query)
        # Only in select query we need to use fetch all

        if query_type == "SELECT":
            rows = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]

            # Convert rows to list of dictionaries
            data = [dict(zip(column_names, row)) for row in rows]
            return data
        else:
            logging.info("Query is executed successfully")
            return True
    except Exception as e:
        logging.error(f'Error while executing query: {e}')
        return None