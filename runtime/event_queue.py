"""Spec 108 — Event Queue + Replay Inspector v1.

Canonical event queue record, status constants, persistence helpers,
content fingerprinting, and safe dry-run replay.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .taskframe import json_safe, utc_now

# ---------------------------------------------------------------------------
# Storage paths
# ---------------------------------------------------------------------------

EVENT_QUEUE_FILE = "event_queue.jsonl"
EVENT_QUEUE_INDEX_FILE = "event_queue_index.json"


def get_queue_path(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / "events" / EVENT_QUEUE_FILE


def get_queue_index_path(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / "events" / EVENT_QUEUE_INDEX_FILE


# ---------------------------------------------------------------------------
# Canonical event statuses
# ---------------------------------------------------------------------------

STATUS_RECEIVED = "RECEIVED"
STATUS_ROUTE_RESOLVED = "ROUTE_RESOLVED"
STATUS_ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
STATUS_FRAME_CREATED = "FRAME_CREATED"
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_WAITING_FOR_EXECUTE = "WAITING_FOR_EXECUTE"
STATUS_FAILED_VALIDATION = "FAILED_VALIDATION"
STATUS_FAILED_EXECUTION = "FAILED_EXECUTION"
STATUS_FAILED_COMPLETION = "FAILED_COMPLETION"
STATUS_DUPLICATE_EVENT = "DUPLICATE_EVENT"
STATUS_REPLAYED_DRY_RUN = "REPLAYED_DRY_RUN"
STATUS_REPLAY_FAILED = "REPLAY_FAILED"

# Map legacy event_store statuses → canonical queue statuses
_LEGACY_STATUS_MAP: dict[str, str] = {
    "RECEIVED": STATUS_RECEIVED,
    "INVALID_EVENT": STATUS_FAILED_EXECUTION,
    "DUPLICATE_EVENT": STATUS_DUPLICATE_EVENT,
    "NO_ROUTE": STATUS_ROUTE_NOT_FOUND,
    "ROUTE_MAPPING_FAILED": STATUS_FAILED_EXECUTION,
    "MANIFEST_NOT_FOUND": STATUS_FAILED_EXECUTION,
    "FRAME_CREATED": STATUS_FRAME_CREATED,
    "FAILED": STATUS_FAILED_EXECUTION,
    "RUNNING": STATUS_RUNNING,
    "COMPLETED": STATUS_COMPLETED,
    "COMPLETED_NO_DATA": STATUS_COMPLETED,
    "WAITING_FOR_EXECUTE": STATUS_WAITING_FOR_EXECUTE,
    "FAILED_VALIDATION": STATUS_FAILED_VALIDATION,
    "FAILED_EXECUTION": STATUS_FAILED_EXECUTION,
    "FAILED_COMPLETION": STATUS_FAILED_COMPLETION,
}

# Map TaskFrame terminal states → canonical queue statuses
_FRAME_STATE_TO_EVENT_STATUS: dict[str, str] = {
    "COMPLETED": STATUS_COMPLETED,
    "COMPLETED_NO_DATA": STATUS_COMPLETED,
    "WAITING_FOR_EXECUTE": STATUS_WAITING_FOR_EXECUTE,
    "FAILED_VALIDATION": STATUS_FAILED_VALIDATION,
    "FAILED_EXECUTION": STATUS_FAILED_EXECUTION,
    "FAILED_COMPLETION": STATUS_FAILED_COMPLETION,
    "CANCELLED": STATUS_FAILED_EXECUTION,
    "EXPIRED": STATUS_FAILED_EXECUTION,
    "RUNNING": STATUS_RUNNING,
    "EXECUTING_PENDING": STATUS_RUNNING,
    "VERIFYING": STATUS_RUNNING,
}


def frame_state_to_event_status(frame_state: str) -> str:
    return _FRAME_STATE_TO_EVENT_STATUS.get(str(frame_state), STATUS_FAILED_EXECUTION)


def canonical_status(legacy_status: str) -> str:
    return _LEGACY_STATUS_MAP.get(str(legacy_status), STATUS_FAILED_EXECUTION)


# ---------------------------------------------------------------------------
# Queue record builder
# ---------------------------------------------------------------------------

def build_queue_record(
    event_data: dict[str, Any],
    *,
    status: str = STATUS_RECEIVED,
    route_id: str | None = None,
    manifest_id: str | None = None,
    linked_frame_id: str | None = None,
    duplicate: bool = False,
    duplicate_of_event_id: str | None = None,
    failure_reason: str = "",
    failure_code: str = "",
    errors: list[str] | None = None,
    dry_run: bool = True,
    attempt_count: int = 0,
    last_replay_frame_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    meta = dict(metadata or {})
    fingerprint = build_event_fingerprint(event_data)
    meta.setdefault("fingerprint", fingerprint)

    existing_created_at = str(event_data.get("created_at", "") or "")
    return {
        "event_id": str(event_data.get("event_id", "") or ""),
        "source": str(event_data.get("source", "") or ""),
        "event_type": str(event_data.get("event_type", "") or ""),
        "payload": dict(event_data.get("payload") or {}),
        "received_at": str(event_data.get("received_at", "") or now),
        "status": status,
        "duplicate": bool(duplicate),
        "duplicate_of_event_id": duplicate_of_event_id,
        "route_id": route_id,
        "manifest_id": manifest_id,
        "linked_frame_id": linked_frame_id,
        "attempt_count": int(attempt_count),
        "last_attempted_at": now,
        "last_replay_frame_id": last_replay_frame_id,
        "failure_reason": str(failure_reason),
        "failure_code": str(failure_code),
        "errors": list(errors or []),
        "dry_run": bool(dry_run),
        "created_at": existing_created_at or now,
        "updated_at": now,
        "schema_version": 1,
        "runtime_version": int(event_data.get("runtime_version", 1) or 1),
        "metadata": meta,
    }


def update_queue_record(existing: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Return a new record merging existing fields with overrides."""
    updated = dict(existing)
    updated.update(overrides)
    updated["updated_at"] = utc_now()
    updated["runtime_version"] = int(updated.get("runtime_version", 1) or 1) + 1
    meta_update = overrides.get("metadata")
    if isinstance(meta_update, dict):
        merged_meta = dict(existing.get("metadata") or {})
        merged_meta.update(meta_update)
        updated["metadata"] = merged_meta
    return updated


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def write_queue_record(
    record: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
) -> None:
    """Append record to JSONL ledger and update index."""
    queue_path = get_queue_path(runtime_data_dir)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(json_safe(record), ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    _update_queue_index(record, runtime_data_dir)
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    if getattr(backend, "backend_name", "filesystem") != "filesystem":
        backend.save_queue_record(record)


def _update_queue_index(
    record: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
) -> None:
    index_path = get_queue_index_path(runtime_data_dir)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index: dict[str, Any] = {}
    if index_path.is_file():
        try:
            raw = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                index = raw
        except (json.JSONDecodeError, OSError):
            pass
    event_id = str(record.get("event_id", ""))
    if event_id:
        index[event_id] = json_safe(record)
    with index_path.open("w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def load_queue_record(
    event_id: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any] | None:
    """Load the latest queue record for an event from the index."""
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    if getattr(backend, "backend_name", "filesystem") != "filesystem":
        record = backend.get_queue_record(event_id)
        if record is not None:
            return record
    index_path = get_queue_index_path(runtime_data_dir)
    if not index_path.is_file():
        return None
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    record = raw.get(str(event_id))
    return dict(record) if isinstance(record, dict) else None


def list_queue_records(
    *,
    runtime_data_dir: str | Path = "runtime_data",
    status: str | None = None,
    source: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List queue records from the index, optionally filtered."""
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    if getattr(backend, "backend_name", "filesystem") != "filesystem":
        return backend.list_queue_records(limit=limit, status=status, source=source, event_type=event_type)
    index_path = get_queue_index_path(runtime_data_dir)
    if not index_path.is_file():
        return []
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw, dict):
        return []

    records = [dict(v) for v in raw.values() if isinstance(v, dict)]
    records.sort(key=lambda r: str(r.get("received_at", "") or ""), reverse=True)

    if status:
        records = [r for r in records if r.get("status") == status]
    if source:
        records = [r for r in records if r.get("source") == source]
    if event_type:
        records = [r for r in records if r.get("event_type") == event_type]

    return records[:int(limit)]


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------

def build_event_fingerprint(event: dict[str, Any]) -> str:
    """Content fingerprint for optional duplicate detection.

    Based on source + event_type + canonical JSON payload.
    Stored in metadata only; not used for hard blocking in v1.
    """
    key = {
        "source": str(event.get("source", "") or ""),
        "event_type": str(event.get("event_type", "") or ""),
        "payload": event.get("payload") or {},
    }
    encoded = json.dumps(key, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Spec 137 — Durable queue operations
# ---------------------------------------------------------------------------

DURABLE_QUEUE_DIR = "queue"
DURABLE_QUEUE_FILE = "durable_queue.jsonl"
DURABLE_QUEUE_INDEX_FILE = "durable_queue_index.json"


def _get_durable_queue_dir(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / DURABLE_QUEUE_DIR


def _save_durable_record(
    record: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
) -> None:
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    backend.save_durable_queue_record(record)


def _load_durable_record(
    queue_id: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any] | None:
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    return backend.get_durable_queue_record(queue_id)


def _list_durable_records(
    runtime_data_dir: str | Path = "runtime_data",
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    filters: dict[str, Any] = {}
    if status:
        filters["status"] = status
    return backend.list_durable_queue_records(limit=limit, **filters)


def _find_active_by_dedupe_key(
    dedupe_key: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any] | None:
    from .event_queue_contract import TERMINAL_STATUSES

    records = _list_durable_records(runtime_data_dir=runtime_data_dir, limit=10_000)
    for record in records:
        if record.get("dedupe_key") == dedupe_key and record.get("status") not in TERMINAL_STATUSES:
            return record
    return None


def enqueue_event(
    event: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
    *,
    priority: int = 100,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Enqueue an event as a durable queue record.

    Returns ok=True with the new queue record, or ok=False with duplicate info.
    """
    from .event_queue_contract import build_dedupe_key, build_durable_queue_record, TERMINAL_STATUSES

    dedupe_key = build_dedupe_key(event)
    existing = _find_active_by_dedupe_key(dedupe_key, runtime_data_dir)
    if existing is not None:
        return {
            "ok": False,
            "duplicate": True,
            "existing_queue_id": existing.get("queue_id"),
            "existing_status": existing.get("status"),
            "dedupe_key": dedupe_key,
        }

    record = build_durable_queue_record(event, priority=priority, max_attempts=max_attempts)
    _save_durable_record(record, runtime_data_dir)
    return {"ok": True, "duplicate": False, "queue_id": record["queue_id"], "record": record}


def claim_next_event(
    worker_id: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Claim the next PENDING event ordered by priority then available_at."""
    from .event_queue_contract import STATUS_PENDING, STATUS_CLAIMED, update_durable_queue_record

    now = utc_now()
    records = _list_durable_records(runtime_data_dir=runtime_data_dir, status=STATUS_PENDING, limit=100)
    eligible = [r for r in records if str(r.get("available_at", "") or "") <= now]
    if not eligible:
        return {"ok": False, "no_pending_event": True, "message": "No PENDING events available."}

    eligible.sort(key=lambda r: (int(r.get("priority", 100) or 100), str(r.get("available_at") or "")))
    record = eligible[0]

    claimed = update_durable_queue_record(record, status=STATUS_CLAIMED, claimed_at=now, claimed_by=str(worker_id))
    _save_durable_record(claimed, runtime_data_dir)
    return {"ok": True, "queue_id": claimed["queue_id"], **claimed}


def mark_event_processing(
    queue_id: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Transition a CLAIMED event to PROCESSING."""
    from .event_queue_contract import STATUS_PROCESSING, update_durable_queue_record

    record = _load_durable_record(queue_id, runtime_data_dir)
    if record is None:
        return {"ok": False, "error": f"Queue record not found: {queue_id}"}

    updated = update_durable_queue_record(record, status=STATUS_PROCESSING)
    _save_durable_record(updated, runtime_data_dir)
    return {"ok": True, "queue_id": queue_id, "status": STATUS_PROCESSING}


def mark_event_completed(
    queue_id: str,
    frame_id: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Mark a PROCESSING event as COMPLETED, linking the resulting TaskFrame."""
    from .event_queue_contract import STATUS_COMPLETED, update_durable_queue_record

    record = _load_durable_record(queue_id, runtime_data_dir)
    if record is None:
        return {"ok": False, "error": f"Queue record not found: {queue_id}"}

    now = utc_now()
    updated = update_durable_queue_record(
        record,
        status=STATUS_COMPLETED,
        linked_frame_id=str(frame_id or ""),
        completed_at=now,
    )
    _save_durable_record(updated, runtime_data_dir)
    return {"ok": True, "queue_id": queue_id, "frame_id": frame_id, "status": STATUS_COMPLETED}


def mark_event_failed(
    queue_id: str,
    error: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Mark a queue item as failed, classifying into retryable or permanent failure."""
    from .event_queue_contract import (
        STATUS_FAILED_RETRYABLE,
        STATUS_FAILED_PERMANENT,
        STATUS_DEAD_LETTER,
        is_retryable_failure_category,
        DEFAULT_MAX_ATTEMPTS,
        update_durable_queue_record,
    )

    record = _load_durable_record(queue_id, runtime_data_dir)
    if record is None:
        return {"ok": False, "error": f"Queue record not found: {queue_id}"}

    category = str(error.get("category", "") or "")
    message = str(error.get("message", "") or "")
    attempt_count = int(record.get("attempt_count", 0) or 0) + 1
    max_attempts = int(record.get("max_attempts", DEFAULT_MAX_ATTEMPTS) or DEFAULT_MAX_ATTEMPTS)

    retryable = is_retryable_failure_category(category)

    if not retryable:
        new_status = STATUS_FAILED_PERMANENT
    elif attempt_count >= max_attempts:
        new_status = STATUS_DEAD_LETTER
    else:
        new_status = STATUS_FAILED_RETRYABLE

    updated = update_durable_queue_record(
        record,
        status=new_status,
        attempt_count=attempt_count,
        last_error=message,
        failure_category=category,
    )
    _save_durable_record(updated, runtime_data_dir)
    return {
        "ok": True,
        "queue_id": queue_id,
        "status": new_status,
        "attempt_count": attempt_count,
        "failure_category": category,
    }


def retry_event(
    queue_id: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Re-queue a FAILED_RETRYABLE item back to PENDING."""
    from .event_queue_contract import STATUS_FAILED_RETRYABLE, STATUS_PENDING, update_durable_queue_record

    record = _load_durable_record(queue_id, runtime_data_dir)
    if record is None:
        return {"ok": False, "error": f"Queue record not found: {queue_id}"}

    if record.get("status") != STATUS_FAILED_RETRYABLE:
        return {
            "ok": False,
            "error": f"Only FAILED_RETRYABLE records can be retried. Current status: {record.get('status')}",
        }

    updated = update_durable_queue_record(
        record,
        status=STATUS_PENDING,
        available_at=utc_now(),
        claimed_at="",
        claimed_by="",
    )
    _save_durable_record(updated, runtime_data_dir)
    return {"ok": True, "queue_id": queue_id, "status": STATUS_PENDING}


def cancel_event(
    queue_id: str,
    reason: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Cancel a non-terminal queue item."""
    from .event_queue_contract import STATUS_CANCELLED, TERMINAL_STATUSES, update_durable_queue_record

    record = _load_durable_record(queue_id, runtime_data_dir)
    if record is None:
        return {"ok": False, "error": f"Queue record not found: {queue_id}"}

    if record.get("status") in TERMINAL_STATUSES:
        return {
            "ok": False,
            "error": f"Cannot cancel a terminal record. Status: {record.get('status')}",
        }

    updated = update_durable_queue_record(
        record,
        status=STATUS_CANCELLED,
        last_error=str(reason),
    )
    _save_durable_record(updated, runtime_data_dir)
    return {"ok": True, "queue_id": queue_id, "status": STATUS_CANCELLED}


def list_queue(
    status: str | None = None,
    limit: int = 100,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """List durable queue records, optionally filtered by status."""
    records = _list_durable_records(runtime_data_dir=runtime_data_dir, status=status, limit=limit)
    return {"ok": True, "count": len(records), "records": records}


def queue_health(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    """Return queue health summary with counts per status and oldest pending item."""
    from .event_queue_contract import STATUS_PENDING, STATUS_FAILED_RETRYABLE, STATUS_DEAD_LETTER
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    backend_health = backend.health()

    all_records = _list_durable_records(runtime_data_dir=runtime_data_dir, limit=10_000)
    counts: dict[str, int] = {}
    for r in all_records:
        s = str(r.get("status", "") or "unknown")
        counts[s] = counts.get(s, 0) + 1

    pending = [r for r in all_records if r.get("status") == STATUS_PENDING]
    pending.sort(key=lambda r: str(r.get("created_at", "") or ""))
    oldest_pending = pending[0] if pending else None

    return {
        "ok": True,
        "backend": str(getattr(backend, "backend_name", "unknown")),
        "counts_by_status": counts,
        "total": len(all_records),
        "pending_count": counts.get(STATUS_PENDING, 0),
        "failed_retryable_count": counts.get(STATUS_FAILED_RETRYABLE, 0),
        "dead_letter_count": counts.get(STATUS_DEAD_LETTER, 0),
        "oldest_pending_created_at": str(oldest_pending.get("created_at", "") or "") if oldest_pending else "",
    }


def recover_stale_queue_items(
    runtime_data_dir: str | Path = "runtime_data",
    stale_timeout_minutes: int = 15,
) -> dict[str, Any]:
    """Find CLAIMED/PROCESSING items older than stale_timeout_minutes and recover them."""
    from .event_queue_contract import (
        STATUS_CLAIMED,
        STATUS_PROCESSING,
        STATUS_FAILED_RETRYABLE,
        STATUS_DEAD_LETTER,
        DEFAULT_MAX_ATTEMPTS,
        update_durable_queue_record,
    )
    import datetime

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    cutoff_dt = now_dt - datetime.timedelta(minutes=int(stale_timeout_minutes))
    cutoff_str = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    all_records = _list_durable_records(runtime_data_dir=runtime_data_dir, limit=10_000)
    stale_statuses = {STATUS_CLAIMED, STATUS_PROCESSING}
    recovered: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for record in all_records:
        if record.get("status") not in stale_statuses:
            continue
        updated_at = str(record.get("updated_at", "") or "")
        if updated_at >= cutoff_str:
            continue

        queue_id = str(record.get("queue_id", ""))
        attempt_count = int(record.get("attempt_count", 0) or 0)
        max_attempts = int(record.get("max_attempts", DEFAULT_MAX_ATTEMPTS) or DEFAULT_MAX_ATTEMPTS)

        if attempt_count >= max_attempts:
            new_status = STATUS_DEAD_LETTER
        else:
            new_status = STATUS_FAILED_RETRYABLE

        updated = update_durable_queue_record(
            record,
            status=new_status,
            last_error=f"Stale {record.get('status')} item recovered after {stale_timeout_minutes}m timeout.",
            failure_category="runtime_exception",
        )
        _save_durable_record(updated, runtime_data_dir)
        recovered.append({"queue_id": queue_id, "old_status": record.get("status"), "new_status": new_status})

    return {
        "ok": True,
        "recovered_count": len(recovered),
        "skipped_count": len(skipped),
        "recovered": recovered,
        "stale_timeout_minutes": stale_timeout_minutes,
    }


def replay_event_dry_run(
    event_id: str,
    *,
    runtime_data_dir: str | Path = "runtime_data",
    manifest_dir: str | Path = "manifests",
    replayed_by: str = "operator",
    reason: str = "",
) -> dict[str, Any]:
    """Replay a known event in dry-run mode, creating a new TaskFrame.

    Rules:
    - Always dry_run=True.
    - Never mutates the original event payload.
    - Creates a new TaskFrame linked via last_replay_frame_id.
    - Increments attempt_count.
    - Updates queue status to REPLAYED_DRY_RUN or REPLAY_FAILED.
    """
    from .event_store import intake_and_run_event, get_event

    queue_record = load_queue_record(event_id, runtime_data_dir)
    if queue_record is None:
        # Fall back to event ledger
        raw_event = get_event(event_id, runtime_data_dir)
        if raw_event is None:
            return {
                "ok": False,
                "event_id": event_id,
                "original_frame_id": None,
                "replay_frame_id": None,
                "route_id": None,
                "manifest_id": None,
                "status": STATUS_REPLAY_FAILED,
                "errors": [f"Event not found: {event_id}"],
            }
        queue_record = build_queue_record(raw_event)

    original_frame_id = queue_record.get("linked_frame_id")
    attempt_count = int(queue_record.get("attempt_count", 0) or 0) + 1

    # Build replay payload — must not mutate original
    replay_event_data = {
        "event_id": f"{event_id}_replay_{attempt_count}",
        "source": str(queue_record.get("source", "") or ""),
        "event_type": str(queue_record.get("event_type", "") or ""),
        "payload": dict(queue_record.get("payload") or {}),
        "received_at": utc_now(),
        "metadata": {
            "replay": True,
            "replay_of": event_id,
            "replay_attempt": attempt_count,
            "replayed_by": replayed_by,
            "replay_reason": reason,
        },
    }

    errors: list[str] = []
    replay_frame_id: str | None = None
    new_status: str = STATUS_REPLAY_FAILED

    try:
        result = intake_and_run_event(
            replay_event_data,
            runtime_data_dir=runtime_data_dir,
            manifest_dir=manifest_dir,
        )
        replay_frame_id = result.get("frame_id")
        errors = list(result.get("errors") or [])
        if result.get("ok"):
            new_status = STATUS_REPLAYED_DRY_RUN
        else:
            new_status = STATUS_REPLAY_FAILED
            if not errors:
                errors = [str(result.get("status", "REPLAY_FAILED"))]
    except Exception as exc:
        errors = [str(exc)]
        new_status = STATUS_REPLAY_FAILED

    # Update replay history in metadata
    replay_history = list(queue_record.get("metadata", {}).get("replay_history") or [])
    replay_history.append({
        "attempt": attempt_count,
        "replay_frame_id": replay_frame_id,
        "replayed_by": replayed_by,
        "reason": reason,
        "status": new_status,
        "replayed_at": utc_now(),
    })

    updated = update_queue_record(
        queue_record,
        status=new_status,
        attempt_count=attempt_count,
        last_replay_frame_id=replay_frame_id,
        errors=errors,
        metadata={"replay_history": replay_history},
    )
    write_queue_record(updated, runtime_data_dir)

    return {
        "ok": new_status == STATUS_REPLAYED_DRY_RUN,
        "event_id": event_id,
        "original_frame_id": original_frame_id,
        "replay_frame_id": replay_frame_id,
        "route_id": queue_record.get("route_id"),
        "manifest_id": queue_record.get("manifest_id"),
        "status": new_status,
        "errors": errors,
    }
