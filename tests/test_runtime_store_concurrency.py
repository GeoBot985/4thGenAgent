from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.approval import approve_action
from runtime.runtime_locking import (
    RuntimeLockTimeoutError,
    acquire_runtime_lock,
    cleanup_expired_runtime_locks,
    get_runtime_lock_path,
    list_runtime_locks,
    mutate_runtime_json,
)
from runtime.runtime_store import ensure_runtime_store_layout, validate_runtime_store
from runtime.persistence import PersistenceManager, get_taskframe_path, load_taskframe_dict
from runtime.taskframe import create_taskframe
from runtime.taskframe import to_dict as taskframe_to_dict
from runtime.taskframe_reload import taskframe_from_dict
from runtime.manifest_loader import load_manifest


def _seed_frame(runtime_root: Path, *, action_id: str = "ACT-001") -> str:
    ensure_runtime_store_layout(runtime_root)
    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.state = "WAITING_FOR_EXECUTE"
    frame.pending_actions.append(
        {
            "action_id": action_id,
            "tool": "write_sheet",
            "output_alias": "report",
            "args": {"sheet_id": "abc123"},
            "status": "PENDING_APPROVAL",
            "requested_at": "2026-01-01T00:00:00Z",
        }
    )
    PersistenceManager(runtime_root).save_snapshot(frame)
    return frame.frame_id


