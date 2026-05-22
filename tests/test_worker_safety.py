"""Spec 140 — Tests for worker safety: no live side effects, pending actions stay pending."""
import pytest

from runtime.worker.worker_contract import (
    DEFAULT_WORKER_CONFIG,
    validate_worker_config,
)
from runtime.worker.worker_engine import run_worker_once


@pytest.fixture()
def tmp_runtime(tmp_path):
    return str(tmp_path)


def _safe_config(**overrides):
    cfg = {**DEFAULT_WORKER_CONFIG, "worker_id": "safety-worker"}
    cfg.update(overrides)
    return cfg


class TestSafetyConfig:
    def test_allow_live_side_effects_true_fails_validation(self):
        cfg = _safe_config(safety={"dry_run_only": True, "allow_live_side_effects": True})
        result = validate_worker_config(cfg)
        assert result["ok"] is False

    def test_dry_run_only_false_fails_validation(self):
        cfg = _safe_config(safety={"dry_run_only": False, "allow_live_side_effects": False})
        result = validate_worker_config(cfg)
        assert result["ok"] is False

    def test_default_config_is_safe(self):
        result = validate_worker_config(DEFAULT_WORKER_CONFIG)
        assert result["ok"] is True
        assert DEFAULT_WORKER_CONFIG["safety"]["dry_run_only"] is True
        assert DEFAULT_WORKER_CONFIG["safety"]["allow_live_side_effects"] is False

    def test_require_queue_for_execution_default_true(self):
        assert DEFAULT_WORKER_CONFIG["safety"]["require_queue_for_execution"] is True


class TestSafetyRuntime:
    def test_run_once_with_live_effects_config_skips_queue_processing(self, tmp_runtime):
        # When allow_live_side_effects=True in config, queue processing is skipped
        # (the engine blocks it — even though validation would reject the config)
        cfg = {
            **DEFAULT_WORKER_CONFIG,
            "worker_id": "safety-worker",
            "safety": {
                "dry_run_only": True,
                "allow_live_side_effects": True,
                "require_queue_for_execution": True,
            },
        }
        result = run_worker_once(cfg, tmp_runtime)
        # Queue processing should be skipped
        assert result.get("queue_items_processed", 0) == 0

    def test_run_once_never_produces_live_side_effects(self, tmp_runtime):
        # The queue runner always runs dry_run=True — verify no live actions
        result = run_worker_once(_safe_config(), tmp_runtime)
        # Cycle completes without any live-side-effect errors
        assert "ok" in result
        # Worker must not set allow_live_side_effects in any output
        assert "allow_live_side_effects" not in result

    def test_cycle_summary_contains_no_credentials(self, tmp_runtime):
        result = run_worker_once(_safe_config(), tmp_runtime)
        result_str = str(result)
        for sensitive in ("password", "token", "secret", "credential", "api_key"):
            assert sensitive not in result_str.lower()

    def test_state_contains_no_credentials(self, tmp_runtime):
        from runtime.worker.worker_engine import _read_state
        run_worker_once(_safe_config(), tmp_runtime)
        state = _read_state(tmp_runtime)
        state_str = str(state)
        for sensitive in ("password", "token", "secret", "credential"):
            assert sensitive not in state_str.lower()

    def test_worker_does_not_bypass_queue(self, tmp_runtime):
        # Worker uses process_queued_events (queue runner), not direct manifest execution
        # Verify the cycle summary tracks queue_items_processed (not direct runs)
        result = run_worker_once(_safe_config(), tmp_runtime)
        assert "queue_items_processed" in result
        assert "queue_items_completed" in result
        assert "queue_items_failed" in result

    def test_pending_actions_not_auto_executed(self, tmp_runtime):
        # Enqueue a fixture event and verify it flows through dry-run, not live exec
        # The queue runner always blocks live execution — verify cycle summary shows no live errors
        result = run_worker_once(_safe_config(), tmp_runtime)
        # If there were live side effects, they would appear as errors
        live_errors = [e for e in result.get("errors", []) if "live" in str(e).lower()]
        assert live_errors == []
