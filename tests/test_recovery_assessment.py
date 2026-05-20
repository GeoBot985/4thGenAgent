from __future__ import annotations

from pathlib import Path

from runtime.recovery import assess_recovery, generate_recovery_report
from runtime.persistence import load_taskframe_dict, save_taskframe
from runtime.taskframe import add_audit_event, create_taskframe

from tests.recovery_test_utils import seed_recovery_runtime, write_recovery_manifest


def _load_frame(runtime_root: Path, frame_id: str) -> dict:
    return load_taskframe_dict(frame_id, runtime_root)


def test_read_only_timeout_is_retryable(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    manifest_dir = tmp_path / "manifests"
    manifest_path = write_recovery_manifest(
        manifest_dir,
        retry={
            "max_attempts": 3,
            "retry_on": ["external_dependency_unavailable", "timeout"],
            "do_not_retry_on": ["business_validation_failure", "duplicate_side_effect_risk"],
            "delay_seconds": 0,
        },
    )
    frame = seed_recovery_runtime(runtime_root, manifest_path)
    frame.state = "FAILED_EXECUTION"
    frame.steps[0].status = "FAILED"
    frame.steps[0].last_error = "Connection timeout while reading external data"
    frame.errors.append(
        {
            "type": "tool",
            "message": frame.steps[0].last_error,
            "data": {},
            "timestamp": frame.updated_at,
        }
    )
    frame.attempts.append({"step_id": frame.steps[0].step_id, "attempt": 1, "status": "FAILED"})
    save_taskframe(frame, runtime_root)

    assessment = assess_recovery(_load_frame(runtime_root, frame.frame_id), runtime_data_dir=runtime_root, manifest_dir=manifest_dir)

    assert assessment["recovery_status"] == "retryable"
    assert assessment["safe_to_retry"] is True
    assert assessment["safe_to_resume"] is False
    assert assessment["failure_category"] == "external_dependency_unavailable"
    assert assessment["command_suggestion"].startswith("taskframe recover retry-step")


def test_validation_failure_requires_manual_review(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    manifest_dir = tmp_path / "manifests"
    manifest_path = write_recovery_manifest(manifest_dir)
    frame = seed_recovery_runtime(runtime_root, manifest_path)
    frame.state = "FAILED_VALIDATION"
    frame.steps[0].status = "FAILED"
    frame.validations.append({"validation_id": "validation_1", "ok": False, "message": "Business validation failed"})
    frame.errors.append({"type": "validation", "message": "Business validation failed", "data": {}, "timestamp": frame.updated_at})
    save_taskframe(frame, runtime_root)

    assessment = assess_recovery(_load_frame(runtime_root, frame.frame_id), runtime_data_dir=runtime_root, manifest_dir=manifest_dir)

    assert assessment["recovery_status"] == "manual_review_required"
    assert assessment["safe_to_retry"] is False
    assert assessment["safe_to_resume"] is False
    assert assessment["reason"]


def test_missing_manifest_is_not_recoverable(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = write_recovery_manifest(manifest_dir, manifest_id="recovery.missing")
    frame = seed_recovery_runtime(runtime_root, manifest_path)
    frame.manifest_id = "manifest.does.not.exist"
    frame.state = "FAILED_EXECUTION"
    frame.steps[0].status = "FAILED"
    save_taskframe(frame, runtime_root)

    assessment = assess_recovery(_load_frame(runtime_root, frame.frame_id), runtime_data_dir=runtime_root, manifest_dir=manifest_dir)

    assert assessment["recovery_status"] == "not_recoverable"
    assert "Manifest" in assessment["reason"]


def test_stale_running_frame_is_resumable_when_safe(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    manifest_dir = tmp_path / "manifests"
    manifest_path = write_recovery_manifest(manifest_dir)
    frame = seed_recovery_runtime(runtime_root, manifest_path)
    frame.state = "RUNNING"
    frame.updated_at = "2026-05-01T10:00:00Z"
    save_taskframe(frame, runtime_root)

    assessment = assess_recovery(_load_frame(runtime_root, frame.frame_id), runtime_data_dir=runtime_root, manifest_dir=manifest_dir)

    assert assessment["recovery_status"] == "resumable"
    assert assessment["safe_to_resume"] is True
    assert assessment["command_suggestion"].startswith("taskframe recover resume")


def test_executed_side_effect_is_not_retryable(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    manifest_dir = tmp_path / "manifests"
    manifest_path = write_recovery_manifest(manifest_dir)
    frame = seed_recovery_runtime(runtime_root, manifest_path)
    frame.state = "FAILED_EXECUTION"
    frame.steps[0].status = "FAILED"
    frame.executed_actions.append(
        {
            "action_id": "action_1",
            "step_id": frame.steps[0].step_id,
            "tool": "g/check",
            "namespace": "g",
            "action": "check",
            "action_type": "read_mail",
            "output_alias": "unread_mail",
            "args": {"max_results": 5},
            "status": "EXECUTED",
            "dry_run": False,
            "live": True,
            "live_side_effect": True,
            "side_effect_performed": True,
            "idempotency_key": "recovery.retryable:frame:check_mail:read_mail:mailbox",
            "business_ref": "mailbox",
            "result_type": "mail_result",
            "executed_at": frame.updated_at,
            "governance": {},
        }
    )
    save_taskframe(frame, runtime_root)

    assessment = assess_recovery(_load_frame(runtime_root, frame.frame_id), runtime_data_dir=runtime_root, manifest_dir=manifest_dir)

    assert assessment["recovery_status"] in {"blocked", "manual_review_required"}
    assert assessment["safe_to_retry"] is False
    assert assessment["side_effect_risk"] == "executed"


def test_recovery_report_includes_side_effect_risk(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    manifest_dir = tmp_path / "manifests"
    manifest_path = write_recovery_manifest(manifest_dir)
    frame = seed_recovery_runtime(runtime_root, manifest_path)
    frame.state = "FAILED_EXECUTION"
    frame.steps[0].status = "FAILED"
    frame.steps[0].last_error = "temporary failure"
    frame.pending_actions.append(
        {
            "action_id": "action_1",
            "step_id": frame.steps[0].step_id,
            "tool": "g/check",
            "namespace": "g",
            "action": "check",
            "action_type": "read_mail",
            "output_alias": "unread_mail",
            "args": {"max_results": 5},
            "status": "APPROVED",
            "dry_run": True,
            "side_effect_performed": False,
            "idempotency_key": "recovery.retryable:frame:check_mail:read_mail:mailbox",
            "business_ref": "mailbox",
            "executed_at": "",
        }
    )
    save_taskframe(frame, runtime_root)

    report = generate_recovery_report(_load_frame(runtime_root, frame.frame_id), runtime_data_dir=runtime_root, manifest_dir=manifest_dir)

    payload = report["payload"]
    assert payload["assessment"]["side_effect_risk"] in {"staged", "executed"}
    assert Path(report["json_path"]).is_file()
    assert Path(report["markdown_path"]).is_file()
