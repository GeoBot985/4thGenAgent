from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.sheet_write_tool import (
    SHEET_WRITE_AUDIT_EVENT_BLOCKED,
    SHEET_WRITE_AUDIT_EVENT_EXECUTED,
    SHEET_WRITE_TOOL_KEY,
    build_sheet_write_audit_event,
    build_sheet_write_report,
    write_sheet_write_report,
)


class TestBuildSheetWriteReport(unittest.TestCase):
    def _report(self, **overrides) -> dict:
        defaults = dict(
            frame_id="frame-001",
            action_id="pa-001",
            spreadsheet_id="sheet-abc123",
            range_name="ExceptionRegister!A:H",
            write_mode="append",
            row_count=3,
        )
        defaults.update(overrides)
        return build_sheet_write_report(**defaults)

    def test_report_type_is_sheet_write_attempt(self):
        report = self._report()
        self.assertEqual(report["report_type"], "sheet_write_attempt")

    def test_report_has_generated_at(self):
        report = self._report()
        self.assertIn("generated_at", report)
        self.assertTrue(report["generated_at"])

    def test_report_has_frame_id(self):
        report = self._report()
        self.assertEqual(report["frame_id"], "frame-001")

    def test_report_has_action_id(self):
        report = self._report()
        self.assertEqual(report["action_id"], "pa-001")

    def test_report_has_tool(self):
        report = self._report()
        self.assertEqual(report["tool"], SHEET_WRITE_TOOL_KEY)

    def test_report_has_spreadsheet_id(self):
        report = self._report()
        self.assertEqual(report["spreadsheet_id"], "sheet-abc123")

    def test_report_has_range_name(self):
        report = self._report()
        self.assertEqual(report["range_name"], "ExceptionRegister!A:H")

    def test_report_has_write_mode(self):
        report = self._report()
        self.assertEqual(report["write_mode"], "append")

    def test_report_has_row_count(self):
        report = self._report()
        self.assertEqual(report["row_count"], 3)

    def test_report_written_false_by_default(self):
        report = self._report()
        self.assertFalse(report["written"])

    def test_report_blocked_false_by_default(self):
        report = self._report()
        self.assertFalse(report["blocked"])

    def test_report_has_idempotency_key(self):
        report = self._report(idempotency_key="idem-001")
        self.assertEqual(report["idempotency_key"], "idem-001")

    def test_report_has_business_ref(self):
        report = self._report(business_ref="INV-10042")
        self.assertEqual(report["business_ref"], "INV-10042")

    def test_report_has_approval_record(self):
        report = self._report(approved_by="operator@example.com")
        self.assertEqual(report["approval_record"]["approved_by"], "operator@example.com")

    def test_report_row_payload_not_included(self):
        report = self._report()
        # Row payload must NOT be in the report
        self.assertNotIn("rows", report)
        self.assertNotIn("row_data", report)

    def test_report_updated_range_present(self):
        report = self._report(updated_range="ExceptionRegister!A42:H44")
        self.assertEqual(report["updated_range"], "ExceptionRegister!A42:H44")

    def test_report_includes_expected_headers(self):
        report = self._report(expected_headers=["InvoiceRef", "Type", "Status"])
        self.assertEqual(report["expected_headers"], ["InvoiceRef", "Type", "Status"])

    def test_report_manifest_id_and_profile(self):
        report = self._report(manifest_id="manifest-001", profile="live")
        self.assertEqual(report["manifest_id"], "manifest-001")
        self.assertEqual(report["profile"], "live")


