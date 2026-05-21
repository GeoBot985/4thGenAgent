"""Spec 138 — Scheduler engine: due-time calculation, tick execution, misfire handling."""
from __future__ import annotations

import datetime
from typing import Any

from .scheduler_contract import (
    MISFIRE_ENQUEUE_ALL,
    MISFIRE_ENQUEUE_LATEST,
    MISFIRE_SKIP,
    RUN_STATUS_DUPLICATE,
    RUN_STATUS_ENQUEUED,
    RUN_STATUS_FAILED,
    RUN_STATUS_SKIPPED,
    TYPE_DAILY,
    TYPE_INTERVAL,
    TYPE_WEEKLY,
    build_scheduled_event,
)


# ---------------------------------------------------------------------------
# Due-time calculation
# ---------------------------------------------------------------------------


def calculate_next_due(schedule: dict[str, Any], after: datetime.datetime) -> datetime.datetime | None:
    """Return the next due UTC datetime after *after*, or None if not calculable."""
    stype = str(schedule.get("schedule_type", "") or "")
    if stype == TYPE_INTERVAL:
        interval_minutes = int(schedule.get("interval_minutes", 0) or 0)
        if interval_minutes <= 0:
            return None
        return after + datetime.timedelta(minutes=interval_minutes)

    if stype in (TYPE_DAILY, TYPE_WEEKLY):
        tod_str = str(schedule.get("time_of_day", "") or "")
        try:
            parts = tod_str.split(":")
            hour, minute = int(parts[0]), int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
        except (IndexError, ValueError):
            return None

        tz_name = str(schedule.get("timezone", "UTC") or "UTC")
        try:
            tz = _get_timezone(tz_name)
        except Exception:
            return None

        after_utc = after.replace(tzinfo=datetime.timezone.utc) if after.tzinfo is None else after.astimezone(datetime.timezone.utc)
        after_local = after_utc.astimezone(tz)
        candidate_date = after_local.date()

        for days_ahead in range(0, 8):
            check_date = candidate_date + datetime.timedelta(days=days_ahead)
            if stype == TYPE_WEEKLY:
                day_of_week = str(schedule.get("day_of_week", "") or "").lower()
                day_index = _DOW_INDEX.get(day_of_week)
                if day_index is None:
                    return None
                if check_date.weekday() != day_index:
                    continue
            candidate_local = tz.localize(
                datetime.datetime(check_date.year, check_date.month, check_date.day, hour, minute, second)
            ) if hasattr(tz, "localize") else datetime.datetime(
                check_date.year, check_date.month, check_date.day, hour, minute, second, tzinfo=tz
            )
            candidate_utc = candidate_local.astimezone(datetime.timezone.utc)
            if candidate_utc > after_utc:
                return candidate_utc.replace(tzinfo=datetime.timezone.utc)

    return None


_DOW_INDEX = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _get_timezone(tz_name: str) -> Any:
    if tz_name in ("UTC", "utc", ""):
        return datetime.timezone.utc
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(tz_name)
    except Exception:
        pass
    try:
        import pytz
        return pytz.timezone(tz_name)
    except Exception:
        pass
    return datetime.timezone.utc


# ---------------------------------------------------------------------------
# Missed windows calculation
# ---------------------------------------------------------------------------


def get_missed_windows(
    schedule: dict[str, Any],
    since: datetime.datetime,
    until: datetime.datetime,
) -> list[datetime.datetime]:
    """Return all nominal fire times for *schedule* in the half-open interval (since, until]."""
    windows: list[datetime.datetime] = []
    cursor = since
    for _ in range(1000):
        next_due = calculate_next_due(schedule, cursor)
        if next_due is None:
            break
        if next_due > until:
            break
        windows.append(next_due)
        cursor = next_due
    return windows


# ---------------------------------------------------------------------------
# Find due schedules
# ---------------------------------------------------------------------------


