"""Spec 140 — Operator worker panel data source."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def build_worker_panel(
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Return a panel-ready dict: status, health, last cycle, recent history."""
    from runtime.worker.worker_engine import (
        _read_recent_cycles,
        build_worker_health,
        build_worker_status,
    )

    try:
        status = build_worker_status(runtime_data_dir)
    except Exception as exc:
        status = {"ok": False, "error": str(exc), "status": "STOPPED", "worker_id": ""}

    try:
        health = build_worker_health(runtime_data_dir)
    except Exception as exc:
        health = {"ok": False, "error": str(exc), "checks": {}, "warnings": []}

    try:
        recent_cycles = _read_recent_cycles(runtime_data_dir, limit=5)
    except Exception:
        recent_cycles = []

    last_cycle: dict[str, Any] = (
        status.get("last_cycle_summary")
        or (recent_cycles[0] if recent_cycles else {})
    )

    warnings: list[str] = list(health.get("warnings") or [])

    summary = {
        "status": status.get("status", "STOPPED"),
        "worker_id": status.get("worker_id", ""),
        "last_heartbeat_at": status.get("last_heartbeat_at", ""),
        "last_cycle_completed_at": status.get("last_cycle_completed_at", ""),
        "queue_items_processed": int(last_cycle.get("queue_items_processed") or 0),
        "errors": len(last_cycle.get("errors") or []),
    }

    return {
        "ok": True,
        "summary": summary,
        "worker_state": status,
        "last_cycle": last_cycle,
        "recent_cycles": recent_cycles,
        "health": health,
        "warnings": warnings,
    }
