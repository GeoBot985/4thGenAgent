"""Spec 138 — Operator scheduler panel: read-only summary for the scheduler subsystem."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def build_scheduler_panel(*, runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    """Return a read-only summary of the scheduler subsystem state.

    Never triggers processing. Returns:
      {ok, total_schedules, enabled_count, disabled_count, schedules, recent_runs}
    """
    from runtime.scheduler_store import list_schedules, list_schedule_runs

    try:
        all_schedules = list_schedules(runtime_data_dir=runtime_data_dir)
        enabled = [s for s in all_schedules if s.get("enabled")]
        disabled = [s for s in all_schedules if not s.get("enabled")]

        schedule_summaries = [
            {
                "schedule_id": s.get("schedule_id", ""),
                "name": s.get("name", ""),
                "event_type": s.get("event_type", ""),
                "schedule_type": s.get("schedule_type", ""),
                "enabled": s.get("enabled", False),
                "misfire_mode": s.get("misfire_mode", ""),
                "timezone": s.get("timezone", "UTC"),
                "time_of_day": s.get("time_of_day", ""),
                "interval_minutes": s.get("interval_minutes", 0),
                "last_scheduled_for": s.get("last_scheduled_for", ""),
                "last_run_at": s.get("last_run_at", ""),
                "last_run_status": s.get("last_run_status", ""),
            }
            for s in all_schedules
        ]

        recent_runs = list_schedule_runs(limit=20, runtime_data_dir=runtime_data_dir)

        return {
            "ok": True,
            "total_schedules": len(all_schedules),
            "enabled_count": len(enabled),
            "disabled_count": len(disabled),
            "schedules": schedule_summaries,
            "recent_runs": recent_runs,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "total_schedules": 0, "enabled_count": 0, "disabled_count": 0, "schedules": [], "recent_runs": []}
