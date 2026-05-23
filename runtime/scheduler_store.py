"""Spec 138 — Scheduler store: CRUD operations for schedule records."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .scheduler_contract import (
    MISFIRE_SKIP,
    TYPE_DAILY,
    build_schedule_record,
    build_schedule_run_record,
    validate_schedule,
)
from .taskframe import utc_now


def _get_backend(runtime_data_dir: Path | str):
    """Return the appropriate persistence backend."""
    from runtime.persistence_backends.filesystem_backend import FilesystemPersistenceBackend
    return FilesystemPersistenceBackend(runtime_data_dir=runtime_data_dir)


# ---------------------------------------------------------------------------
# Schedule CRUD
# ---------------------------------------------------------------------------


def create_schedule(
    schedule_id: str,
    name: str,
    event_type: str,
    schedule_type: str = TYPE_DAILY,
    *,
    runtime_data_dir: Path | str = "runtime_data",
    **kwargs: Any,
) -> dict[str, Any]:
    """Create and persist a new schedule. Returns {ok, schedule_id, record} or {ok: False, error}."""
    record = build_schedule_record(
        schedule_id=schedule_id,
        name=name,
        event_type=event_type,
        schedule_type=schedule_type,
        **kwargs,
    )
    ok, errors = validate_schedule(record)
    if not ok:
        return {"ok": False, "error": "; ".join(errors)}

    backend = _get_backend(runtime_data_dir)
    existing = backend.get_schedule_record(schedule_id)
    if existing:
        return {"ok": False, "error": f"Schedule {schedule_id!r} already exists"}

    backend.save_schedule_record(record)
    return {"ok": True, "schedule_id": schedule_id, "record": record}


def get_schedule(schedule_id: str, *, runtime_data_dir: Path | str = "runtime_data") -> dict[str, Any] | None:
    """Return the schedule record or None."""
    return _get_backend(runtime_data_dir).get_schedule_record(schedule_id)


def list_schedules(
    *,
    enabled_only: bool = False,
    runtime_data_dir: Path | str = "runtime_data",
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List all schedules, optionally filtered to enabled ones."""
    backend = _get_backend(runtime_data_dir)
    filters: dict[str, Any] = {}
    if enabled_only:
        filters["enabled"] = True
    return backend.list_schedule_records(limit=limit, **filters)


def update_schedule(
    schedule_id: str,
    *,
    runtime_data_dir: Path | str = "runtime_data",
    **updates: Any,
) -> dict[str, Any]:
    """Apply field updates to an existing schedule. Returns {ok, record} or {ok: False, error}."""
    backend = _get_backend(runtime_data_dir)
    existing = backend.get_schedule_record(schedule_id)
    if not existing:
        return {"ok": False, "error": f"Schedule {schedule_id!r} not found"}
    updated = dict(existing)
    updated.update(updates)
    updated["updated_at"] = utc_now()
    updated["runtime_version"] = int(updated.get("runtime_version", 1) or 1) + 1
    ok, errors = validate_schedule(updated)
    if not ok:
        return {"ok": False, "error": "; ".join(errors)}
    backend.save_schedule_record(updated)
    return {"ok": True, "record": updated}


def enable_schedule(schedule_id: str, *, runtime_data_dir: Path | str = "runtime_data") -> dict[str, Any]:
    return update_schedule(schedule_id, enabled=True, runtime_data_dir=runtime_data_dir)


def disable_schedule(schedule_id: str, *, runtime_data_dir: Path | str = "runtime_data") -> dict[str, Any]:
    return update_schedule(schedule_id, enabled=False, runtime_data_dir=runtime_data_dir)


def delete_schedule(schedule_id: str, *, runtime_data_dir: Path | str = "runtime_data") -> dict[str, Any]:
    """Soft-delete: disables and marks deleted_at. Returns {ok}."""
    backend = _get_backend(runtime_data_dir)
    existing = backend.get_schedule_record(schedule_id)
    if not existing:
        return {"ok": False, "error": f"Schedule {schedule_id!r} not found"}
    deleted = dict(existing)
    deleted["enabled"] = False
    deleted["deleted_at"] = utc_now()
    deleted["updated_at"] = utc_now()
    deleted["runtime_version"] = int(deleted.get("runtime_version", 1) or 1) + 1
    backend.save_schedule_record(deleted)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Schedule run log
