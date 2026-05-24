from __future__ import annotations

"""Spec 159 — Demo Home cards contain all required demo entries."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_build_demo_card_method_exists() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "_build_demo_card" in content


def test_demo_home_has_customer_support_card() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "Customer Support Demo" in content


def test_demo_home_has_procurement_card() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "Procurement Demo" in content


def test_demo_home_has_invoiceops_card() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "InvoiceOps Bookkeeping Demo" in content


def test_demo_home_has_live_showcase_card() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "Live Bookkeeping Showcase" in content


def test_demo_cards_have_run_button() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "Run Demo" in content or "Run Boundary Demo" in content


def test_demo_cards_use_scenario_ids() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "customer_status_happy_path" in content
    assert "procurement_low_stock_happy_path" in content
    assert "supplier_invoice_match_happy_path" in content


def test_chip_styles_defined() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "Chip.Ready.TLabel" in content
    assert "Chip.Running.TLabel" in content
    assert "Chip.Completed.TLabel" in content
    assert "Chip.Failed.TLabel" in content


def test_demo_card_status_vars_tracked() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "_demo_card_status_vars" in content


def test_demo_home_has_open_console_link() -> None:
    content = (ROOT / "src" / "operator_ui.py").read_text(encoding="utf-8")
    assert "Open Operator Console" in content or "_go_to_console" in content
