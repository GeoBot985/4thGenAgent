"""Spec 140 — Tests for worker with SQLite persistence backend."""
import json
from pathlib import Path

import pytest

from runtime.worker.worker_contract import DEFAULT_WORKER_CONFIG
from runtime.worker.worker_engine import (
    _read_recent_cycles,
    _read_state,
    build_worker_health,
    run_worker_once,
)


@pytest.fixture()
def tmp_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFRAME_PERSISTENCE_BACKEND", "sqlite")
    return str(tmp_path)


def _make_config(**overrides):
    cfg = {**DEFAULT_WORKER_CONFIG, "worker_id": "sqlite-worker"}
    cfg.update(overrides)
    return cfg


class TestSQLitePersistence:
    def test_run_once_succeeds_with_sqlite_backend(self, tmp_runtime):
        result = run_worker_once(_make_config(), tmp_runtime)
        assert "cycle_id" in result

    def test_run_once_state_still_on_filesystem(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        state_path = Path(tmp_runtime) / "worker" / "state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["worker_id"] == "sqlite-worker"

    def test_run_once_cycles_still_on_filesystem(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        cycles_path = Path(tmp_runtime) / "worker" / "cycles.jsonl"
        assert cycles_path.exists()

    def test_lock_released_after_cycle_sqlite(self, tmp_runtime):
        from runtime.worker.worker_lock import is_worker_locked
        run_worker_once(_make_config(), tmp_runtime)
        locked = is_worker_locked(tmp_runtime)
        assert locked["locked"] is False

    def test_health_checks_sqlite_backend(self, tmp_runtime):
        result = build_worker_health(tmp_runtime)
        assert "persistence_backend" in result["checks"]

    def test_cycle_summary_valid(self, tmp_runtime):
        result = run_worker_once(_make_config(), tmp_runtime)
        assert result["ok"] is True
        assert result["duration_ms"] >= 0

    def test_multiple_cycles_append_jsonl(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        run_worker_once(_make_config(), tmp_runtime)
        recent = _read_recent_cycles(tmp_runtime, limit=10)
        assert len(recent) == 2

    def test_state_count_increments_sqlite(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        run_worker_once(_make_config(), tmp_runtime)
        state = _read_state(tmp_runtime)
        assert state["cycle_count"] == 2
