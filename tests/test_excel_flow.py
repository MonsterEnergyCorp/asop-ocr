import sys
import types
import unittest
from pathlib import Path
from unittest import mock

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))


class _AnyConfig:
    # Any setting the Excel handler reads at import time; empty string is enough for these tests.
    def __getattr__(self, name):
        return ""


_hana_pushes = []
_erp_calls = []

# Stand-ins for HANA, Blob and config so the real excel_parsing_flow() runs without a network.
# They are installed only while the Excel handler is imported, then removed, so other tests in the
# same run still get the real core.* modules.
_STUBBED = {
    "core.config": {"config": _AnyConfig()},
    "core.azure_storage.blob_storage_connection": {},
    "core.db.connection": {"connect_to_db": lambda: "conn", "close_connection": lambda connection: None},
    "core.util": {
        "erp_data_fetch": lambda connection, file_id: {"file_path": "x.xlsx", "region": "LATAM", "file_name": "x.xlsx"},
        "read_file_from_object_store": lambda path: b"",
        "hana_storage_push": lambda file_id, connection, values: _hana_pushes.append(values),
        "push_to_erp": lambda url, file_id: _erp_calls.append(file_id),
    },
}
_saved = {name: sys.modules.get(name) for name in list(_STUBBED) + ["apps.excel_parser.excel_parse_handler"]}
for _name, _attrs in _STUBBED.items():
    _module = types.ModuleType(_name)
    _module.__dict__.update(_attrs)
    sys.modules[_name] = _module
try:
    from apps.excel_parser import excel_parse_handler as handler  # noqa: E402
finally:
    for _name, _original in _saved.items():
        if _original is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _original


class ExcelFlowNoUsableSheetTests(unittest.TestCase):
    def setUp(self):
        _hana_pushes.clear()
        _erp_calls.clear()

    def _run_flow(self, workbook_sheets):
        with mock.patch.object(handler.openpyxl, "load_workbook", return_value=mock.Mock()), \
             mock.patch.object(handler, "parse_data", return_value=workbook_sheets), \
             mock.patch.object(handler, "sheet_traversal", return_value={}), \
             mock.patch.object(handler, "detect_template_region", return_value="LATAM"):
            return handler.excel_parsing_flow("file-1")

    def test_every_sheet_skipped_still_goes_to_hana_and_erp_as_status_52(self):
        result = self._run_flow({"Order": object(), "Notes": object()})

        self.assertEqual({}, result)
        self.assertEqual(1, len(_hana_pushes))
        self.assertIn("UNEXTRACTED", _hana_pushes[0])
        self.assertIn('"Status": "52"', _hana_pushes[0])
        self.assertEqual(["file-1"], _erp_calls)

    def test_workbook_without_sheets_still_goes_to_hana_and_erp_as_status_52(self):
        result = self._run_flow({})

        self.assertEqual({}, result)
        self.assertEqual(1, len(_hana_pushes))
        self.assertIn("UNEXTRACTED", _hana_pushes[0])
        self.assertEqual(["file-1"], _erp_calls)


