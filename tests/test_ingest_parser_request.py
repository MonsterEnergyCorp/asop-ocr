import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from apps.ingest_documents.ocr_ingest_doc import push_to_parsers
from core.azure_storage import blob_storage_connection


class BlobUploadTests(unittest.TestCase):
    def test_buffered_file_upload_preserves_all_bytes(self):
        for content_type, content in (
            ("text/html", b"<html><body>Orden de compra: PO-123</body></html>"),
            ("text/csv", b"FOLIO;CANTIDAD\n123;10\n"),
            ("application/pdf", b"%PDF-1.7\n"),
            ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK\x03\x04test"),
            ("message/rfc822", b"Subject: Test\r\n\r\nTest email"),
        ):
            with self.subTest(content_type=content_type), tempfile.TemporaryDirectory() as directory:
                with open(Path(directory) / "attachment", "w+b") as temporary:
                    temporary.write(content)
                    with patch.object(blob_storage_connection, "connect_to_blob_storage") as connect:
                        upload = connect.return_value.get_blob_client.return_value.upload_blob
                        uploaded = []
                        upload.side_effect = lambda stream, **kwargs: uploaded.append(stream.read())
                        result = blob_storage_connection.push_to_blob_storage(
                            "dev/LATAM/attachment", content_type, "", "", "", tmp_file=temporary
                        )
                    self.assertEqual([content], uploaded)
                    self.assertEqual("dev/LATAM/attachment", result)

    def test_empty_file_is_rejected_before_azure_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(Path(directory) / "attachment", "w+b") as temporary:
                with patch.object(blob_storage_connection, "connect_to_blob_storage") as connect:
                    with self.assertRaisesRegex(ValueError, "empty"):
                        blob_storage_connection.push_to_blob_storage(
                            "attachment", "text/html", "", "", "", tmp_file=temporary
                        )
                    connect.assert_not_called()

    def test_empty_direct_content_is_rejected(self):
        with patch.object(blob_storage_connection, "connect_to_blob_storage") as connect:
            with self.assertRaisesRegex(ValueError, "empty"):
                blob_storage_connection.push_to_blob_storage(
                    "attachment", "text/html", "", "", "", content=b""
                )
            connect.assert_not_called()

    def test_direct_content_is_uploaded_unchanged(self):
        content = b"<html>test</html>"
        with patch.object(blob_storage_connection, "connect_to_blob_storage") as connect:
            blob_storage_connection.push_to_blob_storage(
                "attachment", "text/html", "", "", "", content=content
            )
            upload = connect.return_value.get_blob_client.return_value.upload_blob
            self.assertEqual(content, upload.call_args.args[0])


class IngestParserRequestTests(unittest.TestCase):
    def test_parser_request_sends_json_checks_status_and_uses_timeout(self):
        response = Mock()
        with patch(
            "apps.ingest_documents.ocr_ingest_doc.requests.post",
            return_value=response
        ) as post:
            result = push_to_parsers("http://parser/dev/parse/html", "file-1")

        self.assertIs(response, result)
        post.assert_called_once_with(
            "http://parser/dev/parse/html",
            json={"file_id": "file-1"},
            timeout=30
        )
        response.raise_for_status.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()