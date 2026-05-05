import tempfile
import unittest
from pathlib import Path

from runtime.event_store import intake_and_run_event, intake_event
from runtime.taskframe_reload import load_taskframe


class FirstDemoEventWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.runtime_dir = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_demo_ping_event_routes_correctly(self) -> None:
        event = {
            "event_id": "evt-demo-001",
            "source": "external",
            "event_type": "demo_ping",
            "payload": {"message": "hello from event"},
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "FRAME_CREATED")
        self.assertEqual(result["route_id"], "external.demo_ping")
        self.assertEqual(result["manifest_id"], "event.demo_ping")
        self.assertIsNotNone(result["frame_id"])

    def test_demo_ping_event_runs_to_completion(self) -> None:
        event = {
            "event_id": "evt-demo-001",
            "source": "external",
            "event_type": "demo_ping",
            "payload": {"message": "hello from event"},
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_and_run_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "COMPLETED")
        self.assertIsNotNone(result["frame_id"])
        demo_response = result["outputs"]["demo_response"]
        self.assertTrue(demo_response["received"])
        self.assertEqual(demo_response["message"], "hello from event")
        self.assertEqual(demo_response["response"], "Demo event processed: hello from event")

    def test_taskframe_contains_event_trigger_metadata(self) -> None:
        event = {
            "event_id": "evt-demo-001",
            "source": "external",
            "event_type": "demo_ping",
            "payload": {"message": "hello from event"},
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        frame = load_taskframe(result["frame_id"], self.runtime_dir)
        self.assertEqual(
            frame.trigger,
            {
                "kind": "event",
                "event_id": "evt-demo-001",
                "source": "external",
                "event_type": "demo_ping",
                "route_id": "external.demo_ping",
            },
        )

    def test_missing_message_fails_mapping_before_execution(self) -> None:
        event = {
            "event_id": "evt-demo-missing-message",
            "source": "external",
            "event_type": "demo_ping",
            "payload": {},
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "ROUTE_MAPPING_FAILED")
        self.assertIsNone(result["frame_id"])

    def test_duplicate_demo_event_does_not_create_second_frame(self) -> None:
        event = {
            "event_id": "evt-demo-dup-001",
            "source": "external",
            "event_type": "demo_ping",
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
