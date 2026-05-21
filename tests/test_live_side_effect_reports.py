from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.live_execution_reports import (
    append_live_audit_event,
    build_live_execution_report,
    write_live_execution_report,
)
from runtime.live_side_effect_contract import (
    build_live_blocked_audit_event,
    build_live_executed_audit_event,
    LIVE_PROFILE_NOT_ALLOWED,
)


def _sample_approval_record() -> dict:
    return {"approved_by": "operator", "approved_at": "2026-05-20T10:00:00Z", "approval_reason": "test"}


def _sample_guardrail_result() -> dict:
    return {"ok": True, "guardrail": "sheet_create", "checks": [{"name": "title_present", "ok": True, "message": ""}]}


def _sample_execution_result() -> dict:
    return {"ok": True, "type": "sheet_create_result", "data": {"spreadsheetId": "fake_123"}}


class TestBuildLiveExecutionReport(unittest.TestCase):
    def test_report_contains_required_fields(self):
        report = build_live_execution_report(
            frame_id="frame_1",
            manifest_id="test.manifest",
            profile="live",
            action_id="pa_1",
            tool="sheet/create",
            business_ref="inv-001",
            idempotency_key="ikey_1",
            approval_record=_sample_approval_record(),
            guardrail_result=_sample_guardrail_result(),
            execution_result=_sample_execution_result(),
            blocked=False,
        )
        for field in (
            "report_type",
            "generated_at",
            "frame_id",
            "manifest_id",
            "profile",
            "action_id",
            "tool",
            "business_ref",
            "idempotency_key",
            "approval_record",
            "guardrail_result",
            "execution_result",
            "blocked",
            "executed",
            "error_code",
            "evidence_path",
        ):
            self.assertIn(field, report, field)

    def test_report_type_is_correct(self):
        report = build_live_execution_report(
            frame_id="f1", manifest_id="m1", profile="live", action_id="a1",
            tool="sheet/create", business_ref="", idempotency_key="k1",
            approval_record={}, guardrail_result={}, execution_result=None, blocked=True,
        )
        self.assertEqual(report["report_type"], "live_execution_attempt")

    def test_blocked_report_has_executed_false(self):
        report = build_live_execution_report(
            frame_id="f1", manifest_id="m1", profile="live", action_id="a1",
            tool="sheet/create", business_ref="", idempotency_key="k1",
            approval_record={}, guardrail_result={}, execution_result=None, blocked=True,
        )
        self.assertTrue(report["blocked"])
        self.assertFalse(report["executed"])

    def test_executed_report_has_executed_true(self):
        report = build_live_execution_report(
            frame_id="f1", manifest_id="m1", profile="live", action_id="a1",
            tool="sheet/create", business_ref="", idempotency_key="k1",
            approval_record={}, guardrail_result={}, execution_result={"ok": True}, blocked=False,
        )
        self.assertFalse(report["blocked"])
        self.assertTrue(report["executed"])


class TestWriteLiveExecutionReport(unittest.TestCase):
    def test_writes_json_and_md_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_live_execution_report(
                frame_id="frame_abc",
                manifest_id="test.manifest",
                profile="live",
                action_id="pa_1",
                tool="sheet/create",
                business_ref="inv-001",
                idempotency_key="ikey_1",
                approval_record=_sample_approval_record(),
                guardrail_result=_sample_guardrail_result(),
                execution_result=_sample_execution_result(),
                blocked=False,
            )
            result = write_live_execution_report(report, runtime_data_dir=tmp)

            self.assertTrue(result["ok"], result)
            self.assertTrue(Path(result["json_path"]).is_file())
            self.assertTrue(Path(result["md_path"]).is_file())

    def test_json_report_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_live_execution_report(
                frame_id="frame_xyz",
                manifest_id="m1",
                profile="live",
                action_id="pa_2",
                tool="sheet/create",
                business_ref="ref",
                idempotency_key="ikey_2",
                approval_record=_sample_approval_record(),
                guardrail_result=_sample_guardrail_result(),
                execution_result=_sample_execution_result(),
                blocked=False,
            )
            result = write_live_execution_report(report, runtime_data_dir=tmp)
            content = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(content["frame_id"], "frame_xyz")

    def test_md_report_contains_frame_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_live_execution_report(
                frame_id="frame_md_check",
                manifest_id="m1",
                profile="live",
                action_id="pa_3",
                tool="sheet/create",
                business_ref="ref",
                idempotency_key="ikey_3",
                approval_record=_sample_approval_record(),
                guardrail_result=_sample_guardrail_result(),
                execution_result=None,
                blocked=True,
                error_code="LIVE_PROFILE_NOT_ALLOWED",
            )
            result = write_live_execution_report(report, runtime_data_dir=tmp)
            md_text = Path(result["md_path"]).read_text(encoding="utf-8")
            self.assertIn("frame_md_check", md_text)

    def test_report_file_path_contains_frame_and_action_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_live_execution_report(
                frame_id="frame_path_test",
                manifest_id="m1",
                profile="live",
                action_id="pa_path_test",
                tool="sheet/create",
                business_ref="",
                idempotency_key="ikey",
                approval_record={},
                guardrail_result={},
                execution_result=None,
                blocked=True,
            )
            result = write_live_execution_report(report, runtime_data_dir=tmp)
            json_name = Path(result["json_path"]).name
            self.assertIn("frame_path_test", json_name)
            self.assertIn("pa_path_test", json_name)


class TestAppendLiveAuditEvent(unittest.TestCase):
    def test_executed_event_appended_to_audit_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            event = build_live_executed_audit_event(
                frame_id="frame_1",
                action_id="pa_1",
                tool="sheet/create",
                idempotency_key="ikey_1",
                approved_by="operator",
                guardrail_result={"ok": True},
            )
            append_live_audit_event(event, runtime_data_dir=tmp)
            audit_log = Path(tmp) / "audit" / "live_side_effect_audit.jsonl"
            self.assertTrue(audit_log.is_file())
            lines = [json.loads(line) for line in audit_log.read_text().splitlines() if line.strip()]
            self.assertEqual(lines[0]["event_type"], "LIVE_SIDE_EFFECT_EXECUTED")

    def test_blocked_event_appended_to_audit_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            event = build_live_blocked_audit_event(
                frame_id="frame_1",
                action_id="pa_1",
                tool="sheet/create",
                reason="Profile blocked.",
                error_code=LIVE_PROFILE_NOT_ALLOWED,
            )
            append_live_audit_event(event, runtime_data_dir=tmp)
            audit_log = Path(tmp) / "audit" / "live_side_effect_audit.jsonl"
            lines = [json.loads(line) for line in audit_log.read_text().splitlines() if line.strip()]
            self.assertEqual(lines[0]["event_type"], "LIVE_SIDE_EFFECT_BLOCKED")

    def test_multiple_events_appended_as_separate_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(3):
                event = build_live_blocked_audit_event(
                    frame_id=f"frame_{i}",
                    action_id=f"pa_{i}",
                    tool="sheet/create",
                    reason="blocked",
                    error_code=LIVE_PROFILE_NOT_ALLOWED,
                )
                append_live_audit_event(event, runtime_data_dir=tmp)
            audit_log = Path(tmp) / "audit" / "live_side_effect_audit.jsonl"
            lines = [l for l in audit_log.read_text().splitlines() if l.strip()]
            self.assertEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
