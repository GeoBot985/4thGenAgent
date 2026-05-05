from __future__ import annotations

from pathlib import Path


def test_orchestrator_contains_no_customer_domain_step_kinds():
    source = Path("runtime/orchestrator.py").read_text(encoding="utf-8")
    forbidden = [
        "extract_order_id",
        "demo_order_lookup",
        "validate_customer_owns_order",
        "draft_customer_status_reply",
        "validate_customer_status_reply",
        "prepare_pending_customer_message",
    ]
    for item in forbidden:
        assert item not in source
