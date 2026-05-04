import tempfile
import unittest
from pathlib import Path

from runtime.event_store import intake_and_run_event, intake_event
from runtime.taskframe_reload import load_taskframe


class FirstMockEventWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.runtime_dir = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_mock_ping_event_routes_correctly(self) -> None:
        event = {
            "event_id": "evt-mock-001",
            "source": "external",
            "event_type": "mock_ping",
            "payload": {"message": "hello from event"},
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "FRAME_CREATED")
        self.assertEqual(result["route_id"], "external.mock_ping")
        self.assertEqual(result["manifest_id"], "event.mock_ping")
        self.assertIsNotNone(result["frame_id"])

    def test_mock_ping_event_runs_to_completion(self) -> None:
        event = {
            "event_id": "evt-mock-001",
            "source": "external",
            "event_type": "mock_ping",
            "payload": {"message": "hello from event"},
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_and_run_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "COMPLETED")
        self.assertIsNotNone(result["frame_id"])
        mock_response = result["outputs"]["mock_response"]
        self.assertTrue(mock_response["received"])
        self.assertEqual(mock_response["message"], "hello from event")
        self.assertEqual(mock_response["response"], "Mock event processed: hello from event")

    def test_taskframe_contains_event_trigger_metadata(self) -> None:
        event = {
            "event_id": "evt-mock-001",
            "source": "external",
            "event_type": "mock_ping",
            "payload": {"message": "hello from event"},
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        frame = load_taskframe(result["frame_id"], self.runtime_dir)
        self.assertEqual(
            frame.trigger,
            {
                "kind": "event",
                "event_id": "evt-mock-001",
                "source": "external",
                "event_type": "mock_ping",
                "route_id": "external.mock_ping",
            },
        )

    def test_missing_message_fails_mapping_before_execution(self) -> None:
        event = {
            "event_id": "evt-mock-missing-message",
            "source": "external",
            "event_type": "mock_ping",
            "payload": {},
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "ROUTE_MAPPING_FAILED")
        self.assertIsNone(result["frame_id"])

    def test_duplicate_mock_event_does_not_create_second_frame(self) -> None:
        event = {
            "event_id": "evt-mock-dup-001",
            "source": "external",
            "event_type": "mock_ping",
            "payload": {"message": "hello from event"},
            "received_at": "2026-05-01T10:00:00Z",
        }
        first = intake_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        second = intake_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertTrue(first["ok"])
        self.assertEqual(first["status"], "FRAME_CREATED")
        self.assertTrue(second["ok"])
        self.assertEqual(second["status"], "DUPLICATE_EVENT")
        self.assertEqual(second["frame_id"], first["frame_id"])


if __name__ == "__main__":
    unittest.main()
