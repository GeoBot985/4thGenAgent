from __future__ import annotations

import inspect

from src import operator_ui


def test_operator_ui_contains_recovery_assessment_panel() -> None:
    source = inspect.getsource(operator_ui)
    for text in (
        "Recovery Assessment",
        "safe-to-retry",
        "safe-to-resume",
        "side-effect risk",
        "recommended action",
        "retry/resume command suggestion",
        "assess_recovery",
    ):
        assert text in source
