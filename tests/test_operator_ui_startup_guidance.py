from __future__ import annotations

"""Spec 159 — Startup shows guidance instead of empty panels."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_demo_home_guidance_label_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "demo_home_guidance_label" in content


def test_startup_guidance_text_defined() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "Choose a demo and click Run" in content


def test_no_demo_has_been_run_guidance() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "No demo has been run yet" in content


def test_run_summary_strip_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "demo_home_run_summary_frame" in content
    assert "demo_home_run_summary_label" in content


def test_refresh_demo_home_view_updates_summary() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "_refresh_demo_home_view" in content
    # Summary includes key fields after a run
    assert "Pending actions" in content
    assert "Report" in content
    assert "Evidence" in content


def test_startup_state_var_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "startup_state_var" in content
    assert "startup_detail_var" in content


def test_demo_home_view_has_section_label() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "Demo Home" in content


def test_four_demo_panels_still_exist_in_console() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    # Legacy panels preserved in Console (demo_view_frame)
    assert "Incoming Request" in content
    assert "Automation Progress" in content
    assert "Business Result" in content
    assert "Approval / Evidence" in content
