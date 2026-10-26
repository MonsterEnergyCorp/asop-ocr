"""
Run the CSV parser LOCALLY on one or more .csv files - no HANA, Blob or ERP needed.

This file lives in code/backend/apps/csv_parser, next to csv_parse_handler.py and mappings.py, and
mirrors debug_excel_local.py. It runs the REAL csv_parsing_flow() - the production branch: HANA lookup,
Blob read, parse, HANA update and the ERP decision. Only HANA, Blob and ERP are replaced by stand-ins
that record what would have been written or sent. For example:

    python debug_csv_local.py "C:\\path\\Cargas Masivas_20-07-2026_Loginsa.csv"
    python debug_csv_local.py "C:\\path\\Cargas Masivas_20-07-2026_Ecsa.csv" --email client@example.com
    python debug_csv_local.py "C:\\path\\file.csv" --push-to-erp     (same as TEMPLATE_PARSER_TEST_MODE=false)
    python debug_csv_local.py "C:\\path\\file.csv" --out payload.json

Set breakpoints in csv_parse_handler.py and run this file in the debugger to step through (F11).
"""
import argparse
import json
import logging
import re
import sys
import types
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]  # code/backend
sys.path.insert(0, str(BACKEND_DIR))

state = {}


def _module(name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module
    return module


def install_stand_ins(push_to_erp):
    # --- stand-ins for config / HANA / Blob / ERP (core.*) ---
    config = types.SimpleNamespace(
        local_test_mode=False,
        template_parser_test_mode=not push_to_erp,
        ocr_erp_push_url="<stub ERP push url>",
    )
    _module("core")
    _module("core.config", config=config)
    _module("core.azure_storage")
    _module("core.azure_storage.blob_storage_connection")
    _module("core.db")
    _module(
        "core.db.connection",
        connect_to_db=lambda: "stub-connection",
        close_connection=lambda connection: state.update(closed=True),
    )
    _module(
        "core.util",
        erp_data_fetch=lambda connection, file_id: state["hana"],
        read_file_from_object_store=lambda path: Path(path).read_bytes(),
        hana_storage_push=lambda file_id, connection, values: state.update(sql=values),
        push_to_erp=lambda url, file_id: state["erp_calls"].append({"url": url, "file_id": file_id}) or "Success",
    )


def decode_stored_sql(sql):
    # '"erp_request_payload" = '<json>' , "po_numbers" = '<po>'' -> (payload dict, po numbers)
    match = re.match(r'"erp_request_payload" = \'(.*)\' , "po_numbers" = \'(.*)\'$', sql, re.S)
    return json.loads(match.group(1).replace("''", "'")), match.group(2).replace("''", "'")


def run(csv_path, email, region, file_type, push_to_erp):
    csv_path = Path(csv_path)
    state.clear()
    state["erp_calls"] = []
    state["hana"] = {
        "file_path": str(csv_path),
        "region": region,
        "sender_email": email,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "file_name": csv_path.name,
        "file_type": file_type,
    }
    install_stand_ins(push_to_erp)
    from apps.csv_parser.csv_parse_handler import csv_parsing_flow

    final_output = csv_parsing_flow("local-test")               # <-- breakpoint here, step in (F11)
    payload, po_numbers = decode_stored_sql(state["sql"])
    return final_output, payload, po_numbers


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Run the CSV parser locally (stand-ins for HANA/Blob/ERP)")
    arg_parser.add_argument("file", help="path to the .csv file")
    arg_parser.add_argument("--email", default="sender@example.com", help="sender email (HANA sender_email)")
    arg_parser.add_argument("--region", default="LATAM", help="region the file arrives under (HANA region)")
    arg_parser.add_argument("--file-type", default="text/csv", help="content type stored in HANA")
    arg_parser.add_argument("--push-to-erp", action="store_true", help="call the ERP push (TEMPLATE_PARSER_TEST_MODE=false)")
    arg_parser.add_argument("--out", help="also write the stored ERP payload to this JSON file")
    arg_parser.add_argument("--verbose", action="store_true", help="show the parser's own log lines")
    args = arg_parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.CRITICAL)
    final_output, payload, po_numbers = run(args.file, args.email, args.region, args.file_type, args.push_to_erp)

    print(f"file: {Path(args.file).name}  |  region: {args.region}  |  sender: {args.email}")
    print(f"line items: {len(final_output.get('NavHeadToItem', []))}  |  payload keys: {list(payload.keys())}")
    print(f"po_numbers stored in HANA: {po_numbers}")
    if state["erp_calls"]:
        print(f"ERP push CALLED: {state['erp_calls']}")
    else:
        print("ERP push NOT called (TEMPLATE_PARSER_TEST_MODE=true; use --push-to-erp to simulate false)")
    print("--- erp_request_payload stored in HANA ---")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"written: {Path(args.out).resolve()}")
