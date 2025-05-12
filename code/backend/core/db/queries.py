# This file contains all the queries which will be executed on the database at runtime by application.

# Query to get a single invoice from the database based on the document number.
GET_INVOICE_QUERY: str = 'SELECT * FROM {DATABASE_NAME}.{INVOICES_COLLECTION_NAME} WHERE "document_no" = \'{document_no}\';'

# Query to get all invoices from the database based on the filter, search, sort, skip and page size.
GET_INVOICES_QUERY_WITH_FILTER: str = 'SELECT * FROM {DATABASE_NAME}.{INVOICES_COLLECTION_NAME} where {query} order by {sort_query} limit {page_size} offset {skip_value};'

# Query to get all invoices from the database based on the sort, skip and page size.
GET_INVOICES_QUERY_WITHOUT_FILTER: str = 'SELECT * FROM {DATABASE_NAME}.{INVOICES_COLLECTION_NAME} order by {sort_query} limit {page_size} offset {skip_value};'

# Query to get the count of invoices in the database.
GET_INVOICE_COUNT_QUERY: str = 'SELECT COUNT(*) as count FROM {DATABASE_NAME}.{INVOICES_COLLECTION_NAME};'

# Query to get count of invoices with where condition.
GET_INVOICE_COUNT_QUERY_WITH_FILTER: str = 'SELECT COUNT(*) as count FROM {DATABASE_NAME}.{INVOICES_COLLECTION_NAME} WHERE {query};'

GET_STATUS_FLOW_QUERY: str = 'SELECT * FROM {DATABASE_NAME}.{STATUS_FLOW_COLLECTION_NAME};'

GET_STATUS_FLOW_BY_STATUS_QUERY: str = 'SELECT * FROM {DATABASE_NAME}.{STATUS_FLOW_COLLECTION_NAME} WHERE "current_status" = \'{current_status}\';'

GET_STATUS_FLOW_BY_STATUS_AND_ACTION_QUERY: str = 'SELECT * FROM {DATABASE_NAME}.{STATUS_FLOW_COLLECTION_NAME} WHERE "current_status" = \'{current_status}\' AND "possible_action" = \'{possible_action}\';'

# Invoice aging query to get the count of invoices based on the aging days.
# building case conditions for invoice aging query
case_conditions_invoice_aging = """
    WHEN JSON_VALUE("{date_field}", '$.attribute_value') >= add_days('{dt}', -5) THEN '{map_labels[0]}'
    WHEN JSON_VALUE("{date_field}", '$.attribute_value') < add_days('{dt}', -5) AND JSON_VALUE("{date_field}", '$.attribute_value') >= add_days('{dt}', -10) THEN '{map_labels[1]}'
    WHEN JSON_VALUE("{date_field}", '$.attribute_value') < add_days('{dt}', -10) AND JSON_VALUE("{date_field}", '$.attribute_value') >= add_days('{dt}', -15) THEN '{map_labels[2]}'
"""
# Invoice aging query 
INVOICE_AGING_QUERY = """
    SELECT 
        CASE 
            {case_conditions}
            ELSE '{map_labels[3]}'
        END AS "_id",
        COUNT(*) AS "total"
    FROM {table_view_name}
    WHERE {match_status_and_date}
    GROUP BY 
        CASE 
            {case_conditions}
            ELSE '{map_labels[3]}'
        END;
"""

# GET INVOICE STATUS QUERY
INVOICE_STATUS_QUERY = 'SELECT "invoice_status" AS "_id", COUNT(*) AS "total" FROM {table_view_name} WHERE {status_conditions} GROUP BY "invoice_status"'

# Invoice due date query to get the count of invoices based on the due date.
# building case conditions for due date query
case_conditions_invoice_due_date = """
    WHEN JSON_VALUE("{date_field}", '$.attribute_value') < '{dt}' THEN '{map_labels[0]}'
    WHEN JSON_VALUE("{date_field}", '$.attribute_value') < add_days('{dt}', 3) AND JSON_VALUE("{date_field}", '$.attribute_value') >= '{dt}' THEN '{map_labels[1]}'
    WHEN JSON_VALUE("{date_field}", '$.attribute_value') < add_days('{dt}', 5) AND JSON_VALUE("{date_field}", '$.attribute_value') >= add_days('{dt}', 3) THEN '{map_labels[2]}'
"""
# Invoice due date query
INVOICE_DUE_DATE_QUERY = """
    SELECT 
        CASE 
            {case_conditions}
            ELSE '{map_labels[3]}'
        END AS "_id",
        COUNT(*) AS "total"
    FROM {table_view_name}
    WHERE {match_status_and_date}
    GROUP BY 
        CASE 
            {case_conditions}
            ELSE '{map_labels[3]}'
        END;
"""

# GET total count of invoices based on the status
GET_INVOICE_COUNT_BY_STATUS = 'SELECT COUNT(*) AS "total" FROM {table_view_name} WHERE {status_conditions}'


GET_INVOICE_REFERENCE_DATA = "SELECT * FROM {DATBASE_NAME}.{DROPDOWN_COLLECTION_NAME};"

GET_INVOICE_REFERENCE_DATA_BY_FIELDS = "SELECT * FROM {DATBASE_NAME}.{DROPDOWN_COLLECTION_NAME} WHERE field_name IN ({fields});"

SELECT_ALL_QUERY = "SELECT * FROM {DATABASE_NAME}.{COLLECTION_NAME};"

SELECT_ALL_FROM_QUERY = "SELECT * FROM {DATABASE_NAME}.{COLLECTION_NAME} WHERE {FIELD_NAME} = '{FIELD_VALUE}';"

UPDATE_ONE_QUERY = "UPDATE {DATABASE_NAME}.{COLLECTION_NAME} SET {SET_VALUES} WHERE {FIELD_NAME} = '{FIELD_VALUE}';"

SELECT_ONE_QUERY = "SELECT {projection} FROM {DATABASE_NAME}.{COLLECTION_NAME} WHERE {FIELD_NAME} = '{FIELD_VALUE}';"

INSERT_INTO_DB_QUERY = "INSERT INTO {DATABASE_NAME}.{COLLECTION_NAME} VALUES ('{DATA}');"

UPDATE_QUERY_WITH_WHERE_CONDITION = "UPDATE {DATABASE_NAME}.{COLLECTION_NAME} SET {SET_VALUES} WHERE {WHERE_CONDITION};"

GET_AUDIT_QUERY = 'SELECT * FROM {DATABASE_NAME}.{AUDIT_COLLECTION_NAME} WHERE "document_no" = \'{document_no}\';'

GET_QUERY_WITH_WHERE_CONDITION = 'SELECT * FROM {DATABASE_NAME}.{COLLECTION_NAME} WHERE "{field_name}" = \'{field_value}\';'

DELETE_RECORD_FROM_DB = "DELETE FROM {DATABASE_NAME}.{COLLECTION_NAME} WHERE {FIELD_NAME} = '{FIELD_VALUE}';"