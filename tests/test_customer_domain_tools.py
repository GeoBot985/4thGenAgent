from __future__ import annotations

import unittest

from runtime.domain_customer_tools import (
    build_customer_status_context,
    customer_order_context_lookup,
    extract_order_ref_from_text,
    prepare_customer_message_action,
    validate_customer_owns_order,
    validate_customer_status_reply,
)


class CustomerDomainToolsTests(unittest.TestCase):
    def test_extract_order_ref_from_text(self):
        result = extract_order_ref_from_text("Where is order ORD-10042?")
        self.assertTrue(result["ok"])
        self.assertEqual(result["order_ref"], "ORD-10042")

    def test_customer_order_context_lookup(self):
        result = customer_order_context_lookup("CUST-1001", "ORD-10042")
        self.assertTrue(result["ok"])
        self.assertEqual(result["customer"]["customer_id"], "CUST-1001")
        self.assertEqual(result["order"]["order_ref"], "ORD-10042")

    def test_validate_customer_owns_order(self):
        result = validate_customer_owns_order("CUST-1001", {"order_ref": "ORD-10042", "customer_id": "CUST-1001"})
        self.assertTrue(result["ok"])

    def test_build_customer_status_context(self):
        result = build_customer_status_context({"customer_id": "CUST-1001", "name": "Alex"}, {"order_ref": "ORD-10042", "customer_id": "CUST-1001", "status": "shipped"}, {"shipment_id": "SHIP-1", "status": "in_transit", "estimated_delivery": "2026-05-03"})
        self.assertTrue(result["ok"])
        self.assertTrue(result["facts"])

    def test_validate_customer_status_reply(self):
        result = validate_customer_status_reply({"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit."}, {"order_ref": "ORD-10042", "status": "shipped"}, {"status": "in_transit"})
        self.assertTrue(result["ok"])

    def test_prepare_customer_message_action(self):
        result = prepare_customer_message_action("CUST-1001", "callcentre", {"reply": "Hello"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["action_type"], "send_customer_message")


if __name__ == "__main__":
    unittest.main()
