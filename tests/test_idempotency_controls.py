from __future__ import annotations

from pathlib import Path

from runtime.recovery import ensure_pending_action_idempotency, verify_pending_action_safe_to_execute

from tests.recovery_test_utils import seed_recovery_runtime, write_recovery_manifest


def test_pending_action_receives_idempotency_key(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    manifest_dir = tmp_path / "manifests"
    manifest_path = write_recovery_manifest(manifest_dir)
    frame = seed_recovery_runtime(runtime_root, manifest_path)
    pending_action = {
        "action_id": "action_1",
        "step_id": frame.steps[0].step_id,
        "tool": "g/check",
        "namespace": "g",
        "action": "check",
        "action_type": "read_mail",
        "output_alias": "unread_mail",
        "business_ref": "mailbox",
        "status": "APPROVED",
    }

    normalized = ensure_pending_action_idempotency(frame, pending_action, step_id=frame.steps[0].step_id)

    assert normalized["idempotency_key"] == f"{frame.manifest_id}:{frame.frame_id}:{frame.steps[0].step_id}:read_mail:mailbox"
    assert normalized["side_effect_performed"] is False


def test_duplicate_idempotency_key_blocks_execution(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    manifest_dir = tmp_path / "manifests"
    manifest_path = write_recovery_manifest(manifest_dir)
    frame = seed_recovery_runtime(runtime_root, manifest_path)
    duplicate_key = f"{frame.manifest_id}:{frame.frame_id}:{frame.steps[0].step_id}:read_mail:mailbox"
    frame.state = "WAITING_FOR_EXECUTE"
    frame.pending_actions.append(
        {
            "action_id": "action_1",
            "step_id": frame.steps[0].step_id,
            "tool": "g/check",
            "namespace": "g",
            "action": "check",
            "action_type": "read_mail",
            "output_alias": "unread_mail",
            "business_ref": "mailbox",
            "status": "APPROVED",
            "side_effect_performed": False,
            "idempotency_key": duplicate_key,
        }
    )
    frame.executed_actions.append(
        {
            "action_id": "action_2",
            "step_id": frame.steps[0].step_id,
            "tool": "g/check",
            "namespace": "g",
            "action": "check",
            "action_type": "read_mail",
            "output_alias": "unread_mail",
            "business_ref": "mailbox",
            "status": "EXECUTED",
            "dry_run": False,
            "live": True,
            "live_side_effect": True,
            "side_effect_performed": True,
            "idempotency_key": duplicate_key,
            "result_type": "mail_result",
            "executed_at": frame.updated_at,
            "governance": {},
        }
    )

    check = verify_pending_action_safe_to_execute(frame, frame.pending_actions[0], runtime_data_dir=runtime_root, profile_name="demo")

    assert check["ok"] is False
    assert check["error_code"] == "DUPLICATE_SIDE_EFFECT_BLOCKED"
    assert any(item.get("id") == "duplicate_side_effect_blocked" for item in check["blockers"])