# ---------------------------------------------------------------------------


def record_schedule_run(
    schedule_id: str,
    scheduled_for: str,
    *,
    status: str,
    queue_id: str = "",
    failure_reason: str = "",
    runtime_data_dir: Path | str = "runtime_data",
) -> dict[str, Any]:
    """Persist a schedule run record and update last_run_* fields on the schedule."""
    run = build_schedule_run_record(
        schedule_id=schedule_id,
        scheduled_for=scheduled_for,
        status=status,
        queue_id=queue_id,
        failure_reason=failure_reason,
    )
    backend = _get_backend(runtime_data_dir)
    backend.save_schedule_run_record(run)

    existing = backend.get_schedule_record(schedule_id)
    if existing:
        updated = dict(existing)
        updated["last_scheduled_for"] = scheduled_for
        updated["last_run_at"] = run["created_at"]
        updated["last_run_status"] = status
        updated["updated_at"] = utc_now()
        updated["runtime_version"] = int(updated.get("runtime_version", 1) or 1) + 1
        backend.save_schedule_record(updated)

    return run


def list_schedule_runs(
    schedule_id: str | None = None,
    *,
    limit: int = 100,
    runtime_data_dir: Path | str = "runtime_data",
) -> list[dict[str, Any]]:
    """List recent schedule run records."""
    backend = _get_backend(runtime_data_dir)
    filters: dict[str, Any] = {}
    if schedule_id:
        filters["schedule_id"] = schedule_id
    return backend.list_schedule_run_records(limit=limit, **filters)


# ---------------------------------------------------------------------------
# Fixture loader
# ---------------------------------------------------------------------------


def load_schedule_fixture(fixture_path: str | Path, *, runtime_data_dir: Path | str = "runtime_data") -> dict[str, Any]:
    """Load a schedule fixture JSON file and persist it. Returns {ok, schedule_id} or {ok: False, error}."""
    import json
    path = Path(fixture_path)
    if not path.is_file():
        return {"ok": False, "error": f"Fixture not found: {path}"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "error": f"Failed to read fixture: {exc}"}
    if not isinstance(data, dict):
        return {"ok": False, "error": "Fixture must be a JSON object"}

    schedule_id = str(data.get("schedule_id", "") or "")
    if not schedule_id:
        return {"ok": False, "error": "Fixture missing schedule_id"}

    backend = _get_backend(runtime_data_dir)
    existing = backend.get_schedule_record(schedule_id)
    record = build_schedule_record(
        schedule_id=schedule_id,
        name=str(data.get("name", schedule_id)),
        event_type=str(data.get("event_type", "")),
        schedule_type=str(data.get("schedule_type", TYPE_DAILY)),
        enabled=bool(data.get("enabled", True)),
        misfire_mode=str(data.get("misfire_mode", MISFIRE_SKIP)),
        timezone=str(data.get("timezone", "UTC")),
        time_of_day=str(data.get("time_of_day", "")),
        interval_minutes=int(data.get("interval_minutes", 0) or 0),
        day_of_week=str(data.get("day_of_week", "")),
        payload_template=dict(data.get("payload_template") or {}),
        max_catchup_windows=int(data.get("max_catchup_windows", 3) or 3),
        priority=int(data.get("priority", 100) or 100),
        description=str(data.get("description", "")),
        tags=list(data.get("tags") or []),
    )
    if existing:
        record["created_at"] = existing.get("created_at", record["created_at"])

    ok, errors = validate_schedule(record)
    if not ok:
        return {"ok": False, "error": "; ".join(errors)}

    backend.save_schedule_record(record)
    return {"ok": True, "schedule_id": schedule_id, "record": record}
