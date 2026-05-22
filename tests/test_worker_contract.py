"""Spec 140 — Tests for worker_contract: config and state validation."""
import pytest

from runtime.worker.worker_contract import (
    DEFAULT_WORKER_CONFIG,
    WORKER_MODES,
    WORKER_STATUSES,
    build_empty_cycle_summary,
    build_empty_worker_state,
    validate_worker_config,
    validate_worker_state,
)


class TestValidateWorkerConfig:
    def test_default_config_is_valid(self):
        result = validate_worker_config(DEFAULT_WORKER_CONFIG)
        assert result["ok"] is True
        assert result["errors"] == []

    def test_minimal_valid_config(self):
        cfg = {"worker_id": "test-worker", "mode": "run_once", "safety": {"dry_run_only": True, "allow_live_side_effects": False}}
        result = validate_worker_config(cfg)
        assert result["ok"] is True

    def test_missing_worker_id_fails(self):
        cfg = {**DEFAULT_WORKER_CONFIG, "worker_id": ""}
        result = validate_worker_config(cfg)
        assert result["ok"] is False
        assert any("worker_id" in e for e in result["errors"])

    def test_invalid_mode_fails(self):
        cfg = {**DEFAULT_WORKER_CONFIG, "mode": "daemon"}
        result = validate_worker_config(cfg)
        assert result["ok"] is False
        assert any("mode" in e for e in result["errors"])

    def test_valid_modes(self):
        for mode in WORKER_MODES:
            cfg = {**DEFAULT_WORKER_CONFIG, "mode": mode}
            result = validate_worker_config(cfg)
            assert result["ok"] is True, f"mode {mode!r} should be valid: {result['errors']}"

    def test_live_side_effects_not_allowed(self):
        cfg = {**DEFAULT_WORKER_CONFIG, "safety": {"dry_run_only": True, "allow_live_side_effects": True}}
        result = validate_worker_config(cfg)
        assert result["ok"] is False
        assert any("allow_live_side_effects" in e for e in result["errors"])

    def test_dry_run_only_false_fails(self):
        cfg = {**DEFAULT_WORKER_CONFIG, "safety": {"dry_run_only": False, "allow_live_side_effects": False}}
        result = validate_worker_config(cfg)
        assert result["ok"] is False

    def test_invalid_max_cycles_fails(self):
        cfg = {**DEFAULT_WORKER_CONFIG, "cycle": {"max_cycles": 0, "sleep_seconds": 5, "max_runtime_seconds": 300}}
        result = validate_worker_config(cfg)
        assert result["ok"] is False

    def test_non_dict_fails(self):
        result = validate_worker_config("not a dict")
        assert result["ok"] is False

    def test_non_dict_cycle_fails(self):
        cfg = {**DEFAULT_WORKER_CONFIG, "cycle": "bad"}
        result = validate_worker_config(cfg)
        assert result["ok"] is False

    def test_negative_sleep_fails(self):
        cfg = {**DEFAULT_WORKER_CONFIG, "cycle": {"max_cycles": 1, "sleep_seconds": -1, "max_runtime_seconds": 300}}
        result = validate_worker_config(cfg)
        assert result["ok"] is False


class TestValidateWorkerState:
    def test_valid_stopped_state(self):
        state = build_empty_worker_state("test-worker")
        result = validate_worker_state(state)
        assert result["ok"] is True

    def test_all_statuses_valid(self):
        for status in WORKER_STATUSES:
            state = {**build_empty_worker_state("w"), "status": status}
            result = validate_worker_state(state)
            assert result["ok"] is True, f"status {status!r} should be valid"

    def test_invalid_status_fails(self):
        state = {**build_empty_worker_state("w"), "status": "ZOMBIE"}
        result = validate_worker_state(state)
        assert result["ok"] is False

    def test_non_dict_fails(self):
        result = validate_worker_state("bad")
        assert result["ok"] is False


class TestBuildHelpers:
    def test_empty_worker_state_shape(self):
        state = build_empty_worker_state("local-worker-1")
        assert state["worker_id"] == "local-worker-1"
        assert state["status"] == "STOPPED"
        assert state["cycle_count"] == 0
        assert state["last_cycle_summary"] == {}

    def test_empty_cycle_summary_shape(self):
        summary = build_empty_cycle_summary("local-worker-1", "cycle_001")
        assert summary["ok"] is True
        assert summary["worker_id"] == "local-worker-1"
        assert summary["cycle_id"] == "cycle_001"
        assert summary["queue_items_processed"] == 0
        assert summary["warnings"] == []
        assert summary["errors"] == []
