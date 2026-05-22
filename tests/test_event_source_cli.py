"""Spec 109 — Event Source CLI command tests."""
from __future__ import annotations

import json
import unittest
from io import StringIO
from unittest.mock import patch

from src.taskframe_cli import main


def _capture_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout_buf = StringIO()
    stderr_buf = StringIO()
    with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
        try:
            rc = main(argv)
        except SystemExit as exc:
            rc = int(exc.code) if isinstance(exc.code, int) else 1
    return rc, stdout_buf.getvalue(), stderr_buf.getvalue()


class TestCliEventSourcesList(unittest.TestCase):

    def test_event_sources_list_exits_zero(self):
        rc, out, _ = _capture_cli(["event-sources", "list"])
        self.assertEqual(rc, 0)

    def test_event_sources_list_json_has_contracts(self):
        rc, out, _ = _capture_cli(["event-sources", "list", "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("contracts", data)
        self.assertIsInstance(data["contracts"], list)
        self.assertGreater(data.get("count", 0), 0)

    def test_event_sources_list_includes_known_sources(self):
        rc, out, _ = _capture_cli(["event-sources", "list", "--json"])
        data = json.loads(out)
        source_types = {c.get("source_type") for c in data.get("contracts", [])}
        for expected in ("operator_ui", "schedule", "gmail", "system"):
            self.assertIn(expected, source_types, f"Missing source: {expected}")


class TestCliEventSourcesShow(unittest.TestCase):

    def test_show_known_source_exits_zero(self):
        rc, out, _ = _capture_cli(["event-sources", "show", "operator_ui"])
        self.assertEqual(rc, 0)

    def test_show_json_has_source_type(self):
        rc, out, _ = _capture_cli(["event-sources", "show", "gmail", "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data.get("source_type"), "gmail")

    def test_show_unknown_source_fails(self):
        rc, out, err = _capture_cli(["event-sources", "show", "no_such_source_xyz"])
        self.assertNotEqual(rc, 0)


class TestCliEventSourcesValidate(unittest.TestCase):

    def test_validate_exits_zero(self):
        rc, out, _ = _capture_cli(["event-sources", "validate"])
        self.assertEqual(rc, 0)

    def test_validate_json_has_results(self):
        rc, out, _ = _capture_cli(["event-sources", "validate", "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("results", data)
        self.assertIn("count", data)


class TestCliEventSourcesValidateEvent(unittest.TestCase):

    def test_validate_event_known_source_passes(self):
        event_json = json.dumps({
            "source": "operator_ui",
            "event_type": "manual.ping",
            "payload": {}
        })
        rc, out, _ = _capture_cli(["event-sources", "validate-event", event_json])
        self.assertEqual(rc, 0)

    def test_validate_event_missing_required_field_fails(self):
        event_json = json.dumps({
            "source": "gmail",
            "event_type": "email.received",
            "payload": {}
        })
        rc, out, _ = _capture_cli(["event-sources", "validate-event", event_json, "--json"])
        self.assertNotEqual(rc, 0)
        data = json.loads(out)
        self.assertFalse(data.get("ok"))

    def test_validate_event_unknown_source_passes_with_warning(self):
        event_json = json.dumps({
            "source": "unknown_source_xyz",
            "event_type": "some.event",
            "payload": {}
        })
        rc, out, _ = _capture_cli(["event-sources", "validate-event", event_json, "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertTrue(data.get("ok"))
        self.assertGreater(len(data.get("warnings", [])), 0)


class TestCliEventSourcesRouteAlignment(unittest.TestCase):

    def test_route_alignment_exits_zero(self):
        rc, out, _ = _capture_cli(["event-sources", "route-alignment"])
        self.assertEqual(rc, 0)

    def test_route_alignment_json_has_findings(self):
        rc, out, _ = _capture_cli(["event-sources", "route-alignment", "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("findings", data)
        self.assertIn("route_count", data)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Spec 139 — External event source polling CLI tests
# ---------------------------------------------------------------------------

import sys
import tempfile
from io import StringIO as _StringIO
from unittest.mock import patch as _patch


def _run_esrc_cli(*args: str, rdd: str = "") -> tuple[int, str]:
    from src.taskframe_cli import main as cli_main

    argv = ["taskframe"] + list(args)
    if rdd:
        argv += ["--runtime-data-dir", rdd]
    buf = _StringIO()
    with _patch("sys.stdout", buf), _patch("sys.argv", argv):
        try:
            rc = cli_main()
        except SystemExit as exc:
            rc = int(exc.code) if exc.code is not None else 0
    return rc, buf.getvalue()


class TestSpec139EventSourcesStatus(unittest.TestCase):

    def setUp(self):
        import tempfile as _tmp
        self._tmp = _tmp.TemporaryDirectory()
        self.rdd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_status_exits_zero(self):
        rc, _ = _run_esrc_cli("event-sources", "status", rdd=self.rdd)
        self.assertEqual(rc, 0)

    def test_status_json_has_summary(self):
        rc, out = _run_esrc_cli("event-sources", "status", "--json", rdd=self.rdd)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("summary", data)

    def test_list_sources_empty_json(self):
        rc, out = _run_esrc_cli("event-sources", "list-sources", "--json", rdd=self.rdd)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data["count"], 0)

    def test_create_fixture_json(self):
        rc, out = _run_esrc_cli("event-sources", "create-fixture", "cli139_src", "--json", rdd=self.rdd)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertTrue(data["ok"])

    def test_poll_fixture_json(self):
        _run_esrc_cli("event-sources", "create-fixture", "cli139_poll", rdd=self.rdd)
        rc, out = _run_esrc_cli("event-sources", "poll", "cli139_poll", "--json", rdd=self.rdd)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertTrue(data["ok"])

    def test_poll_enabled_json(self):
        _run_esrc_cli("event-sources", "create-fixture", "cli139_enabled", rdd=self.rdd)
        rc, out = _run_esrc_cli("event-sources", "poll-enabled", "--json", rdd=self.rdd)
        self.assertEqual(rc, 0)

    def test_history_json_empty(self):
        rc, out = _run_esrc_cli("event-sources", "history", "--json", rdd=self.rdd)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data["count"], 0)

    def test_history_json_after_poll(self):
        _run_esrc_cli("event-sources", "create-fixture", "cli139_hist", rdd=self.rdd)
        _run_esrc_cli("event-sources", "poll", "cli139_hist", rdd=self.rdd)
        rc, out = _run_esrc_cli("event-sources", "history", "--json", rdd=self.rdd)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertGreater(data["count"], 0)

    def test_enable_and_disable(self):
        _run_esrc_cli("event-sources", "create-fixture", "cli139_tgl", rdd=self.rdd)
        rc_dis, _ = _run_esrc_cli("event-sources", "disable", "cli139_tgl", rdd=self.rdd)
        self.assertEqual(rc_dis, 0)
        rc_en, _ = _run_esrc_cli("event-sources", "enable", "cli139_tgl", rdd=self.rdd)
        self.assertEqual(rc_en, 0)

    def test_poll_nonexistent_returns_nonzero(self):
        rc, _ = _run_esrc_cli("event-sources", "poll", "nonexistent_src_xyz", rdd=self.rdd)
        self.assertNotEqual(rc, 0)
