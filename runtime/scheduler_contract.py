"""Spec 138 — Scheduler subsystem canonical record, constants, and helpers."""
from __future__ import annotations

import re
import uuid
from typing import Any

from .taskframe import utc_now

# ---------------------------------------------------------------------------
# Schedule type constants
# ---------------------------------------------------------------------------

TYPE_DAILY = "daily"
TYPE_INTERVAL = "interval"
TYPE_WEEKLY = "weekly"
TYPE_CRON = "cron"

VALID_SCHEDULE_TYPES: frozenset[str] = frozenset({
    TYPE_DAILY,
    TYPE_INTERVAL,
    TYPE_WEEKLY,
    TYPE_CRON,
})

# ---------------------------------------------------------------------------
# Misfire mode constants
# ---------------------------------------------------------------------------

MISFIRE_SKIP = "skip"
MISFIRE_ENQUEUE_LATEST = "enqueue_latest"
MISFIRE_ENQUEUE_ALL = "enqueue_all"

VALID_MISFIRE_MODES: frozenset[str] = frozenset({
    MISFIRE_SKIP,
    MISFIRE_ENQUEUE_LATEST,
    MISFIRE_ENQUEUE_ALL,
})

# ---------------------------------------------------------------------------
# Schedule run status constants
# ---------------------------------------------------------------------------

RUN_STATUS_ENQUEUED = "enqueued"
RUN_STATUS_SKIPPED = "skipped"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_DUPLICATE = "duplicate"

# ---------------------------------------------------------------------------
# Day-of-week constants for weekly schedules
# ---------------------------------------------------------------------------

DAYS_OF_WEEK = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

# ---------------------------------------------------------------------------
# Failure category constants
# ---------------------------------------------------------------------------

FAILURE_INVALID_SCHEDULE = "invalid_schedule"
FAILURE_MANIFEST_NOT_FOUND = "manifest_not_found"
FAILURE_EVENT_ROUTE_MISSING = "event_route_missing"
FAILURE_QUEUE_ENQUEUE_FAILED = "queue_enqueue_failed"
FAILURE_DUPLICATE_SKIPPED = "duplicate_skipped"
FAILURE_DISABLED_SCHEDULE = "disabled_schedule"
FAILURE_MISFIRE_LIMIT_EXCEEDED = "misfire_limit_exceeded"
FAILURE_PERSISTENCE_ERROR = "persistence_error"

# ---------------------------------------------------------------------------
# Schedule record builder
# ---------------------------------------------------------------------------


def build_schedule_record(
    schedule_id: str,
    name: str,
    event_type: str,
    schedule_type: str,
    *,
    enabled: bool = True,
    misfire_mode: str = MISFIRE_SKIP,
    timezone: str = "UTC",
    time_of_day: str = "",
    interval_minutes: int = 0,
    day_of_week: str = "",
    payload_template: dict[str, Any] | None = None,
    max_catchup_windows: int = 3,
    priority: int = 100,
    description: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Build a canonical schedule record."""
    now = utc_now()
    if not schedule_id:
        schedule_id = str(uuid.uuid4())
    return {
        "schedule_id": schedule_id,
        "name": name,
        "description": description,
        "event_type": event_type,
        "schedule_type": schedule_type,
        "enabled": bool(enabled),
        "misfire_mode": misfire_mode,
        "timezone": timezone,
        "time_of_day": time_of_day,
        "interval_minutes": int(interval_minutes),
        "day_of_week": day_of_week,
        "payload_template": dict(payload_template or {}),
        "max_catchup_windows": int(max_catchup_windows),
        "priority": int(priority),
        "tags": list(tags or []),
        "last_scheduled_for": "",
        "last_run_at": "",
        "last_run_status": "",
        "created_at": now,
        "updated_at": now,
        "schema_version": 1,
        "runtime_version": 1,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")


def validate_schedule(record: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return (ok, errors) for a schedule record."""
    errors: list[str] = []

    if not str(record.get("schedule_id", "") or "").strip():
        errors.append("schedule_id is required")
    if not str(record.get("name", "") or "").strip():
        errors.append("name is required")
    if not str(record.get("event_type", "") or "").strip():
        errors.append("event_type is required")

    stype = str(record.get("schedule_type", "") or "")
    if stype not in VALID_SCHEDULE_TYPES:
        errors.append(f"schedule_type must be one of {sorted(VALID_SCHEDULE_TYPES)}, got {stype!r}")

    misfire = str(record.get("misfire_mode", "") or "")
    if misfire not in VALID_MISFIRE_MODES:
        errors.append(f"misfire_mode must be one of {sorted(VALID_MISFIRE_MODES)}, got {misfire!r}")

    if stype in (TYPE_DAILY, TYPE_WEEKLY):
        tod = str(record.get("time_of_day", "") or "")
        if not _TIME_RE.match(tod):
            errors.append(f"time_of_day must be HH:MM or HH:MM:SS for {stype} schedules, got {tod!r}")

    if stype == TYPE_WEEKLY:
        dow = str(record.get("day_of_week", "") or "").lower()
        if dow not in DAYS_OF_WEEK:
            errors.append(f"day_of_week must be one of {DAYS_OF_WEEK}, got {dow!r}")

    if stype == TYPE_INTERVAL:
        interval = int(record.get("interval_minutes", 0) or 0)
        if interval <= 0:
            errors.append("interval_minutes must be > 0 for interval schedules")

    max_catchup = int(record.get("max_catchup_windows", 0) or 0)
    if max_catchup < 0:
        errors.append("max_catchup_windows must be >= 0")

    return (len(errors) == 0, errors)


# ---------------------------------------------------------------------------
# Scheduled event builder
# ---------------------------------------------------------------------------


def build_scheduled_event(schedule: dict[str, Any], scheduled_for: str) -> dict[str, Any]:
    """Build the standard event dict for a scheduled firing.

    scheduled_for: ISO-8601 UTC string representing the nominal fire time.
    event_id format: evt_sched_{schedule_id}_{yyyymmddTHHMMSS}
    """
    schedule_id = str(schedule.get("schedule_id", "") or "")
    event_type = str(schedule.get("event_type", "") or "")
    payload_template = dict(schedule.get("payload_template") or {})

    compact_ts = scheduled_for.replace("-", "").replace(":", "").replace("Z", "").replace(" ", "T")
    if "." in compact_ts:
        compact_ts = compact_ts.split(".")[0]
    event_id = f"evt_sched_{schedule_id}_{compact_ts}"

    payload = dict(payload_template)
    payload["schedule_id"] = schedule_id
    payload["scheduled_for"] = scheduled_for

    return {
        "event_id": event_id,
        "source": "schedule",
        "event_type": event_type,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Schedule run record builder
# ---------------------------------------------------------------------------


def build_schedule_run_record(
    schedule_id: str,
    scheduled_for: str,
    *,
    status: str = RUN_STATUS_ENQUEUED,
    queue_id: str = "",
    failure_reason: str = "",
) -> dict[str, Any]:
    """Build a canonical schedule run record."""
    now = utc_now()
    return {
        "run_id": str(uuid.uuid4()),
        "schedule_id": schedule_id,
        "scheduled_for": scheduled_for,
        "status": status,
        "queue_id": queue_id,
        "failure_reason": failure_reason,
        "created_at": now,
    }
