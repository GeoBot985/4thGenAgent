import json
import tempfile
import unittest
from pathlib import Path

from runtime.event_store import intake_event
from runtime.manifest_catalog import load_event_routes, map_event_inputs, resolve_event_route, validate_event_route


class EventToManifestRoutingTests(unittest.TestCase):
    def test_route_config_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            route_path = Path(tmp) / "event_routes.json"
            route_path.write_text(
                json.dumps(
                    {
                        "routes": [
                            {
                                "route_id": "external.stub",
                                "source": "external",
                                "event_type": "stub",
                                "manifest_id": "event.stub",
                                "input_map": {"message": "payload.message"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            routes = load_event_routes(str(route_path))

            self.assertEqual(len(routes), 1)
            self.assertEqual(routes[0]["route_id"], "external.stub")

    def test_valid_event_resolves_route(self):
        routes = [
            {
                "route_id": "external.stub",
                "source": "external",
                "event_type": "stub",
                "manifest_id": "event.stub",
                "input_map": {"message": "payload.message"},
            }
        ]
        event = {
            "event_id": "evt-001",
            "source": "external",
            "event_type": "stub",
            "payload": {"message": "hello"},
            "received_at": "2026-05-01T10:00:00Z",
        }
        route = resolve_event_route(event, routes)
        self.assertIsNotNone(route)
        self.assertEqual(route["route_id"], "external.stub")
        self.assertEqual(route["manifest_id"], "event.stub")

    def test_unmapped_event_returns_no_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = intake_event(
                {
                    "event_id": "evt-002",
                    "source": "gmail",
                    "event_type": "new_email",
                    "payload": {"subject": "hello"},
                    "received_at": "2026-05-01T10:00:00Z",
                },
                runtime_data_dir=tmp,
                manifest_dir="manifests",
                routes_path="config/event_routes.json",
            )

            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "NO_ROUTE")
            self.assertIsNone(result["frame_id"])

    def test_event_payload_maps_to_taskframe_inputs(self):
        route = {
            "route_id": "external.stub",
            "source": "external",
            "event_type": "stub",
            "manifest_id": "event.stub",
            "input_map": {
                "message": "payload.message",
                "customer_id": "payload.customer_id",
                "event_id": "event_id",
            },
        }
        event = {
            "event_id": "evt-003",
            "source": "external",
            "event_type": "stub",
            "payload": {"message": "Where is my order?", "customer_id": "CUST-001"},
            "received_at": "2026-05-01T10:00:00Z",
        }

        mapped, errors = map_event_inputs(event, route)

        self.assertEqual(errors, [])
        self.assertEqual(
            mapped,
            {"message": "Where is my order?", "customer_id": "CUST-001", "event_id": "evt-003"},
        )

    def test_missing_mapped_field_fails_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            route_path = Path(tmp) / "event_routes.json"
            route_path.write_text(
                json.dumps(
                    {
                        "routes": [
                            {
                                "route_id": "external.stub",
                                "source": "external",
                                "event_type": "stub",
                                "manifest_id": "event.stub",
                                "input_map": {
                                    "message": "payload.message",
                                    "customer_id": "payload.customer_id",
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = intake_event(
                {
                    "event_id": "evt-004",
                    "source": "external",
                    "event_type": "stub",
                    "payload": {"message": "hello"},
                    "received_at": "2026-05-01T10:00:00Z",
                },
                runtime_data_dir=tmp,
                manifest_dir="manifests",
                routes_path=str(route_path),
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "ROUTE_MAPPING_FAILED")
            self.assertIsNone(result["frame_id"])
            self.assertTrue(any("payload.customer_id" in error for error in result["errors"]))

    def test_missing_manifest_fails_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            route_path = Path(tmp) / "event_routes.json"
            route_path.write_text(
                json.dumps(
                    {
                        "routes": [
                            {
                                "route_id": "external.bad_manifest",
                                "source": "external",
                                "event_type": "bad_manifest",
                                "manifest_id": "missing.manifest",
                                "input_map": {"message": "payload.message"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = intake_event(
                {
                    "event_id": "evt-005",
                    "source": "external",
                    "event_type": "bad_manifest",
                    "payload": {"message": "hello"},
                    "received_at": "2026-05-01T10:00:00Z",
                },
                runtime_data_dir=tmp,
                manifest_dir="manifests",
                routes_path=str(route_path),
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "MANIFEST_NOT_FOUND")
            self.assertIsNone(result["frame_id"])

    def test_valid_routed_event_creates_taskframe(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = intake_event(
                {
                    "event_id": "evt-006",
                    "source": "external",
                    "event_type": "stub",
                    "payload": {"message": "hello"},
                    "received_at": "2026-05-01T10:00:00Z",
                },
                runtime_data_dir=tmp,
                manifest_dir="manifests",
                routes_path="config/event_routes.json",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "FRAME_CREATED")
            self.assertEqual(result["route_id"], "external.stub")
            self.assertEqual(result["manifest_id"], "event.stub")
            self.assertIsNotNone(result["frame_id"])
            self.assertEqual(result["inputs"]["message"], "hello")


if __name__ == "__main__":
    unittest.main()
