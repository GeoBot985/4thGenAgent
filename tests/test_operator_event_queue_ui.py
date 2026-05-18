"""Spec 108 — Operator UI event queue and inspection command tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.event_store import intake_event
from runtime.inspection_commands import InspectionCommandRunner
from runtime.inspection import RunInspector


def _make_event(event_id: str, source: str = "external", event_type: str = "stub") -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "event_type": event_type,
        "payload": {"msg": "ui-test"},
        "received_at": "2026-05-17T00:00:00Z",
    }


class TestOperatorUIContainsEventQueueControls(unittest.TestCase):
    """Verify the operator UI module has the event queue surface."""

    def test_operator_ui_contains_event_queue_controls(self):
        import inspect
        import importlib

        try:
            operator_ui = importlib.import_module("src.operator_ui")
        except ImportError:
            self.skipTest("operator_ui cannot be imported (tkinter unavailable).")
            return

        source = inspect.getsource(operator_ui)
        self.assertIn("group_events_for_queue", source,
                      "operator_ui must use group_events_for_queue for event queue display.")

    def test_operator_data_exports_group_events_for_queue(self):
        from src.operator_data import group_events_for_queue
        self.assertTrue(callable(group_events_for_queue))

    def test_group_events_for_queue_returns_grouped_dict(self):
        from src.operator_data import group_events_for_queue

        events = [
            {"event_id": "e1", "status": "FRAME_CREATED", "linked_frame_id": "f1"},
            {"event_id": "e2", "status": "NO_ROUTE"},
        ]
        frames_by_id = {}
        groups = group_events_for_queue(events, frames_by_id)
        self.assertIsInstance(groups, dict)
        # All events should appear in one of the groups
        all_event_ids = {ev["event_id"] for evs in groups.values() for ev in evs}
        self.assertIn("e1", all_event_ids)
        self.assertIn("e2", all_event_ids)


class TestInspectionCommandSupportsEventsReadOnly(unittest.TestCase):

    def test_inspection_command_supports_events_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-ui-001"), runtime_data_dir=rd)

            inspector = RunInspector(runtime_data_dir=rd)
            result = inspector.list_events(limit=10)
            self.assertTrue(result.ok)
            self.assertIsInstance(result.data, dict)
            self.assertIn("events", result.data)

    def test_inspection_command_runner_events_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-ui-002"), runtime_data_dir=rd)

            inspector = RunInspector(runtime_data_dir=rd)
            runner = InspectionCommandRunner(inspector=inspector)

            # Simulate calling via InspectionCommandRunner._run_action
            result = runner._run_action("events", {"limit": "10"})
            self.assertTrue(result.ok)

    def test_inspection_command_runner_event_detail_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-ui-003"), runtime_data_dir=rd)

            inspector = RunInspector(runtime_data_dir=rd)
            runner = InspectionCommandRunner(inspector=inspector)

            result = runner._run_action("event_detail", {"event_id": "evt-ui-003"})
            self.assertTrue(result.ok)


class TestReplayNotAvailableAsManifestInspectionCommand(unittest.TestCase):
    """Replay is an action and must NOT be available in inspection command runner."""

    def test_replay_is_not_available_as_manifest_inspection_command(self):
        from runtime.inspection_commands import InspectionCommandRunner
        from runtime.errors import InspectionCommandError

        runner = InspectionCommandRunner()
        with self.assertRaises((InspectionCommandError, Exception)):
            runner._run_action("replay_event_dry_run", {"event_id": "evt-some-id"})

    def test_replay_dry_run_not_in_inspection_command_actions(self):
        import inspect
        from runtime import inspection_commands

        source = inspect.getsource(inspection_commands)
        # replay_event_dry_run should not be dispatched as an inspection action
        self.assertNotIn('"replay_event_dry_run"', source)
        self.assertNotIn("'replay_event_dry_run'", source)

    def test_replay_action_available_in_event_queue_module_not_inspection(self):
        from runtime import event_queue
        self.assertTrue(hasattr(event_queue, "replay_event_dry_run"), "replay_event_dry_run must be in event_queue module.")
        from runtime import inspection_commands
        # InspectionCommandRunner should not have a replay method
        runner = InspectionCommandRunner()
        self.assertFalse(hasattr(runner, "replay_event_dry_run"))


if __name__ == "__main__":
    unittest.main()
