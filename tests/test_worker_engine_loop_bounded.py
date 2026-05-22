"""Spec 140 — Tests for run_worker_loop: bounded cycles, sleep, max_runtime."""
import json
import time
from pathlib import Path

import pytest

from runtime.worker.worker_contract import DEFAULT_WORKER_CONFIG
from runtime.worker.worker_engine import (
    _read_recent_cycles,
    _read_state,
    run_worker_loop,
)


@pytest.fixture()
def tmp_runtime(tmp_path):
    return str(tmp_path)


def _make_loop_config(max_cycles=2, sleep_seconds=0, max_runtime_seconds=60):
    return {
        **DEFAULT_WORKER_CONFIG,
        "worker_id": "loop-worker",
        "mode": "bounded_loop",
        "cycle": {
            "max_cycles": max_cycles,
            "sleep_seconds": sleep_seconds,
            "max_runtime_seconds": max_runtime_seconds,
        },
    }


class TestBoundedLoop:
    def test_runs_exactly_max_cycles(self, tmp_runtime):
        result = run_worker_loop(_make_loop_config(max_cycles=2, sleep_seconds=0), tmp_runtime)
        assert result["cycles_run"] == 2

    def test_one_cycle_loop(self, tmp_runtime):
        result = run_worker_loop(_make_loop_config(max_cycles=1, sleep_seconds=0), tmp_runtime)
        assert result["cycles_run"] == 1
        assert result["stopped_early"] is False

    def test_three_cycle_loop(self, tmp_runtime):
        result = run_worker_loop(_make_loop_config(max_cycles=3, sleep_seconds=0), tmp_runtime)
        assert result["cycles_run"] == 3

    def test_summaries_count_matches_cycles_run(self, tmp_runtime):
        result = run_worker_loop(_make_loop_config(max_cycles=3, sleep_seconds=0), tmp_runtime)
        assert len(result["summaries"]) == result["cycles_run"]

    def test_cycle_history_persisted(self, tmp_runtime):
        run_worker_loop(_make_loop_config(max_cycles=2, sleep_seconds=0), tmp_runtime)
        recent = _read_recent_cycles(tmp_runtime, limit=10)
        assert len(recent) >= 2

    def test_ok_when_all_cycles_ok(self, tmp_runtime):
        result = run_worker_loop(_make_loop_config(max_cycles=2, sleep_seconds=0), tmp_runtime)
        assert result["ok"] is True

    def test_max_runtime_stops_loop_early(self, tmp_runtime):
        # max_runtime_seconds=0 means immediately timeout before any cycle runs
        cfg = _make_loop_config(max_cycles=10, sleep_seconds=0, max_runtime_seconds=0)
        result = run_worker_loop(cfg, tmp_runtime)
        # With 0s budget, the loop must stop before completing max_cycles
        assert result["cycles_run"] < 10

    def test_result_shape(self, tmp_runtime):
        result = run_worker_loop(_make_loop_config(max_cycles=1, sleep_seconds=0), tmp_runtime)
        assert "ok" in result
        assert "worker_id" in result
        assert "cycles_run" in result
        assert "max_cycles" in result
        assert "stopped_early" in result
        assert "stop_reason" in result
        assert "summaries" in result

    def test_worker_id_in_result(self, tmp_runtime):
        result = run_worker_loop(_make_loop_config(max_cycles=1, sleep_seconds=0), tmp_runtime)
        assert result["worker_id"] == "loop-worker"

    def test_state_cycle_count_accumulates(self, tmp_runtime):
        run_worker_loop(_make_loop_config(max_cycles=3, sleep_seconds=0), tmp_runtime)
        state = _read_state(tmp_runtime)
        assert int(state.get("cycle_count", 0)) == 3

    def test_stop_reason_empty_when_not_stopped_early(self, tmp_runtime):
        result = run_worker_loop(_make_loop_config(max_cycles=1, sleep_seconds=0), tmp_runtime)
        assert result["stopped_early"] is False
        assert result["stop_reason"] == ""
