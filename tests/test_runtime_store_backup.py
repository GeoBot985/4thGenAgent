from __future__ import annotations

import json
import zipfile
from pathlib import Path

from runtime.manifest_loader import load_manifest
from runtime.persistence import PersistenceManager, write_json_atomic
from runtime.run_report import generate_operator_run_report
from runtime.runtime_store import backup_runtime_store, ensure_runtime_store_layout
from runtime.taskframe import create_taskframe


def _seed_runtime_store(runtime_root: Path) -> str:
    ensure_runtime_store_layout(runtime_root)
    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.state = "WAITING_FOR_EXECUTE"
    frame.pending_actions.append({"action_id": "pa_1", "tool": "wa/send", "status": "PENDING_APPROVAL"})
    PersistenceManager(runtime_root).save_snapshot(frame)
    generate_operator_run_report(runtime_root, frame.frame_id, rebuild=True)
    write_json_atomic(runtime_root / "tool_health" / "latest_tool_health.json", {"schema_version": 1, "generated_at": frame.updated_at, "results": [], "by_tool": {}, "summary": {}})
    return frame.frame_id


def test_backup_zip_contains_manifest_and_counts(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    _seed_runtime_store(runtime_root)

    result = backup_runtime_store(runtime_root)

    backup_path = Path(result["backup_path"])
    assert backup_path.is_file()
    assert Path(result["manifest_path"]).is_file()
    assert result["manifest"]["schema_version"] == 1
    assert result["manifest"]["artifact_counts"]["taskframes"] >= 1
    assert result["manifest"]["contains_pending_actions"] is True

    with zipfile.ZipFile(backup_path, "r") as archive:
        names = set(archive.namelist())
        assert "backup_manifest.json" in names
        manifest = json.loads(archive.read("backup_manifest.json").decode("utf-8"))
        assert manifest["artifact_counts"]["taskframes"] >= 1
        assert manifest["profile"] in {"demo", "dev", "test", "release", "pilot", "live"}
