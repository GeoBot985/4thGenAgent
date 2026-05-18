"""Spec 109 — Event Source Route Alignment tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.event_source_route_alignment import validate_event_source_route_alignment


def _write_routes(tmp: Path, routes: list[dict]) -> Path:
    p = tmp / "event_routes.json"
    p.write_text(json.dumps({"routes": routes}), encoding="utf-8")
    return p


def _write_contracts(tmp: Path, contracts: list[dict]) -> Path:
    p = tmp / "event_source_contracts.json"
    p.write_text(json.dumps({"version": 1, "contracts": contracts}), encoding="utf-8")
    return p


class TestRouteAlignmentResult(unittest.TestCase):

    def test_alignment_returns_ok_structure(self):
        result = validate_event_source_route_alignment()
        for key in ("ok", "route_count", "contract_count", "findings", "mismatches", "warnings"):
            self.assertIn(key, result, f"Missing key: {key}")

    def test_aligned_route_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            routes_path = _write_routes(td, [
                {"route_id": "operator_ui.ping", "source": "operator_ui", "event_type": "manual.ping", "manifest_id": "ping"}
            ])
            contracts_path = _write_contracts(td, [
                {
                    "source_type": "operator_ui",
                    "display_name": "Operator UI",
                    "description": "desc",
                    "delivery_mode": "push",
                    "side_effect_level": "none",
                    "required_payload_fields": [],
                    "optional_payload_fields": [],
                    "allowed_event_types": ["manual.*"],
                    "metadata": {},
                }
            ])
            result = validate_event_source_route_alignment(routes_path=routes_path, contracts_path=contracts_path)
            findings_ok = [f for f in result["findings"] if f["status"] == "OK"]
            self.assertGreater(len(findings_ok), 0)

    def test_mismatched_event_type_is_flagged_as_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            routes_path = _write_routes(td, [
                {"route_id": "gmail.ping", "source": "gmail", "event_type": "manual.ping", "manifest_id": "ping"}
            ])
            contracts_path = _write_contracts(td, [
                {
                    "source_type": "gmail",
                    "display_name": "Gmail",
                    "description": "desc",
                    "delivery_mode": "push",
                    "side_effect_level": "none",
                    "required_payload_fields": ["message_id", "from", "subject"],
                    "optional_payload_fields": [],
                    "allowed_event_types": ["email.*", "gmail.*"],
                    "metadata": {},
                }
            ])
            result = validate_event_source_route_alignment(routes_path=routes_path, contracts_path=contracts_path)
            mismatches = result["mismatches"]
            self.assertGreater(len(mismatches), 0)

    def test_route_with_no_contract_is_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            routes_path = _write_routes(td, [
                {"route_id": "unknown_source.event", "source": "unknown_source", "event_type": "any.event", "manifest_id": "m1"}
            ])
            contracts_path = _write_contracts(td, [])
            result = validate_event_source_route_alignment(routes_path=routes_path, contracts_path=contracts_path)
            no_contract_findings = [f for f in result["findings"] if f["status"] == "NO_CONTRACT"]
            self.assertGreater(len(no_contract_findings), 0)

    def test_unused_contract_is_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            routes_path = _write_routes(td, [])
            contracts_path = _write_contracts(td, [
                {
                    "source_type": "gmail",
                    "display_name": "Gmail",
                    "description": "desc",
                    "delivery_mode": "push",
                    "side_effect_level": "none",
                    "required_payload_fields": [],
                    "optional_payload_fields": [],
                    "allowed_event_types": [],
                    "metadata": {},
                }
            ])
            result = validate_event_source_route_alignment(routes_path=routes_path, contracts_path=contracts_path)
            self.assertIn("gmail", result.get("unused_contracts", []))

    def test_live_routes_file_alignment(self):
        result = validate_event_source_route_alignment()
        self.assertIsInstance(result["findings"], list)
        self.assertGreaterEqual(result["route_count"], 0)


if __name__ == "__main__":
    unittest.main()
