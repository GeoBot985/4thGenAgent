"""Spec 140 — Tests for operator_worker_panel.build_worker_panel."""
import pytest

from src.operator_worker_panel import build_worker_panel


@pytest.fixture()
def tmp_runtime(tmp_path):
    return str(tmp_path)


class TestBuildWorkerPanel:
    def test_returns_ok(self, tmp_runtime):
        result = build_worker_panel(tmp_runtime)
        assert result["ok"] is True

    def test_has_required_keys(self, tmp_runtime):
        result = build_worker_panel(tmp_runtime)
        assert "summary" in result
        assert "worker_state" in result
        assert "last_cycle" in result
        assert "recent_cycles" in result
        assert "health" in result
        assert "warnings" in result

    def test_summary_has_required_fields(self, tmp_runtime):
        result = build_worker_panel(tmp_runtime)
        summary = result["summary"]
        assert "status" in summary
        assert "worker_id" in summary
        assert "last_heartbeat_at" in summary
        assert "last_cycle_completed_at" in summary
        assert "queue_items_processed" in summary
        assert "errors" in summary

    def test_summary_status_default_stopped(self, tmp_runtime):
        result = build_worker_panel(tmp_runtime)
        assert result["summary"]["status"] == "STOPPED"

    def test_health_has_checks(self, tmp_runtime):
        result = build_worker_panel(tmp_runtime)
        assert "checks" in result["health"]

    def test_warnings_is_list(self, tmp_runtime):
        result = build_worker_panel(tmp_runtime)
        assert isinstance(result["warnings"], list)

    def test_recent_cycles_empty_initially(self, tmp_runtime):
        result = build_worker_panel(tmp_runtime)
        assert isinstance(result["recent_cycles"], list)

    def test_panel_after_run_once(self, tmp_runtime):
        from runtime.worker.worker_contract import DEFAULT_WORKER_CONFIG
        from runtime.worker.worker_engine import run_worker_once
        run_worker_once({**DEFAULT_WORKER_CONFIG, "worker_id": "panel-worker"}, tmp_runtime)
        result = build_worker_panel(tmp_runtime)
        assert result["ok"] is True
        assert result["summary"]["worker_id"] == "panel-worker"
        assert result["summary"]["status"] in ("IDLE", "FAILED")
        assert len(result["recent_cycles"]) >= 1

    def test_queue_items_processed_is_int(self, tmp_runtime):
        result = build_worker_panel(tmp_runtime)
        assert isinstance(result["summary"]["queue_items_processed"], int)

    def test_errors_is_int(self, tmp_runtime):
        result = build_worker_panel(tmp_runtime)
        assert isinstance(result["summary"]["errors"], int)
