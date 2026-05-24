from __future__ import annotations

import tkinter as tk

import pytest

from src import operator_ui


def test_operator_ui_schedules_deferred_refresh_without_sync_health(monkeypatch, tmp_path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")

    scheduled: list[tuple[int, str]] = []

    def fake_after(delay, callback, *args):
        scheduled.append((delay, getattr(callback, "__name__", "")))
        return "after-id"

    monkeypatch.setattr(root, "after", fake_after, raising=False)
    monkeypatch.setattr(operator_ui.OperatorConsole, "refresh_runtime_data", lambda self: (_ for _ in ()).throw(AssertionError("refresh_runtime_data must not run synchronously")))
    monkeypatch.setattr(operator_ui, "check_all_tool_health", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("check_all_tool_health must not run at startup")))
    monkeypatch.setattr(operator_ui, "build_monitoring_summary", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("build_monitoring_summary must not run at startup")))
    monkeypatch.setattr(operator_ui, "assess_recovery", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("assess_recovery must not run at startup")))

    try:
        root.withdraw()
        built = operator_ui.build_operator_ui(root, runtime_root=str(tmp_path / "runtime_data"))
        console = getattr(built, "operator_console", None)
        assert console is not None
        assert console.startup_state_var.get() == "Loading runtime data..."
        assert scheduled == [(100, "safe_initial_refresh")]
    finally:
        root.destroy()

