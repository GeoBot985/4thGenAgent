from __future__ import annotations

import tkinter as tk

import pytest

from src import operator_ui


def test_operator_ui_renders_startup_error_panel(monkeypatch, tmp_path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")

    monkeypatch.setattr(root, "after", lambda delay, callback, *args: "after-id", raising=False)

    try:
        root.withdraw()
        built = operator_ui.build_operator_ui(root, runtime_root=str(tmp_path / "runtime_data"))
        console = getattr(built, "operator_console", None)
        assert console is not None

        def boom() -> None:
            raise RuntimeError("startup failure")

        monkeypatch.setattr(console, "load_cached_runtime_data", boom)
        console.safe_initial_refresh()

        assert console.startup_state_var.get() == "Startup refresh failed."
        assert "RuntimeError" in console.startup_detail_var.get()
        assert "startup failure" in console.startup_detail_var.get()
        text = console.startup_error_text.get("1.0", "end").strip()
        assert "RuntimeError" in text
        assert "startup failure" in text
        assert "Traceback" in text
    finally:
        root.destroy()

