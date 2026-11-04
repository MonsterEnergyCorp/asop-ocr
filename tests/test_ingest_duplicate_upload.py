import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))
from apps.ingest_documents import ocr_ingest_doc as ingest_doc


class DuplicateUploadTests(unittest.TestCase):
    def setUp(self):
        self.stored = set()

    def fake_check(self, file_id):
        # Stands in for the HANA lookup; slow enough that two checks would overlap without the lock.
        found = file_id in self.stored
        time.sleep(0.2)
        return [{"file_id": file_id}] if found else []

    def fake_process(self, data):
        time.sleep(0.5)  # Blob upload and HANA insert take time in real use
        self.stored.add(data["file_id"])
        return {"status_code": 200, "message": "stored"}

    def test_identical_sends_at_the_same_time_are_stored_once(self):
        payload = {"data": {"file_type": "application/pdf"}, "region": "LATAM", "file_id": "TEST-DUP-1"}
        results = []
        with mock.patch.object(ingest_doc, "check_for_existing_process", side_effect=self.fake_check),              mock.patch.object(ingest_doc, "process_upload", side_effect=self.fake_process) as process:
            threads = [threading.Thread(target=lambda: results.append(ingest_doc.upload_invoice_file(dict(payload)))) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(1, process.call_count, "both identical uploads were processed")
        self.assertEqual(sorted([200, 400]), sorted(r["status_code"] for r in results))

    def test_resent_file_is_rejected_for_the_flat_input_shape_too(self):
        # The duplicate check used to run only for the nested {data, region} shape.
        self.stored.add("TEST-DUP-2")
        flat_payload = {"file_id": "TEST-DUP-2", "file_name": "po.pdf", "file_type": "application/pdf", "region": "LATAM"}
        with mock.patch.object(ingest_doc, "check_for_existing_process", side_effect=self.fake_check),              mock.patch.object(ingest_doc, "process_upload", side_effect=self.fake_process) as process:
            result = ingest_doc.upload_invoice_file(flat_payload)

        process.assert_not_called()
        self.assertEqual(400, result["status_code"])

    def test_different_files_are_not_serialized(self):
        results = []
        with mock.patch.object(ingest_doc, "check_for_existing_process", side_effect=self.fake_check),              mock.patch.object(ingest_doc, "process_upload", side_effect=self.fake_process):
            threads = []
            started = time.monotonic()
            for index in range(2):
                body = {"data": {"file_type": "application/pdf"}, "region": "LATAM", "file_id": f"TEST-OTHER-{index}"}
                threads.append(threading.Thread(target=lambda b=body: results.append(ingest_doc.upload_invoice_file(b))))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            elapsed = time.monotonic() - started

        self.assertEqual([200, 200], [r["status_code"] for r in results])
        self.assertLess(elapsed, 1.2, f"two different files took {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
