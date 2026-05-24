from __future__ import annotations

"""Spec 159 — InvoiceOps Showcase guided panel in Demo Home."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_showcase_guided_section_title_in_demo_home() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "InvoiceOps Live Bookkeeping Showcase" in content


def test_showcase_step_1_configure_in_demo_home() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "1. Configure Google Sheet" in content or "Configure Google Sheet" in content


def test_showcase_step_2_prepare_in_demo_home() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "2. Prepare Demo Sheet" in content or "Prepare Demo Sheet" in content


def test_showcase_step_3_run_in_demo_home() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "3. Run Invoice Batch" in content or "Run Invoice Batch" in content


def test_showcase_step_4_review_in_demo_home() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "4. Review Dashboard" in content or "Review Dashboard" in content


def test_showcase_step_5_evidence_in_demo_home() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "5. Open Evidence" in content or "Open Evidence" in content


def test_showcase_run_live_button_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "Run Live Showcase Demo" in content


def test_showcase_open_google_sheet_button_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "Open Google Sheet" in content


def test_showcase_panel_check_config_button() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "Check Config" in content


def test_showcase_prepare_sheet_method_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "_showcase_prepare_sheet" in content


def test_showcase_run_live_prompt_method_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "_showcase_run_live_prompt" in content


def test_showcase_open_google_sheet_method_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "_showcase_open_google_sheet" in content
