"""Spec 109 — Event Source Builders tests."""
from __future__ import annotations

import unittest

from runtime.event_source_builders import (
    build_calendar_event,
    build_customer_inbox_event,
    build_gmail_event,
    build_operator_event,
    build_rpa_event,
    build_schedule_event,
    build_sheet_event,
    build_system_event,
)


def _assert_event_shape(tc: unittest.TestCase, ev: dict, expected_source: str) -> None:
    for key in ("event_id", "source", "event_type", "payload", "received_at"):
        tc.assertIn(key, ev, f"Event missing key: {key}")
    tc.assertEqual(ev["source"], expected_source)
    tc.assertIsInstance(ev["payload"], dict)
    tc.assertTrue(str(ev.get("event_id", "")).strip(), "event_id must not be empty")


class TestBuildOperatorEvent(unittest.TestCase):

    def test_builds_operator_event_with_correct_source(self):
        ev = build_operator_event("manual.mock_ping", payload={"message": "test"})
        _assert_event_shape(self, ev, "operator_ui")

    def test_operator_event_carries_payload(self):
        ev = build_operator_event("manual.mock_ping", payload={"message": "hello"})
        self.assertEqual(ev["payload"]["message"], "hello")

    def test_empty_payload_is_valid(self):
        ev = build_operator_event("manual.mock_ping")
        self.assertIsInstance(ev["payload"], dict)


class TestBuildScheduleEvent(unittest.TestCase):

    def test_builds_schedule_event_with_correct_source(self):
        ev = build_schedule_event("daily.low_stock_check", schedule_id="sched-001")
        _assert_event_shape(self, ev, "schedule")

    def test_schedule_id_in_payload(self):
        ev = build_schedule_event("daily.check", schedule_id="sched-abc")
        self.assertEqual(ev["payload"]["schedule_id"], "sched-abc")

    def test_cron_expression_in_payload(self):
        ev = build_schedule_event("daily.check", cron_expression="0 6 * * *")
        self.assertIn("cron_expression", ev["payload"])


class TestBuildCustomerInboxEvent(unittest.TestCase):

    def test_builds_customer_inbox_event(self):
        ev = build_customer_inbox_event("inbound.message", "msg-001", "Where is my order?", "email")
        _assert_event_shape(self, ev, "customer_inbox")

    def test_required_fields_in_payload(self):
        ev = build_customer_inbox_event("inbound.message", "msg-002", "Help", "chat")
        self.assertEqual(ev["payload"]["message_id"], "msg-002")
        self.assertEqual(ev["payload"]["message"], "Help")
        self.assertEqual(ev["payload"]["channel"], "chat")

    def test_optional_customer_id(self):
        ev = build_customer_inbox_event("inbound.message", "msg-003", "Hi", "email", customer_id="cust-1")
        self.assertEqual(ev["payload"]["customer_id"], "cust-1")


class TestBuildGmailEvent(unittest.TestCase):

    def test_builds_gmail_event(self):
        ev = build_gmail_event("email.received", "gmail-001", "user@example.com", "Test subject")
        _assert_event_shape(self, ev, "gmail")

    def test_required_fields_in_payload(self):
        ev = build_gmail_event("email.received", "gmail-002", "sender@example.com", "Re: Order")
        self.assertEqual(ev["payload"]["message_id"], "gmail-002")
        self.assertEqual(ev["payload"]["from"], "sender@example.com")
        self.assertEqual(ev["payload"]["subject"], "Re: Order")

    def test_optional_body(self):
        ev = build_gmail_event("email.received", "gmail-003", "a@b.com", "Sub", body="Hello body")
        self.assertEqual(ev["payload"]["body"], "Hello body")


class TestBuildCalendarEvent(unittest.TestCase):

    def test_builds_calendar_event(self):
        ev = build_calendar_event("calendar.event_start", "cal-001", "Review", "2026-05-17T09:00:00Z")
        _assert_event_shape(self, ev, "calendar")

    def test_required_fields_in_payload(self):
        ev = build_calendar_event("calendar.event_start", "cal-002", "Meeting", "2026-05-17T10:00:00Z")
        self.assertEqual(ev["payload"]["event_id"], "cal-002")
        self.assertEqual(ev["payload"]["title"], "Meeting")
        self.assertEqual(ev["payload"]["start"], "2026-05-17T10:00:00Z")

    def test_optional_attendees(self):
        ev = build_calendar_event("calendar.event_start", "cal-003", "Sync", "2026-05-17T11:00:00Z", attendees=["a@b.com"])
        self.assertEqual(ev["payload"]["attendees"], ["a@b.com"])


class TestBuildSheetEvent(unittest.TestCase):

    def test_builds_sheet_event(self):
        ev = build_sheet_event("sheet.range_updated", "1ABC123", "Payments!A1:Z100")
        _assert_event_shape(self, ev, "sheet")

    def test_required_fields_in_payload(self):
        ev = build_sheet_event("sheet.updated", "sheet-id-001", "A1:B10")
        self.assertEqual(ev["payload"]["spreadsheet_id"], "sheet-id-001")
        self.assertEqual(ev["payload"]["range"], "A1:B10")

    def test_optional_values(self):
        ev = build_sheet_event("sheet.updated", "sid", "A1:B2", values=[[1, 2], [3, 4]])
        self.assertEqual(ev["payload"]["values"], [[1, 2], [3, 4]])


class TestBuildRpaEvent(unittest.TestCase):

    def test_builds_rpa_event(self):
        ev = build_rpa_event("rpa.task_completed", "rpa-001", "form_fill")
        _assert_event_shape(self, ev, "rpa")

    def test_required_fields_in_payload(self):
        ev = build_rpa_event("rpa.done", "rpa-002", "screenshot")
        self.assertEqual(ev["payload"]["task_id"], "rpa-002")
        self.assertEqual(ev["payload"]["task_type"], "screenshot")

    def test_optional_url(self):
        ev = build_rpa_event("rpa.done", "rpa-003", "navigate", url="https://example.com")
        self.assertEqual(ev["payload"]["url"], "https://example.com")


class TestBuildSystemEvent(unittest.TestCase):

    def test_builds_system_event(self):
        ev = build_system_event("health.check", "orchestrator", "health_check_passed")
        _assert_event_shape(self, ev, "system")

    def test_required_fields_in_payload(self):
        ev = build_system_event("lifecycle.started", "runtime", "startup")
        self.assertEqual(ev["payload"]["component"], "runtime")
        self.assertEqual(ev["payload"]["event_name"], "startup")

    def test_optional_severity(self):
        ev = build_system_event("error.raised", "orchestrator", "frame_failed", severity="high")
        self.assertEqual(ev["payload"]["severity"], "high")


if __name__ == "__main__":
    unittest.main()
