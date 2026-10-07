"""
Runs the full csv_parsing_flow / html_parsing_flow end-to-end locally,
using core/local_test_storage.py instead of HANA + Azure blob storage.

Requires environment variable LOCAL_TEST_MODE=true (set below for you).

Usage:
    python tools/run_local_flow.py --type csv --file "path\\to\\sample.csv"
    python tools/run_local_flow.py --type html --file "path\\to\\sample.html"
"""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("LOCAL_TEST_MODE", "true")

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from core.local_test_storage import register_local_test_file


def main():
    parser = argparse.ArgumentParser(description="Run the full LATAM CSV/HTML flow locally")
    parser.add_argument("--type", choices=["csv", "html"], required=True)
    parser.add_argument("--file", required=True, help="Path to the sample CSV or HTML file")
    parser.add_argument("--region", default="LATAM")
    args = parser.parse_args()

    file_path = Path(args.file).resolve()
    file_id = f"local-test-{uuid.uuid4()}"
    file_type = "text/csv" if args.type == "csv" else "text/html"
    register_local_test_file(file_id, file_path, args.region, file_type)

    if args.type == "csv":
        from apps.csv_parser.csv_parse_handler import csv_parsing_flow
        result = csv_parsing_flow(file_id)
    else:
        from apps.html_parser.html_parse_handler import html_parsing_flow
        result = html_parsing_flow(file_id)

    print(f"file_id: {file_id}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    output_path = Path(__file__).resolve().parent / "local_test_storage" / "output" / f"{file_id}.txt"
    print(f"\nOutput also written to: {output_path}")


if __name__ == "__main__":
    main()
