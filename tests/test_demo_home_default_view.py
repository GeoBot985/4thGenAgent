from __future__ import annotations

"""Spec 159 — Demo Home is the default startup view."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_view_mode_var_defaults_to_demo_home() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert 'tk.StringVar(value="Demo Home")' in content, "view_mode_var must default to 'Demo Home'"


def test_demo_home_view_frame_in_layout() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "demo_home_view_frame" in content
    assert "_build_demo_home_view" in content


def test_switch_view_mode_handles_demo_home() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert '"Demo Home"' in content
    assert "_switch_view_mode" in content
    assert "demo_home_view_frame.grid()" in content


def test_nav_includes_demo_home() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert '"Demo Home"' in content
    # Navigation includes Console (operator console)
    assert '"Console"' in content


def test_render_current_view_handles_demo_home() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "_refresh_demo_home_view" in content


def test_go_to_console_method_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "_go_to_console" in content


def test_demo_home_state_vars_defined() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "demo_home_status_var" in content
    assert "demo_home_run_summary_var" in content
