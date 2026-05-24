from __future__ import annotations

import tkinter as tk

import pytest

from src import operator_ui


def test_operator_ui_constructor_does_not_run_tool_health(monkeypatch, tmp_path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")

    monkeypatch.setattr(root, "after", lambda delay, callback, *args: "after-id", raising=False)
    monkeypatch.setattr(operator_ui, "check_all_tool_health", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("check_all_tool_health must not run at startup")))
    monkeypatch.setattr(operator_ui, "build_monitoring_summary", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("build_monitoring_summary must not run at startup")))
    monkeypatch.setattr(operator_ui, "assess_recovery", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("assess_recovery must not run at startup")))

    try:
        root.withdraw()
        built = operator_ui.build_operator_ui(root, runtime_root=str(tmp_path / "runtime_data"))
        console = getattr(built, "operator_console", None)
        assert console is not None
        assert "Loading runtime data" in console.startup_state_var.get()
    finally:
        root.destroy()

