from __future__ import annotations

"""Tests for the InvoiceOps Showcase Demo operator UI panel (Spec 158)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_showcase_panel_methods_defined_in_operator_ui() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    for method in (
        "_check_invoiceops_showcase_config",
        "_run_invoiceops_showcase_boundary",
        "_open_invoiceops_showcase_report",
        "iosc_status_var",
        "iosc_details_text",
    ):
        assert method in content, f"Missing in operator_ui.py: {method}"


def test_showcase_panel_buttons_defined() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    for btn_text in (
        "Check Showcase Config",
        "Run Boundary-Only Showcase",
        "Open Showcase Report",
    ):
        assert btn_text in content, f"Missing button text: {btn_text!r}"


def test_showcase_panel_label_defined() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "InvoiceOps Showcase Demo" in content
