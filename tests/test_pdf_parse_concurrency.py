import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))
from fastapi.testclient import TestClient
from apps.pdf_parser import server as pdf_server


class PdfParseConcurrencyTests(unittest.TestCase):
    def test_pdf_requests_are_not_blocked_by_each_other(self):
        # Each PDF takes 1 second in the (blocking) polling loop. Two PDFs sent together should
        # finish in about 1 second; if the endpoint were async they would run one after another (2 seconds).
        def slow_flow(data):
            time.sleep(1)
            return {"file_id": data["file_id"]}

        with TestClient(pdf_server.create_app()) as client:
            with mock.patch.object(pdf_server, "pdf_parsing_flow", side_effect=slow_flow):
                threads = []
                started = time.monotonic()
                for index in range(2):
                    payload = {"file_id": f"TEST-PDF-{index}"}
                    threads.append(threading.Thread(target=lambda body=payload: client.post(f"/{pdf_server.env}/parse/pdf", json=body)))
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.8, f"two PDFs took {elapsed:.2f}s, so they were processed one after another")


if __name__ == "__main__":
    unittest.main()
