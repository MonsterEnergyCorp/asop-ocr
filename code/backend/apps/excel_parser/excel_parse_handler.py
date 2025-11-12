import json
import openpyxl
from datetime import datetime
from io import BytesIO
from apps.excel_parser.auxiliary_data import *
from apps.excel_parser.post_processing import *
from core.azure_storage.blob_storage_connection import *
from core.config import config
from core.db.connection import *
from core.util import *
import logging
import copy
import traceback
import re

po_key = "CustPo"
main_table_key = "Material"

ocr_erp_push_url = config.ocr_erp_push_url


# Environment variables
sas_token = config.sas_token
account_url = config.account_url
container_name = config.container_name
db_name = config.db_name
db_collection = config.db_collection

# --- Begin of code to check Order Type for determining POS template - By Mansi on 30/09/2025 for INC0081672/ RITM0037876 ---
# --- POS identification via ORDER TYPE (new requirement) ---
try:
    POS_ORDER_TYPES = {t.strip().upper() for t in getattr(config, 'pos_order_types', [])} or {'ZPOS', 'ZORP'}
except Exception:
    POS_ORDER_TYPES = {'ZPOS', 'ZORP'}


def _get_order_type_from_header(header_data: dict):
    """
    Retrive OrderType from header_data. All possible values maintained.
    Returns a list of normalized order types if found, else an empty list.
    """
    checkvariable = [
        header_data.get('OrderType'),
        header_data.get('Order_Type'),
        header_data.get('Order Type'),
        header_data.get('ORDERTYPE'),
        header_data.get('SalesDocType'),
    ]
    raw = next((c for c in checkvariable if c), None)
    if not raw:
        return []
    parts = str(raw).replace(';', ',').split(',')
    return [p.strip().upper() for p in parts if p and p.strip()]


def is_pos_order(header_data: dict) -> bool:
    """
    Function to return true or false if Order Type matches with the maintained list.
    """
    order_types = _get_order_type_from_header(header_data)
    logging.info(f'Order Type: {order_types}')
    return any(ot in POS_ORDER_TYPES for ot in order_types)


def extract_numeric_cost_centre(values):
    """
    Extract the last 6–12 digit number from a list of strings.
    """
    for v in reversed(values):
        matches = re.findall(r"\b\d{6,12}\b", str(v))
        if matches:
            return matches[-1]
    return ""

# --- End of code to check Order Type for determining POS template - By Mansi on 30/09/2025 for INC0081672/ RITM0037876 ---

def parse_data(wb):
    """Function to parse the data from the Excel workbook using openpyxl.
    args: wb: openpyxl.Workbook object
    returns: A dictionary containing the parsed data from the workbook with keys as sheet names."""
    data = {}
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        sheet_data = []
        for row in sheet.iter_rows(values_only=True):
            row_data = [cell for cell in row]
            sheet_data.append(row_data)
        data[sheet_name] = sheet_data
    return data

def scan_horizontal(row, start_index, keys):
    """
    Function to scan horizontally. Stop condition includes 3 consecutive empty cells or a cell containing a key.
    """
    collected = []
    consecutive_empty = 0
    for col, cell in enumerate(row[start_index:]):
        transformed_cell = transform_string(cell)
        if transformed_cell in keys:
            # Stop if the cell contains a key.
            break
        if transformed_cell in [None, ""]:
            consecutive_empty += 1
            if consecutive_empty >= 5:
                # Three consecutive empty cells encountered, so break.
                break
        else:
            # Reset empty cell count when a valid cell is found.
            consecutive_empty = 0
            collected.append({col:cell})
    return collected