class TestWriteSheetWriteReport(unittest.TestCase):
    def _report(self) -> dict:
        return build_sheet_write_report(
            frame_id="frame-001",
            action_id="pa-001",
            spreadsheet_id="sheet-abc123",
            range_name="ExceptionRegister!A:H",
            write_mode="append",
            row_count=2,
            written=True,
            updated_range="ExceptionRegister!A42:H43",
            idempotency_key="idem-001",
            business_ref="INV-10042",
        )

    def test_writes_json_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self._report()
            result = write_sheet_write_report(report, runtime_data_dir=tmpdir)
            self.assertTrue(result["ok"])
            self.assertTrue(Path(result["json_path"]).is_file())

    def test_writes_md_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self._report()
            result = write_sheet_write_report(report, runtime_data_dir=tmpdir)
            self.assertTrue(result["ok"])
            self.assertTrue(Path(result["md_path"]).is_file())

    def test_json_file_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self._report()
            result = write_sheet_write_report(report, runtime_data_dir=tmpdir)
            data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(data["frame_id"], "frame-001")

    def test_md_file_contains_status_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self._report()
            result = write_sheet_write_report(report, runtime_data_dir=tmpdir)
            md = Path(result["md_path"]).read_text(encoding="utf-8")
            self.assertIn("WRITTEN", md)

    def test_md_file_contains_spreadsheet_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self._report()
            result = write_sheet_write_report(report, runtime_data_dir=tmpdir)
            md = Path(result["md_path"]).read_text(encoding="utf-8")
            self.assertIn("sheet-abc123", md)

    def test_md_file_contains_range_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self._report()
            result = write_sheet_write_report(report, runtime_data_dir=tmpdir)
            md = Path(result["md_path"]).read_text(encoding="utf-8")
            self.assertIn("ExceptionRegister", md)

    def test_md_file_contains_idempotency_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self._report()
            result = write_sheet_write_report(report, runtime_data_dir=tmpdir)
            md = Path(result["md_path"]).read_text(encoding="utf-8")
            self.assertIn("idem-001", md)

    def test_md_file_does_not_contain_row_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self._report()
            result = write_sheet_write_report(report, runtime_data_dir=tmpdir)
            md = Path(result["md_path"]).read_text(encoding="utf-8")
            self.assertIn("payloads are not included", md.lower())

    def test_report_stem_starts_with_sheet_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self._report()
            result = write_sheet_write_report(report, runtime_data_dir=tmpdir)
            json_name = Path(result["json_path"]).name
            self.assertTrue(json_name.startswith("sheet_write_"))

    def test_blocked_report_shows_blocked_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_sheet_write_report(
                frame_id="frame-001",
                action_id="pa-001",
                spreadsheet_id="sheet-abc123",
                range_name="ExceptionRegister!A:H",
                write_mode="append",
                row_count=1,
                blocked=True,
                error_code="LIVE_GUARDRAIL_FAILED",
            )
            result = write_sheet_write_report(report, runtime_data_dir=tmpdir)
            md = Path(result["md_path"]).read_text(encoding="utf-8")
            self.assertIn("BLOCKED", md)


class TestBuildSheetWriteAuditEvent(unittest.TestCase):
    def test_executed_event_has_correct_type(self):
        event = build_sheet_write_audit_event(
            event_type=SHEET_WRITE_AUDIT_EVENT_EXECUTED,
            frame_id="frame-001",
            action_id="pa-001",
            idempotency_key="idem-001",
            business_ref="INV-10042",
            spreadsheet_id="sheet-abc123",
            range_name="ExceptionRegister!A:H",
            updated_range="ExceptionRegister!A42:H44",
            row_count=3,
            approved_by="operator@example.com",
        )
        self.assertEqual(event["event_type"], "LIVE_SHEET_ROWS_WRITTEN")

    def test_blocked_event_has_correct_type(self):
        event = build_sheet_write_audit_event(
            event_type=SHEET_WRITE_AUDIT_EVENT_BLOCKED,
            frame_id="frame-001",
            action_id="pa-001",
            idempotency_key="idem-001",
            business_ref="INV-10042",
            spreadsheet_id="sheet-abc123",
            range_name="ExceptionRegister!A:H",
            error_code="LIVE_GUARDRAIL_FAILED",
            reason="Guardrail check failed.",
        )
        self.assertEqual(event["event_type"], "LIVE_SHEET_WRITE_BLOCKED")

    def test_audit_event_has_tool_key(self):
        event = build_sheet_write_audit_event(
            event_type=SHEET_WRITE_AUDIT_EVENT_EXECUTED,
            frame_id="f",
            action_id="a",
            idempotency_key="i",
            business_ref="ref",
            spreadsheet_id="s",
            range_name="R!A:B",
        )
        self.assertEqual(event["tool"], SHEET_WRITE_TOOL_KEY)

    def test_audit_event_has_executed_at(self):
        event = build_sheet_write_audit_event(
            event_type=SHEET_WRITE_AUDIT_EVENT_EXECUTED,
            frame_id="f",
            action_id="a",
            idempotency_key="i",
            business_ref="ref",
            spreadsheet_id="s",
            range_name="R!A:B",
        )
        self.assertIn("executed_at", event)
        self.assertTrue(event["executed_at"])

    def test_audit_event_has_updated_range(self):
        event = build_sheet_write_audit_event(
            event_type=SHEET_WRITE_AUDIT_EVENT_EXECUTED,
            frame_id="f",
            action_id="a",
            idempotency_key="i",
            business_ref="ref",
            spreadsheet_id="s",
            range_name="R!A:B",
            updated_range="R!A42:B44",
            row_count=3,
        )
        self.assertEqual(event["updated_range"], "R!A42:B44")
        self.assertEqual(event["row_count"], 3)


if __name__ == "__main__":
    unittest.main()
