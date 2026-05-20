from __future__ import annotations

from pathlib import Path

from runtime.persistence import PersistenceManager, write_json_atomic
from runtime.manifest_loader import load_manifest
from runtime.run_report import generate_operator_run_report
from runtime.runtime_store import ensure_runtime_store_layout, validate_runtime_store
from runtime.taskframe import create_taskframe


def _seed_runtime_store(runtime_root: Path, *, pending: bool = False, state: str = "COMPLETED") -> str:
    ensure_runtime_store_layout(runtime_root)
    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.state = state
    if pending:
        frame.state = "WAITING_FOR_EXECUTE"
        frame.pending_actions.append({"action_id": "pa_1", "tool": "wa/send", "status": "PENDING_APPROVAL"})
    PersistenceManager(runtime_root).save_snapshot(frame)
    generate_operator_run_report(runtime_root, frame.frame_id, rebuild=True)
    write_json_atomic(runtime_root / "tool_health" / "latest_tool_health.json", {"schema_version": 1, "generated_at": frame.updated_at, "results": [], "by_tool": {}, "summary": {}})
    return frame.frame_id


def test_valid_seeded_runtime_store_passes_validation(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    _seed_runtime_store(runtime_root, pending=True)

    result = validate_runtime_store(runtime_root)

    assert result["ok"] is True
    assert result["artifact_counts"]["taskframes"] >= 1
    assert result["index_rebuildable"] is True


def test_missing_folder_is_reported(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    _seed_runtime_store(runtime_root)
    (runtime_root / "approval_packs").rmdir()

    result = validate_runtime_store(runtime_root)

    assert result["ok"] is False
    assert any(issue["category"] == "missing_folder" for issue in result["issues"])


def test_invalid_taskframe_json_is_reported_not_fatal(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    ensure_runtime_store_layout(runtime_root)
    bad = runtime_root / "taskframes" / "corrupted.json"
    bad.write_text("{not valid json", encoding="utf-8")

    result = validate_runtime_store(runtime_root)

    assert result["ok"] is False
    assert any(issue["category"] == "invalid_json" for issue in result["issues"])


def test_unknown_taskframe_state_is_reported(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    frame_id = _seed_runtime_store(runtime_root)
    taskframe_path = runtime_root / "runs" / frame_id / "taskframe.json"
    payload = taskframe_path.read_text(encoding="utf-8")
    payload = payload.replace('"state": "COMPLETED"', '"state": "NOT_A_REAL_STATE"')
    taskframe_path.write_text(payload, encoding="utf-8")

    result = validate_runtime_store(runtime_root)

    assert result["ok"] is False
    assert any(issue["category"] == "unknown_state" for issue in result["issues"])


def test_approval_pack_referencing_missing_frame_is_reported(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    ensure_runtime_store_layout(runtime_root)
    write_json_atomic(
        runtime_root / "approval_packs" / "orphan.json",
        {"schema_version": 1, "frame_id": "frame_missing", "manifest_id": "manifest.missing", "state": "READY_FOR_CONFIRMATION"},
    )

    result = validate_runtime_store(runtime_root)

    assert any(issue["category"] == "orphaned_artifact" for issue in result["issues"])
