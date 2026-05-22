"""Spec 140 — Worker lock: prevents duplicate local workers per runtime_data_dir."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOCK_STALE_SECONDS = 120


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _worker_dir(runtime_data_dir: str | Path) -> Path:
    return Path(runtime_data_dir) / "worker"


def _lock_path(runtime_data_dir: str | Path) -> Path:
    return _worker_dir(runtime_data_dir) / "worker.lock.json"


def _ensure_worker_dir(runtime_data_dir: str | Path) -> None:
    _worker_dir(runtime_data_dir).mkdir(parents=True, exist_ok=True)


def _read_lock(lock_path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _pid_running(pid: int) -> bool:
    """Return True if the given PID is alive in the current OS."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _is_stale(lock: dict[str, Any]) -> bool:
    """True when the lock heartbeat is older than LOCK_STALE_SECONDS AND the PID is gone."""
    heartbeat_str = lock.get("last_heartbeat_at") or lock.get("acquired_at") or ""
    if not heartbeat_str:
        return True
    try:
        hb = datetime.fromisoformat(heartbeat_str.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - hb).total_seconds()
        if age < LOCK_STALE_SECONDS:
            return False
    except Exception:
        return True

    pid = int(lock.get("pid") or 0)
    return not _pid_running(pid)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def acquire_worker_lock(
    worker_id: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Acquire the exclusive worker lock.

    Returns {ok, lock_id, lock} on success.
    Returns {ok=False, error, message, existing_lock} on conflict.
    """
    _ensure_worker_dir(runtime_data_dir)
    lock_path = _lock_path(runtime_data_dir)

    if lock_path.exists():
        existing = _read_lock(lock_path)
        if existing and not _is_stale(existing):
            return {
                "ok": False,
                "error": "worker_lock_conflict",
                "message": (
                    f"Worker lock held by {existing.get('worker_id')!r} "
                    f"(PID {existing.get('pid')})"
                ),
                "existing_lock": existing,
            }

    lock_id = uuid.uuid4().hex
    lock = {
        "worker_id": worker_id,
        "pid": os.getpid(),
        "lock_id": lock_id,
        "acquired_at": _utc_now(),
        "last_heartbeat_at": _utc_now(),
    }
    lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    return {"ok": True, "lock_id": lock_id, "lock": lock}


def release_worker_lock(
    lock_id: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Release the lock if it belongs to us (matched by lock_id)."""
    lock_path = _lock_path(runtime_data_dir)
    if not lock_path.exists():
        return {"ok": True, "message": "no lock to release"}

    existing = _read_lock(lock_path)
    if existing and existing.get("lock_id") != lock_id:
        return {
            "ok": False,
            "error": "lock_id_mismatch",
            "message": "Cannot release a lock we do not own",
        }

    try:
        lock_path.unlink(missing_ok=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True}


def is_worker_locked(
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Return {locked, lock?} — does not distinguish stale vs live."""
    lock_path = _lock_path(runtime_data_dir)
    if not lock_path.exists():
        return {"locked": False}
    existing = _read_lock(lock_path)
    if existing and not _is_stale(existing):
        return {"locked": True, "lock": existing}
    return {"locked": False, "stale_lock": existing}


def detect_stale_lock(
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Check whether an existing lock is stale."""
    lock_path = _lock_path(runtime_data_dir)
    if not lock_path.exists():
        return {"stale": False, "no_lock": True}
    existing = _read_lock(lock_path)
    if existing and _is_stale(existing):
        return {"stale": True, "lock": existing}
    return {"stale": False, "lock": existing}


def clear_stale_lock(
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Explicitly clear a stale lock. Refuses to touch a live lock."""
    lock_path = _lock_path(runtime_data_dir)
    if not lock_path.exists():
        return {"ok": True, "message": "no lock present"}

    existing = _read_lock(lock_path)
    if existing and not _is_stale(existing):
        return {
            "ok": False,
            "error": "worker_lock_conflict",
            "message": "Lock appears live — will not force-clear a live lock",
            "lock": existing,
        }

    try:
        lock_path.unlink(missing_ok=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "cleared": existing}
