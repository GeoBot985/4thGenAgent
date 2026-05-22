from __future__ import annotations

from argparse import Namespace
from subprocess import CompletedProcess

import src.taskframe_cli as taskframe_cli


def test_taskframe_validate_delegates_to_bounded_runner(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, cwd=None):  # type: ignore[no-untyped-def]
        calls.append(list(command))
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(taskframe_cli.subprocess, "run", fake_run)

    result = taskframe_cli._run_validate(
        Namespace(mode="local", timeout_scale=2.0, continue_on_failure=True),
    )

    assert result == 0
    assert calls
    assert calls[0][0].endswith("python.exe") or calls[0][0].endswith("python")
    assert "run_bounded_validation.py" in calls[0][1]
    assert "local" in calls[0]
    assert "--timeout-scale" in calls[0]
    assert "2.0" in calls[0]
    assert "--continue-on-failure" in calls[0]