def scan_vertical(sheet, start_row, col, keys, cell_value):
    """
    Function containing logic to scan vertically. Stop condition includes 3 consecutive empty cells or a cell containing a key for certain fields.

    :param sheet: 2D list representing the entire Excel sheet.
    :param start_row: The row index from which to start scanning downward.
    :param col: The column index of the cells to scan.
    :param keys: The list of keys that should stop the scan.
    :return: A list of collected non-empty cell values.
    """
    collected = []
    additional_description = []
    consecutive_empty = 0
    for r in range(start_row, len(sheet)):
        cell = sheet[r][col]
        transformed_cell = transform_string(cell)
        if transformed_cell in keys:
            break
        if transformed_cell in [None, ""] and multi_valued.get(cell_value)!="multi_valued":
            if non_columnar_entry_keys.get(cell_value):
                additional_description.append({r:sheet[r][col+non_columnar_entry_keys.get(cell_value)]})
            collected.append({r:cell})   #CHANGED
            consecutive_empty += 1
            if consecutive_empty >= 5:
                break
        else:
            consecutive_empty = 0
            collected.append({r:cell})
            if non_columnar_entry_keys.get(cell_value):
                logging.info(f'\nVAL: {sheet[r][col-1]}, {r},{col-1}')
                logging.info(f'VAL1: {sheet[r][col]}, {r},{col}, {cell_value}n')
                additional_description.append({r:sheet[r][col+non_columnar_entry_keys.get(cell_value)]})
    return collected, additional_description


def sheet_traversal(sheet, keys):
    """
    Parses the sheet data into a JSON-like structure.

    :param sheet: A 2D list where each inner list is a row from the Excel sheet.
    :param keys: A list of known keys.
    :return: A dictionary mapping keys to a list of occurrences, where each occurrence
             contains extracted values under "right" and/or "below".
    """
    results = {}
    num_rows = len(sheet)
    num_cols = len(sheet[0]) if num_rows > 0 else 0

    for i in range(num_rows):
        for j in range(num_cols):
            cell_value = sheet[i][j]
            cell_value = transform_string(cell_value)
            if cell_value in keys:
                key = cell_value
                occurrence = {}
                additional_occurences = {}

                # Initialize the results for this key if needed.
                if key not in results:
                    results[key] = []

                # Horizontal scan (to the right)
                if j + 1 < num_cols and directional_biases.get(cell_value) in [None, 'right']:
                    horizontal_values = scan_horizontal(sheet[i], j + 1, keys)
                    if horizontal_values:
                        occurrence["right"] = horizontal_values

                # Vertical scan (downward)
                if i + 1 < num_rows and  directional_biases.get(cell_value) in [None, 'below']:
                    vertical_values, additional_description = scan_vertical(sheet, i + 1, j, keys, cell_value)
                    if vertical_values:
                        occurrence["below"] = vertical_values
                    if additional_description:
                        additional_occurences["below"] = additional_description
                results[key].append(occurrence)
                if additional_occurences:
                    if "DESCRIPTION" not in results:
                        results["DESCRIPTION"] = []
                    results["DESCRIPTION"].append(additional_occurences)

    return results

def transform_string(cell):
    """
    Function to transform the cell value to a string and remove any whitespace.
    """
    return cell.replace(' ','').replace('\n','') if isinstance(cell, str) else cell

def erp_field_mapping(parsed_data, region):
    """
    Function to map the parsed data to the ERP fields.
    """
    mapped_data={}
    if "PACKAGE" in parsed_data and "DESCRIPTION" in parsed_data:
        parsed_data.pop("DESCRIPTION")
    regional_map = regional_map_lvl1.get(region,{})
    for k,v in parsed_data.items():
        if regional_map.get(k):
            mapped_data[regional_map.get(k)]=v
        elif data_mapping.get(k):
            mapped_data[data_mapping.get(k)] = v
    return mapped_data

def get_tabular_keys_instance(region, parsed_data):
    tabular_keys_instance = tabular_keys.get(region) if tabular_keys.get(region) else tabular_keys.get("Other")
    return tabular_keys_instance

def extract_tabular_data(data, tabular_keys_instance):
    """
    Extracts tabular data from the parsed JSON that is used as LINEITEMS
    """
    try:
        data = {i:data.get(i) for i in tabular_keys_instance.get(main_table_key) if data.get(i)}
        result = []
        tab_keys = data.keys()
        sub_key = next(iter(data[main_table_key][0].keys()))  # Dynamically derive the sub-key (e.g., 'below')

        for i in range(len(data[main_table_key])):
            order_code_sub = data[main_table_key][i].get(sub_key, [])
            #other_sub_data = {key: data[key][i].get(sub_key, []) for key in tab_keys if key != main_table_key}

            other_sub_data = {}
            for key in tab_keys:
                if key != main_table_key:
                    other_sub_data[key] = data[key][i].get(sub_key, [])

            for item in order_code_sub:
                for key, value in item.items():
                    if value is not None:
                        matched_data = {main_table_key: str(value)}
                        for other_key, other_sub in other_sub_data.items():
                            val = next((d.get(key) for d in other_sub if key in d), None)
                            matched_data[other_key] = str(val) if val else None
                        result.append(matched_data)
    except Exception as e:
        logging.info(f'Error in extract_tabular_data: {e}')
        logging.info(f'TRACEBACK: {traceback.format_exc()}')
    return result

