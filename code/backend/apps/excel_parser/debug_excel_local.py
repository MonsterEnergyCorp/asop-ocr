"""
Run the Excel parser LOCALLY on one or more .xlsx files - no HANA, Blob or ERP needed.

Put this file next to auxiliary_data.py, excel_parse_handler.py and post_processing.py
(code/backend/apps/excel_parser), then run, for example:

    python debug_excel_local.py "C:\\path\\China_FG_PO-revised.xlsx" APAC
    python debug_excel_local.py "C:\\path\\Macau_FG_PO-revised.xlsx" US
    python debug_excel_local.py "C:\\path\\existing_template.xlsx" EMEA

The second argument is the region the file would arrive under (default US).
Set breakpoints in the parser files and run this file in the debugger to step through.
"""
import importlib.util
import json
import logging
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

PARSER_DIR = Path(__file__).resolve().parent


def _module(name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module
    return module


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, PARSER_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


state = {}

# --- stand-ins for HANA / Blob / ERP (core.*) ---
_module("core")
_module("core.config", config=MagicMock())
_module("core.azure_storage")
_module("core.azure_storage.blob_storage_connection")
_module("core.db")
_module("core.db.connection", connect_to_db=lambda: object(), close_connection=lambda connection: None)
_module(
    "core.util",
    erp_data_fetch=lambda connection, file_id: state["hana"],
    read_file_from_object_store=lambda path: Path(path).read_bytes(),
    hana_storage_push=lambda file_id, connection, values: state.update(pushed=values),
    push_to_erp=lambda url, file_id: None,
)

# --- your real parser files ---
_module("apps")
package = _module("apps.excel_parser")
package.auxiliary_data = _load("apps.excel_parser.auxiliary_data", "auxiliary_data.py")
package.post_processing = _load("apps.excel_parser.post_processing", "post_processing.py")
handler = _load("excel_parse_handler", "excel_parse_handler.py")


def run(xlsx_path, region="US", show_meta=False):
    xlsx_path = Path(xlsx_path)
    state["hana"] = {
        "file_path": str(xlsx_path),
        "region": region,
        "sender_email": "tester@example.com",
        "created_at": "2026-10-13",
        "file_name": xlsx_path.stem,
        "file_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    result = handler.excel_parsing_flow("local-test")           # <-- breakpoint here, step in (F11)
    if not show_meta:
        for payload in result.values():
            payload.pop("NavHeadtoMeta", None)
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    logging.disable(logging.CRITICAL)                            # remove this line to see the parser's own logs
    file_arg = sys.argv[1]
    region_arg = sys.argv[2] if len(sys.argv) > 2 else "US"
    output = run(file_arg, region_arg)
    print(f"{Path(file_arg).name}  |  region tag: {region_arg}  |  POs: {list(output.keys()) or 'none (failure payload would be stored)'}")
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str))