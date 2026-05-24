from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from runtime.persistence import ensure_dir
from runtime.worker.worker_contract import build_empty_cycle_summary
from runtime.worker.worker_lock import LOCK_STALE_SECONDS
from runtime.taskframe import utc_now


def _worker_dir(runtime_data_dir: str | Path) -> Path:
    return Path(runtime_data_dir) / "worker"


def _lock_path(runtime_data_dir: str | Path) -> Path:
    return _worker_dir(runtime_data_dir) / "worker.lock.json"


def _cycles_path(runtime_data_dir: str | Path) -> Path:
    return _worker_dir(runtime_data_dir) / "cycles.jsonl"


def _stop_request_path(runtime_data_dir: str | Path) -> Path:
    return _worker_dir(runtime_data_dir) / "stop.request.json"


def _write_json(path: Path, payload: Any) -> Path:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_active_lock_fixture(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    worker_id: str = "active-worker",
    pid: int | None = None,
) -> Path:
    ensure_dir(_worker_dir(runtime_data_dir))
    payload = {
        "worker_id": worker_id,
        "pid": int(pid if pid is not None else os.getpid()),
        "lock_id": "active-lock-fixture",
        "acquired_at": utc_now(),
        "last_heartbeat_at": utc_now(),
    }
    return _write_json(_lock_path(runtime_data_dir), payload)


def write_stale_lock_fixture(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    worker_id: str = "stale-worker",
) -> Path:
    ensure_dir(_worker_dir(runtime_data_dir))
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=LOCK_STALE_SECONDS + 60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "worker_id": worker_id,
        "pid": 99999999,
        "lock_id": "stale-lock-fixture",
        "acquired_at": stale_time,
        "last_heartbeat_at": stale_time,
    }
    return _write_json(_lock_path(runtime_data_dir), payload)


def write_failed_cycle_fixture(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    worker_id: str = "fixture-worker",
    cycle_id: str = "cycle_failed_fixture",
) -> Path:
    summary = build_empty_cycle_summary(worker_id, cycle_id)
    summary.update(
        {
            "ok": False,
            "duration_ms": 42,
            "queue_items_processed": 1,
            "queue_items_failed": 1,
            "errors": ["queue_processing: simulated failure"],
        }
    )
    return _append_cycle(runtime_data_dir, summary)


def write_partial_failure_cycle_fixture(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    worker_id: str = "fixture-worker",
    cycle_id: str = "cycle_partial_failure_fixture",
) -> Path:
    summary = build_empty_cycle_summary(worker_id, cycle_id)
    summary.update(
        {
            "ok": False,
            "duration_ms": 20,
            "queue_items_processed": 1,
            "queue_items_completed": 0,
            "queue_items_failed": 1,
            "warnings": ["partial failure simulated"],
            "errors": ["event_source_poll_failed: simulated failure"],
        }
    )
    return _append_cycle(runtime_data_dir, summary)


def write_slow_cycle_fixture(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    worker_id: str = "fixture-worker",
    cycle_id: str = "cycle_slow_fixture",
    duration_ms: int = 7500,
) -> Path:
    summary = build_empty_cycle_summary(worker_id, cycle_id)
    summary.update(
        {
            "ok": True,
            "duration_ms": int(duration_ms),
            "queue_items_processed": 0,
            "warnings": ["slow cycle simulated"],
        }
    )
    return _append_cycle(runtime_data_dir, summary)


def write_stop_request_fixture(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    worker_id: str = "fixture-worker",
    reason: str = "manual_stop",
) -> Path:
    ensure_dir(_worker_dir(runtime_data_dir))
    payload = {
        "worker_id": worker_id,
        "requested_at": utc_now(),
        "requested_by": "operator",
        "reason": reason,
    }
    return _write_json(_stop_request_path(runtime_data_dir), payload)


def _append_cycle(runtime_data_dir: str | Path, summary: dict[str, Any]) -> Path:
    ensure_dir(_worker_dir(runtime_data_dir))
    path = _cycles_path(runtime_data_dir)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return path
