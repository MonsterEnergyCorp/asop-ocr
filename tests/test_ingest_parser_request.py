import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from apps.ingest_documents.ocr_ingest_doc import push_to_parsers


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