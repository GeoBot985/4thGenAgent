"""Spec 139 — Test: Gmail read-only adapter safety and structure."""
from __future__ import annotations

import unittest

from runtime.event_sources.adapters.gmail_readonly import GmailReadonlyAdapter, _FORBIDDEN_OPERATIONS


def _gmail_config(enabled: bool = True, requires_credentials: bool = True) -> dict:
    return {
        "source_id": "test_gmail_src",
        "name": "Test Gmail Source",
        "adapter": "gmail_readonly",
        "mode": "live_read",
        "event_source": "gmail",
        "event_type": "customer_message_received",
        "enabled": enabled,
        "auth": {"requires_credentials": requires_credentials},
        "poll": {"query": "label:inbox", "max_events_per_poll": 5, "include_body": True},
        "dedupe": {"key_template": "gmail:{message_id}"},
    }


class TestGmailReadonlyAdapterSafety(unittest.TestCase):

    def test_forbidden_operations_defined(self):
        """Forbidden ops must be enumerated in the adapter."""
        for op in ("send", "draft", "archive", "delete", "label", "mark_read", "mark_unread"):
            self.assertIn(op, _FORBIDDEN_OPERATIONS)

    def test_health_returns_needs_auth_without_credentials(self):
        adapter = GmailReadonlyAdapter()
        config = _gmail_config(requires_credentials=True)
        result = adapter.health(config)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "needs_auth")
        self.assertEqual(result["error_category"], "credentials_missing")

    def test_poll_returns_credentials_missing_without_auth(self):
        adapter = GmailReadonlyAdapter()
        config = _gmail_config()
        state = {"source_id": "test_gmail_src", "cursor": {"seen_ids": []}}
        result = adapter.poll(config, state)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "credentials_missing")

    def test_poll_rejects_unsupported_mode(self):
        adapter = GmailReadonlyAdapter()
        config = dict(_gmail_config())
        config["mode"] = "fixture"
        config["auth"] = {"requires_credentials": False}
        state = {"source_id": "test_gmail_src", "cursor": {"seen_ids": []}}
        result = adapter.poll(config, state)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "unsupported_mode")

    def test_adapter_id_is_gmail_readonly(self):
        adapter = GmailReadonlyAdapter()
        self.assertEqual(adapter.adapter_id, "gmail_readonly")

    def test_normalize_produces_standard_shape(self):
        adapter = GmailReadonlyAdapter()
        config = _gmail_config()
        raw = {
            "message_id": "gmsg-001",
            "from": "customer@example.com",
            "subject": "My question",
            "date": "Thu, 21 May 2026 08:00:00 +0000",
            "body": "Hello, I need help.",
        }
        event = adapter.normalize(raw, config)
        self.assertIn("event_id", event)
        self.assertTrue(event["event_id"].startswith("evt_gmail_"))
        self.assertEqual(event["source"], "gmail")
        self.assertEqual(event["event_type"], "customer_message_received")
        self.assertIn("payload", event)
        self.assertEqual(event["payload"]["message_id"], "gmsg-001")
        self.assertEqual(event["payload"]["channel"], "email")

    def test_normalize_body_included_when_include_body_true(self):
        adapter = GmailReadonlyAdapter()
        config = dict(_gmail_config())
        config["poll"] = {"include_body": True}
        raw = {"message_id": "gmsg-002", "body": "Body content here.", "from": "x@y.com"}
        event = adapter.normalize(raw, config)
        self.assertIn("message", event["payload"])

    def test_normalize_body_excluded_when_include_body_false(self):
        adapter = GmailReadonlyAdapter()
        config = dict(_gmail_config())
        config["poll"] = {"include_body": False}
        raw = {"message_id": "gmsg-003", "body": "Secret body.", "from": "x@y.com"}
        event = adapter.normalize(raw, config)
        self.assertNotIn("message", event["payload"])

    def test_gmail_requires_credentials_by_default(self):
        """Gmail source must require credentials unless explicitly overridden."""
        config = _gmail_config()
        self.assertTrue(config["auth"]["requires_credentials"])


class TestGmailReadonlyAdapterNoMutations(unittest.TestCase):
    """Verify no mutation operations are called anywhere in the adapter source."""

    def test_source_code_does_not_call_forbidden_ops(self):
        import inspect
        import runtime.event_sources.adapters.gmail_readonly as mod
        source = inspect.getsource(mod)
        # Check for actual method call patterns (not string constants)
        mutation_api_calls = [
            '.send(', '.trash(', '.archive(', '.delete(', '.modify(',
            '.insert(', '.mark_read(', '.mark_unread(', '.forward(',
            'labels().create', 'messages().send',
        ]
        for bad_call in mutation_api_calls:
            self.assertNotIn(
                bad_call, source,
                f"Forbidden mutation API call found in gmail_readonly adapter: {bad_call!r}"
            )


if __name__ == "__main__":
    unittest.main()
