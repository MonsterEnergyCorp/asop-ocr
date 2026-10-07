import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from apps.publish_to_erp import publish_to_erp_handler


class PublishToErpDispatchTests(unittest.TestCase):
    def call_publisher(self, file_type):
        connection = object()
        hana_data = {
            "erp_request_payload": '{"PO-1": {"NavHeadtoMeta": [{}]}}',
            "eml_file_path": "email.eml",
            "file_type": file_type
        }
        with (
            patch.object(publish_to_erp_handler, "connect_to_db", return_value=connection),
            patch.object(publish_to_erp_handler, "erp_data_fetch", return_value=hana_data),
            patch.object(publish_to_erp_handler, "read_file_from_object_store", return_value=b"email"),
            patch.object(publish_to_erp_handler, "excel_call_to_erp", return_value=("Published", {})) as excel_call,
            patch.object(publish_to_erp_handler, "close_connection")
        ):
            result = publish_to_erp_handler.publish_to_erp({"file_id": "file-1"})
        return result, excel_call

    def test_csv_and_html_types_use_existing_payload_publisher(self):
        file_types = [
            "text/csv",
            "application/csv",
            "application/vnd.ms-excel",
            "text/html",
            "application/html",
            "application/xhtml+xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel.sheet.macroenabled.12"
        ]
        for file_type in file_types:
            with self.subTest(file_type=file_type):
                result, excel_call = self.call_publisher(file_type)
                self.assertEqual("Success", result)
                excel_call.assert_called_once()

    def test_unknown_type_returns_bad_request(self):
        with patch.object(publish_to_erp_handler, "connect_to_db", return_value=object()), \
                patch.object(publish_to_erp_handler, "erp_data_fetch", return_value={
                    "erp_request_payload": "{}",
                    "eml_file_path": "email.eml",
                    "file_type": "application/unknown"
                }), \
                patch.object(publish_to_erp_handler, "read_file_from_object_store", return_value=b"email"), \
                patch.object(publish_to_erp_handler, "close_connection"):
            with self.assertRaises(HTTPException) as context:
                publish_to_erp_handler.publish_to_erp({"file_id": "file-1"})

        self.assertEqual(400, context.exception.status_code)


if __name__ == "__main__":
    unittest.main()