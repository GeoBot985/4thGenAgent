"""Spec 140 — Worker engine: coordinated run-once and bounded-loop cycle."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .worker_contract import build_empty_cycle_summary, build_empty_worker_state
from .worker_lock import (
    acquire_worker_lock,
    clear_stale_lock,
    detect_stale_lock,
    is_worker_locked,
    release_worker_lock,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ms_now() -> float:
    return time.monotonic() * 1000


def _worker_dir(runtime_data_dir: str | Path) -> Path:
    return Path(runtime_data_dir) / "worker"


def _state_path(runtime_data_dir: str | Path) -> Path:
    return _worker_dir(runtime_data_dir) / "state.json"


def _cycles_path(runtime_data_dir: str | Path) -> Path:
    return _worker_dir(runtime_data_dir) / "cycles.jsonl"


def _stop_request_path(runtime_data_dir: str | Path) -> Path:
    return _worker_dir(runtime_data_dir) / "stop.request.json"


def _ensure_worker_dir(runtime_data_dir: str | Path) -> None:
    _worker_dir(runtime_data_dir).mkdir(parents=True, exist_ok=True)


# ─── State helpers ───────────────────────────────────────────────────────────

def _read_state(runtime_data_dir: str | Path) -> dict[str, Any]:
    path = _state_path(runtime_data_dir)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_state(state: dict[str, Any], runtime_data_dir: str | Path) -> None:
    _ensure_worker_dir(runtime_data_dir)
    _state_path(runtime_data_dir).write_text(
        json.dumps({**state, "updated_at": _utc_now()}, indent=2),
        encoding="utf-8",
    )


def _append_cycle(summary: dict[str, Any], runtime_data_dir: str | Path) -> None:
    _ensure_worker_dir(runtime_data_dir)
    with _cycles_path(runtime_data_dir).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, ensure_ascii=False) + "\n")


def _read_recent_cycles(
    runtime_data_dir: str | Path,
    limit: int = 10,
) -> list[dict[str, Any]]:
    path = _cycles_path(runtime_data_dir)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        results: list[dict[str, Any]] = []
        for line in reversed(lines):
            try:
                results.append(json.loads(line))
                if len(results) >= limit:
                    break
            except Exception:
                pass
        return results
    except Exception:
        return []


def _read_stop_request(runtime_data_dir: str | Path) -> dict[str, Any] | None:
    path = _stop_request_path(runtime_data_dir)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _clear_stop_request(runtime_data_dir: str | Path) -> None:
    _stop_request_path(runtime_data_dir).unlink(missing_ok=True)


# ─── Single cycle ─────────────────────────────────────────────────────────────

def run_worker_once(
    config: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Execute exactly one bounded worker cycle.

    Cycle order: lock → heartbeat → stale-recovery → scheduler-tick →
    event-source-poll → queue-process → cycle-summary → heartbeat → unlock.

    Returns the cycle summary dict.
    """
    _ensure_worker_dir(runtime_data_dir)
    worker_id = str(config.get("worker_id") or "local-worker-1")
    features = config.get("features") or {}
    limits = config.get("limits") or {}
    safety = config.get("safety") or {}
    frame_metadata = dict(config.get("frame_metadata") or {})

    # ── Acquire lock ──────────────────────────────────────────────────────
    lock_result = acquire_worker_lock(worker_id, runtime_data_dir)
    if not lock_result.get("ok"):
        return {
            "ok": False,
            "worker_id": worker_id,
            "error": lock_result.get("error", "worker_lock_conflict"),
            "message": lock_result.get("message", "Could not acquire worker lock"),
        }
    lock_id: str = lock_result["lock_id"]

    # ── Initialise state ──────────────────────────────────────────────────
    state = _read_state(runtime_data_dir) or build_empty_worker_state(worker_id)
    state.update(
        {
            "worker_id": worker_id,
            "status": "STARTING",
            "pid": os.getpid(),
            "lock_id": lock_id,
            "started_at": state.get("started_at") or _utc_now(),
            "last_heartbeat_at": _utc_now(),
        }
    )
    _write_state(state, runtime_data_dir)

    # ── Build cycle ID / summary ──────────────────────────────────────────
    now_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    cycle_count = int(state.get("cycle_count") or 0) + 1
    cycle_id = f"cycle_{now_tag}_{cycle_count}"
    summary = build_empty_cycle_summary(worker_id, cycle_id)
    summary["started_at"] = _utc_now()
    t0 = _ms_now()

    state.update(
        {"status": "RUNNING", "last_cycle_started_at": summary["started_at"], "last_heartbeat_at": _utc_now()}
    )
    _write_state(state, runtime_data_dir)

    # ── Stage 1: recover stale queue items ────────────────────────────────
    if features.get("recover_stale_queue", True):
        try:
            from runtime.event_queue import recover_stale_queue_items

            recovered = recover_stale_queue_items(runtime_data_dir=runtime_data_dir)
            summary["stale_queue_recovered"] = len(recovered.get("recovered") or [])
        except Exception as exc:
            summary["warnings"].append(f"stale_recovery: {exc}")

    # ── Stage 2: scheduler tick ───────────────────────────────────────────
    if features.get("run_scheduler_tick", True):
        try:
            from runtime.scheduler_engine import run_scheduler_tick

            tick = run_scheduler_tick(runtime_data_dir=runtime_data_dir, dry_run=True)
            summary["schedule_events_enqueued"] = int(tick.get("enqueued") or 0)
        except Exception as exc:
            summary["warnings"].append(f"scheduler_tick: {exc}")

    # ── Stage 3: poll event sources ───────────────────────────────────────
    if features.get("poll_event_sources", True):
        try:
            from runtime.event_sources.polling_engine import poll_enabled_event_sources

            max_src = int(limits.get("max_sources_per_cycle") or 10)
            poll = poll_enabled_event_sources(
                runtime_data_dir=runtime_data_dir, limit=max_src
            )
            summary["event_sources_polled"] = int(poll.get("polled") or 0)
            summary["source_events_enqueued"] = int(poll.get("enqueued_total") or 0)
        except Exception as exc:
            summary["warnings"].append(f"event_source_poll: {exc}")

    # ── Stage 4: process queue batch ─────────────────────────────────────
    if features.get("process_queue", True) and not safety.get("allow_live_side_effects", False):
        try:
            from runtime.event_queue_runner import process_queued_events

            max_items = int(limits.get("max_queue_items_per_cycle") or 10)
            batch = process_queued_events(
                limit=max_items,
                runtime_data_dir=runtime_data_dir,
                worker_id=worker_id,
                frame_metadata=frame_metadata or None,
            )
            summary["queue_items_processed"] = int(batch.get("processed") or 0)
            summary["queue_items_completed"] = int(batch.get("completed") or 0)
            summary["queue_items_failed"] = int(batch.get("failed") or 0)
        except Exception as exc:
            summary["errors"].append(f"queue_processing: {exc}")

    # ── Finalise summary ──────────────────────────────────────────────────
    summary["completed_at"] = _utc_now()
    summary["duration_ms"] = int(_ms_now() - t0)
    summary["ok"] = len(summary["errors"]) == 0

    try:
        from runtime.event_queue import queue_health

        qh = queue_health(runtime_data_dir=runtime_data_dir)
        summary["dead_letter_count"] = int(qh.get("dead_letter_count") or 0)
    except Exception:
        pass

    _append_cycle(summary, runtime_data_dir)

    # ── Update state ──────────────────────────────────────────────────────
    final_status = "IDLE" if summary["ok"] else "FAILED"
    state.update(
        {
            "status": final_status,
            "cycle_count": cycle_count,
            "last_cycle_completed_at": summary["completed_at"],
            "last_cycle_summary": summary,
            "last_heartbeat_at": _utc_now(),
            "last_error": summary["errors"][-1] if summary["errors"] else "",
        }
    )
    _write_state(state, runtime_data_dir)

    # ── Release lock ──────────────────────────────────────────────────────
    release_worker_lock(lock_id, runtime_data_dir)
    state["lock_id"] = ""
    _write_state(state, runtime_data_dir)

    return summary