class ChileAndinaTemplateTests(unittest.TestCase):
    """Chile Andina order form: BILL TO / SHIP TO without colons, no Sold-To, Sales Org or Order Type values."""

    def setUp(self):
        _hana_pushes.clear()
        _erp_calls.clear()

    def _workbook_bytes(self):
        import openpyxl
        from io import BytesIO
        from datetime import datetime

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws["A5"], ws["C5"], ws["F5"], ws["I5"], ws["J5"] = "ORDER DATE", "REQUESTED DELIVERY DATE", "PO#(required)", "Sales Org", "Order Type"
        ws["A6"], ws["C6"], ws["F6"] = datetime(2026, 2, 26), datetime(2026, 3, 1), 4100185159
        ws["A7"], ws["F7"] = "BILL TO", "SHIP TO"
        ws["A8"], ws["F8"] = 1003966, 4012628
        ws["A9"], ws["F9"] = "Embotelladora Andina S.A.", "Miraflores 9153 Renca, Santiago, Chile"
        ws["A15"], ws["G15"], ws["H15"], ws["I15"], ws["J15"] = "PRODUCT DESCRIPTION", "Order\nCode", "Type of Product", "Cases/\nPallet", "# of Cases"
        ws["A16"] = "Monster Energy CL 4/6/473ml Cans (6pks) Clear Shrink*"
        ws["A17"], ws["G17"], ws["H17"], ws["I17"], ws["J17"] = "Monster Energy", 107458, "CL", 80, 101200
        ws["A18"], ws["G18"], ws["H18"], ws["I18"] = "Monster Ultra", 107533, "CL", 80
        ws["A19"], ws["G19"], ws["H19"], ws["I19"], ws["J19"] = "Monster Mango Loco", 109458, "CL", 80, 13040
        buffer = BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    def test_missing_sold_to_sales_org_and_order_type_are_blank_and_addresses_are_filled(self):
        import json
        import re
        content = self._workbook_bytes()
        with mock.patch.object(handler, "erp_data_fetch", return_value={"file_path": "x.xlsx", "region": "LATAM", "file_name": "x.xlsx"}),              mock.patch.object(handler, "read_file_from_object_store", return_value=content):
            result = handler.excel_parsing_flow("file-2")

        self.assertEqual({"4100185159"}, set(result))
        record = result["4100185159"]
        self.assertEqual("", record["SoldTo"])
        self.assertEqual("", record["SalesOrg"])
        self.assertEqual("", record["SalesDocType"])
        self.assertEqual("1003966", record["BillTo"])
        self.assertEqual("4012628", record["ShipTo"])
        self.assertEqual("Embotelladora Andina S.A.", record["BillAddress"])
        self.assertTrue(record["ShipAddress"].startswith("Miraflores 9153 Renca"))
        self.assertEqual(["107458", "109458"], [item["Material"] for item in record["NavHeadToItem"]])
        self.assertEqual(["101200", "13040"], [item["Quantity"] for item in record["NavHeadToItem"]])

        stored = re.match(r"\"erp_request_payload\" = '(.*)' , \"po_numbers\" = '(.*)'$", _hana_pushes[0], re.S)
        self.assertEqual("", json.loads(stored.group(1))["4100185159"]["SoldTo"])
        self.assertEqual(["file-2"], _erp_calls)


