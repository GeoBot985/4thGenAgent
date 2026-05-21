from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.gmail_send_tool import (
    GMAIL_SEND_TOOL_KEY,
    build_gmail_send_report,
    build_gmail_send_audit_event,
    write_gmail_send_report,
    GMAIL_SEND_AUDIT_EVENT_BLOCKED,
    GMAIL_SEND_AUDIT_EVENT_EXECUTED,
)
from runtime.live_execution_reports import append_live_audit_event


class TestBuildGmailSendReport(unittest.TestCase):
    def _build(self, **overrides) -> dict:
        defaults = dict(
            frame_id="frame-001",
            action_id="pa-001",
            to=["user@example.com"],
            subject="Test Subject",
            message_id="msg-abc",
            sent=True,
            blocked=False,
            idempotency_key="idem-001",
            business_ref="ref-001",
            approved_by="operator@example.com",
        )
        defaults.update(overrides)
        return build_gmail_send_report(**defaults)

    def test_report_type_is_gmail_send_attempt(self):
        report = self._build()
        self.assertEqual(report["report_type"], "gmail_send_attempt")

    def test_tool_is_gmail_send(self):
        report = self._build()
        self.assertEqual(report["tool"], GMAIL_SEND_TOOL_KEY)

    def test_to_recipients_in_report(self):
        report = self._build(to=["a@b.com", "c@d.com"])
        self.assertEqual(report["to"], ["a@b.com", "c@d.com"])

    def test_subject_in_report(self):
        report = self._build(subject="Hello World")
        self.assertEqual(report["subject"], "Hello World")

    def test_body_not_in_report(self):
        report = self._build()
        self.assertNotIn("body", report)

    def test_message_id_in_report(self):
        report = self._build(message_id="msg-xyz")
        self.assertEqual(report["message_id"], "msg-xyz")

    def test_sent_true_when_executed(self):
        report = self._build(sent=True)
        self.assertTrue(report["sent"])

    def test_blocked_false_when_sent(self):
        report = self._build(blocked=False)
        self.assertFalse(report["blocked"])

    def test_blocked_true_when_blocked(self):
        report = self._build(sent=False, blocked=True, message_id="")
        self.assertTrue(report["blocked"])

    def test_idempotency_key_in_report(self):
        report = self._build(idempotency_key="idem-key-abc")
        self.assertEqual(report["idempotency_key"], "idem-key-abc")

    def test_business_ref_in_report(self):
        report = self._build(business_ref="biz-ref-001")
        self.assertEqual(report["business_ref"], "biz-ref-001")

    def test_approval_record_in_report(self):
        report = self._build(approved_by="ops@example.com")
        self.assertEqual(report["approval_record"]["approved_by"], "ops@example.com")

    def test_generated_at_present(self):
        report = self._build()
        self.assertIn("generated_at", report)
        self.assertTrue(report["generated_at"])


class TestGmailSendReportBodySecurity(unittest.TestCase):
    """Body must never appear in reports."""

    def test_build_report_never_includes_body(self):
        report = build_gmail_send_report(
            frame_id="f",
            action_id="a",
            to=["r@example.com"],
            subject="Sub",
        )
        self.assertNotIn("body", report)
        report_str = json.dumps(report)
        self.assertNotIn("sensitive-body-content", report_str)

    def test_markdown_report_does_not_contain_body(self):
        from runtime.gmail_send_tool import _build_gmail_report_md
        report = build_gmail_send_report(
            frame_id="f",
            action_id="a",
            to=["r@example.com"],
            subject="Sub",
        )
        md = _build_gmail_report_md(report)
        self.assertNotIn("body", md.lower()[:50])  # header check
        self.assertIn("body is not included", md.lower())


