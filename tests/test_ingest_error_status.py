import sys
import unittest
from pathlib import Path
from unittest import mock

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))
from fastapi.testclient import TestClient
from apps.ingest_documents import server


class IngestErrorStatusTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.create_app())
        self.path = f"/{server.env}/ocr/ingest"
        self.body = {"data": {"file_type": "application/pdf"}, "region": "LATAM", "file_id": "TEST-ERR-1"}

    def test_failed_upload_returns_http_500_with_the_error_in_data(self):
        failure = {"status_code": 500, "message": "Error Processing request - AuthenticationFailed: blob rejected"}
        with mock.patch.object(server, "upload_invoice_file", return_value=failure):
            response = self.client.post(self.path, json=self.body)
        self.assertEqual(500, response.status_code)
        self.assertEqual("File ingestion failed", response.json()["message"])
        self.assertEqual(failure, response.json()["data"])

    def test_duplicate_upload_returns_http_400(self):
        duplicate = {"status_code": 400, "message": "File already ingested in OCR"}
        with mock.patch.object(server, "upload_invoice_file", return_value=duplicate):
            response = self.client.post(self.path, json=self.body)
        self.assertEqual(400, response.status_code)
        self.assertEqual(duplicate, response.json()["data"])

    def test_invalid_file_type_returns_http_400_in_the_same_shape(self):
        bad = {"data": {"file_type": "image/png"}, "region": "LATAM", "file_id": "TEST-ERR-2"}
        with mock.patch.object(server, "upload_invoice_file") as upload:
            response = self.client.post(self.path, json=bad)
        upload.assert_not_called()
        self.assertEqual(400, response.status_code)
        self.assertEqual("Invalid file type.", response.json()["data"]["message"])

    def test_successful_upload_keeps_the_same_response_shape(self):
        success = {"status_code": 200, "message": {"message": "file uploaded", "document_no": "TEST-ERR-1"}}
        with mock.patch.object(server, "upload_invoice_file", return_value=success):
            response = self.client.post(self.path, json=self.body)
        self.assertEqual(200, response.status_code)
        self.assertEqual("File ingested successfully", response.json()["message"])
        self.assertEqual(success, response.json()["data"])


if __name__ == "__main__":
    unittest.main()