def _lock_audit_records(runtime_root: Path) -> list[dict[str, object]]:
    audit_path = runtime_root / "runtime_store_audit" / "runtime_store_audit.jsonl"
    if not audit_path.is_file():
        return []
    records: list[dict[str, object]] = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def test_new_mutable_artifact_receives_runtime_version_1(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    frame_id = _seed_frame(runtime_root)

    payload = load_taskframe_dict(frame_id, runtime_root)

    assert payload["runtime_version"] == 1
    assert payload["schema_version"] == 1
    assert payload["updated_at"]


def test_mutation_increments_version_and_updates_timestamp(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    frame_id = _seed_frame(runtime_root)
    path = get_taskframe_path(frame_id, runtime_root)
    before = load_taskframe_dict(frame_id, runtime_root)

    result = mutate_runtime_json(
        path,
        lambda payload: {**payload, "state": "WAITING_FOR_EXECUTE"},
        resource_key=f"taskframe/{frame_id}",
        runtime_data_dir=runtime_root,
        owner="test",
        request_id="REQ-version-bump",
    )

    after = load_taskframe_dict(frame_id, runtime_root)

    assert result["ok"] is True
    assert after["runtime_version"] == before["runtime_version"] + 1
    assert after["updated_at"] != before["updated_at"]


def test_stale_expected_version_returns_conflict(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    frame_id = _seed_frame(runtime_root)
    path = get_taskframe_path(frame_id, runtime_root)

    result = mutate_runtime_json(
        path,
        lambda payload: payload,
        expected_version=0,
        resource_key=f"taskframe/{frame_id}",
        runtime_data_dir=runtime_root,
        owner="test",
        request_id="REQ-stale",
    )

    assert result["ok"] is False
    assert result["error"] == "VERSION_CONFLICT"
    assert result["expected_version"] == 0
    assert result["actual_version"] == 1


def test_lock_file_is_created_and_released_during_mutation(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    frame_id = _seed_frame(runtime_root)
    path = get_taskframe_path(frame_id, runtime_root)
    lock_path = get_runtime_lock_path(f"taskframe/{frame_id}", runtime_root)

    def _mutator(payload: dict[str, object]) -> dict[str, object]:
        assert lock_path.is_file()
        return {**payload, "state": "WAITING_FOR_EXECUTE"}

    result = mutate_runtime_json(
        path,
        _mutator,
        resource_key=f"taskframe/{frame_id}",
        runtime_data_dir=runtime_root,
        owner="test",
        request_id="REQ-lock-create",
    )

    assert result["ok"] is True
    assert not lock_path.exists()


def test_lock_file_is_released_after_mutation_failure(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    frame_id = _seed_frame(runtime_root)
    path = get_taskframe_path(frame_id, runtime_root)
    lock_path = get_runtime_lock_path(f"taskframe/{frame_id}", runtime_root)

    def _mutator(payload: dict[str, object]) -> dict[str, object]:
        assert lock_path.is_file()
        raise RuntimeError("boom")

    result = mutate_runtime_json(
        path,
        _mutator,
        resource_key=f"taskframe/{frame_id}",
        runtime_data_dir=runtime_root,
        owner="test",
        request_id="REQ-lock-failure",
    )

    assert result["ok"] is False
    assert result["error"] == "MUTATION_FAILED"
    assert not lock_path.exists()


def test_expired_lock_can_be_reclaimed(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    ensure_runtime_store_layout(runtime_root)
    lock_path = get_runtime_lock_path("taskframe/TF-001", runtime_root)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "resource_key": "taskframe/TF-001",
                "lock_id": "LOCK-EXPIRED",
                "owner": "test",
                "pid": 999999,
                "created_at": "2026-05-21T23:59:55Z",
                "expires_at": "2026-05-21T23:59:56Z",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    lock = acquire_runtime_lock("taskframe/TF-001", timeout_seconds=0.5, runtime_data_dir=runtime_root, owner="test")
    try:
        assert lock.lock_id != "LOCK-EXPIRED"
        assert lock_path.is_file()
    finally:
        from runtime.runtime_locking import release_runtime_lock

        release_runtime_lock(lock, runtime_root)
    assert not lock_path.exists()


def test_active_lock_timeout_returns_deterministic_failure(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    ensure_runtime_store_layout(runtime_root)

    lock = acquire_runtime_lock("taskframe/TF-001", timeout_seconds=0.1, runtime_data_dir=runtime_root, owner="test")
    try:
        with pytest.raises(RuntimeLockTimeoutError):
            acquire_runtime_lock("taskframe/TF-001", timeout_seconds=0.1, runtime_data_dir=runtime_root, owner="test")
    finally:
        from runtime.runtime_locking import release_runtime_lock

        release_runtime_lock(lock, runtime_root)


def test_two_simulated_approval_updates_produce_one_success_and_one_conflict(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    frame_id = _seed_frame(runtime_root, action_id="ACT-009")
    path = get_taskframe_path(frame_id, runtime_root)

    def _mutate(payload: dict[str, object]) -> dict[str, object]:
        frame = taskframe_from_dict(payload)
        approved = approve_action(frame, "ACT-009", approved_by="api", reason="Approved via test")
        return taskframe_to_dict(approved)

    def _approve() -> dict[str, object]:
        return mutate_runtime_json(
            path,
            _mutate,
            expected_version=1,
            resource_key=f"taskframe/{frame_id}",
            runtime_data_dir=runtime_root,
            owner="test",
            request_id="REQ-race",
        )

    results = [_approve(), _approve()]

    statuses = sorted(200 if result.get("ok") else int(result.get("status_code", 409)) for result in results)
    bodies = results

    assert statuses == [200, 409]
    assert any(body.get("error") == "VERSION_CONFLICT" for body in bodies if isinstance(body, dict))


def test_runtime_store_status_reports_lock_version_health(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    _seed_frame(runtime_root, action_id="ACT-013")
    expired_lock = get_runtime_lock_path("taskframe/expired", runtime_root)
    expired_lock.parent.mkdir(parents=True, exist_ok=True)
    expired_lock.write_text(
        json.dumps(
            {
                "resource_key": "taskframe/expired",
                "lock_id": "LOCK-EXPIRED",
                "owner": "test",
                "pid": 999999,
                "created_at": "2026-05-21T23:59:55Z",
                "expires_at": "2026-05-21T23:59:56Z",
            }
        ),
        encoding="utf-8",
    )

    result = validate_runtime_store(runtime_root)

    assert result["versioned_artifacts"] >= 1
    assert len(result["expired_locks"]) >= 1
    assert any(issue["category"] == "stale_lock" for issue in result["issues"])


def test_cleanup_removes_expired_locks_only(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    ensure_runtime_store_layout(runtime_root)
    active_lock = acquire_runtime_lock("taskframe/active", timeout_seconds=0.1, runtime_data_dir=runtime_root, owner="test")
    expired_lock = get_runtime_lock_path("taskframe/expired", runtime_root)
    expired_lock.parent.mkdir(parents=True, exist_ok=True)
    expired_lock.write_text(
        json.dumps(
            {
                "resource_key": "taskframe/expired",
                "lock_id": "LOCK-EXPIRED",
                "owner": "test",
                "pid": 999999,
                "created_at": "2026-05-21T23:59:55Z",
                "expires_at": "2026-05-21T23:59:56Z",
            }
        ),
        encoding="utf-8",
    )

    payload = cleanup_expired_runtime_locks(runtime_root)

    try:
        assert "taskframe_expired.lock" in payload["removed"]
        assert active_lock.lock_id in {lock.get("lock_id") for lock in list_runtime_locks(runtime_root)}
    finally:
        from runtime.runtime_locking import release_runtime_lock

        release_runtime_lock(active_lock, runtime_root)


def test_audit_event_is_written_for_version_conflict(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    frame_id = _seed_frame(runtime_root, action_id="ACT-014")
    path = get_taskframe_path(frame_id, runtime_root)

    mutate_runtime_json(
        path,
        lambda payload: {**payload, "state": "WAITING_FOR_EXECUTE"},
        resource_key=f"taskframe/{frame_id}",
        runtime_data_dir=runtime_root,
        owner="test",
        request_id="REQ-audit-version",
    )
    mutate_runtime_json(
        path,
        lambda payload: payload,
        expected_version=1,
        resource_key=f"taskframe/{frame_id}",
        runtime_data_dir=runtime_root,
        owner="test",
        request_id="REQ-audit-version",
    )

    records = _lock_audit_records(runtime_root)
    assert any(record.get("event_type") == "RUNTIME_VERSION_CONFLICT" for record in records)


def test_audit_event_is_written_for_lock_timeout(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    ensure_runtime_store_layout(runtime_root)
    lock = acquire_runtime_lock("taskframe/timeout", timeout_seconds=0.1, runtime_data_dir=runtime_root, owner="test")
    try:
        with pytest.raises(RuntimeLockTimeoutError):
            acquire_runtime_lock("taskframe/timeout", timeout_seconds=0.1, runtime_data_dir=runtime_root, owner="test")
    finally:
        from runtime.runtime_locking import release_runtime_lock

        release_runtime_lock(lock, runtime_root)

    records = _lock_audit_records(runtime_root)
    assert any(record.get("event_type") == "RUNTIME_LOCK_TIMEOUT" for record in records)


def test_no_lock_file_contains_tokens_or_secrets(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    ensure_runtime_store_layout(runtime_root)
    lock = acquire_runtime_lock("taskframe/secret-check", timeout_seconds=0.1, runtime_data_dir=runtime_root, owner="test")
    try:
        text = Path(lock.path).read_text(encoding="utf-8")
        assert "token" not in text.lower()
    finally:
        from runtime.runtime_locking import release_runtime_lock

        release_runtime_lock(lock, runtime_root)
