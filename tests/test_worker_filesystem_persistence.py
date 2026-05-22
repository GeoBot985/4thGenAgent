"""Spec 140 — Tests for worker with filesystem persistence backend."""
import json
import os
from pathlib import Path

import pytest

from runtime.worker.worker_contract import DEFAULT_WORKER_CONFIG
from runtime.worker.worker_engine import (
    _read_recent_cycles,
    _read_state,
    run_worker_loop,
    run_worker_once,
)


@pytest.fixture()
def tmp_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFRAME_PERSISTENCE_BACKEND", "filesystem")
    return str(tmp_path)


def _make_config(**overrides):
    cfg = {**DEFAULT_WORKER_CONFIG, "worker_id": "fs-worker"}
    cfg.update(overrides)
    return cfg


class TestFilesystemPersistence:
    def test_run_once_creates_worker_dir(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        worker_dir = Path(tmp_runtime) / "worker"
        assert worker_dir.is_dir()

    def test_run_once_writes_state_json(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        state_path = Path(tmp_runtime) / "worker" / "state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["worker_id"] == "fs-worker"

    def test_run_once_writes_cycles_jsonl(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        cycles_path = Path(tmp_runtime) / "worker" / "cycles.jsonl"
        assert cycles_path.exists()
        line = cycles_path.read_text().strip().splitlines()[-1]
        summary = json.loads(line)
        assert "cycle_id" in summary

    def test_lock_file_created_and_removed(self, tmp_runtime):
        lock_path = Path(tmp_runtime) / "worker" / "worker.lock.json"
        run_worker_once(_make_config(), tmp_runtime)
        assert not lock_path.exists()  # released after cycle

    def test_multiple_cycles_appends_to_jsonl(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        run_worker_once(_make_config(), tmp_runtime)
        cycles_path = Path(tmp_runtime) / "worker" / "cycles.jsonl"
        lines = cycles_path.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_loop_persists_all_cycles(self, tmp_runtime):
        cfg = {
            **_make_config(),
            "mode": "bounded_loop",
            "cycle": {"max_cycles": 3, "sleep_seconds": 0, "max_runtime_seconds": 60},
        }
        run_worker_loop(cfg, tmp_runtime)
        recent = _read_recent_cycles(tmp_runtime, limit=10)
        assert len(recent) == 3

    def test_state_updated_after_loop(self, tmp_runtime):
        cfg = {
            **_make_config(),
            "mode": "bounded_loop",
            "cycle": {"max_cycles": 2, "sleep_seconds": 0, "max_runtime_seconds": 60},
        }
        run_worker_loop(cfg, tmp_runtime)
        state = _read_state(tmp_runtime)
        assert state["cycle_count"] == 2
        assert state["status"] in ("IDLE", "FAILED", "STOPPED")

    def test_state_json_is_valid_json(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        state_path = Path(tmp_runtime) / "worker" / "state.json"
        state = json.loads(state_path.read_text())
        assert isinstance(state, dict)

    def test_backend_health_works_in_filesystem_mode(self, tmp_runtime):
        from runtime.worker.worker_engine import build_worker_health
        result = build_worker_health(tmp_runtime)
        assert "checks" in result
        assert "persistence_backend" in result["checks"]
