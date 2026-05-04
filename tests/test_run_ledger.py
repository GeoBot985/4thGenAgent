import json
import tempfile
import unittest
from pathlib import Path

from runtime.events import create_event
from runtime.manifest_loader import load_manifest
from runtime.persistence import save_taskframe
from runtime.run_ledger import (
    append_ledger_record,
    build_ledger_record,
    find_ledger_record,
    get_ledger_path,
    read_ledger_records,
)
from runtime.runtime_engine import RuntimeEngine
from runtime.taskframe import create_taskframe


class RunLedgerTests(unittest.TestCase):
    def test_get_ledger_path_returns_index_jsonl(self):
        self.assertEqual(get_ledger_path("runtime_data"), Path("runtime_data") / "runs" / "index.jsonl")

    def test_build_ledger_record_contains_expected_fields(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)
        record = build_ledger_record(frame)

        self.assertEqual(record["frame_id"], frame.frame_id)
        self.assertEqual(record["manifest_id"], frame.manifest_id)
        self.assertEqual(record["state"], frame.state)
        self.assertIn("trigger_source", record)
        self.assertIn("trigger_event_type", record)
        self.assertIn("step_count", record)
        self.assertIn("artifact_dir", record)

    def test_append_ledger_record_creates_index_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
            frame = create_taskframe(manifest)
            append_ledger_record(frame, tmp)

            ledger_path = get_ledger_path(tmp)
            self.assertTrue(ledger_path.is_file())
            self.assertEqual(len(ledger_path.read_text(encoding="utf-8").splitlines()), 1)

    def test_append_ledger_record_appends_multiple_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
            frame = create_taskframe(manifest)
            append_ledger_record(frame, tmp)
            append_ledger_record(frame, tmp)

            ledger_path = get_ledger_path(tmp)
            self.assertEqual(len(ledger_path.read_text(encoding="utf-8").splitlines()), 2)

    def test_read_ledger_records_returns_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
            frame = create_taskframe(manifest)
            append_ledger_record(frame, tmp)

            records = read_ledger_records(tmp)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["frame_id"], frame.frame_id)

    def test_read_ledger_records_returns_empty_list_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_ledger_records(tmp), [])

    def test_find_ledger_record_returns_latest_matching_frame_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
            frame = create_taskframe(manifest)
            append_ledger_record(frame, tmp)
            frame.state = "COMPLETED"
            save_taskframe(frame, tmp)
            append_ledger_record(frame, tmp)

            record = find_ledger_record(frame.frame_id, tmp)
            self.assertIsNotNone(record)
            self.assertEqual(record["state"], "COMPLETED")

    def test_find_ledger_record_returns_none_for_missing_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(find_ledger_record("missing", tmp))

    def test_ledger_lines_are_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
            frame = create_taskframe(manifest)
            append_ledger_record(frame, tmp)

            ledger_path = get_ledger_path(tmp)
            for line in ledger_path.read_text(encoding="utf-8").splitlines():
                json.loads(line)

    def test_ledger_latest_record_after_approve_execute_and_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)

            target = engine.handle_event(create_event("manual.whatsapp_stage_send", "manual"), dry_run=True)
            action_id = target.pending_actions[0]["action_id"]
            engine.handle_event(
                create_event(
                    "manual.approve_pending_action",
                    "manual",
                    payload={
                        "frame_id": target.frame_id,
                        "action_id": action_id,
                        "approved_by": "smoke",
                        "reason": "ok",
                    },
                ),
                dry_run=True,
            )
            self.assertEqual(find_ledger_record(target.frame_id, runtime_dir)["state"], "WAITING_FOR_EXECUTE")

            engine.handle_event(
                create_event("manual.execute_approved_pending_actions", "manual", payload={"frame_id": target.frame_id}),
                dry_run=True,
            )
            self.assertEqual(find_ledger_record(target.frame_id, runtime_dir)["state"], "COMPLETED")

            rejected = engine.handle_event(create_event("manual.whatsapp_stage_send", "manual"), dry_run=True)
            reject_action_id = rejected.pending_actions[0]["action_id"]
            engine.handle_event(
                create_event(
                    "manual.reject_pending_action",
                    "manual",
                    payload={
                        "frame_id": rejected.frame_id,
                        "action_id": reject_action_id,
                        "rejected_by": "smoke",
                        "reason": "bad",
                    },
                ),
                dry_run=True,
            )
            self.assertEqual(find_ledger_record(rejected.frame_id, runtime_dir)["state"], "FAILED_COMPLETION")


if __name__ == "__main__":
    unittest.main()
