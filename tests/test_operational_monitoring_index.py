from __future__ import annotations

from runtime.operational_monitoring import rebuild_run_health_index
from runtime.persistence import write_json_atomic, load_taskframe_dict

from tests.operational_monitoring_utils import seed_operational_monitoring_runtime


def test_valid_seeded_runtime_store_rebuilds_run_health_index(tmp_path) -> None:
    runtime_root, frame_ids = seed_operational_monitoring_runtime(tmp_path)

    index = rebuild_run_health_index(runtime_root, profile_name="demo", refresh_tool_health=False)

    assert index["ok"] is True
    assert index["summary"]["total_indexed_runs"] >= 1
    assert any(row["frame_id"] == frame_ids["healthy"] for row in index["runs"])


def test_missing_folder_is_reported(tmp_path) -> None:
    runtime_root, _ = seed_operational_monitoring_runtime(tmp_path)
    (runtime_root / "approval_packs").rmdir()

    index = rebuild_run_health_index(runtime_root, profile_name="demo", refresh_tool_health=False)

    assert index["runtime_store_validation"]["ok"] is False
    assert any(issue["category"] == "missing_folder" for issue in index["runtime_store_validation"]["issues"])


def test_invalid_taskframe_json_is_reported_not_fatal(tmp_path) -> None:
    runtime_root, _ = seed_operational_monitoring_runtime(tmp_path)
    (runtime_root / "taskframes" / "broken.json").write_text("{not valid json", encoding="utf-8")

    index = rebuild_run_health_index(runtime_root, profile_name="demo", refresh_tool_health=False)

    assert index["runtime_store_validation"]["ok"] is False
    assert any(issue["category"] == "invalid_json" for issue in index["runtime_store_validation"]["issues"])


def test_unknown_taskframe_state_is_reported(tmp_path) -> None:
    runtime_root, frame_ids = seed_operational_monitoring_runtime(tmp_path)
    frame_path = runtime_root / "runs" / frame_ids["healthy"] / "taskframe.json"
    payload = load_taskframe_dict(frame_ids["healthy"], runtime_root)
    payload["state"] = "NOT_A_REAL_STATE"
    write_json_atomic(frame_path, payload)

    index = rebuild_run_health_index(runtime_root, profile_name="demo", refresh_tool_health=False)

    assert any(issue["category"] == "unknown_state" for issue in index["runtime_store_validation"]["issues"])


def test_approval_pack_referencing_missing_frame_is_reported(tmp_path) -> None:
    runtime_root, _ = seed_operational_monitoring_runtime(tmp_path)
    write_json_atomic(
        runtime_root / "approval_packs" / "orphan.json",
        {"schema_version": 1, "frame_id": "frame_missing", "manifest_id": "manifest.missing", "state": "READY_FOR_CONFIRMATION"},
    )

    index = rebuild_run_health_index(runtime_root, profile_name="demo", refresh_tool_health=False)

    assert any(issue["category"] == "orphaned_artifact" for issue in index["runtime_store_validation"]["issues"])
