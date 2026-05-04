import tempfile
import unittest
from pathlib import Path

from runtime.event_store import get_event, intake_event, list_events
from runtime.events import create_event, validate_event
from runtime.persistence import load_taskframe_dict, taskframe_exists
from runtime.runtime_engine import RuntimeEngine


class ExternalEventIntakeTests(unittest.TestCase):
    def test_valid_event_creates_taskframe(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            event_data = {
                "event_id": "evt-001",
                "source": "external",
                "event_type": "stub",
                "payload": {"message": "hello"},
                "received_at": "2026-05-01T10:00:00Z",
            }

            result = intake_event(event_data, runtime_data_dir=runtime_dir, manifest_dir="manifests")

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "FRAME_CREATED")
            self.assertEqual(result["manifest_id"], "event.stub")
            self.assertIsNotNone(result["frame_id"])
            self.assertTrue(taskframe_exists(result["frame_id"], runtime_dir))
            frame = load_taskframe_dict(result["frame_id"], runtime_dir)
            self.assertEqual(frame["trigger"]["kind"], "event")
            self.assertEqual(frame["trigger"]["event_id"], "evt-001")

            event = get_event("evt-001", runtime_data_dir=runtime_dir)
            self.assertIsNotNone(event)
            self.assertEqual(event["status"], "FRAME_CREATED")
            self.assertEqual(event["linked_frame_id"], result["frame_id"])

    def test_invalid_event_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            event_data = {
                "source": "external",
                "event_type": "stub",
                "payload": {"message": "hello"},
                "received_at": "2026-05-01T10:00:00Z",
            }

            result = intake_event(event_data, runtime_data_dir=runtime_dir, manifest_dir="manifests")

            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "INVALID_EVENT")
            self.assertIsNone(result["frame_id"])
            self.assertTrue(any(error == "event_id" for error in result["errors"]))
            self.assertEqual(list_events(runtime_data_dir=runtime_dir)[-1]["status"], "INVALID_EVENT")

    def test_unknown_event_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            event_data = {
                "event_id": "evt-unknown-001",
                "source": "gmail",
                "event_type": "new_email",
                "payload": {"subject": "test"},
                "received_at": "2026-05-01T10:00:00Z",
            }

            result = intake_event(event_data, runtime_data_dir=runtime_dir, manifest_dir="manifests")

            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "NO_ROUTE")
            self.assertIsNone(result["manifest_id"])
            self.assertIsNone(result["frame_id"])
            self.assertEqual(get_event("evt-unknown-001", runtime_data_dir=runtime_dir)["status"], "NO_ROUTE")

    def test_command_path_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=False)
            frame = engine.handle_event(create_event("manual.gmail_check", "manual"), dry_run=True)
            self.assertIn(frame.state, {"COMPLETED", "COMPLETED_NO_DATA"})

    def test_validate_event_rules(self):
        ok, errors = validate_event(
            {
                "event_id": "evt-1",
                "source": "external",
                "event_type": "stub",
                "payload": {},
                "received_at": "2026-05-01T10:00:00Z",
            }
        )
        self.assertTrue(ok)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
