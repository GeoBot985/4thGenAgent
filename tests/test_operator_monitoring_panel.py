from __future__ import annotations

import inspect

from src import operator_ui


def test_operator_ui_contains_monitoring_panel_strings() -> None:
    source = inspect.getsource(operator_ui)
    for text in (
        "Operational Monitoring",
        "Refresh Monitoring Snapshot",
        "Open Monitoring Report",
        "Open Alert Candidate Report",
        "build_monitoring_snapshot",
        "write_monitoring_snapshot",
        "on_refresh_monitoring_snapshot",
    ):
        assert text in source


def test_operator_ui_retains_legacy_operational_health_strings() -> None:
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
    ):
        assert text in source
