from runtime.customer_tools import (
    customer_prepare_message_action,
    customer_read,
    customer_validate_owns_order,
)
from runtime.order_tools import order_context_build, order_extract_ref_from_text, order_read
from runtime.payment_tools import payment_read_by_order
from runtime.shipment_tools import shipment_read


def test_order_extract_ref_from_text_finds_ord_reference():
    result = order_extract_ref_from_text("Where is my order ORD-10042?")
    assert result["ok"] is True
    assert result["order_ref"] == "ORD-10042"


def test_order_extract_ref_from_text_fails_without_reference():
    result = order_extract_ref_from_text("Where is my order?")
    assert result["ok"] is False
    assert result["order_ref"] == ""


def test_customer_read_reads_runtime_business_dataset():
    result = customer_read("CUST-1001")
    assert result["ok"] is True
    assert result["customer"]["customer_id"] == "CUST-1001"


def test_order_read_reads_runtime_business_dataset():
    result = order_read("ORD-10042")
    assert result["ok"] is True
    assert result["order"]["order_ref"] == "ORD-10042"


def test_shipment_read_reads_runtime_business_dataset():
    result = shipment_read("ORD-10042")
    assert result["ok"] is True
    assert result["shipment"]["order_ref"] == "ORD-10042"


def test_payment_read_by_order_reads_runtime_business_dataset():
    result = payment_read_by_order("ORD-10042")
    assert result["ok"] is True
    assert result["payment"]["order_ref"] == "ORD-10042"


def test_customer_validate_owns_order_passes_for_matching_customer():
    customer = {"customer_id": "CUST-1001", "name": "Alex Morgan"}
    order = {"order_ref": "ORD-10042", "customer_id": "CUST-1001"}
    result = customer_validate_owns_order(customer, order)
    assert result["ok"] is True


def test_customer_validate_owns_order_fails_for_wrong_customer():
    customer = {"customer_id": "CUST-1004", "name": "Other Customer"}
    order = {"order_ref": "ORD-10042", "customer_id": "CUST-1001"}
    result = customer_validate_owns_order(customer, order)
    assert result["ok"] is False
    assert result["error"] == "CUSTOMER_ORDER_MISMATCH"


def test_order_context_build_outputs_facts():
    customer = {"customer_id": "CUST-1001", "name": "Alex Morgan"}
    order = {"order_ref": "ORD-10042", "customer_id": "CUST-1001", "status": "shipped"}
    shipment = {"shipment_id": "SHIP-5001", "order_ref": "ORD-10042", "status": "in_transit"}
    payment = {"payment_ref": "PAY-1", "order_ref": "ORD-10042", "status": "captured"}
    result = order_context_build(customer, order, shipment, payment)
    assert result["ok"] is True
    assert result["facts"]


def test_customer_prepare_message_action_returns_pending_action_shape():
    customer = {"customer_id": "CUST-1001", "name": "Alex Morgan"}
    result = customer_prepare_message_action(customer, "callcentre", {"reply": "Hello"})
    assert result["ok"] is True
    assert result["action_type"] == "send_customer_message"
    assert result["status"] == "PENDING_APPROVAL"
    assert result["to"] == "CUST-1001"
