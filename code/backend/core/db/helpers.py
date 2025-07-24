import logging
from core.config import config
import datetime
import json
from core.db.queries import GET_INVOICE_QUERY, INSERT_INTO_DB_QUERY, UPDATE_QUERY_WITH_WHERE_CONDITION, GET_AUDIT_QUERY
from core.db.query import execute_query

db_audit_collection = config.INVOICE_AUDIT_COLLECTION_NAME


def get_filter_query(query_params, expected_params):
    """Function gets the filter query to get data from mongodb
    Args: query_params: dict: query params
    Returns: list: filter query for SAP HANA"""
    logging.info(f"query_params: {query_params}")
    
    filters = []
    for column, value in query_params.items():
        if column not in expected_params:
            raise ValueError(f"Invalid filter parameter: {column}")
        column_name = expected_params.get(column).get("db_name")
        column_type = expected_params.get(column).get("type")
        if "," in value:
            value = ", ".join([f"'{i.strip()}'" for i in value.split(",")])
            filters.append(f'{column_name} IN ({value})')
        else:
            filters.append(f'{column_name} = \'{value}\'')
    filter_query = " AND ".join(filters)
    logging.info(f"filter_query created: {filter_query}")
    return filter_query


def convert_array_str_to_list(invoice):
    """Function to convert invoice/invoice_audit array to list
    Args: invoice: dict: invoice data
    Returns: dict: invoice data with list"""
    # fields from invoice and invoice_audit which are array in collection document

    if "system_actions" in invoice and isinstance(invoice["system_actions"], str):
        invoice["system_actions"] = json.loads(invoice["system_actions"])
    if "items" in invoice and isinstance(invoice["items"], str):
        invoice["items"] = json.loads(invoice["items"])
    if "user_actions" in invoice and isinstance(invoice["user_actions"], str):
        invoice["user_actions"] = json.loads(invoice["user_actions"])
    return invoice

def get_sorting_query(sort_by, expected_params):
    """Function gets the sorting query to get data from mongodb
    Args: sort_by: str: sorting query from input
    Returns: list: sorting query for SAP HANA"""
    logging.info(f"sort_by: {sort_by}")
    if sort_by:
        sorting_request = []
        for i in sort_by.split(","):
            individual_sort = i.strip().split(":")
            if individual_sort[0] not in expected_params:
                raise ValueError(f"Invalid sort parameter: {individual_sort[0]}")
            individual_sort[0] = expected_params.get(individual_sort[0]).get("db_name")
            sorting_request.append((individual_sort[0], individual_sort[1]))
    else:
        sorting_request = [('"last_modified"', "desc")]
    # prepare the sorting query for sap hana
    sorting_query = ", ".join([f'{k} {v}' for k, v in sorting_request])
    logging.info(f"sorting_query created: {sorting_query}")
    return sorting_query


def get_search_query(search_str):
    """Function gets the search query from the event
    Args: search_str: str: search string from the input
    Returns: dict: search query for mongodb"""
    if not search_str:
        return None
    logging.info(f"search_str: {search_str}")
    search_query = " OR ".join(
        [f"\"{k}\" LIKE '%{search_str}%'" for k in config.SEARCH_PARAMS]
    )
    logging.info(f"search_query: {search_query}")
    return search_query


def parse_result_list(query_result_set):
    """Function to parse the result set returned from the database
    Args: final_data: list: list of dictionaries
    Returns: list: list of dictionaries in the required format"""
    json_encoding = lambda obj: (obj.isoformat() if isinstance(obj, datetime) else None)
    data = list(query_result_set)
    data = json.loads(json.dumps(data, default=json_encoding))
    return data

def get_audit_entry(audit_coll, document_no):
    """
    Retrieves an audit entry from the specified audit collection.

    Args:
        audit_coll (str): The name of the audit collection.
        document_no (str): The document number to query.

    Returns:
        dict: The validated query response containing the audit entry.
    """

    query = GET_AUDIT_QUERY.format(document_no=document_no, DATABASE_NAME=config.DATABASE_NAME, AUDIT_COLLECTION_NAME=audit_coll)
    logging.info(f"query:{query}")
    db_result = execute_query(query)
    result_list = list(db_result)
    return validate_query_response(result_list, document_no, audit_coll)

def validate_query_response(result_list, document_number, audit_coll):
    """
    Validates the query response by checking the number of results and returns the appropriate audit record or error message.

    Args:
        result_list (list): The list of results from the query.
        document_number (str): The document number associated with the query.
        audit_coll (str): The key to retrieve the audit collection from the result.

    Returns:
        tuple: A tuple containing the audit record (dict) if found, and an error message (str) if applicable.
    """
    
    logging.info("Validating query response")
    json_encoding = lambda obj: (obj.isoformat() if isinstance(obj, datetime) else None)
    query_response_list = json.loads(json.dumps(result_list, default=json_encoding))
    result_count = len(query_response_list)
    if result_count == 1:
        return query_response_list[0].get(audit_coll), None
    elif result_count == 0:
        return {}, 'No audit record exists for document number: ' + document_number + '.'
    else:
        return {}, 'Duplicate audit records found for document number: ' + document_number + '.'
    
