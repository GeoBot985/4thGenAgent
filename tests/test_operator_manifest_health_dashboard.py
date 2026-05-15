from __future__ import annotations

import inspect

from src import operator_ui


def _source() -> str:
    return inspect.getsource(operator_ui)


def test_validate_all_button_exists() -> None:
    source = _source()
    assert 'text="Validate All"' in source
    assert "on_workbench_validate_all_manifests" in source


def test_health_dashboard_handler_exists() -> None:
    source = _source()
    assert "def on_workbench_validate_all_manifests" in source
    assert "def _show_manifest_health_dashboard" in source
    assert "Manifest Health Dashboard" in source


def test_health_dashboard_calls_backend_checker() -> None:
    source = _source()
    assert "run_manifest_health_check(" in source
    assert "write_manifest_health_report(" in source


def test_health_dashboard_displays_summary_counts() -> None:
    source = _source()
    for label in ("Total", "Healthy", "Warnings", "Failed", "Repairable", "Manual Fix", "Critical"):
        assert label in source


def test_health_dashboard_table_has_required_columns() -> None:
    source = _source()
    for label in ("Health", "Manifest ID", "Validation", "Smoke", "Repairable", "Top Findings", "Next Action"):
        assert label in source


def test_open_selected_manifest_from_dashboard_loads_editor() -> None:
    source = _source()
    assert "Open Selected Manifest" in source
    assert 'self.on_workbench_load_selected_manifest(str(item.get("path", "")))' in source


def test_health_dashboard_can_open_repair_guidance() -> None:
    source = _source()
    assert "open_repair_guidance" in source
    assert "self.on_workbench_repair_guidance()" in source


def test_health_dashboard_can_open_autofix_preview() -> None:
    source = _source()
    assert "open_autofix_preview" in source
    assert "self.on_workbench_autofix_preview()" in source


def test_health_dashboard_handles_backend_failure_without_crash() -> None:
    source = _source()
    assert "except Exception as exc" in source
    assert '"status": "FAILED"' in source
    assert "Dashboard error:" in source


def test_health_report_paths_are_displayed() -> None:
    source = _source()
    assert "JSON report:" in source
    assert "Markdown report:" in source
    assert "Open JSON Report" in source
    assert "Open Markdown Report" in source
