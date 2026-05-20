from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from runtime.manifest_loader import load_manifest
from runtime.persistence import PersistenceManager, write_json_atomic
from runtime.run_report import generate_operator_run_report
from runtime.runtime_store import ensure_runtime_store_layout
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


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], capture_output=True, text=True, check=False)


def test_runtime_store_cli_commands_return_structured_json(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    _seed_runtime_store(runtime_root)

    check = _run("runtime-store", "check", "--runtime-data-dir", str(runtime_root), "--json")
    assert check.returncode == 0
    check_payload = json.loads(check.stdout)
    assert check_payload["ok"] is True
    assert check_payload["artifact_counts"]["taskframes"] >= 1

    index = _run("runtime-store", "index", "--runtime-data-dir", str(runtime_root), "--json")
    assert index.returncode == 0
    index_payload = json.loads(index.stdout)
    assert index_payload["ok"] is True

    backup = _run("runtime-store", "backup", "--runtime-data-dir", str(runtime_root), "--json")
    assert backup.returncode == 0
    backup_payload = json.loads(backup.stdout)
    assert Path(backup_payload["backup_path"]).is_file()

    retention = _run("runtime-store", "retention-plan", "--runtime-data-dir", str(runtime_root), "--json")
    assert retention.returncode == 0
    retention_payload = json.loads(retention.stdout)
    assert retention_payload["dry_run"] is True

    cleanup = _run("runtime-store", "cleanup", "--runtime-data-dir", str(runtime_root), "--json")
    assert cleanup.returncode == 0
    cleanup_payload = json.loads(cleanup.stdout)
    assert cleanup_payload["dry_run"] is True

    restore_target = tmp_path / "restore_target"
    restore = _run("runtime-store", "restore", "--backup", backup_payload["backup_path"], "--target", str(restore_target), "--json")
    assert restore.returncode == 0
    restore_payload = json.loads(restore.stdout)
    assert restore_payload["ok"] is True
    assert restore_target.joinpath("restore_report.json").is_file()
