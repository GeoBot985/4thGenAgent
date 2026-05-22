"""Spec 140 — Tests for run_worker_once: cycle ordering, feature flags, summary shape."""
import json
from pathlib import Path

import pytest

from runtime.worker.worker_contract import DEFAULT_WORKER_CONFIG
from runtime.worker.worker_engine import (
    _read_recent_cycles,
    _read_state,
    build_worker_status,
    run_worker_once,
)


@pytest.fixture()
def tmp_runtime(tmp_path):
    return str(tmp_path)


def _make_config(**overrides):
    cfg = {**DEFAULT_WORKER_CONFIG, "worker_id": "test-worker"}
    cfg.update(overrides)
    return cfg


class TestRunWorkerOnce:
    def test_returns_cycle_summary_shape(self, tmp_runtime):
        result = run_worker_once(_make_config(), tmp_runtime)
        assert "ok" in result
        assert "cycle_id" in result
        assert "started_at" in result
        assert "completed_at" in result
        assert "duration_ms" in result
        assert "stale_queue_recovered" in result
        assert "schedule_events_enqueued" in result
        assert "event_sources_polled" in result
        assert "queue_items_processed" in result
        assert "queue_items_completed" in result
        assert "queue_items_failed" in result
        assert "warnings" in result
        assert "errors" in result

    def test_ok_when_no_subsystem_errors(self, tmp_runtime):
        result = run_worker_once(_make_config(), tmp_runtime)
        assert result["ok"] is True

    def test_cycle_summary_persisted_to_cycles_jsonl(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        cycles_path = Path(tmp_runtime) / "worker" / "cycles.jsonl"
        assert cycles_path.exists()
        lines = cycles_path.read_text().strip().splitlines()
        assert len(lines) >= 1
        summary = json.loads(lines[-1])
        assert summary["cycle_id"].startswith("cycle_")

    def test_state_json_written(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        state = _read_state(tmp_runtime)
        assert state["worker_id"] == "test-worker"
        assert state["status"] in ("IDLE", "FAILED")
        assert state["cycle_count"] == 1

    def test_lock_released_after_cycle(self, tmp_runtime):
        from runtime.worker.worker_lock import is_worker_locked
        run_worker_once(_make_config(), tmp_runtime)
        locked = is_worker_locked(tmp_runtime)
        assert locked["locked"] is False

    def test_cycle_count_increments(self, tmp_runtime):
        run_worker_once(_make_config(), tmp_runtime)
        run_worker_once(_make_config(), tmp_runtime)
        state = _read_state(tmp_runtime)
        assert state["cycle_count"] == 2

    def test_duration_ms_positive(self, tmp_runtime):
        result = run_worker_once(_make_config(), tmp_runtime)
        assert result["duration_ms"] >= 0

    def test_cycle_id_format(self, tmp_runtime):
        result = run_worker_once(_make_config(), tmp_runtime)
        assert result["cycle_id"].startswith("cycle_")

    def test_worker_id_in_summary(self, tmp_runtime):
        result = run_worker_once(_make_config(), tmp_runtime)
        assert result["worker_id"] == "test-worker"

    def test_second_run_blocked_while_locked(self, tmp_runtime):
        from runtime.worker.worker_lock import acquire_worker_lock
        # Simulate another worker holding the lock
        lock_result = acquire_worker_lock("other-worker", tmp_runtime)
        assert lock_result["ok"] is True

        result = run_worker_once(_make_config(), tmp_runtime)
        assert result["ok"] is False
        assert "lock" in result.get("error", "").lower() or "lock" in result.get("message", "").lower()


class TestDisabledFeatures:
    def _config_with_features(self, **feature_overrides):
        cfg = _make_config()
        cfg["features"] = {**cfg["features"], **feature_overrides}
        return cfg

    def test_all_features_disabled_still_returns_summary(self, tmp_runtime):
        cfg = self._config_with_features(
            recover_stale_queue=False,
            run_scheduler_tick=False,
            poll_event_sources=False,
            process_queue=False,
        )
        result = run_worker_once(cfg, tmp_runtime)
        assert "cycle_id" in result

    def test_scheduler_disabled_enqueued_is_zero(self, tmp_runtime):
        cfg = self._config_with_features(run_scheduler_tick=False)
        result = run_worker_once(cfg, tmp_runtime)
        assert result["schedule_events_enqueued"] == 0

    def test_event_sources_disabled_polled_is_zero(self, tmp_runtime):
        cfg = self._config_with_features(poll_event_sources=False)
        result = run_worker_once(cfg, tmp_runtime)
        assert result["event_sources_polled"] == 0

    def test_queue_disabled_processed_is_zero(self, tmp_runtime):
        cfg = self._config_with_features(process_queue=False)
        result = run_worker_once(cfg, tmp_runtime)
        assert result["queue_items_processed"] == 0