def add_new_audit_status(document_no, error, success_status, failure_status):
    """ Update audit status: queries audit table, creates new success/failure
        audit status, updates/creates entry in audit table.
    """
    audit_entry, audit_error = get_audit_entry(db_audit_collection, document_no)
    audit_entry = json.loads(audit_entry) if isinstance(audit_entry, str) else audit_entry
    convert_array_str_to_list(audit_entry)
    status = create_audit_status(audit_error, error, document_no, success_status, failure_status)
    if audit_entry:
        system_actions = audit_entry.get('system_actions', [])
        system_actions.append(status)
        set_clause = f"\"system_actions\" = '{json.dumps(system_actions)}'"
        where_clause = f"\"document_no\" = '{document_no}'"
        query = UPDATE_QUERY_WITH_WHERE_CONDITION.format(DATABASE_NAME=config.DATABASE_NAME, COLLECTION_NAME=config.INVOICE_AUDIT_COLLECTION_NAME, SET_VALUES=set_clause, WHERE_CONDITION=where_clause)
        execute_query(query, query_type="UPDATE")
    if not audit_entry:
        create_error_audit_entry(db_audit_collection, document_no, status)

def create_error_audit_entry(audit_coll, document_no, status):
    """ In case of error in retrieving audit table entry, create new entry
        documenting failure status
    """
    audit_entry = {
        "document_no": document_no,
        "system_actions": [
            status
        ]
    }
    value = (f"{audit_entry}").replace("'", '"')
    query = INSERT_INTO_DB_QUERY.format(DATABASE_NAME=config.DATABASE_NAME, COLLECTION_NAME=audit_coll, KEY_VALUE=value)
    logging.info(f"creating audit entry:{query}")
    execute_query(query, query_type="INSERT")

def create_audit_status(audit_error, error, document_no, success_status, failure_status):
    """ Creates new audit status. Fail status is created if there was an error
        encountered in the code or while retrieving audit table entry.
        Otherwise, success status is created and invoice audit table is updated.
    """
    logging.info(f"error:{error}\naudit_error:{audit_error}")
    if audit_error:
        error = audit_error + ' ' + error if error else audit_error
    if error:
        status = {
            'status': failure_status,
            'status_message': error,
            'status_created': datetime.datetime.now().isoformat()
        }
    else:
        status_message = 'Invoice ' + document_no + ' updated with Fuzzy Match information.'
        status = {
            'status': success_status,
            'status_message': status_message,
            'status_created': datetime.datetime.now().isoformat()
        }
    return status

def handle_nested_dict(nested_dict, parent_keys=[]):
    """
        This function will be called from construct_set_clause function to handle nested dictionaries
    """
    set_clause_parts = []
    for nested_key, nested_value in nested_dict.items():
        current_keys = parent_keys + [nested_key]
        if isinstance(nested_value, dict):
            set_clause_parts.extend(handle_nested_dict(nested_value, current_keys))
        else:
            full_key = ".".join(f'"{k}"' for k in current_keys)
            if nested_value is None:
                set_clause_parts.append(f'{full_key} = null')
            elif isinstance(nested_value, str):
                set_clause_parts.append(f'{full_key} = \'{nested_value}\'')
            else:
                set_clause_parts.append(f'{full_key} = {nested_value}')
    return set_clause_parts

def construct_set_clause(document):
    """
    Construct the set clause for update query
    Example Input:
        {
            "supplier": {
                "attribute_value": "Appriss Health",
                "confidence": 0.7052471,
                "edited_by_user": False
            },
            "net_amt: {
                "attribute_value": 165245.0,
                "confidence": 0.97313684,
                "edited_by_user": False
            }
        }
    Example Output:
        "supplier"."attribute_value" = 'Appriss Health', "supplier"."confidence" = 0.7052471, "supplier"."edited_by_user" = False, "net_amt"."attribute_value" = 165245.0, "net_amt"."confidence" = 0.97313684, "net_amt"."edited_by_user" = False
    """
    set_clause_parts = []
    for key, value in document.items():
        if isinstance(value, dict):
            set_clause_parts.extend(handle_nested_dict(value, [key]))
        else:
            if value is None:
                set_clause_parts.append(f'"{key}" = null')
            elif isinstance(value, str):
                set_clause_parts.append(f'"{key}" = \'{value}\'')
            else:
                set_clause_parts.append(f'"{key}" = {value}')
    return ", ".join(set_clause_parts)