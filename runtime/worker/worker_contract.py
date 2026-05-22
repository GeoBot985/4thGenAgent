"""Spec 140 — Worker contract: canonical config/state schemas and validation."""
from __future__ import annotations

from typing import Any

WORKER_MODES = {"run_once", "bounded_loop"}

WORKER_STATUSES = {
    "STOPPED",
    "STARTING",
    "RUNNING",
    "IDLE",
    "FAILED",
    "LOCKED",
    "STOPPING",
}

FAILURE_CODES = {
    "worker_lock_conflict",
    "worker_lock_stale",
    "persistence_unavailable",
    "queue_recovery_failed",
    "scheduler_tick_failed",
    "event_source_poll_failed",
    "queue_processing_failed",
    "cycle_timeout",
    "stop_requested",
    "unexpected_exception",
}

DEFAULT_WORKER_CONFIG: dict[str, Any] = {
    "worker_id": "local-worker-1",
    "enabled": True,
    "mode": "run_once",
    "runtime_data_dir": "runtime_data",
    "cycle": {
        "max_cycles": 1,
        "sleep_seconds": 5,
        "max_runtime_seconds": 300,
    },
    "features": {
        "recover_stale_queue": True,
        "run_scheduler_tick": True,
        "poll_event_sources": True,
        "process_queue": True,
    },
    "limits": {
        "max_sources_per_cycle": 10,
        "max_queue_items_per_cycle": 10,
        "max_schedule_events_per_tick": 10,
    },
    "safety": {
        "dry_run_only": True,
        "allow_live_side_effects": False,
        "require_queue_for_execution": True,
    },
}


def validate_worker_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate a worker config dict. Returns {ok, errors}."""
    errors: list[str] = []

    if not isinstance(config, dict):
        return {"ok": False, "errors": ["config must be a dict"]}

    worker_id = config.get("worker_id")
    if not worker_id or not isinstance(worker_id, str):
        errors.append("worker_id must be a non-empty string")

    mode = config.get("mode", "run_once")
    if mode not in WORKER_MODES:
        errors.append(f"mode must be one of: {sorted(WORKER_MODES)}")

    cycle = config.get("cycle", {})
    if not isinstance(cycle, dict):
        errors.append("cycle must be a dict")
    else:
        max_cycles = cycle.get("max_cycles", 1)
        if not isinstance(max_cycles, int) or max_cycles < 1:
            errors.append("cycle.max_cycles must be a positive integer")
        sleep_sec = cycle.get("sleep_seconds", 5)
        if not isinstance(sleep_sec, (int, float)) or sleep_sec < 0:
            errors.append("cycle.sleep_seconds must be >= 0")
        max_rt = cycle.get("max_runtime_seconds", 300)
        if not isinstance(max_rt, (int, float)) or max_rt < 1:
            errors.append("cycle.max_runtime_seconds must be >= 1")

    safety = config.get("safety", {})
    if not isinstance(safety, dict):
        errors.append("safety must be a dict")
    else:
        if safety.get("allow_live_side_effects"):
            errors.append(
                "safety.allow_live_side_effects must be false — "
                "live side effects are not permitted in worker v1"
            )
        if not safety.get("dry_run_only", True):
            errors.append("safety.dry_run_only must be true")

    limits = config.get("limits", {})
    if not isinstance(limits, dict):
        errors.append("limits must be a dict")
    else:
        for key in ("max_sources_per_cycle", "max_queue_items_per_cycle"):
            val = limits.get(key)
            if val is not None and (not isinstance(val, int) or val < 1):
                errors.append(f"limits.{key} must be a positive integer")

    return {"ok": len(errors) == 0, "errors": errors}


def validate_worker_state(state: dict[str, Any]) -> dict[str, Any]:
    """Validate a worker state dict. Returns {ok, errors}."""
    errors: list[str] = []

    if not isinstance(state, dict):
        return {"ok": False, "errors": ["state must be a dict"]}

    status = state.get("status", "")
    if status not in WORKER_STATUSES:
        errors.append(f"status must be one of: {sorted(WORKER_STATUSES)}")

    return {"ok": len(errors) == 0, "errors": errors}


def build_empty_worker_state(worker_id: str) -> dict[str, Any]:
    return {
        "worker_id": worker_id,
        "status": "STOPPED",
        "pid": 0,
        "lock_id": "",
        "started_at": "",
        "last_heartbeat_at": "",
        "last_cycle_started_at": "",
        "last_cycle_completed_at": "",
        "cycle_count": 0,
        "last_cycle_summary": {},
        "last_error": "",
        "updated_at": "",
    }


def build_empty_cycle_summary(worker_id: str, cycle_id: str) -> dict[str, Any]:
    return {
        "ok": True,
        "worker_id": worker_id,
        "cycle_id": cycle_id,
        "started_at": "",
        "completed_at": "",
        "duration_ms": 0,
        "stale_queue_recovered": 0,
        "schedule_events_enqueued": 0,
        "event_sources_polled": 0,
        "source_events_enqueued": 0,
        "queue_items_processed": 0,
        "queue_items_completed": 0,
        "queue_items_failed": 0,
        "dead_letter_count": 0,
        "warnings": [],
        "errors": [],
    }
