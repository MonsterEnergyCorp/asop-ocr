import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))
from fastapi.testclient import TestClient
from apps.ingest_documents import server as ingest_server


class HealthCheckWhileUploadingTests(unittest.TestCase):
    def test_health_check_answers_while_an_upload_is_running(self):
        # A slow upload (Blob, HANA and parser calls take seconds in real use).
        # The health check must still answer quickly, or Kubernetes restarts the pod.
        def slow_upload(data):
            time.sleep(3)
            return {"status_code": 200, "message": "ok"}

        payload = {"data": {"file_type": "text/html"}, "region": "LATAM", "file_id": "TEST-HEALTH-1"}
        with TestClient(ingest_server.create_app()) as client:
            with mock.patch.object(ingest_server, "upload_invoice_file", side_effect=slow_upload):
                upload = threading.Thread(target=lambda: client.post(f"/{ingest_server.env}/ocr/ingest", json=payload))
                upload.start()
                time.sleep(0.5)
                started = time.monotonic()
                response = client.get("/")
                elapsed = time.monotonic() - started
                upload.join()

        self.assertEqual(200, response.status_code)
        self.assertLess(elapsed, 1.0, f"health check took {elapsed:.2f}s while an upload was running")


    def test_several_attachments_sent_together_are_processed_in_parallel(self):
        # Three attachments sent at once, each taking 1 second: parallel takes about 1s, one at a time takes 3s.
        def slow_upload(data):
            time.sleep(1)
            return {"status_code": 200, "message": "ok"}

        with TestClient(ingest_server.create_app()) as client:
            with mock.patch.object(ingest_server, "upload_invoice_file", side_effect=slow_upload):
                threads = []
                started = time.monotonic()
                for index in range(3):
                    payload = {"data": {"file_type": "text/html"}, "region": "LATAM", "file_id": f"TEST-PAR-{index}"}
                    threads.append(threading.Thread(target=lambda body=payload: client.post(f"/{ingest_server.env}/ocr/ingest", json=body)))
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                elapsed = time.monotonic() - started

        self.assertLess(elapsed, 2.5, f"three uploads took {elapsed:.2f}s, so they were not processed in parallel")


if __name__ == "__main__":
    unittest.main()