class CambodiaKitTemplateTests(unittest.TestCase):
    """Cambodia KIT order form (Monster Energy Concentrate Order Form): values change, the layout does not."""

    def _workbook_bytes(self):
        import openpyxl
        from io import BytesIO
        from datetime import datetime

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Template"
        ws["A8"], ws["B8"] = "MEC Sold-To", 1003940
        ws["A9"], ws["B9"] = "MEC Ship-To", 4012592
        ws["A10"], ws["B10"] = "MEC Bill-To", 1003940
        ws["A11"], ws["B11"] = "MEC Payer:", 1006530
        ws["A12"], ws["B12"] = "Inco Term:", "CIF Sihanoukvile"
        ws["A13"], ws["B13"] = "Order Type:", "ZKIT"
        ws["A14"], ws["B14"] = "Sales Org:", "0638"
        ws["A15"], ws["B15"] = "Item Category:", "ZTBM"
        ws["A16"], ws["B16"] = "Currency:", "USD"
        ws["A17"], ws["B17"] = "Shipping Condition:", "Pick Up"
        ws["F7"], ws["G7"] = "Ship-To Address:", "CAMBODIA BEVERAGE COMPANY LTD"
        ws["G8"] = "National Road 5,287 Phum Mittapheap,Phnom Penh"
        ws["G9"] = "Kingdom of Cambodia"
        ws["A21"], ws["B21"], ws["C21"], ws["D21"], ws["E21"], ws["F21"], ws["G21"] = (
            "Customer PO #", "Customer SKU#", "MEC SKU#", "SKU Description", "Brand",
            "Quantity (UNITS)", "Requested Delivery Date\nMM/DD/YYYY")
        ws["A22"], ws["C22"], ws["D22"], ws["F22"], ws["G22"] = (
            4502325902, 121175, "KIT FURY GOLD STRIKE KH 6UN V2", 36, datetime(2026, 8, 15))
        ws["D31"], ws["F31"], ws["G31"] = "Customer Signature:", " PO Date:", datetime(2026, 7, 16)
        buffer = BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    def test_header_items_and_ship_to_block_are_read_from_the_template(self):
        import json
        import re
        content = self._workbook_bytes()
        with mock.patch.object(handler, "erp_data_fetch", return_value={"file_path": "x.xlsx", "region": "LATAM", "file_name": "x.xlsx"}),              mock.patch.object(handler, "read_file_from_object_store", return_value=content):
            result = handler.excel_parsing_flow("file-3")

        record = result["4502325902"]
        self.assertEqual({
            "SoldTo": "1003940", "ShipTo": "4012592", "BillTo": "1003940",
            "IncoTerm": "CIF", "IncoTerm2": "Sihanoukvile", "SalesOrg": "0638", "SalesDocType": "ZKIT",
            "ItemCat": "ZTBM", "Currency": "USD", "ShippingCond": "Pick Up", "PODate": "2026-07-16",
            "ShipName": "CAMBODIA BEVERAGE COMPANY LTD",
            "ShipAddress": "CAMBODIA BEVERAGE COMPANY LTD National Road 5,287 Phum Mittapheap,Phnom Penh Kingdom of Cambodia",
        }, {k: record[k] for k in ["SoldTo", "ShipTo", "BillTo", "IncoTerm", "IncoTerm2", "SalesOrg", "SalesDocType",
                                   "ItemCat", "Currency", "ShippingCond", "PODate", "ShipName", "ShipAddress"]})
        self.assertNotIn("BillAddress", record)
        self.assertEqual([{
            "Material": "121175", "Quantity": "36", "MatDesc": "KIT FURY GOLD STRIKE KH 6UN V2",
            "DlvDate": "2026-08-15", "CustPo": "4502325902", "AsopNo": "0000000000", "OCRItemno": "10", "Uom": "",
        }], record["NavHeadToItem"])

        stored = re.match(r"\"erp_request_payload\" = '(.*)' , \"po_numbers\" = '(.*)'$", _hana_pushes[0], re.S)
        self.assertEqual("1003940", json.loads(stored.group(1))["4502325902"]["SoldTo"])


