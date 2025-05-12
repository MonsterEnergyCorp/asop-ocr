import logging
import re
from datetime import datetime

def process_bill_and_ship_to(header_data):
    """
    Process the bill-to and ship-to data to extract the relevant information.
    """
    bill_to = {}
    ship_to = {}
    address_sub_keys = ["Name", "City",  "Street", "Zip"]
    if all(key in header_data for key in address_sub_keys):
        for key in address_sub_keys:
            values = header_data.get(key, [])
            if values:
                bill_to[f"Bill{key}"] = str(values[0]) if len(values) > 0 else None
                ship_to[f"Ship{key}"] = str(values[1]) if len(values) > 1 else None

        for key in address_sub_keys:
            header_data.pop(key, None)
        header_data["BillTo"] = ','.join([str(i) for i in header_data.get("BillTo",[]) if i])
        header_data["ShipTo"] = ','.join([str(i) for i in header_data.get("ShipTo",[]) if i])    
        return {**header_data, **bill_to, **ship_to}    
    else:
        logging.info(f'Bill To {header_data.get("BillTo", [])} & Ship To {header_data.get("ShipTo", [])}')
        header_data = generate_addresses(header_data,header_data.get("BillTo", []), "Bill")
        header_data = generate_addresses(header_data,header_data.get("ShipTo", []), "Ship")
        return header_data
    
def special_quantity_transforms(tabular_data):
    for i in tabular_data:
        if i.get('CasesQuantity'):
            i['Quantity'] = i.pop('CasesQuantity')
            i['Uom'] = 'CS'
            if 'EachesQuantity' in i:
                i.pop('EachesQuantity')
        elif i.get('EachesQuantity'):
            i['Quantity'] = i.pop('EachesQuantity')
            i['Uom'] = 'EA'
            if 'CasesQuantity' in i:
                i.pop('CasesQuantity')
    return tabular_data 

def region_specific_tabular_transforms(region, item):
    if region=="EMEA":
        item['DlvDate'] = convert_date_format(item.get('DlvDate',""))
        if item.get("ItemShipTo"):
            item['ShipTo'] = item.pop("ItemShipTo")
    return item        

def convert_date_format(date_str):
    if isinstance(date_str, datetime):
        return date_str.strftime('%Y-%m-%d')
    # Define possible date formats
    date_formats = ['%Y-%m-%d %H:%M:%S','%d/%m/%Y', '%d.%m.%Y', '%m.%d.%y', '%m/%d/%Y', '%d-%m-%Y', '%d-%m-%y', '%Y-%m-%d', '%b %d, %Y', '%B %d, %Y', '%d %b %Y', '%d %B %Y','%B %d %Y', '%b %d %Y', '%m/%d/%y', '%m-%d-%y', '%m-%d-%Y', '%m.%d.%Y']

    for date_format in date_formats:
        try:
            # Try to parse the date string with the current format
            date_obj = datetime.strptime(str(date_str), date_format)
            # Convert to 'YYYY-MM-DD' format
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            # If parsing fails, try the next format
            continue

    # If none of the formats match, raise an error
    return ""

def process_tabular_data(tabular_data, po_key, region):
    """
    Process the tabular data to extract the relevant information.
    args:
        tabular_data: list of dictionaries
        po_key: key to sort the tabular data
    Filters out the tabular data based on the quantity field and adds Item number and AsopNo.
    If customer number is present, it sorts and groups based on string entry.
    """
    tabular_data = special_quantity_transforms(tabular_data)
    quantity_field = "Quantity"
    transformed_tabular_data = []
    line_count=0
    tabular_data = sort_cust_po_in_tabular_data(tabular_data, po_key)
    for i in tabular_data:
        if i.get(quantity_field):
            i = {i_key: ('' if i_value is None else i_value) for i_key, i_value in i.items()}
            i["AsopNo"] = "0000000000"
            line_count += 10
            i["OCRItemno"] = str(line_count)
            i["Uom"] = i.get("Uom") if i.get("Uom") else "CS"
            i = region_specific_tabular_transforms(region,i)
            transformed_tabular_data.append(i)
            
    return transformed_tabular_data

def sort_cust_po_in_tabular_data(tabular_data, sort_key):
    return sorted(tabular_data, key=lambda x: (x.get(sort_key) is None, x.get(sort_key, '')))

def generate_addresses(header_data, address_data, address_type):
    """Generates the address string from the address data for bill or ship to"""
    address_dict={}
    try:
        if isinstance(address_data, list) and len(address_data)==3:
            address_dict[f'{address_type}Name'] = address_data[0]
            address_dict[f'{address_type}Street'] = address_data[1]
            address_third_line=address_data[2].split(',') if address_data[2] else []
            address_dict[f'{address_type}City'] = address_third_line[0]
            address_region_zip = separate_region_and_zip(address_third_line[1])
            address_dict[f'{address_type}Region'] = address_region_zip.get('region','')
            address_dict[f'{address_type}Zip'] = address_region_zip.get("zip", "")
            header_data.pop(f"{address_type}To")
            header_data = {**header_data, **address_dict}  
        elif isinstance(address_data, list) and all(isinstance(i, int) for i in address_data if i):
            header_data[f"{address_type}To"] = ','.join([str(i) for i in address_data if i])    
        else:
            address_val = header_data.pop(f"{address_type}To","")
            header_data[f"{address_type}Address"] = ','.join([str(i) for i in address_val if i])
    except Exception as e:
        logging.info(f'Generation Address Exception: {e}')
        address_val = header_data.pop(f"{address_type}To","")
        header_data[f"{address_type}Address"] = ','.join([str(i) for i in address_val if i])
    return header_data

            
def separate_region_and_zip(input_string):
    parts = re.split(r'(\d+)', input_string.replace(" ",""))
    result = {"region": "", "zip": ""}
    for part in parts:
        if part.isdigit():
            result["zip"] += part
        else:
            result["region"] += part       
    return result

def finalize_cust_po_level(header_data, po_key):
    """Removes cust po from header level if present at line item level"""
    po_key_val = header_data.get(po_key)
    if po_key and  isinstance(po_key_val, list) and len(po_key_val)>1:
        header_data.pop(po_key)
    return header_data

def add_erp_metadata_information(file_data):
    """
    Function to format the metadata for the parsed data
    args -
    cleaned_data - cleaned data from the parsed output
    content - pdf file content
    extracted_data - extracted data from the parsed output
    file_data - data from the file
    return -
    metadata - formatted metadata for the parsed data
    """
    metadata = {}
    metadata["AsopNo"] = "0000000000"
    metadata["CustEmail"] = file_data.get("sender_email","")
    metadata["MonsterEmail"] = ""
    metadata["FileDate"] = file_data.get("created_at","")
    metadata["FileName"] = f'{file_data.get('file_name',"placeholder")}.eml'
    metadata["MimeType"] = file_data.get('file_type',"")
    metadata['Field1'] = ''
    metadata['Field2'] = ''
    metadata['Field3'] = ''
    metadata['Field4'] = ''
    metadata['Field5'] = ''
    
    return [metadata]


def post_processing_transformations(header_data, tabular_data, po_key, hana_data, region):
    """Primary post processing function to drive the transformations"""
    header_data = process_bill_and_ship_to(header_data)
    header_data = finalize_cust_po_level(header_data, po_key)
    tabular_data = process_tabular_data(tabular_data, po_key, region)
    metadata = add_erp_metadata_information(hana_data)
    return header_data, tabular_data, metadata



    


