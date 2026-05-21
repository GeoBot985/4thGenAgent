"""Spec 109 — Release verifier event source contract checks."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.release


class TestEventSourceContractsFileExists(unittest.TestCase):

    def test_event_source_contracts_json_exists(self):
        path = ROOT / "config" / "event_source_contracts.json"
        self.assertTrue(path.is_file(), "config/event_source_contracts.json must exist.")

    def test_event_source_contracts_json_has_eight_builtin_contracts(self):
        path = ROOT / "config" / "event_source_contracts.json"
        self.assertTrue(path.is_file())
        data = json.loads(path.read_text(encoding="utf-8"))
        contracts = data.get("contracts", [])
        self.assertGreaterEqual(len(contracts), 8, "Must have at least 8 built-in contracts.")

    def test_all_builtin_sources_present_in_contracts_file(self):
        path = ROOT / "config" / "event_source_contracts.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        source_types = {c.get("source_type") for c in data.get("contracts", [])}
        required = {"operator_ui", "schedule", "customer_inbox", "gmail", "calendar", "sheet", "rpa", "system"}
        missing = required - source_types
        self.assertFalse(missing, f"Missing contracts for sources: {missing}")


class TestEventSourceContractsAreValid(unittest.TestCase):

    def test_all_contracts_pass_shape_validation(self):
        from runtime.event_source_registry import validate_all_event_source_contracts

        result = validate_all_event_source_contracts()
        self.assertTrue(result.get("ok"), f"Contract validation failed: {result}")

    def test_no_missing_builtin_sources_in_validation(self):
        from runtime.event_source_registry import validate_all_event_source_contracts

        result = validate_all_event_source_contracts()
        self.assertEqual(result.get("missing_builtin_sources", []), [], "All built-in sources must have contracts.")


class TestEventSourceBuildersExist(unittest.TestCase):

    def test_all_eight_builders_importable(self):
        from runtime.event_source_builders import (
            build_calendar_event,
            build_customer_inbox_event,
            build_gmail_event,
            build_operator_event,
            build_rpa_event,
            build_schedule_event,
            build_sheet_event,
            build_system_event,
        )
        for fn in (build_operator_event, build_schedule_event, build_customer_inbox_event,
                   build_gmail_event, build_calendar_event, build_sheet_event, build_rpa_event, build_system_event):
            self.assertTrue(callable(fn))


class TestEventSourceRouteAlignmentIsHealthy(unittest.TestCase):

    def test_route_alignment_check_passes(self):
        from runtime.event_source_route_alignment import validate_event_source_route_alignment

        result = validate_event_source_route_alignment()
        self.assertTrue(result.get("ok"), f"Route alignment failed: {result}")

    def test_route_alignment_has_no_errors(self):
        from runtime.event_source_route_alignment import validate_event_source_route_alignment

        result = validate_event_source_route_alignment()
        self.assertEqual(result.get("errors", []), [])


class TestEventSourceCLIIsRegistered(unittest.TestCase):

    def test_event_sources_subcommand_registered_in_cli(self):
        from src.taskframe_cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["event-sources", "list", "--json"])
        self.assertEqual(args.command, "event-sources")
        self.assertEqual(args.esrc_command, "list")

    def test_all_event_source_subcommands_parseable(self):
        from src.taskframe_cli import build_parser

        parser = build_parser()
        for sub in ("list", "validate"):
            args = parser.parse_args(["event-sources", sub])
            self.assertEqual(args.command, "event-sources")


if __name__ == "__main__":
    unittest.main()