class TestWriteGmailSendReport(unittest.TestCase):
    def test_write_creates_json_and_md(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_gmail_send_report(
                frame_id="frame-001",
                action_id="pa-001",
                to=["user@example.com"],
                subject="Test",
                sent=True,
            )
            result = write_gmail_send_report(report, runtime_data_dir=tmpdir)
            self.assertTrue(result["ok"])
            self.assertTrue(Path(result["json_path"]).is_file())
            self.assertTrue(Path(result["md_path"]).is_file())

    def test_json_path_has_email_send_prefix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_gmail_send_report(
                frame_id="frame-001",
                action_id="pa-001",
                to=["user@example.com"],
                subject="Test",
            )
            result = write_gmail_send_report(report, runtime_data_dir=tmpdir)
            json_name = Path(result["json_path"]).name
            self.assertTrue(json_name.startswith("email_send_"))

    def test_md_path_has_email_send_prefix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_gmail_send_report(
                frame_id="frame-001",
                action_id="pa-001",
                to=["user@example.com"],
                subject="Test",
            )
            result = write_gmail_send_report(report, runtime_data_dir=tmpdir)
            md_name = Path(result["md_path"]).name
            self.assertTrue(md_name.startswith("email_send_"))

    def test_json_content_is_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_gmail_send_report(
                frame_id="frame-001",
                action_id="pa-001",
                to=["user@example.com"],
                subject="Test",
            )
            result = write_gmail_send_report(report, runtime_data_dir=tmpdir)
            content = json.loads(Path(result["json_path"]).read_text())
            self.assertEqual(content["report_type"], "gmail_send_attempt")

    def test_json_does_not_contain_body(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_gmail_send_report(
                frame_id="frame-001",
                action_id="pa-001",
                to=["user@example.com"],
                subject="Test",
            )
            result = write_gmail_send_report(report, runtime_data_dir=tmpdir)
            content = json.loads(Path(result["json_path"]).read_text())
            self.assertNotIn("body", content)

    def test_reports_in_live_execution_subdir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_gmail_send_report(
                frame_id="frame-001",
                action_id="pa-001",
                to=["user@example.com"],
                subject="Test",
            )
            result = write_gmail_send_report(report, runtime_data_dir=tmpdir)
            json_path = Path(result["json_path"])
            self.assertEqual(json_path.parent.name, "live_execution")


class TestBuildGmailSendAuditEvent(unittest.TestCase):
    def test_executed_event_type(self):
        event = build_gmail_send_audit_event(
            event_type=GMAIL_SEND_AUDIT_EVENT_EXECUTED,
            frame_id="f",
            action_id="a",
            idempotency_key="k",
            to=["r@example.com"],
            subject="S",
            message_id="msg-abc",
        )
        self.assertEqual(event["event_type"], "LIVE_EMAIL_SENT")

    def test_blocked_event_type(self):
        event = build_gmail_send_audit_event(
            event_type=GMAIL_SEND_AUDIT_EVENT_BLOCKED,
            frame_id="f",
            action_id="a",
            idempotency_key="k",
            to=["r@example.com"],
            subject="S",
            error_code="LIVE_PROFILE_NOT_ALLOWED",
        )
        self.assertEqual(event["event_type"], "LIVE_EMAIL_SEND_BLOCKED")

    def test_event_has_tool_key(self):
        event = build_gmail_send_audit_event(
            event_type=GMAIL_SEND_AUDIT_EVENT_EXECUTED,
            frame_id="f",
            action_id="a",
            idempotency_key="k",
            to=["r@example.com"],
            subject="S",
        )
        self.assertEqual(event["tool"], GMAIL_SEND_TOOL_KEY)

    def test_event_does_not_include_body(self):
        event = build_gmail_send_audit_event(
            event_type=GMAIL_SEND_AUDIT_EVENT_EXECUTED,
            frame_id="f",
            action_id="a",
            idempotency_key="k",
            to=["r@example.com"],
            subject="S",
        )
        self.assertNotIn("body", event)

    def test_event_has_recorded_at(self):
        event = build_gmail_send_audit_event(
            event_type=GMAIL_SEND_AUDIT_EVENT_EXECUTED,
            frame_id="f",
            action_id="a",
            idempotency_key="k",
            to=["r@example.com"],
            subject="S",
        )
        self.assertIn("recorded_at", event)
        self.assertTrue(event["recorded_at"])

    def test_event_recipients_present(self):
        event = build_gmail_send_audit_event(
            event_type=GMAIL_SEND_AUDIT_EVENT_EXECUTED,
            frame_id="f",
            action_id="a",
            idempotency_key="k",
            to=["user@example.com"],
            subject="S",
        )
        self.assertEqual(event["to"], ["user@example.com"])


class TestAuditLogAppend(unittest.TestCase):
    def test_audit_event_appended_to_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            event = build_gmail_send_audit_event(
                event_type=GMAIL_SEND_AUDIT_EVENT_EXECUTED,
                frame_id="frame-001",
                action_id="pa-001",
                idempotency_key="idem-001",
                to=["user@example.com"],
                subject="Test",
                message_id="msg-abc",
            )
            append_live_audit_event(event, runtime_data_dir=tmpdir)
            audit_path = Path(tmpdir) / "audit" / "live_side_effect_audit.jsonl"
            self.assertTrue(audit_path.is_file())
            line = audit_path.read_text().strip()
            loaded = json.loads(line)
            self.assertEqual(loaded["event_type"], "LIVE_EMAIL_SENT")

    def test_multiple_events_appended(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                event = build_gmail_send_audit_event(
                    event_type=GMAIL_SEND_AUDIT_EVENT_EXECUTED,
                    frame_id=f"frame-{i}",
                    action_id=f"pa-{i}",
                    idempotency_key=f"idem-{i}",
                    to=["user@example.com"],
                    subject="Test",
                )
                append_live_audit_event(event, runtime_data_dir=tmpdir)
            audit_path = Path(tmpdir) / "audit" / "live_side_effect_audit.jsonl"
            lines = audit_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