class PosAsopMassOrderTests(unittest.TestCase):
    """POS ASOP mass order: a flat table, one row per line item, the column names in the first row."""

    def setUp(self):
        _hana_pushes.clear()
        _erp_calls.clear()

    HEADER = [
        "Order Type", "Sold to", "Ship To", "Payer", "Sales \nOrg", "Distr \nChannel", "Div", "PO/\nRef #",
        "PO Date\nMM/DD/YYYY", "Ship to Name", "Ship To Street", "Ship To House Num2", "Ship TO Street 2",
        "Ship to City", "Ship To State", "Ship to Zip", "Ship to Ctry", "Shipping Instructions (Text)",
        "Request Delivery Date MM/DD/YY", "Shipping Condition (01=Truck\n02=Pickup)", "Inco Terms 1",
        "Delivery Priority", "Line #", "Material#", "Qty", "Sales Unit of Measure", "Price (ZORP Only)",
        "Currency  (ZORP Only)", "Plant", "SLOC (ZORP only)", "Internal Order", "Cost Center", "Item Category",
    ]

    def _workbook_bytes(self):
        import openpyxl
        from io import BytesIO
        from datetime import datetime

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(self.HEADER)
        ws.append(["ZORP", 15162, 4023350, None, 1001, 10, 10, "R2938274", None, "Kailey Dodson",
                   "301 Leroy Court", "H12827", "Street1", "San Luis Obispo", "CA", 93405, "US", 9513675478,
                   datetime(2026, 2, 14), "04", "CIF", None, "n", 181016, 7, "CS", None, "USD", "1000", None,
                   401914, None, "ZTAN"])
        ws.append(["ZORP", 15162, 4023350, None, 1001, 10, 10, "R2938275", None, "Kailey Dodson",
                   "301 Leroy Court", "H12828", "Street2", "San Luis Obispo 2", "CA", 93405, "US", 9513675478,
                   datetime(2026, 2, 14), "04", None, None, 2, 107310, 7, "CS", None, "USD", "1000", None,
                   401914, None, None])
        buffer = BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    def test_each_row_is_a_line_item_and_blank_fields_stay_blank(self):
        content = self._workbook_bytes()
        with mock.patch.object(handler, "erp_data_fetch", return_value={"file_path": "x.xlsx", "region": "EMEA", "file_name": "x.xlsx"}), \
             mock.patch.object(handler, "read_file_from_object_store", return_value=content):
            result = handler.excel_parsing_flow("file-4")

        self.assertEqual({"R2938274", "R2938275"}, set(result))
        record = result["R2938274"]
        self.assertEqual({"AsopNo": "0000000000", "Region": "EMEA", "Podoctype": "EXCEL"},
                         {k: record[k] for k in ["AsopNo", "Region", "Podoctype"]})
        item = record["NavHeadToItem"][0]
        self.assertEqual({
            "OCRItemno": "10", "Material": "181016", "Quantity": "7", "Uom": "CS", "Plant": "1000",
            "ItmCat": "ZTAN", "IncoTerm": "CIF", "ShippingCond": "04", "CustPo": "R2938274",
            "ShipTo": "4023350", "SalesDocType": "ZORP", "SalesOrg": "1001", "SoldTo": "15162",
            "DlvDate": "2026-02-14", "PODate": "", "Payer": "", "CostCenter": "", "UnitPrice": "",
            "Currency": "USD", "ShipCity": "San Luis Obispo", "ShipZip": "93405", "ShipInst": "9513675478",
        }, {k: item[k] for k in ["OCRItemno", "Material", "Quantity", "Uom", "Plant", "ItmCat", "IncoTerm",
                                 "ShippingCond", "CustPo", "ShipTo", "SalesDocType", "SalesOrg", "SoldTo",
                                 "DlvDate", "PODate", "Payer", "CostCenter", "UnitPrice", "Currency",
                                 "ShipCity", "ShipZip", "ShipInst"]})
        self.assertEqual(
            ["AsopNo", "OCRItemno", "Material", "MaterialCC", "MatDesc", "Quantity", "QuantityCC", "Uom",
             "UnitPrice", "ExtPrice", "DlvDate", "Plant", "ItmCat", "IncoTerm", "ShippingCond", "AddField1",
             "AddField2", "AddField3", "AddField4", "AddField5", "Size", "Pallet", "CustPo", "ShipTo",
             "SapPriceInd", "SalesDocType", "SalesOrg", "SoldTo", "PODate", "TemplateInd", "POSTotalCost",
             "MatTextInd", "ShipCity", "Payer", "DistChannel", "Division", "ShipName", "ShipStreet", "ShipHouse",
             "ShipStreet2", "ShipState", "ShipZip", "ShipCountry", "ShipInst", "Currency", "InternalOrder",
             "CostCenter", "POItemNo"],
            list(item.keys()))
        second = result["R2938275"]["NavHeadToItem"][0]
        self.assertEqual("", second["IncoTerm"])
        self.assertEqual("107310", second["Material"])
        self.assertEqual(["file-4"], _erp_calls)


class PodoctypeFromFileTests(unittest.TestCase):
    """A Podoctype label in the file is used; without one the default EXCEL is kept."""

    def _with_label(self, value):
        import openpyxl
        from io import BytesIO
        wb = openpyxl.load_workbook(BytesIO(ChileAndinaTemplateTests._workbook_bytes(self)))
        ws = wb.active
        if value is not None:
            ws["L1"], ws["M1"] = "Podoctype", value
        buffer = BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    def _run(self, content):
        with mock.patch.object(handler, "erp_data_fetch", return_value={"file_path": "x.xlsx", "region": "LATAM", "file_name": "x.xlsx"}), \
             mock.patch.object(handler, "read_file_from_object_store", return_value=content):
            return handler.excel_parsing_flow("file-5")

    def test_podoctype_label_in_the_file_is_used(self):
        result = self._run(self._with_label("CUSTOMFORM"))
        self.assertEqual("CUSTOMFORM", result["4100185159"]["Podoctype"])

    def test_without_the_label_the_default_is_used(self):
        result = self._run(self._with_label(None))
        self.assertEqual("EXCEL", result["4100185159"]["Podoctype"])


if __name__ == "__main__":
    unittest.main()
