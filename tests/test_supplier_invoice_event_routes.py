from __future__ import annotations

import json
from pathlib import Path

from runtime.event_router import EventRouter
from runtime.events import create_event


def test_supplier_invoice_route_resolves_to_manifest():
    router = EventRouter("manifests/event_routes.json", "manifests")
    event = create_event("manual.supplier_invoice_match", "operator_scenario_pack", payload={"invoice_ref": "SIN-4001"})
    manifest = router.resolve_manifest(event)
    assert manifest.manifest_id == "supplier_invoice.match_to_po_receipt"


def test_supplier_invoice_route_entry_exists():
    routes = json.loads(Path("manifests/event_routes.json").read_text(encoding="utf-8"))
    route = next(route for route in routes["routes"] if route.get("route_id") == "operator.supplier_invoice_match")
    assert route["enabled"] is True
    assert route["manifest_id"] == "supplier_invoice.match_to_po_receipt"
