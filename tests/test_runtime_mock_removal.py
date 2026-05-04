from pathlib import Path


def test_no_business_mock_branches_in_orchestrator():
    text = Path("runtime/orchestrator.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "mock_order_lookup",
        "mock_event_response",
        "extract_order_id",
        "validate_customer_owns_order",
        "draft_customer_status_reply",
        "validate_customer_status_reply",
        "prepare_pending_customer_message",
        "pending_customer_message_prepared",
        "mock_order_lookup_completed",
        "mock_event_response_created",
    ]
    found = [term for term in forbidden if term in text]
    assert not found, f"Business/mock logic leaked into orchestrator: {found}"
