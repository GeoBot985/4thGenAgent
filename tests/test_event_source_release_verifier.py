"""Spec 139 — Test: release verifier event source polling check."""
from __future__ import annotations

import unittest


class TestEventSourceReleaseVerifier(unittest.TestCase):

    def test_check_function_importable(self):
        from tools.run_release_candidate_verification import _check_external_event_source_polling
        self.assertTrue(callable(_check_external_event_source_polling))

    def test_check_returns_dict_with_name_and_status(self):
        from tools.run_release_candidate_verification import _check_external_event_source_polling
        result = _check_external_event_source_polling()
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("name"), "external_event_source_polling")
        self.assertIn(result.get("status"), ("PASS", "FAIL"))

    def test_check_passes(self):
        from tools.run_release_candidate_verification import _check_external_event_source_polling
        result = _check_external_event_source_polling()
        missing = result.get("missing") or []
        self.assertEqual(
            result.get("status"), "PASS",
            f"external_event_source_polling check failed: {missing}"
        )

    def test_all_required_imports_present(self):
        from runtime.event_sources.event_source_contract import (
            build_event_source_config,
            build_fixture_source_config,
            validate_event_source_config,
            ADAPTER_FIXTURE_JSON,
            ADAPTER_GMAIL_READONLY,
        )
        from runtime.event_sources.event_source_state import (
            save_event_source,
            get_event_source,
            list_event_sources,
            get_event_source_state,
            list_event_source_history,
            create_event_source,
        )
        from runtime.event_sources.adapters.fixture_json import FixtureJsonAdapter
        from runtime.event_sources.adapters.gmail_readonly import GmailReadonlyAdapter
        from runtime.event_sources.polling_engine import (
            poll_event_source,
            poll_enabled_event_sources,
            enqueue_polled_events,
        )
        from src.operator_event_sources_panel import build_event_sources_panel
        self.assertTrue(True)

    def test_fixture_source_can_be_created_and_polled(self):
        import tempfile
        from pathlib import Path
        from runtime.event_sources.event_source_contract import build_fixture_source_config
        from runtime.event_sources.event_source_state import create_event_source
        from runtime.event_sources.polling_engine import poll_event_source

        fixture_path = str(
            Path(__file__).parent / "fixtures" / "event_sources" / "customer_messages.json"
        )
        with tempfile.TemporaryDirectory() as rdd:
            config = build_fixture_source_config(
                source_id="rv_test_src_01",
                name="RV Test Fixture Source",
                event_source="fixture_customer_inbox",
                event_type="customer_message_received",
                fixture_path=fixture_path,
                enabled=True,
            )
            create_result = create_event_source(config, rdd)
            self.assertTrue(create_result["ok"])

            poll_result = poll_event_source("rv_test_src_01", rdd)
            self.assertTrue(poll_result["ok"])
            self.assertGreater(poll_result["event_count"], 0)

    def test_gmail_adapter_reports_needs_auth_safely(self):
        from runtime.event_sources.adapters.gmail_readonly import GmailReadonlyAdapter

        adapter = GmailReadonlyAdapter()
        config = {
            "source_id": "rv_gmail_test",
            "name": "RV Gmail Test",
            "adapter": "gmail_readonly",
            "mode": "live_read",
            "event_source": "gmail",
            "event_type": "customer_message_received",
            "enabled": False,
            "auth": {"requires_credentials": True},
            "poll": {},
            "dedupe": {},
        }
        health = adapter.health(config)
        self.assertFalse(health["ok"])
        self.assertEqual(health["error_category"], "credentials_missing")

    def test_no_live_side_effects_in_fixture_poll(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from runtime.event_sources.event_source_contract import build_fixture_source_config
        from runtime.event_sources.event_source_state import create_event_source
        from runtime.event_sources.polling_engine import poll_event_source

        fixture_path = str(
            Path(__file__).parent / "fixtures" / "event_sources" / "customer_messages.json"
        )
        with tempfile.TemporaryDirectory() as rdd:
            config = build_fixture_source_config(
                source_id="no_side_effects_src",
                name="No Side Effects Test",
                event_source="fixture_inbox",
                event_type="msg",
                fixture_path=fixture_path,
                enabled=True,
            )
            create_event_source(config, rdd)

            import subprocess
            call_log = []
            original_run = subprocess.run
            with patch("subprocess.run", side_effect=lambda *a, **kw: call_log.append(a) or original_run(*a, **kw)):
                poll_event_source("no_side_effects_src", rdd)

            self.assertEqual(call_log, [], "subprocess.run should not be called during fixture polling")


if __name__ == "__main__":
    unittest.main()
