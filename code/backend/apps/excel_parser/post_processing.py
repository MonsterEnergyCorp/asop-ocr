import logging
import re
from datetime import datetime
from apps.excel_parser.auxiliary_data import *

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
        regional_reverse_map = regional_map_lvl2.get(region, {})
        item['DlvDate'] = convert_date_format(item['DlvDate'])
        if item.get('ItemPODate'):
            item['ItemPODate'] = convert_date_format(item['ItemPODate'])
        valid_reverse_maps = [field for field in item if regional_reverse_map.get(field)]
        if valid_reverse_maps:
            for field in valid_reverse_maps:
                item[regional_reverse_map[field]] = item.pop(field)
    #ARCA            
    elif region=="LATAM":
        regional_reverse_map = regional_map_lvl2.get(region, {}) 
        valid_reverse_maps = [field for field in item if regional_reverse_map.get(field)]
        if valid_reverse_maps:
            for field in valid_reverse_maps:
                item[regional_reverse_map[field]] = item.pop(field)              
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
        if is_quantity_field_empty(i):
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
            if address_val[0] and isinstance(address_val[0], int):
                header_data[f"{address_type}To"] = str(address_val[0])
                address_val = address_val[1:] if len(address_val)>1 else address_val
            header_data[f"{address_type}Address"] = ','.join([str(i) for i in address_val if i])
    except Exception as e:
        logging.info(f'Generation Address Exception: {e}')
        address_val = header_data.pop(f"{address_type}To","")
        header_data[f"{address_type}Address"] = ','.join([str(i) for i in address_val if i])
    return header_data

def is_quantity_field_empty(tabular_row):
    """
    Check if the quantity field in the tabular row is empty or not.
    """
    quantity = tabular_row.get("Quantity")
    if isinstance(quantity, str):
        return True if quantity.strip() not in ["", "0", "-"] else False
    elif isinstance(quantity, (int, float)):
        return True if quantity**2 == quantity else False
    return True if quantity else False


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

def pos_template_custom_process_headers(header_data, special_template_type):
    print(f'Incoming headers: {header_data}')
    if special_template_type == "POS":
        pos_company = header_data.pop("POSCompany", [])
        pos_company = [x for i, x in enumerate(pos_company) if i % 2 == 0]
        header_data["SoldToName"] = str(pos_company[0]) if pos_company else ""
        header_data["ShipName"] = str(pos_company[1]) if len(pos_company) > 1 else ""

        pos_street = header_data.pop("AddressStreet", [])
        pos_street = [x for i, x in enumerate(pos_street) if i % 2 == 0]
        header_data["SoldStreet"] = str(pos_street[0]) if pos_street else ""
        header_data["ShipStreet"] = str(pos_street[1]) if len(pos_street) > 1 else ""

        pos_hybrid_address = header_data.pop("HybridCityStateZip", "").split()
        header_data["SoldCity"] = ' '.join(pos_hybrid_address[0:-2]) if len(pos_hybrid_address) > 2 else ""
        header_data["SoldRegion"] = str(pos_hybrid_address[-2]) if len(pos_hybrid_address) > 1 else ""
        header_data["SoldZip"] = str(pos_hybrid_address[-1]) if len(pos_hybrid_address) > 0 else ""

        city_details = header_data.pop("City", [])
        header_data["ShipCity"] = str(city_details[0]) if city_details else ""

        zip_details = header_data.pop("Zip", [])
        header_data["ShipZip"] = str(zip_details[0]) if zip_details else ""

        header_data["ShipTo"] = header_data.pop("ShipAddress", "")

        header_data["CustPo"] = header_data.pop("CustPo", "").split(',')[0]

        header_data["NewShipToAdd"] = "true" if header_data.get("NewShipToAdd", []) else "false"

    elif special_template_type == "POS_CONSUMER_MARKETING":
        city = header_data.pop("City", []) 
        header_data["ShipCity"] = city[0] if city else ""
        header_data["ShipTo"] = header_data.pop("ShipAddress", "").split(',')[0]   
        header_data["NewShipToAdd"] = "true"
    elif special_template_type == "POS_ATHLETE":
        header_data["SoldToName"] = header_data.pop("Name", [""])[0] 
        header_data["ShipName"] = header_data.pop("POSCompany", [""])[0]
        header_data["ShipStreet"] = header_data.pop("AddressStreet", [""])[0]
        header_data["ShipCity"] = header_data.pop("City", [""])[0]
        header_data["ShipZip"] = str(header_data.pop("Zip", [""])[0])


    return header_data


def pos_line_item_custom_processing(consolidated_outputs, special_template_type):
    """
    Custom processing for POS line items based on the special template type.
    """
    consolidated_tabular_data = [i.pop("NavHeadToItem",[]) for i in consolidated_outputs if "NavHeadToItem" in i]
    if special_template_type == "POS":
        tabular_data = []
        for sublist in consolidated_tabular_data:
            for item in sublist:
                if "MatTextInd" in item:
                    item["MatTextInd"] = "true"
                tabular_data.append(item)  
    else:
        tabular_data = [item for sublist in consolidated_tabular_data for item in sublist]              
    return tabular_data




def special_template_custom_procesing(final_output, distributed_line_items, special_template_type, custom_rulesets=False):
    print(f'special template custom processing: {special_template_type}\n\n\n')
    if distributed_line_items:
        consolidated_outputs = list(final_output.values())
        consolidated_tabular_data = pos_line_item_custom_processing(consolidated_outputs, special_template_type)
        header_data = consolidated_outputs[0]
        header_data = pos_template_custom_process_headers(header_data, special_template_type)
        final_output = {"POS_TRANSFORMS":{**header_data, "NavHeadToItem": consolidated_tabular_data}}
        return final_output
    elif special_template_type == "ARCA":
        final_output_values = list(final_output.values())[0]
        final_output_values["AddField1"] = "MASSCREATION"
        final_output_values["PODate"] = datetime.today().strftime('%Y-%m-%d')
        final_output_values["ShipTo"] = final_output_values.get("ShipTo","").split(",")[0]
    return final_output  


def apparels_form_check(sheet_name, region, header_data):
    """
    Check if the sheet is an apparels form based on the sheet name and region.
    """
    sales_org = header_data.get("SalesDocType")
    if sales_org == "ZEM":
        if region == "US" and sheet_name.lower() == "apparel":
            header_data["AddField1"] = "APPAREL"
        else:
            header_data["AddField1"] = "PRODUCT"

    return header_data

def post_processing_transformations(header_data, tabular_data, po_key, hana_data, region):
    """Primary post processing function to drive the transformations"""
    header_data = process_bill_and_ship_to(header_data)
    logging.info(f'First Stage header: {header_data}')
    logging.info(f'First stage unprocessed line items: {tabular_data}\n')
    header_data = finalize_cust_po_level(header_data, po_key)
    tabular_data = process_tabular_data(tabular_data, po_key, region)
    metadata = add_erp_metadata_information(hana_data)
    return header_data, tabular_data, metadata