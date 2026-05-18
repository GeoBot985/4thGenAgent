"""Spec 110 — Order Management event route tests."""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from runtime.manifest_catalog import load_event_routes, resolve_event_route


class TestOrderManagementRoutes(unittest.TestCase):
    def _make_event(self, source, event_type, payload=None):
        return {"event_id": "evt-test", "source": source, "event_type": event_type, "payload": payload or {}, "received_at": "2026-05-18T00:00:00Z"}

    def test_order_routes_resolve_to_manifests(self):
        routes = load_event_routes("config/event_routes.json")
        for event_type, manifest_id in [
            ("manual.order_validate_new", "order.validate_new"),
            ("manual.order_reserve_stock", "order.reserve_stock"),
            ("manual.order_release_paid", "order.release_paid"),
            ("manual.order_detect_delayed", "order.detect_delayed"),
            ("manual.order_update_shipment_status", "order.update_shipment_status"),
        ]:
            event = self._make_event("operator_scenario_pack", event_type)
            route = resolve_event_route(event, routes)
            self.assertIsNotNone(route, f"Route not found for {event_type}")
            self.assertEqual(route.get("manifest_id"), manifest_id, f"Wrong manifest for {event_type}")


if __name__ == "__main__":
    unittest.main()
