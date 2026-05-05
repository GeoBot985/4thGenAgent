from pathlib import Path


def test_no_business_demo_branches_in_orchestrator():
    text = Path("runtime/orchestrator.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "demo_order_lookup",
        "demo_event_response",
        "extract_order_id",
        "validate_customer_owns_order",
        "draft_customer_status_reply",
        "validate_customer_status_reply",
        "prepare_pending_customer_message",
        "pending_customer_message_prepared",
        "demo_order_lookup_completed",
        "demo_event_response_created",
    ]
    found = [term for term in forbidden if term in text]
    assert not found, f"Business/demo logic leaked into orchestrator: {found}"