# ─── Bounded loop ────────────────────────────────────────────────────────────

def run_worker_loop(
    config: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Run a bounded worker loop.

    Respects max_cycles, sleep_seconds, max_runtime_seconds, and stop requests.
    Never runs indefinitely.
    """
    cycle_cfg = config.get("cycle") or {}
    _mc = cycle_cfg.get("max_cycles")
    max_cycles = int(_mc if _mc is not None else 1)
    _ss = cycle_cfg.get("sleep_seconds")
    sleep_seconds = float(_ss if _ss is not None else 5)
    _mr = cycle_cfg.get("max_runtime_seconds")
    max_runtime_seconds = float(_mr if _mr is not None else 300)
    worker_id = str(config.get("worker_id") or "local-worker-1")

    t_start = time.monotonic()
    cycles_run = 0
    summaries: list[dict[str, Any]] = []
    stopped_early = False
    stop_reason = ""

    for i in range(max_cycles):
        # Check stop request before each cycle
        stop_req = _read_stop_request(runtime_data_dir)
        if stop_req:
            stopped_early = True
            stop_reason = stop_req.get("reason") or "stop_requested"
            _clear_stop_request(runtime_data_dir)
            # Update state to reflect graceful stop
            state = _read_state(runtime_data_dir) or build_empty_worker_state(worker_id)
            state.update({"status": "STOPPED", "last_heartbeat_at": _utc_now()})
            _write_state(state, runtime_data_dir)
            break

        # Check max runtime
        elapsed = time.monotonic() - t_start
        if elapsed >= max_runtime_seconds:
            stopped_early = True
            stop_reason = "cycle_timeout"
            break

        summary = run_worker_once(config, runtime_data_dir)
        summaries.append(summary)
        cycles_run += 1

        # Sleep between cycles (skip after the last cycle)
        if i < max_cycles - 1:
            elapsed = time.monotonic() - t_start
            remaining = max_runtime_seconds - elapsed
            actual_sleep = min(sleep_seconds, max(0.0, remaining))
            if actual_sleep > 0:
                time.sleep(actual_sleep)

    return {
        "ok": all(s.get("ok") for s in summaries) if summaries else True,
        "worker_id": worker_id,
        "cycles_run": cycles_run,
        "max_cycles": max_cycles,
        "stopped_early": stopped_early,
        "stop_reason": stop_reason,
        "summaries": summaries,
    }


# ─── Status / health ─────────────────────────────────────────────────────────

def build_worker_status(
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Return current worker status including lock state and last cycle."""
    state = _read_state(runtime_data_dir) or {}
    lock_info = is_worker_locked(runtime_data_dir)
    recent = _read_recent_cycles(runtime_data_dir, limit=1)
    hardening = _safe_worker_hardening(runtime_data_dir)

    return {
        "ok": True,
        "worker_id": state.get("worker_id", ""),
        "status": state.get("status", "STOPPED"),
        "pid": state.get("pid", 0),
        "lock_id": state.get("lock_id", ""),
        "locked": lock_info.get("locked", False),
        "started_at": state.get("started_at", ""),
        "last_heartbeat_at": state.get("last_heartbeat_at", ""),
        "last_cycle_started_at": state.get("last_cycle_started_at", ""),
        "last_cycle_completed_at": state.get("last_cycle_completed_at", ""),
        "cycle_count": state.get("cycle_count", 0),
        "last_cycle_summary": state.get("last_cycle_summary", {}),
        "last_error": state.get("last_error", ""),
        "last_cycle": recent[0] if recent else {},
        "hardening": {
            "ok": bool(hardening.get("ok", False)),
            "classification": str(hardening.get("classification", "BLOCKED")),
            "anomalies": list(hardening.get("anomalies", [])),
            "recommendations": list(hardening.get("recommendations", [])),
        },
    }


def build_worker_health(
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Run availability checks on all worker dependencies."""
    checks: dict[str, bool] = {}
    warnings: list[str] = []
    hardening = _safe_worker_hardening(runtime_data_dir)

    # Persistence backend
    try:
        from runtime.persistence_backends.backend_factory import get_persistence_backend

        backend = get_persistence_backend(runtime_data_dir)
        h = backend.health()
        checks["persistence_backend"] = bool(h.get("ok"))
        if not h.get("ok"):
            warnings.append(f"persistence backend unhealthy: {h.get('error', '')}")
    except Exception as exc:
        checks["persistence_backend"] = False
        warnings.append(f"persistence_backend unavailable: {exc}")

    # Queue
    try:
        from runtime.event_queue import queue_health

        qh = queue_health(runtime_data_dir=runtime_data_dir)
        checks["queue"] = bool(qh.get("ok"))
    except Exception as exc:
        checks["queue"] = False
        warnings.append(f"queue unavailable: {exc}")

    # Scheduler
    try:
        from runtime.scheduler_store import list_schedules

        list_schedules(runtime_data_dir=runtime_data_dir)
        checks["scheduler"] = True
    except Exception as exc:
        checks["scheduler"] = False
        warnings.append(f"scheduler unavailable: {exc}")

    # Event sources
    try:
        from runtime.event_sources.event_source_state import list_event_sources

        list_event_sources(runtime_data_dir=runtime_data_dir)
        checks["event_sources"] = True
    except Exception as exc:
        checks["event_sources"] = False
        warnings.append(f"event_sources unavailable: {exc}")

    # Lock state
    stale = detect_stale_lock(runtime_data_dir)
    checks["lock_valid"] = not stale.get("stale", False)
    if stale.get("stale"):
        warnings.append("stale lock detected — run 'taskframe worker clear-stale-lock'")

    hardening_profile = str(hardening.get("profile", "") or "")
    checks["service_ready"] = bool(hardening.get("service_ready", True))
    checks["soak_ready"] = bool(hardening.get("soak_ready", True))
    checks["worker_identity_present"] = bool(hardening.get("worker_identity_present", True)) if hardening_profile == "service" else True

    return {
        "ok": all(checks.values()),
        "checks": checks,
        "warnings": warnings,
        "soak_ready": bool(hardening.get("soak_ready", False)),
        "service_ready": bool(hardening.get("service_ready", False)),
        "hardening_checks": dict(hardening.get("hardening_checks", {})),
        "blockers": list(hardening.get("blockers", [])),
        "hardening": {
            "ok": bool(hardening.get("ok", False)),
            "classification": str(hardening.get("classification", "BLOCKED")),
            "anomalies": list(hardening.get("anomalies", [])),
            "recommendations": list(hardening.get("recommendations", [])),
        },
    }


# ─── Control ──────────────────────────────────────────────────────────────────

def request_worker_stop(
    worker_id: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Write a stop-request file. The running loop will honour it after the current cycle."""
    _ensure_worker_dir(runtime_data_dir)
    stop_req = {
        "worker_id": worker_id,
        "requested_at": _utc_now(),
        "requested_by": "operator",
        "reason": "manual_stop",
    }
    _stop_request_path(runtime_data_dir).write_text(
        json.dumps(stop_req, indent=2), encoding="utf-8"
    )

    state = _read_state(runtime_data_dir) or {}
    if state.get("status") in ("RUNNING", "IDLE", "STARTING"):
        state["status"] = "STOPPING"
        _write_state(state, runtime_data_dir)

    return {"ok": True, "stop_request": stop_req}


def clear_stale_worker_lock(
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Clear a stale worker lock. Safe — refuses to touch a live lock."""
    return clear_stale_lock(runtime_data_dir)


def _safe_worker_hardening(runtime_data_dir: str | Path) -> dict[str, Any]:
    try:
        from runtime.worker.worker_hardening import build_worker_hardening_status

        return build_worker_hardening_status(runtime_data_dir=runtime_data_dir)
    except Exception as exc:
        return {
            "ok": False,
            "classification": "BLOCKED",
            "anomalies": [{"id": "hardening_unavailable", "severity": "error", "message": str(exc)}],
            "recommendations": ["Inspect the worker hardening module error before retrying."],
            "service_ready": False,
            "soak_ready": False,
            "hardening_checks": {"hardening_unavailable": False},
            "blockers": [{"id": "hardening_unavailable", "message": str(exc)}],
        }
