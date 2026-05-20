from __future__ import annotations

from runtime.operational_monitoring import build_monitoring_summary, build_run_health_summary
from runtime.persistence import load_taskframe_dict

from tests.operational_monitoring_utils import seed_operational_monitoring_runtime


def test_completed_frame_classified_as_healthy(tmp_path) -> None:
    runtime_root, frame_ids = seed_operational_monitoring_runtime(tmp_path)
    frame = load_taskframe_dict(frame_ids["healthy"], runtime_root)

    summary = build_run_health_summary(frame, runtime_data_dir=runtime_root)

    assert summary.health == "healthy"
    assert summary.state == "COMPLETED"


def test_failed_validation_frame_classified_as_failed(tmp_path) -> None:
    runtime_root, frame_ids = seed_operational_monitoring_runtime(tmp_path)
    frame = load_taskframe_dict(frame_ids["failed_validation"], runtime_root)

    summary = build_run_health_summary(frame, runtime_data_dir=runtime_root)

    assert summary.health == "failed"
    assert summary.failure_category == "business_validation_failure"
    assert summary.affected_step_id


def test_failed_execution_frame_classified_as_failed(tmp_path) -> None:
    runtime_root, frame_ids = seed_operational_monitoring_runtime(tmp_path)
    frame = load_taskframe_dict(frame_ids["failed_execution"], runtime_root)

    summary = build_run_health_summary(frame, runtime_data_dir=runtime_root)

    assert summary.health == "failed"
    assert summary.failure_category == "tool_execution_failure"


def test_waiting_for_execute_frame_classified_as_pending(tmp_path) -> None:
    runtime_root, frame_ids = seed_operational_monitoring_runtime(tmp_path)
    frame = load_taskframe_dict(frame_ids["waiting"], runtime_root)

    summary = build_run_health_summary(frame, runtime_data_dir=runtime_root)

    assert summary.health == "pending"
    assert summary.pending_action_count == 1


def test_stale_running_frame_classified_as_stuck(tmp_path) -> None:
    runtime_root, frame_ids = seed_operational_monitoring_runtime(tmp_path)
    frame = load_taskframe_dict(frame_ids["stale"], runtime_root)

    summary = build_run_health_summary(frame, runtime_data_dir=runtime_root)

    assert summary.health == "stuck"


def test_external_auth_error_classified_as_blocked(tmp_path) -> None:
    runtime_root, frame_ids = seed_operational_monitoring_runtime(tmp_path)
    frame = load_taskframe_dict(frame_ids["blocked_auth"], runtime_root)

    summary = build_run_health_summary(frame, runtime_data_dir=runtime_root)

    assert summary.health == "blocked"
    assert summary.failure_category == "external_auth_failure"


def test_external_dependency_error_classified_as_blocked(tmp_path) -> None:
    runtime_root, frame_ids = seed_operational_monitoring_runtime(tmp_path)
    frame = load_taskframe_dict(frame_ids["blocked_dep"], runtime_root)

    summary = build_run_health_summary(frame, runtime_data_dir=runtime_root)

    assert summary.health == "blocked"
    assert summary.failure_category == "external_dependency_unavailable"


def test_tool_health_status_appears_in_summary(tmp_path) -> None:
    runtime_root, _ = seed_operational_monitoring_runtime(tmp_path)
    summary = build_monitoring_summary(runtime_root, rebuild=False)

    assert summary["tool_health_status"]["status"] == "blocked"
    assert summary["summary"]["pending_count"] >= 1
