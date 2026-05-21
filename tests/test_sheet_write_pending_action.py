from __future__ import annotations

import unittest

from runtime.sheet_write_tool import (
    SHEET_WRITE_TOOL_KEY,
    build_sheet_write_pending_action,
)


class TestSheetWritePendingActionStructure(unittest.TestCase):
    def _build(self, **overrides) -> dict:
        defaults = dict(
            action_id="pa-001",
            business_ref="INV-10042",
            idempotency_key="idem-001",
            spreadsheet_id="sheet-abc123",
            range_name="ExceptionRegister!A:H",
            rows=[["INV-10042", "PO mismatch", "open"]],
            write_mode="append",
        )
        defaults.update(overrides)
        return build_sheet_write_pending_action(**defaults)

    def test_action_id_present(self):
        action = self._build()
        self.assertEqual(action["action_id"], "pa-001")

    def test_tool_is_sheet_write_rows(self):
        action = self._build()
        self.assertEqual(action["tool"], SHEET_WRITE_TOOL_KEY)

    def test_operation_is_side_effect(self):
        action = self._build()
        self.assertEqual(action["operation"], "side_effect")

    def test_status_default_pending_approval(self):
        action = self._build()
        self.assertEqual(action["status"], "PENDING_APPROVAL")

    def test_business_ref_present(self):
        action = self._build()
        self.assertEqual(action["business_ref"], "INV-10042")

    def test_idempotency_key_present(self):
        action = self._build()
        self.assertEqual(action["idempotency_key"], "idem-001")

    def test_live_capable_is_true(self):
        action = self._build()
        self.assertTrue(action["live_capable"])

    def test_live_executed_is_false(self):
        action = self._build()
        self.assertFalse(action["live_executed"])

    def test_live_executed_at_is_empty(self):
        action = self._build()
        self.assertEqual(action["live_executed_at"], "")

    def test_dry_run_executed_is_false(self):
        action = self._build()
        self.assertFalse(action["dry_run_executed"])

    def test_guardrail_result_is_none(self):
        action = self._build()
        self.assertIsNone(action["guardrail_result"])


class TestSheetWritePendingActionPayload(unittest.TestCase):
    def _build(self, **overrides) -> dict:
        defaults = dict(
            action_id="pa-001",
            business_ref="INV-10042",
            idempotency_key="idem-001",
            spreadsheet_id="sheet-abc123",
            range_name="ExceptionRegister!A:H",
            rows=[["INV-10042", "PO mismatch", "open"]],
        )
        defaults.update(overrides)
        return build_sheet_write_pending_action(**defaults)

    def test_payload_has_spreadsheet_id(self):
        action = self._build()
        self.assertEqual(action["payload"]["spreadsheet_id"], "sheet-abc123")

    def test_payload_has_range_name(self):
        action = self._build()
        self.assertEqual(action["payload"]["range_name"], "ExceptionRegister!A:H")

    def test_payload_has_rows(self):
        action = self._build()
        self.assertIsInstance(action["payload"]["rows"], list)
        self.assertEqual(len(action["payload"]["rows"]), 1)

    def test_payload_has_write_mode(self):
        action = self._build()
        self.assertEqual(action["payload"]["write_mode"], "append")

    def test_payload_has_expected_headers(self):
        action = self._build(expected_headers=["InvoiceRef", "ExceptionType", "Status"])
        self.assertEqual(action["payload"]["expected_headers"], ["InvoiceRef", "ExceptionType", "Status"])

    def test_payload_has_source_ref(self):
        action = self._build(source_ref="INV-10042-match-run")
        self.assertEqual(action["payload"]["source_ref"], "INV-10042-match-run")

    def test_default_write_mode_is_append(self):
        action = self._build()
        self.assertEqual(action["payload"]["write_mode"], "append")

    def test_rows_are_deep_copied(self):
        original_rows = [["a", "b"]]
        action = self._build(rows=original_rows)
        original_rows[0].append("c")
        self.assertEqual(len(action["payload"]["rows"][0]), 2)


class TestSheetWritePendingActionApprovalFields(unittest.TestCase):
    def test_approved_by_default_empty(self):
        action = build_sheet_write_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            spreadsheet_id="sheet-001",
            range_name="Sheet1!A:B",
            rows=[["x"]],
        )
        self.assertEqual(action["approved_by"], "")

    def test_approved_at_default_empty(self):
        action = build_sheet_write_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            spreadsheet_id="sheet-001",
            range_name="Sheet1!A:B",
            rows=[["x"]],
        )
        self.assertEqual(action["approved_at"], "")

    def test_approved_by_can_be_set(self):
        action = build_sheet_write_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            spreadsheet_id="sheet-001",
            range_name="Sheet1!A:B",
            rows=[["x"]],
            approved_by="operator@example.com",
            approved_at="2026-01-01T00:00:00Z",
            status="APPROVED",
        )
        self.assertEqual(action["approved_by"], "operator@example.com")
        self.assertEqual(action["status"], "APPROVED")


class TestSheetWritePendingActionExample(unittest.TestCase):
    """Verifies the Spec 134 example business use case payload."""

    def test_invoice_exception_register_append(self):
        action = build_sheet_write_pending_action(
            action_id="pa-inv-001",
            business_ref="INV-10042",
            idempotency_key="inv-10042-exception-append-001",
            spreadsheet_id="sheet-abc123",
            range_name="ExceptionRegister!A:H",
            rows=[
                ["INV-10042", "PO mismatch", "Supplier invoice total differs from PO", "open"]
            ],
            write_mode="append",
        )
        self.assertEqual(action["tool"], "sheet/write_rows")
        self.assertEqual(action["payload"]["range_name"], "ExceptionRegister!A:H")
        self.assertEqual(action["payload"]["write_mode"], "append")
        self.assertEqual(len(action["payload"]["rows"]), 1)


if __name__ == "__main__":
    unittest.main()
