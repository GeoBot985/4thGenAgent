from __future__ import annotations

from pathlib import Path


def test_no_procurement_business_logic_in_orchestrator():
    text = Path("runtime/orchestrator.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "procurement",
        "low_stock",
        "reorder",
        "purchase_order",
        "supplier_select",
        "build_draft_po",
        "validate_draft_po",
    ]
    found = [term for term in forbidden if term in text]
    assert not found, f"Procurement logic leaked into orchestrator: {found}"
