from __future__ import annotations

from runtime.worker import worker_engine
from runtime.worker.worker_contract import DEFAULT_WORKER_CONFIG
from runtime.worker.worker_engine import run_worker_loop, run_worker_once
from runtime.worker.worker_failure_fixtures import (
    write_active_lock_fixture,
    write_failed_cycle_fixture,
    write_partial_failure_cycle_fixture,
    write_slow_cycle_fixture,
    write_stale_lock_fixture,
    write_stop_request_fixture,
)
from runtime.worker.worker_lock import clear_stale_lock, detect_stale_lock


def test_stale_lock_detected_and_cleared(tmp_path):
    runtime_data_dir = tmp_path / "runtime_data"
    write_stale_lock_fixture(runtime_data_dir, worker_id="stale-worker")

    detected = detect_stale_lock(runtime_data_dir)
    assert detected["stale"] is True

    cleared = clear_stale_lock(runtime_data_dir)
    assert cleared["ok"] is True
    assert not (runtime_data_dir / "worker" / "worker.lock.json").exists()


def test_active_lock_is_not_cleared(tmp_path):
    runtime_data_dir = tmp_path / "runtime_data"
    write_active_lock_fixture(runtime_data_dir, worker_id="active-worker")

    cleared = clear_stale_lock(runtime_data_dir)
    assert cleared["ok"] is False
    assert "live" in cleared["message"].lower()


def test_duplicate_worker_execution_is_blocked(tmp_path):
    runtime_data_dir = tmp_path / "runtime_data"
    write_active_lock_fixture(runtime_data_dir, worker_id="other-worker")

    result = run_worker_once(DEFAULT_WORKER_CONFIG, runtime_data_dir=runtime_data_dir)
    assert result["ok"] is False
    assert "worker_lock_conflict" in result.get("error", "")


def test_stop_request_is_honoured_after_current_cycle(tmp_path, monkeypatch):
    runtime_data_dir = tmp_path / "runtime_data"
    stop_written = {"count": 0}
    original_run_worker_once = worker_engine.run_worker_once

    def wrapped_run_worker_once(config, runtime_data_dir):
        result = original_run_worker_once(config, runtime_data_dir)
        if stop_written["count"] == 0:
            write_stop_request_fixture(runtime_data_dir, worker_id=str(config.get("worker_id") or "local-worker-1"))
            stop_written["count"] += 1
        return result

    monkeypatch.setattr(worker_engine, "run_worker_once", wrapped_run_worker_once)

    config = {
        **DEFAULT_WORKER_CONFIG,
        "worker_id": "local-worker-1",
        "cycle": {"max_cycles": 3, "sleep_seconds": 0, "max_runtime_seconds": 30},
    }
    result = run_worker_loop(config, runtime_data_dir=runtime_data_dir)

    assert result["cycles_run"] == 1
    assert result["stopped_early"] is True
    assert result["stop_reason"] == "manual_stop"


def test_cycle_fixtures_write_history(tmp_path):
    runtime_data_dir = tmp_path / "runtime_data"
    write_failed_cycle_fixture(runtime_data_dir)
    write_partial_failure_cycle_fixture(runtime_data_dir)
    write_slow_cycle_fixture(runtime_data_dir)
    assert (runtime_data_dir / "worker" / "cycles.jsonl").is_file()
