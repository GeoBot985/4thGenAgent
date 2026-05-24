from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.live_execution_ledger import (
    LEDGER_STATUS_EXECUTED,
    LEDGER_STATUS_FAILED,
    LEDGER_STATUS_BLOCKED,
    LEDGER_STATUS_EXECUTING,
    append_ledger_entry,
    build_ledger_entry,
    build_ledger_report,
    get_ledger_entry,
    hash_payload,
    is_idempotency_key_in_ledger,
    read_ledger_entries,
)


def _entry(**overrides) -> dict:
    base = dict(
        frame_id="f1",
        action_id="a1",
        tool="sheet/write_rows",
        idempotency_key="ikey_test_1",
        business_ref="inv-001",
        target_ref="spreadsheet_id_1",
        prepared_payload_hash="hash_abc",
        approved_by="operator",
        worker_identity="worker_1",
        status=LEDGER_STATUS_EXECUTED,
    )
    base.update(overrides)
    return build_ledger_entry(**base)


class TestBuildLedgerEntry(unittest.TestCase):
    def test_entry_has_required_fields(self):
        entry = _entry()
        for field in ("frame_id", "action_id", "tool", "idempotency_key", "business_ref",
                      "target_ref", "prepared_payload_hash", "approved_by", "worker_identity",
                      "status", "recorded_at", "rollback_plan", "execution_result"):
            self.assertIn(field, entry, f"Missing field: {field}")

    def test_entry_has_correct_tool(self):
        entry = _entry(tool="sheet/write_rows")
        self.assertEqual(entry["tool"], "sheet/write_rows")

    def test_entry_has_correct_status(self):
        entry = _entry(status=LEDGER_STATUS_EXECUTED)
        self.assertEqual(entry["status"], LEDGER_STATUS_EXECUTED)

    def test_entry_default_rollback_plan_is_dict(self):
        entry = _entry()
        self.assertIsInstance(entry["rollback_plan"], dict)

    def test_entry_versioned(self):
        entry = _entry()
        self.assertEqual(entry.get("ledger_entry_version"), "1")


class TestAppendAndReadLedger(unittest.TestCase):
    def test_append_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = _entry()
            append_ledger_entry(entry, runtime_data_dir=tmp)
            ledger_path = Path(tmp) / "live_execution" / "live_execution_ledger.jsonl"
            self.assertTrue(ledger_path.is_file())

    def test_read_empty_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = read_ledger_entries(runtime_data_dir=tmp)
            self.assertEqual(entries, [])

    def test_append_and_read_single_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = _entry()
            append_ledger_entry(entry, runtime_data_dir=tmp)
            entries = read_ledger_entries(runtime_data_dir=tmp)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["idempotency_key"], "ikey_test_1")

    def test_append_multiple_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            append_ledger_entry(_entry(idempotency_key="key1"), runtime_data_dir=tmp)
            append_ledger_entry(_entry(idempotency_key="key2"), runtime_data_dir=tmp)
            entries = read_ledger_entries(runtime_data_dir=tmp)
            self.assertEqual(len(entries), 2)


class TestIdempotencyKeyLookup(unittest.TestCase):
    def test_key_found_after_executed_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            append_ledger_entry(_entry(idempotency_key="ikey_a", status=LEDGER_STATUS_EXECUTED), runtime_data_dir=tmp)
            self.assertTrue(is_idempotency_key_in_ledger("ikey_a", runtime_data_dir=tmp))

    def test_key_not_found_in_empty_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(is_idempotency_key_in_ledger("ikey_a", runtime_data_dir=tmp))

    def test_key_not_found_for_failed_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            append_ledger_entry(_entry(idempotency_key="ikey_b", status=LEDGER_STATUS_FAILED), runtime_data_dir=tmp)
            self.assertFalse(is_idempotency_key_in_ledger("ikey_b", runtime_data_dir=tmp))

    def test_key_not_found_for_blocked_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            append_ledger_entry(_entry(idempotency_key="ikey_c", status=LEDGER_STATUS_BLOCKED), runtime_data_dir=tmp)
            self.assertFalse(is_idempotency_key_in_ledger("ikey_c", runtime_data_dir=tmp))

    def test_different_key_not_matched(self):
        with tempfile.TemporaryDirectory() as tmp:
            append_ledger_entry(_entry(idempotency_key="ikey_x", status=LEDGER_STATUS_EXECUTED), runtime_data_dir=tmp)
            self.assertFalse(is_idempotency_key_in_ledger("ikey_y", runtime_data_dir=tmp))


class TestGetLedgerEntry(unittest.TestCase):
    def test_get_entry_returns_most_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            append_ledger_entry(_entry(idempotency_key="ikey_d", status=LEDGER_STATUS_EXECUTING), runtime_data_dir=tmp)
            append_ledger_entry(_entry(idempotency_key="ikey_d", status=LEDGER_STATUS_EXECUTED), runtime_data_dir=tmp)
            found = get_ledger_entry("ikey_d", runtime_data_dir=tmp)
            self.assertIsNotNone(found)
            self.assertEqual(found["status"], LEDGER_STATUS_EXECUTED)

    def test_get_entry_returns_none_for_missing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = get_ledger_entry("ikey_missing", runtime_data_dir=tmp)
            self.assertIsNone(result)


class TestHashPayload(unittest.TestCase):
    def test_hash_is_string(self):
        self.assertIsInstance(hash_payload({"rows": [["a", "b"]]}), str)

    def test_same_payload_same_hash(self):
        payload = {"rows": [["a", "b"]], "sheet": "Sheet1"}
        self.assertEqual(hash_payload(payload), hash_payload(payload))

    def test_different_payload_different_hash(self):
        h1 = hash_payload({"rows": [["a"]]})
        h2 = hash_payload({"rows": [["b"]]})
        self.assertNotEqual(h1, h2)


class TestLedgerReport(unittest.TestCase):
    def test_report_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_ledger_report(runtime_data_dir=tmp)
            self.assertIn("total_entries", report)
            self.assertIn("executed_count", report)
            self.assertIn("failed_count", report)
            self.assertIn("recent_entries", report)

    def test_report_counts_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            append_ledger_entry(_entry(idempotency_key="k1", status=LEDGER_STATUS_EXECUTED), runtime_data_dir=tmp)
            append_ledger_entry(_entry(idempotency_key="k2", status=LEDGER_STATUS_FAILED), runtime_data_dir=tmp)
            report = build_ledger_report(runtime_data_dir=tmp)
            self.assertEqual(report["executed_count"], 1)
            self.assertEqual(report["failed_count"], 1)


if __name__ == "__main__":
    unittest.main()
