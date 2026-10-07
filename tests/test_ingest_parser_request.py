import sys
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from apps.ingest_documents.ocr_ingest_doc import push_to_parsers
from apps.ingest_documents import server as ingest_server
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
    def test_public_path_uses_existing_endpoint_and_validation(self):
        public_path = "/s4-dev/ocr/ingest"
        with patch.object(ingest_server.config, "ingest_public_path", public_path):
            app = ingest_server.create_app()
        routes = {route.path: route for route in app.routes}
        endpoint = routes[public_path].endpoint
        self.assertIs(routes[f"/{ingest_server.env}/ocr/ingest"].endpoint, endpoint)
        self.assertEqual({"POST"}, routes[public_path].methods)
        payload = {"data": {"file_type": "text/html"}, "region": "LATAM"}
        with patch.object(ingest_server, "upload_invoice_file", return_value={"status_code": 200}) as upload:
            result = asyncio.run(endpoint(payload))
            upload.assert_called_once_with(payload)
            self.assertEqual(200, result["data"]["status_code"])
            with self.assertRaises(ingest_server.HTTPException) as raised:
                asyncio.run(endpoint({"data": {"file_type": "invalid"}}))
            self.assertEqual(400, raised.exception.status_code)
            upload.assert_called_once()

    def test_no_extra_route_when_public_path_is_unset_or_matches_internal_path(self):
        for public_path in ("", f"/{ingest_server.env}/ocr/ingest"):
            with self.subTest(public_path=public_path), patch.object(
                ingest_server.config, "ingest_public_path", public_path
            ):
                app = ingest_server.create_app()
                post_routes = [route for route in app.routes if "POST" in getattr(route, "methods", set())]
                self.assertEqual(1, len(post_routes))

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