def extract_innermost_values(obj):
    """
    Helper function to recursively extract the innermost values from a nested dictionary or list.
    """
    if isinstance(obj, dict):
        values = []
        for value in obj.values():
            values.extend(extract_innermost_values(value))
        return values
    elif isinstance(obj, list):
        values = []
        for item in obj:
            values.extend(extract_innermost_values(item))
        return values
    elif isinstance(obj, (str, int, float, datetime)):
        return [obj]
    else:
        return []

def header_value_extraction(key,value):
    header_val = extract_innermost_values(value)
    # --- Begin of code to check Cost Center for Consumer Marketing template - By Mansi on 11/11/2025 for INC0081672/ RITM0037876 ---
    # Custom logic for CostCentre     
    if key == "CostCentre":
        return extract_numeric_cost_centre(header_val)
    # --- End of code to check Cost Center for Consumer Marketing template - By Mansi on 11/11/2025 for INC0081672/ RITM0037876 ---
    if data_dimensions.get(key) == "singular":
        header_val = number_check_for_integer( header_val[0]) if header_val else ''
    if data_dimensions.get(key) == "date_type":
        header_val = convert_date_format(header_val[0]) if header_val else ''
    if data_dimensions.get(key) == "possible_singular":
        if len([v for v in header_val if v is not None]) <= 1:
            header_val = number_check_for_integer( header_val[0]) if header_val else ''
        else:
            header_val = ','.join([str(i) for i in header_val if i])
    return header_val

def number_check_for_integer(value):
    if isinstance(value, (int, float)) and value == int(value):
        return str(int(value))
    return str(value)

def extract_header_data(data, tabular_keys_instance):
    """
    Parse the JSON data to extract the header information.
    """
    parsed_json = {}
    for key, value in data.items():
        if key not in tabular_keys_instance.get(main_table_key):
            parsed_json[key] = header_value_extraction(key, value)
    
    # Fallback: if CostCentre is missing or not numeric, try ShipAddress
    cc = parsed_json.get("CostCentre", "")
    if not re.fullmatch(r"\d{6,12}", str(cc)):
        for field in ("ShipAddress", "ShipTo"):
            val = parsed_json.get(field, "")
            match = extract_numeric_cost_centre([val])
            if match:
                parsed_json["CostCentre"] = match
                break

    return parsed_json

def extract_po_numbers(header_data, tabular_data, sheet_name):
    """
    Extracts the PO numbers from the header and tabular data.
    """
    if header_data.get(po_key):
        sheet_po_numbers = header_data.get(po_key)
    else:
        sheet_po_numbers_list  = [i.get(po_key,'') for i in tabular_data]
        sheet_po_numbers = ','.join(list(set(i for i in sheet_po_numbers_list if i)))
        sheet_po_numbers = sheet_po_numbers if sheet_po_numbers else sheet_name
    return sheet_po_numbers

def update_processed_values(data):
    """
    Function to write the query set values for the processed data for excel.
    """
    po_numbers = ",".join(list(data.keys()))
    data_str = json.dumps(data).replace("'", "''")
    ocr_data = f'"erp_request_payload" = ' + f"'{data_str}'" + " , " + '"po_numbers" = ' + f"'{po_numbers}'"
    return ocr_data

def update_metadata_for_failure(metadata):
    data = {"UNEXTRACTED":{"Status": "52", "NavHeadtoMeta": metadata}} #Status 52 represents failure in SAP :)
    ocr_data = f'"erp_request_payload" = ' + f"'{json.dumps(data)}'"
    return ocr_data

def get_outlier_customers(connection):
    """
    Function to get the outlier customers from the database.
    """
    special_template_data = get_special_templates_data(connection)
    return special_template_data
    #return {"pos": ['1000759', '1000760', '1000761', '1000807'], "ARCA": ['1004572']}