def find_due_schedules(
    schedules: list[dict[str, Any]],
    *,
    now: datetime.datetime | None = None,
) -> list[tuple[dict[str, Any], list[datetime.datetime]]]:
    """Return [(schedule, [missed_windows])] for each enabled schedule that is due."""
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    due: list[tuple[dict[str, Any], list[datetime.datetime]]] = []
    for schedule in schedules:
        if not schedule.get("enabled"):
            continue
        last_for = str(schedule.get("last_scheduled_for", "") or "")
        if last_for:
            try:
                since = datetime.datetime.fromisoformat(last_for.replace("Z", "+00:00"))
            except ValueError:
                since = now - datetime.timedelta(days=1)
        else:
            since = _default_since(schedule, now)

        missed = get_missed_windows(schedule, since, now)
        if missed:
            due.append((schedule, missed))
    return due


def _default_since(schedule: dict[str, Any], now: datetime.datetime) -> datetime.datetime:
    stype = str(schedule.get("schedule_type", "") or "")
    if stype == TYPE_INTERVAL:
        interval_minutes = int(schedule.get("interval_minutes", 0) or 0)
        if interval_minutes > 0:
            return now - datetime.timedelta(minutes=interval_minutes)
    return now - datetime.timedelta(hours=24)


# ---------------------------------------------------------------------------
# Tick execution
# ---------------------------------------------------------------------------


def run_scheduler_tick(
    *,
    runtime_data_dir: str | None = None,
    now: datetime.datetime | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Execute one scheduler tick — always dry_run=True per spec.

    Returns {ok, schedules_checked, windows_found, enqueued, skipped, duplicates, failed, results}.
    """
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)

    from pathlib import Path
    from runtime.scheduler_store import list_schedules, record_schedule_run
    from runtime.event_queue import enqueue_event

    data_dir: str | Path = runtime_data_dir or "runtime_data"

    schedules = list_schedules(enabled_only=True, runtime_data_dir=data_dir)
    due_list = find_due_schedules(schedules, now=now)

    results: list[dict[str, Any]] = []
    enqueued = skipped = duplicates = failed = 0

    for schedule, windows in due_list:
        schedule_id = str(schedule.get("schedule_id", "") or "")
        misfire_mode = str(schedule.get("misfire_mode", MISFIRE_SKIP) or MISFIRE_SKIP)
        max_catchup = int(schedule.get("max_catchup_windows", 3) or 3)

        if len(windows) > 1:
            if misfire_mode == MISFIRE_SKIP:
                windows_to_fire = [windows[-1]]
            elif misfire_mode == MISFIRE_ENQUEUE_LATEST:
                windows_to_fire = [windows[-1]]
            else:
                windows_to_fire = windows[-max_catchup:] if max_catchup > 0 else windows
        else:
            windows_to_fire = windows

        for window_dt in windows_to_fire:
            scheduled_for = window_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            event = build_scheduled_event(schedule, scheduled_for)

            if dry_run:
                run_status = RUN_STATUS_ENQUEUED
                queue_id = "DRY_RUN"
                results.append({"schedule_id": schedule_id, "scheduled_for": scheduled_for, "status": run_status, "dry_run": True})
                enqueued += 1
            else:
                try:
                    eq_result = enqueue_event(event, runtime_data_dir=data_dir, priority=int(schedule.get("priority", 100) or 100))
                    if eq_result.get("duplicate"):
                        run_status = RUN_STATUS_DUPLICATE
                        queue_id = str(eq_result.get("existing_queue_id", "") or "")
                        duplicates += 1
                    else:
                        run_status = RUN_STATUS_ENQUEUED
                        queue_id = str(eq_result.get("queue_id", "") or "")
                        enqueued += 1
                except Exception as exc:
                    run_status = RUN_STATUS_FAILED
                    queue_id = ""
                    failed += 1
                    results.append({"schedule_id": schedule_id, "scheduled_for": scheduled_for, "status": run_status, "error": str(exc)})
                    continue

                results.append({"schedule_id": schedule_id, "scheduled_for": scheduled_for, "status": run_status, "queue_id": queue_id})
                record_schedule_run(
                    schedule_id, scheduled_for,
                    status=run_status, queue_id=queue_id,
                    runtime_data_dir=data_dir,
                )

        if misfire_mode == MISFIRE_SKIP and len(windows) > 1:
            skipped += len(windows) - len(windows_to_fire)

    return {
        "ok": True,
        "dry_run": dry_run,
        "schedules_checked": len(schedules),
        "windows_found": sum(len(w) for _, w in due_list),
        "enqueued": enqueued,
        "skipped": skipped,
        "duplicates": duplicates,
        "failed": failed,
        "results": results,
    }
