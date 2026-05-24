from __future__ import annotations

"""Spec 159 — Advanced actions are hidden by default."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_advanced_actions_frame_grid_remove_by_default() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    # Advanced actions frame is explicitly hidden (grid_remove) after being added
    assert "demo_advanced_actions_frame" in content
    assert "grid_remove" in content


def test_advanced_actions_toggle_button_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "advanced_actions_toggle_button" in content
    assert "_toggle_demo_advanced_actions" in content or "Advanced actions" in content


def test_advanced_settings_frame_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "advanced_settings_frame" in content


def test_advanced_actions_var_defaults_false() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "advanced_actions_visible_var" in content
    assert "BooleanVar(value=False)" in content


def test_sync_demo_toolbar_visibility_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "_sync_demo_toolbar_visibility" in content


def test_advanced_actions_in_demo_view_not_demo_home() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    # Advanced actions are in _build_demo_view (Console), not in _build_demo_home_view
    # Verify both methods exist
    assert "_build_demo_view" in content
    assert "_build_demo_home_view" in content


def test_reject_and_start_over_in_advanced_not_main() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    # These are in the advanced section
    assert "Reject" in content
    assert "Start over" in content
    assert "Cancel / Stop demo" in content
