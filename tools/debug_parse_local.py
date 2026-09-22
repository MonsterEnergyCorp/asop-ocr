"""
Local debug entry point for LATAM CSV/HTML template parsers.

Runs parser code directly against a local file, bypassing blob storage
and HANA, so it can be stepped through with the VS Code debugger.

Usage:
    python tools/debug_parse_local.py --type csv --file "path\\to\\sample.csv"
    python tools/debug_parse_local.py --type html --file "path\\to\\sample.html"
"""
import argparse
import json
import sys
from pathlib import Path

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from apps.csv_parser.csv_parse_handler import parse_latam_csv
from apps.html_parser.html_parse_handler import parse_latam_html


def main():
    parser = argparse.ArgumentParser(description="Debug LATAM CSV/HTML parsers locally")
    parser.add_argument("--type", choices=["csv", "html"], required=True)
    parser.add_argument("--file", required=True, help="Path to the sample CSV or HTML file")
    args = parser.parse_args()

    file_path = Path(args.file)
    file_data = {"file_name": file_path.name, "file_type": f"text/{args.type}"}
    content = file_path.read_bytes()

    if args.type == "csv":
        result = parse_latam_csv(content, file_data)
    else:
        result = parse_latam_html(content, file_data)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
