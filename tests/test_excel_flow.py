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


if __name__ == "__main__":
    unittest.main()
