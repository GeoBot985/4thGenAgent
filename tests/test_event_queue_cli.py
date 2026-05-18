"""Spec 108 — Event queue CLI command tests."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from runtime.event_store import intake_event
from src.taskframe_cli import main


def _make_event(event_id: str = "evt-cli-001", source: str = "external", event_type: str = "stub") -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "event_type": event_type,
        "payload": {"message": "cli-test"},
        "received_at": "2026-05-17T00:00:00Z",
    }


def _capture_cli(argv: list[str]) -> tuple[int, str, str]:
    """Run CLI and capture stdout/stderr. Returns (returncode, stdout, stderr)."""
    stdout_buf = StringIO()
    stderr_buf = StringIO()
    with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
        try:
            rc = main(argv)
        except SystemExit as exc:
            rc = int(exc.code) if isinstance(exc.code, int) else 1
    return rc, stdout_buf.getvalue(), stderr_buf.getvalue()


class TestCliEventsList(unittest.TestCase):

    def test_cli_events_list_outputs_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-cli-l1"), runtime_data_dir=rd)
            rc, out, _ = _capture_cli(["events", "list", "--runtime-data-dir", str(rd)])
            self.assertEqual(rc, 0)
            self.assertIn("event", out.lower())

    def test_cli_events_list_json_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-cli-l2"), runtime_data_dir=rd)
            rc, out, _ = _capture_cli(["events", "list", "--runtime-data-dir", str(rd), "--json"])
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertIn("events", data)
            self.assertIsInstance(data["events"], list)

    def test_cli_events_list_filter_by_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-cli-l3"), runtime_data_dir=rd)
            rc, out, _ = _capture_cli(
                ["events", "list", "--runtime-data-dir", str(rd), "--status", "ROUTE_NOT_FOUND", "--json"]
            )
            self.assertEqual(rc, 0)
            data = json.loads(out)
            for ev in data.get("events", []):
                self.assertEqual(ev.get("status"), "ROUTE_NOT_FOUND")

    def test_cli_events_list_empty_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            rc, out, _ = _capture_cli(["events", "list", "--runtime-data-dir", str(rd)])
            self.assertEqual(rc, 0)


class TestCliEventsShow(unittest.TestCase):

    def test_cli_events_show_outputs_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-cli-s1"), runtime_data_dir=rd)
            rc, out, _ = _capture_cli(["events", "show", "evt-cli-s1", "--runtime-data-dir", str(rd)])
            self.assertEqual(rc, 0)
            self.assertIn("evt-cli-s1", out)

    def test_cli_events_show_json_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-cli-s2"), runtime_data_dir=rd)
            rc, out, _ = _capture_cli(["events", "show", "evt-cli-s2", "--runtime-data-dir", str(rd), "--json"])
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertEqual(data.get("event_id"), "evt-cli-s2")

    def test_cli_events_show_unknown_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            rc, out, err = _capture_cli(["events", "show", "evt-not-exist-xyz", "--runtime-data-dir", str(rd)])
            self.assertNotEqual(rc, 0)


class TestCliEventsReplayDryRun(unittest.TestCase):

    def test_cli_events_replay_dry_run_outputs_new_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-cli-rdr1"), runtime_data_dir=rd)
            rc, out, _ = _capture_cli(
                ["events", "replay-dry-run", "evt-cli-rdr1", "--runtime-data-dir", str(rd), "--json"]
            )
            data = json.loads(out)
            self.assertEqual(data.get("event_id"), "evt-cli-rdr1")
            self.assertIn("status", data)

    def test_cli_events_replay_dry_run_unknown_event_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            rc, out, _ = _capture_cli(
                ["events", "replay-dry-run", "evt-not-exist-xyz2", "--runtime-data-dir", str(rd), "--json"]
            )
            self.assertNotEqual(rc, 0)
            data = json.loads(out)
            self.assertFalse(data.get("ok"))

    def test_cli_events_replay_dry_run_human_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-cli-rdr2"), runtime_data_dir=rd)
            rc, out, _ = _capture_cli(
                ["events", "replay-dry-run", "evt-cli-rdr2", "--runtime-data-dir", str(rd)]
            )
            self.assertIn("Replay Dry-Run", out)


if __name__ == "__main__":
    unittest.main()
