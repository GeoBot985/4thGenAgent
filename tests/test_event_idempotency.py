import json
import tempfile
import unittest
from pathlib import Path

from runtime.event_store import get_event, get_indexed_event, intake_event, is_duplicate_event, list_events, load_event_index


def _write_routes(path: Path, routes: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"routes": routes}, indent=2), encoding="utf-8")


class EventIdempotencyTests(unittest.TestCase):
    def test_first_event_creates_taskframe(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            routes_path = runtime_dir / "event_routes.json"
            _write_routes(
                routes_path,
                [
                    {
                        "route_id": "external.stub",
                        "source": "external",
                        "event_type": "stub",
                        "manifest_id": "event.stub",
                        "input_map": {"message": "payload.message"},
                    }
                ],
            )

            result = intake_event(
                {
                    "event_id": "evt-idem-001",
                    "source": "external",
                    "event_type": "stub",
                    "payload": {"message": "hello"},
                    "received_at": "2026-05-01T10:00:00Z",
                },
                runtime_data_dir=runtime_dir,
                manifest_dir="manifests",
                routes_path=str(routes_path),
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "FRAME_CREATED")
            self.assertIsNotNone(result["frame_id"])
            indexed = get_indexed_event("evt-idem-001", runtime_data_dir=runtime_dir)
            self.assertIsNotNone(indexed)
            self.assertEqual(indexed["seen_count"], 1)
            self.assertEqual(indexed["linked_frame_id"], result["frame_id"])

    def test_duplicate_event_does_not_create_second_taskframe(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            routes_path = runtime_dir / "event_routes.json"
            _write_routes(
                routes_path,
                [
                    {
                        "route_id": "external.stub",
                        "source": "external",
                        "event_type": "stub",
                        "manifest_id": "event.stub",
                        "input_map": {"message": "payload.message"},
                    }
                ],
            )
            event = {
                "event_id": "evt-idem-002",
                "source": "external",
                "event_type": "stub",
                "payload": {"message": "hello"},
                "received_at": "2026-05-01T10:00:00Z",
            }

            first = intake_event(event, runtime_data_dir=runtime_dir, manifest_dir="manifests", routes_path=str(routes_path))
            second = intake_event(event, runtime_data_dir=runtime_dir, manifest_dir="manifests", routes_path=str(routes_path))

            self.assertTrue(first["ok"])
            self.assertEqual(second["status"], "DUPLICATE_EVENT")
            self.assertEqual(second["frame_id"], first["frame_id"])
            indexed = get_indexed_event("evt-idem-002", runtime_data_dir=runtime_dir)
            self.assertEqual(indexed["seen_count"], 2)
            events = list_events(runtime_data_dir=runtime_dir)
            self.assertEqual(events[-1]["duplicate"], True)

    def test_duplicate_failed_no_route_event_does_not_reroute(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            routes_path = runtime_dir / "event_routes.json"
            _write_routes(routes_path, [])
            event = {
                "event_id": "evt-idem-no-route",
                "source": "gmail",
                "event_type": "new_email",
                "payload": {"subject": "hello"},
                "received_at": "2026-05-01T10:00:00Z",
            }

            first = intake_event(event, runtime_data_dir=runtime_dir, manifest_dir="manifests", routes_path=str(routes_path))
            second = intake_event(event, runtime_data_dir=runtime_dir, manifest_dir="manifests", routes_path=str(routes_path))

            self.assertEqual(first["status"], "NO_ROUTE")
            self.assertEqual(second["status"], "DUPLICATE_EVENT")
            self.assertIsNone(second["frame_id"])
            self.assertEqual(get_indexed_event("evt-idem-no-route", runtime_data_dir=runtime_dir)["seen_count"], 2)

    def test_invalid_event_is_not_indexed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            routes_path = runtime_dir / "event_routes.json"
            _write_routes(routes_path, [])

            result = intake_event(
                {
                    "source": "external",
                    "event_type": "stub",
                    "payload": {"message": "hello"},
                    "received_at": "2026-05-01T10:00:00Z",
                },
                runtime_data_dir=runtime_dir,
                manifest_dir="manifests",
                routes_path=str(routes_path),
            )

            self.assertEqual(result["status"], "INVALID_EVENT")
            self.assertEqual(load_event_index(str(runtime_dir / "events" / "event_index.json")), {})

    def test_corrected_event_after_invalid_event_can_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            routes_path = runtime_dir / "event_routes.json"
            _write_routes(
                routes_path,
                [
                    {
                        "route_id": "external.stub",
                        "source": "external",
                        "event_type": "stub",
                        "manifest_id": "event.stub",
                        "input_map": {"message": "payload.message"},
                    }
                ],
            )
            invalid = {
                "source": "external",
                "event_type": "stub",
                "payload": {"message": "hello"},
                "received_at": "2026-05-01T10:00:00Z",
            }
            corrected = {
                "event_id": "evt-corrected-001",
                "source": "external",
                "event_type": "stub",
                "payload": {"message": "hello"},
                "received_at": "2026-05-01T10:00:00Z",
            }

            intake_event(invalid, runtime_data_dir=runtime_dir, manifest_dir="manifests", routes_path=str(routes_path))
            result = intake_event(corrected, runtime_data_dir=runtime_dir, manifest_dir="manifests", routes_path=str(routes_path))

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "FRAME_CREATED")
            self.assertIsNotNone(result["frame_id"])
            self.assertIsNotNone(get_event("evt-corrected-001", runtime_data_dir=runtime_dir))
            self.assertIsNotNone(get_indexed_event("evt-corrected-001", runtime_data_dir=runtime_dir))


if __name__ == "__main__":
    unittest.main()
