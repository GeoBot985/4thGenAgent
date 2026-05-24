"""Spec 156 — InvoiceOps posting approval pack tests."""
from __future__ import annotations

import pytest
from runtime.invoiceops_live_posting import build_invoiceops_live_posting_plan
from runtime.invoiceops_posting_approval_pack import (
    build_invoiceops_posting_approval_pack,
    APPROVAL_CHECKLIST_ITEMS,
)


def _empty_plan():
    return build_invoiceops_live_posting_plan(
        frame_id="frame_001",
        invoice_id="INV-001",
        invoice_number="INV-001",
        supplier_name="Acme Ltd",
        po_number="PO-001",
        match_status="matched",
        prepared_writes=[],
    )


def _full_invoice():
    return {
        "invoice_id": "INV-001",
        "invoice_number": "INV-001",
        "supplier_name": "Acme Ltd",
        "po_number": "PO-001",
        "invoice_total": 1000.0,
        "subtotal": 900.0,
    }


def test_approval_checklist_items_is_list():
    assert isinstance(APPROVAL_CHECKLIST_ITEMS, list)


def test_approval_checklist_items_has_10_entries():
    assert len(APPROVAL_CHECKLIST_ITEMS) == 10


def test_approval_pack_returns_dict():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan)
    assert isinstance(pack, dict)


def test_approval_pack_has_ok_field():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan)
    assert "ok" in pack


def test_approval_pack_has_invoice_fields():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan, invoice=_full_invoice())
    assert pack["invoice_number"] == "INV-001"
    assert pack["supplier_name"] == "Acme Ltd"


def test_approval_pack_has_approval_checklist():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan)
    assert "approval_checklist" in pack
    assert isinstance(pack["approval_checklist"], list)


def test_approval_checklist_has_at_least_8_items():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan)
    assert len(pack["approval_checklist"]) >= 8


def test_approval_checklist_items_have_passed_field():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan)
    for item in pack["approval_checklist"]:
        assert "passed" in item


def test_approval_checklist_items_have_item_field():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan)
    for item in pack["approval_checklist"]:
        assert "item" in item


def test_approval_pack_has_risk_summary():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan)
    assert "risk_summary" in pack
    assert isinstance(pack["risk_summary"], list)


def test_approval_pack_has_rollback_summary():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan)
    assert "rollback_summary" in pack


def test_approval_pack_has_human_summary():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan, invoice=_full_invoice())
    assert "human_summary" in pack
    assert isinstance(pack["human_summary"], str)


def test_approval_pack_human_summary_contains_invoice_number():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan, invoice=_full_invoice())
    assert "INV-001" in pack["human_summary"]


def test_blocked_match_status_risk_summary_contains_critical():
    plan = build_invoiceops_live_posting_plan(
        frame_id="frame_001",
        invoice_id="INV-001",
        invoice_number="INV-001",
        supplier_name="Acme Ltd",
        po_number="PO-001",
        match_status="blocked",
        prepared_writes=[],
    )
    pack = build_invoiceops_posting_approval_pack(
        posting_plan=plan,
        match_result={"match_status": "blocked"},
    )
    assert any("CRITICAL" in r for r in pack["risk_summary"])


def test_exception_match_status_risk_summary_contains_warning():
    plan = build_invoiceops_live_posting_plan(
        frame_id="frame_001",
        invoice_id="INV-001",
        invoice_number="INV-001",
        supplier_name="Acme Ltd",
        po_number="PO-001",
        match_status="exception",
        prepared_writes=[],
    )
    pack = build_invoiceops_posting_approval_pack(
        posting_plan=plan,
        match_result={"match_status": "exception"},
    )
    assert any("WARNING" in r for r in pack["risk_summary"])


def test_approval_pack_has_generated_at():
    plan = _empty_plan()
    pack = build_invoiceops_posting_approval_pack(posting_plan=plan)
    assert "generated_at" in pack
