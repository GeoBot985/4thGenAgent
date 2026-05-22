"""Spec 140 — Bounded release verifier for local_worker_supervisor."""
import json
from pathlib import Path

import pytest

from runtime.worker.worker_contract import DEFAULT_WORKER_CONFIG, validate_worker_config
from runtime.worker.worker_engine import (
    _read_recent_cycles,
    _read_state,
    build_worker_health,
    build_worker_status,
    clear_stale_worker_lock,
    run_worker_once,
)
from runtime.worker.worker_lock import acquire_worker_lock, release_worker_lock


@pytest.fixture()
def tmp_runtime(tmp_path):
    return str(tmp_path)


class TestWorkerReleaseVerifier:
    """Bounded acceptance tests for the local worker supervisor (release verifier gate)."""

    def test_worker_modules_import(self):
        from runtime.worker import worker_contract, worker_engine, worker_lock
        assert worker_contract
        assert worker_engine
        assert worker_lock

    def test_worker_config_validates(self):
        result = validate_worker_config(DEFAULT_WORKER_CONFIG)
        assert result["ok"] is True, result["errors"]

    def test_run_once_executes_against_fixture_runtime(self, tmp_runtime):
        result = run_worker_once(DEFAULT_WORKER_CONFIG, tmp_runtime)
        assert "cycle_id" in result
        assert result["duration_ms"] >= 0

    def test_scheduler_tick_invoked_through_worker(self, tmp_runtime):
        cfg = {
            **DEFAULT_WORKER_CONFIG,
            "features": {**DEFAULT_WORKER_CONFIG["features"], "run_scheduler_tick": True},
        }
        result = run_worker_once(cfg, tmp_runtime)
        assert "schedule_events_enqueued" in result

    def test_fixture_event_source_poll_through_worker(self, tmp_runtime):
        cfg = {
            **DEFAULT_WORKER_CONFIG,
            "features": {**DEFAULT_WORKER_CONFIG["features"], "poll_event_sources": True},
        }
        result = run_worker_once(cfg, tmp_runtime)
        assert "event_sources_polled" in result

    def test_queue_processing_through_worker(self, tmp_runtime):
        cfg = {
            **DEFAULT_WORKER_CONFIG,
            "features": {**DEFAULT_WORKER_CONFIG["features"], "process_queue": True},
        }
        result = run_worker_once(cfg, tmp_runtime)
        assert "queue_items_processed" in result

    def test_lock_prevents_duplicate_worker(self, tmp_runtime):
        lock_result = acquire_worker_lock("blocking-worker", tmp_runtime)
        assert lock_result["ok"] is True
        try:
            result = run_worker_once(DEFAULT_WORKER_CONFIG, tmp_runtime)
            assert result["ok"] is False
        finally:
            release_worker_lock(lock_result["lock_id"], tmp_runtime)

    def test_cycle_history_written(self, tmp_runtime):
        run_worker_once(DEFAULT_WORKER_CONFIG, tmp_runtime)
        recent = _read_recent_cycles(tmp_runtime, limit=5)
        assert len(recent) >= 1
        assert "cycle_id" in recent[0]

    def test_no_live_side_effects_in_cycle(self, tmp_runtime):
        result = run_worker_once(DEFAULT_WORKER_CONFIG, tmp_runtime)
        assert DEFAULT_WORKER_CONFIG["safety"]["allow_live_side_effects"] is False
        # Cycle errors should not include live-side-effect errors
        live_errors = [e for e in result.get("errors", []) if "live" in str(e).lower()]
        assert live_errors == []

    def test_worker_status_readable_after_run(self, tmp_runtime):
        run_worker_once(DEFAULT_WORKER_CONFIG, tmp_runtime)
        status = build_worker_status(tmp_runtime)
        assert status["ok"] is True
        assert status["status"] in ("IDLE", "FAILED")
        assert status["cycle_count"] == 1

    def test_clear_stale_lock_is_explicit(self, tmp_runtime):
        result = clear_stale_worker_lock(tmp_runtime)
        assert result["ok"] is True

    def test_health_check_returns_all_subsystems(self, tmp_runtime):
        health = build_worker_health(tmp_runtime)
        checks = health.get("checks", {})
        assert "persistence_backend" in checks
        assert "queue" in checks
        assert "scheduler" in checks
        assert "event_sources" in checks
        assert "lock_valid" in checks

    def test_no_indefinite_loop(self, tmp_runtime):
        """Verify the loop is bounded by max_cycles."""
        from runtime.worker.worker_engine import run_worker_loop
        cfg = {
            **DEFAULT_WORKER_CONFIG,
            "mode": "bounded_loop",
            "cycle": {"max_cycles": 2, "sleep_seconds": 0, "max_runtime_seconds": 30},
        }
        result = run_worker_loop(cfg, tmp_runtime)
        assert result["cycles_run"] == 2
        assert result["stopped_early"] is False
