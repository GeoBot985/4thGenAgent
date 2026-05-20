from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from runtime.manifest_loader import load_manifest
from runtime.persistence import PersistenceManager, write_json_atomic
from runtime.run_report import generate_operator_run_report
from runtime.runtime_store import backup_runtime_store, ensure_runtime_store_layout, restore_runtime_store_backup
from runtime.taskframe import create_taskframe
from runtime.errors import RuntimeStoreRestoreError


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


def test_restore_validate_only_extracts_into_isolated_target(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    _seed_runtime_store(runtime_root)
    backup = backup_runtime_store(runtime_root)
    target = tmp_path / "restore_target"

    report = restore_runtime_store_backup(backup["backup_path"], target, validate_only=True)

    assert report["ok"] is True
    assert report["validate_only"] is True
    assert (target / "restore_report.json").is_file()
    assert (target / "runs").is_dir()


def test_restore_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("backup_manifest.json", '{"backup_id":"x","created_at":"now","source_runtime_dir":"runtime_data","artifact_counts":{},"profile":"demo","contains_live_data":false,"contains_pending_actions":false,"schema_version":1}')
        archive.writestr("../evil.txt", "boom")

    with pytest.raises(RuntimeStoreRestoreError):
        restore_runtime_store_backup(archive_path, tmp_path / "target", validate_only=True)
