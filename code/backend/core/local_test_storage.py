"""
Local filesystem stand-in for HANA + blob storage, used only when
config.local_test_mode is True. Lets csv_parsing_flow/html_parsing_flow
run end-to-end on a developer machine with no Azure/HANA credentials
and no Kubernetes deployment.
"""
import json
from pathlib import Path

from core.config import config


def _storage_dir():
    path = Path(config.local_test_storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path():
    return _storage_dir() / "manifest.json"


def _load_manifest():
    manifest_path = _manifest_path()
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _save_manifest(manifest):
    _manifest_path().write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def register_local_test_file(file_id, file_path, region, file_type):
    """Registers a local sample file so the flow functions can fetch it by file_id."""
    manifest = _load_manifest()
    manifest[file_id] = {
        "file_id": file_id,
        "file_path": str(file_path),
        "file_name": Path(file_path).name,
        "region": region,
        "file_type": file_type
    }
    _save_manifest(manifest)
    return manifest[file_id]


def local_erp_data_fetch(file_id):
    manifest = _load_manifest()
    if file_id not in manifest:
        raise ValueError(
            f"No local test entry for file_id='{file_id}'. "
            "Call register_local_test_file(...) first."
        )
    return manifest[file_id]


def local_read_file(file_path):
    return Path(file_path).read_bytes()


def local_hana_storage_push(file_id, update_values):
    output_path = _storage_dir() / "output" / f"{file_id}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(update_values, encoding="utf-8")
    return output_path
