"""Spec 140 — Tests for worker stop request: write, honour, clear."""
import json
from pathlib import Path

import pytest

from runtime.worker.worker_contract import DEFAULT_WORKER_CONFIG
from runtime.worker.worker_engine import (
    _read_recent_cycles,
    _read_state,
    _read_stop_request,
    _stop_request_path,
    request_worker_stop,
    run_worker_loop,
)


@pytest.fixture()
def tmp_runtime(tmp_path):
    return str(tmp_path)


def _make_loop_config(max_cycles=5, sleep_seconds=0):
    return {
        **DEFAULT_WORKER_CONFIG,
        "worker_id": "stop-test-worker",
        "mode": "bounded_loop",
        "cycle": {
            "max_cycles": max_cycles,
            "sleep_seconds": sleep_seconds,
            "max_runtime_seconds": 60,
        },
    }


class TestStopRequest:
    def test_request_worker_stop_writes_file(self, tmp_runtime):
        result = request_worker_stop("stop-test-worker", tmp_runtime)
        assert result["ok"] is True
        stop_path = Path(tmp_runtime) / "worker" / "stop.request.json"
        assert stop_path.exists()

    def test_stop_request_shape(self, tmp_runtime):
        request_worker_stop("stop-test-worker", tmp_runtime)
        req = _read_stop_request(tmp_runtime)
        assert req is not None
        assert req["worker_id"] == "stop-test-worker"
        assert req["requested_by"] == "operator"
        assert req["reason"] == "manual_stop"
        assert req["requested_at"]

    def test_loop_honours_stop_request(self, tmp_runtime):
        # Write stop request before starting the loop
        request_worker_stop("stop-test-worker", tmp_runtime)
        result = run_worker_loop(_make_loop_config(max_cycles=5), tmp_runtime)
        assert result["stopped_early"] is True
        assert result["stop_reason"] in ("manual_stop", "stop_requested")

    def test_loop_clears_stop_request_after_honouring(self, tmp_runtime):
        request_worker_stop("stop-test-worker", tmp_runtime)
        run_worker_loop(_make_loop_config(max_cycles=5), tmp_runtime)
        req = _read_stop_request(tmp_runtime)
        assert req is None

    def test_stop_request_returns_stop_request_in_result(self, tmp_runtime):
        result = request_worker_stop("stop-test-worker", tmp_runtime)
        assert "stop_request" in result
        assert result["stop_request"]["worker_id"] == "stop-test-worker"

    def test_no_stop_request_allows_all_cycles(self, tmp_runtime):
        result = run_worker_loop(_make_loop_config(max_cycles=2, sleep_seconds=0), tmp_runtime)
        assert result["stopped_early"] is False
        assert result["cycles_run"] == 2

    def test_stop_request_without_running_worker_still_writes(self, tmp_runtime):
        result = request_worker_stop("any-worker", tmp_runtime)
        assert result["ok"] is True
        stop_path = Path(tmp_runtime) / "worker" / "stop.request.json"
        assert stop_path.exists()