def distributed_line_item_check(header_data, outlier_customers, distributed_line_items):
    """
    Function to check if the customer is an outlier.
    Returns updated value of distributed_line_items.
    POS/distributed behavior is driven ONLY by Order Type (ZPOS, ZORP).
    Customer lists are ignored for POS determination.
    """
    logging.info(f'distributed_line_items: {distributed_line_items}')
    if not distributed_line_items:
        return is_pos_order(header_data)  # True only for POS order types
    return distributed_line_items

def special_template_customers_check(header_data, region, outlier_customers, special_template_type=None):
    """
    Function to check if the customer is an outlier.
    Returns template type
    POS template is chosen ONLY by Order Type (ZPOS, ZORP).
    Customer-based selection applies ONLY to non-POS templates (e.g., ARCA, PROPIMEX).
    """
    sold_to = header_data.get("SoldTo")
    logging.info(f'Incoming  Special Template Type: {special_template_type}')
    logging.info(f'Incoming  Sold To: {sold_to}')

    
    # 1) POS by Order Type, but also check POS_* customer lists
    if is_pos_order(header_data):
        for key, customers in outlier_customers.items():
            if str(key).upper().startswith("POS") and sold_to in customers:
                logging.info(f'Using: {key} & {sold_to}')
                return key
        return "POS"


    # 2) Non-POS special templates by customer list
    if not special_template_type:
        for key, customers in outlier_customers.items():
            if str(key).upper().startswith("POS"):
                continue  # explicitly ignore any POS* lists
            if sold_to in customers:
                return key

    return special_template_type


def excel_parsing_flow(file_id):
    connection = connect_to_db()
    hana_data = erp_data_fetch(connection, file_id)
    file_path = hana_data.get("file_path","")
    region = hana_data.get("region", "US")
    content = read_file_from_object_store(file_path)
    wb = openpyxl.load_workbook(BytesIO(content), data_only=True)
    workbook_data = parse_data(wb)
    distributed_line_items = False
    final_output={}
    failed_sheets = []
    special_template_type=None
    outlier_customers = get_outlier_customers(connection)
    for sheet_name, sheet in workbook_data.items():
        try:
            parsed_data = sheet_traversal(sheet, keys)
            logging.info(f' PARSED DATA: {parsed_data}')
            if not parsed_data:
                continue

            parsed_data = erp_field_mapping(parsed_data, region)
            tabular_keys_instance = get_tabular_keys_instance(region, parsed_data)
            header_data = extract_header_data(parsed_data, tabular_keys_instance)
            tabular_data = extract_tabular_data(parsed_data, tabular_keys_instance)
            special_template_type = special_template_customers_check(header_data, region, outlier_customers, special_template_type)
            logging.info(f'Determined Special Template: {special_template_type}')

            header_data, tabular_data, metadata = post_processing_transformations(header_data, tabular_data, po_key, hana_data, region)   
            logging.info(f'\n processed headers: {header_data}')
            distributed_line_items = distributed_line_item_check(header_data, outlier_customers, distributed_line_items)
            if not distributed_line_items and not tabular_data:
                print(f'PASSING SHEET: {sheet_name}')
                continue
            sheet_po_numbers = extract_po_numbers(header_data, tabular_data, sheet_name)
            header_data = apparels_form_check(sheet_name, region, header_data)  #ZEM
            final_output[sheet_po_numbers] = {**header_data, "NavHeadToItem": tabular_data, "NavHeadtoMeta": metadata}
        except Exception as e:
            logging.info(f'EXCEL EXTRACTION ISSUE: {e}')
            logging.info(f'TRACEBACK: {traceback.format_exc()}')
            failed_sheets.append(sheet_name)
        #final_output = pos_template_custom_procesing(final_output, distributed_line_items)
    final_output = special_template_custom_procesing(final_output,distributed_line_items, special_template_type) 
    print(f'last op: {final_output}')
    if not final_output:
        metadata = add_erp_metadata_information(hana_data)
        ocr_update_data = update_metadata_for_failure(metadata)
    else:
        ocr_update_data = update_processed_values(final_output)
    logging.info("123456")
    hana_storage_push(file_id, connection, ocr_update_data)
    close_connection(connection)
    push_to_erp(ocr_erp_push_url, file_id)
    return final_output
