"""Spec 140 — Tests for worker_lock: acquire, release, stale detection."""
import json
import os
import time
from pathlib import Path

import pytest

from runtime.worker.worker_lock import (
    LOCK_STALE_SECONDS,
    _is_stale,
    acquire_worker_lock,
    clear_stale_lock,
    detect_stale_lock,
    is_worker_locked,
    release_worker_lock,
)


@pytest.fixture()
def tmp_runtime(tmp_path):
    return str(tmp_path)


class TestAcquireRelease:
    def test_acquire_creates_lock_file(self, tmp_runtime):
        result = acquire_worker_lock("worker-1", tmp_runtime)
        assert result["ok"] is True
        assert result["lock_id"]
        lock_path = Path(tmp_runtime) / "worker" / "worker.lock.json"
        assert lock_path.exists()

    def test_acquire_returns_lock_id(self, tmp_runtime):
        result = acquire_worker_lock("worker-1", tmp_runtime)
        assert len(result["lock_id"]) == 32  # uuid4 hex

    def test_lock_contains_pid(self, tmp_runtime):
        acquire_worker_lock("worker-1", tmp_runtime)
        lock_path = Path(tmp_runtime) / "worker" / "worker.lock.json"
        lock = json.loads(lock_path.read_text())
        assert lock["pid"] == os.getpid()

    def test_release_removes_lock_file(self, tmp_runtime):
        result = acquire_worker_lock("worker-1", tmp_runtime)
        lock_id = result["lock_id"]
        rel = release_worker_lock(lock_id, tmp_runtime)
        assert rel["ok"] is True
        lock_path = Path(tmp_runtime) / "worker" / "worker.lock.json"
        assert not lock_path.exists()

    def test_release_wrong_lock_id_fails(self, tmp_runtime):
        acquire_worker_lock("worker-1", tmp_runtime)
        result = release_worker_lock("wrong-id", tmp_runtime)
        assert result["ok"] is False
        assert "mismatch" in result.get("error", "").lower()

    def test_release_no_lock_is_ok(self, tmp_runtime):
        result = release_worker_lock("any-id", tmp_runtime)
        assert result["ok"] is True

    def test_second_worker_blocked_by_active_lock(self, tmp_runtime):
        acquire_worker_lock("worker-1", tmp_runtime)
        result = acquire_worker_lock("worker-2", tmp_runtime)
        assert result["ok"] is False
        assert result["error"] == "worker_lock_conflict"

    def test_second_acquire_same_worker_also_blocked(self, tmp_runtime):
        acquire_worker_lock("worker-1", tmp_runtime)
        result = acquire_worker_lock("worker-1", tmp_runtime)
        assert result["ok"] is False


class TestIsWorkerLocked:
    def test_no_lock_file_returns_not_locked(self, tmp_runtime):
        result = is_worker_locked(tmp_runtime)
        assert result["locked"] is False

    def test_active_lock_returns_locked(self, tmp_runtime):
        acquire_worker_lock("worker-1", tmp_runtime)
        result = is_worker_locked(tmp_runtime)
        assert result["locked"] is True

    def test_after_release_returns_not_locked(self, tmp_runtime):
        r = acquire_worker_lock("worker-1", tmp_runtime)
        release_worker_lock(r["lock_id"], tmp_runtime)
        result = is_worker_locked(tmp_runtime)
        assert result["locked"] is False


class TestStaleLock:
    def _write_stale_lock(self, runtime_dir: str) -> None:
        from datetime import datetime, timedelta, timezone
        lock_dir = Path(runtime_dir) / "worker"
        lock_dir.mkdir(parents=True, exist_ok=True)
        stale_time = (datetime.now(timezone.utc) - timedelta(seconds=LOCK_STALE_SECONDS + 60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        lock = {
            "worker_id": "dead-worker",
            "pid": 99999999,  # almost certainly not running
            "lock_id": "stale-lock-id",
            "acquired_at": stale_time,
            "last_heartbeat_at": stale_time,
        }
        (lock_dir / "worker.lock.json").write_text(json.dumps(lock))

    def test_detect_stale_lock(self, tmp_runtime):
        self._write_stale_lock(tmp_runtime)
        result = detect_stale_lock(tmp_runtime)
        assert result["stale"] is True

    def test_detect_no_lock_is_not_stale(self, tmp_runtime):
        result = detect_stale_lock(tmp_runtime)
        assert result["stale"] is False
        assert result.get("no_lock") is True

    def test_clear_stale_lock_removes_file(self, tmp_runtime):
        self._write_stale_lock(tmp_runtime)
        result = clear_stale_lock(tmp_runtime)
        assert result["ok"] is True
        assert result.get("cleared") is not None
        lock_path = Path(tmp_runtime) / "worker" / "worker.lock.json"
        assert not lock_path.exists()

    def test_clear_live_lock_refused(self, tmp_runtime):
        acquire_worker_lock("worker-1", tmp_runtime)
        result = clear_stale_lock(tmp_runtime)
        assert result["ok"] is False
        assert "live" in result.get("message", "").lower()

    def test_clear_no_lock_is_ok(self, tmp_runtime):
        result = clear_stale_lock(tmp_runtime)
        assert result["ok"] is True

    def test_stale_lock_allows_new_acquire(self, tmp_runtime):
        self._write_stale_lock(tmp_runtime)
        result = acquire_worker_lock("worker-new", tmp_runtime)
        assert result["ok"] is True


class TestIsStale:
    def test_recent_heartbeat_not_stale(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lock = {"last_heartbeat_at": now, "pid": os.getpid()}
        assert _is_stale(lock) is False

    def test_no_heartbeat_is_stale(self):
        lock = {"last_heartbeat_at": "", "pid": os.getpid()}
        assert _is_stale(lock) is True

    def test_old_heartbeat_dead_pid_is_stale(self):
        from datetime import datetime, timedelta, timezone
        old = (datetime.now(timezone.utc) - timedelta(seconds=LOCK_STALE_SECONDS + 60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        lock = {"last_heartbeat_at": old, "pid": 99999999}
        assert _is_stale(lock) is True
