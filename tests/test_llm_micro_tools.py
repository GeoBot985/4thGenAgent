from __future__ import annotations

import unittest

from runtime.llm_micro_tools import (
    build_micro_tool_prompt,
    normalize_micro_tool_output,
    validate_micro_tool_output,
)


class LLMMicroToolTests(unittest.TestCase):
    def test_extract_order_ref_prompt_contract(self):
        system, prompt = build_micro_tool_prompt("extract_order_ref", {"text": "Please check ORD-10042."})
        self.assertIn("Return JSON only", prompt)
        self.assertIn("Do not choose tools", prompt)
        self.assertIn("Do not invent facts", prompt)
        self.assertIn("bounded extraction/drafting function", system)

    def test_extract_order_ref_validates_good_output(self):
        output = normalize_micro_tool_output(
            "extract_order_ref",
            '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
            {"text": "Please check ORD-10042."},
        )
        validations = validate_micro_tool_output("extract_order_ref", output, {"text": "Please check ORD-10042."})
        self.assertTrue(all(item["ok"] for item in validations))

    def test_extract_order_ref_rejects_bad_order_format(self):
        output = normalize_micro_tool_output(
            "extract_order_ref",
            '{"order_ref": "BAD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
            {"text": "Please check BAD-10042."},
        )
        validations = validate_micro_tool_output("extract_order_ref", output, {"text": "Please check BAD-10042."})
        self.assertTrue(any(item["ok"] is False for item in validations))

    def test_classify_customer_message_rejects_unknown_label(self):
        output = normalize_micro_tool_output(
            "classify_customer_message",
            '{"label": "unknown", "confidence": "high", "reason": "oops"}',
            {"text": "Where is my order?"},
        )
        validations = validate_micro_tool_output("classify_customer_message", output, {"text": "Where is my order?"})
        self.assertTrue(any(item["ok"] is False for item in validations))

    def test_draft_customer_status_reply_rejects_invented_compensation(self):
        output = normalize_micro_tool_output(
            "draft_customer_status_reply",
            '{"reply": "Hi, your order ORD-10042 has shipped.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": true}',
            {},
        )
        validations = validate_micro_tool_output(
            "draft_customer_status_reply",
            output,
            {
                "customer": {"name": "Alex"},
                "order": {"order_id": "ORD-10042", "status": "shipped"},
                "shipment": {"status": "in transit"},
            },
        )
        self.assertTrue(any(item["ok"] is False for item in validations))

    def test_compare_reply_to_facts_requires_bool_ok(self):
        output = normalize_micro_tool_output(
            "compare_reply_to_facts",
            '{"ok": "yes", "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "reply matches"}',
            {},
        )
        validations = validate_micro_tool_output("compare_reply_to_facts", output, {})
        self.assertTrue(any(item["ok"] is False for item in validations))


if __name__ == "__main__":
    unittest.main()
