from __future__ import annotations

import inspect

from src import operator_ui


def test_operator_ui_contains_operational_health_panel() -> None:
    source = inspect.getsource(operator_ui)
    for text in (
        "Operational Health",
        "Run Health Summary",
        "Failed Runs",
        "Pending Approvals",
        "Stuck Runs",
        "Tool Health",
        "External Dependencies",
        "Runtime Store Status",
        "Recommended Actions",
        "on_refresh_operational_health",
    ):
        assert text in source


def test_operator_ui_operational_health_panel_uses_monitoring_module() -> None:
    source = inspect.getsource(operator_ui)
    assert "build_monitoring_summary" in source
    assert "build_operational_monitoring_report" in source
