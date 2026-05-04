import json
import tempfile
import unittest
from pathlib import Path

from runtime.errors import SchedulerError
from runtime.scheduler import SchedulerStub


def write_schedules(tmpdir: Path, schedules: list[dict]) -> Path:
    path = tmpdir / "schedules.json"
    path.write_text(json.dumps({"schedules": schedules}, indent=2), encoding="utf-8")
    return path


class SchedulerStubTests(unittest.TestCase):
    def test_load_schedules_loads_valid_schedules(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(
                tmpdir,
                [
                    {
                        "schedule_id": "daily.gmail_check",
                        "event_type": "schedule.gmail_check",
                        "source": "scheduler",
                        "enabled": True,
                        "payload": {},
                    }
                ],
            )
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            schedules = scheduler.load_schedules()

            self.assertEqual(len(schedules), 1)
            self.assertEqual(schedules[0]["schedule_id"], "daily.gmail_check")

    def test_list_enabled_schedules_excludes_disabled_schedules(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(
                tmpdir,
                [
                    {
                        "schedule_id": "daily.gmail_check",
                        "event_type": "schedule.gmail_check",
                        "source": "scheduler",
                        "enabled": True,
                        "payload": {},
                    },
                    {
                        "schedule_id": "disabled.calendar_next",
                        "event_type": "schedule.calendar_next",
                        "source": "scheduler",
                        "enabled": False,
                        "payload": {},
                    },
                ],
            )
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            enabled = scheduler.list_enabled_schedules()

            self.assertEqual(len(enabled), 1)
            self.assertEqual(enabled[0]["schedule_id"], "daily.gmail_check")

    def test_create_event_for_schedule_creates_runtime_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(
                tmpdir,
                [
                    {
                        "schedule_id": "daily.gmail_check",
                        "event_type": "schedule.gmail_check",
                        "source": "scheduler",
                        "enabled": True,
                        "payload": {"max_results": 5},
                    }
                ],
            )
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            event = scheduler.create_event_for_schedule("daily.gmail_check")

            self.assertEqual(event.event_type, "schedule.gmail_check")
            self.assertEqual(event.source, "scheduler")
            self.assertEqual(event.payload, {"max_results": 5})

    def test_unknown_schedule_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(tmpdir, [])
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            with self.assertRaises(SchedulerError):
                scheduler.create_event_for_schedule("missing")

    def test_disabled_schedule_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(
                tmpdir,
                [
                    {
                        "schedule_id": "daily.gmail_check",
                        "event_type": "schedule.gmail_check",
                        "source": "scheduler",
                        "enabled": False,
                        "payload": {},
                    }
                ],
            )
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            with self.assertRaises(SchedulerError):
                scheduler.create_event_for_schedule("daily.gmail_check")

    def test_duplicate_schedule_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(
                tmpdir,
                [
                    {
                        "schedule_id": "daily.gmail_check",
                        "event_type": "schedule.gmail_check",
                        "source": "scheduler",
                        "enabled": True,
                        "payload": {},
                    },
                    {
                        "schedule_id": "daily.gmail_check",
                        "event_type": "schedule.calendar_next",
                        "source": "scheduler",
                        "enabled": True,
                        "payload": {},
                    },
                ],
            )
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            with self.assertRaises(SchedulerError):
                scheduler.load_schedules()

    def test_missing_schedule_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(
                tmpdir,
                [
                    {
                        "event_type": "schedule.gmail_check",
                        "source": "scheduler",
                        "enabled": True,
                        "payload": {},
                    }
                ],
            )
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            with self.assertRaises(SchedulerError):
                scheduler.load_schedules()

    def test_missing_event_type_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(
                tmpdir,
                [
                    {
                        "schedule_id": "daily.gmail_check",
                        "source": "scheduler",
                        "enabled": True,
                        "payload": {},
                    }
                ],
            )
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            with self.assertRaises(SchedulerError):
                scheduler.load_schedules()

    def test_payload_defaults_to_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(
                tmpdir,
                [
                    {
                        "schedule_id": "daily.gmail_check",
                        "event_type": "schedule.gmail_check",
                        "source": "scheduler",
                    }
                ],
            )
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            schedules = scheduler.load_schedules()

            self.assertEqual(schedules[0]["payload"], {})

    def test_payload_must_be_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(
                tmpdir,
                [
                    {
                        "schedule_id": "daily.gmail_check",
                        "event_type": "schedule.gmail_check",
                        "source": "scheduler",
                        "payload": [],
                    }
                ],
            )
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            with self.assertRaises(SchedulerError):
                scheduler.load_schedules()

    def test_create_events_for_all_enabled_returns_one_event_per_enabled_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(
                tmpdir,
                [
                    {
                        "schedule_id": "daily.gmail_check",
                        "event_type": "schedule.gmail_check",
                        "source": "scheduler",
                        "enabled": True,
                        "payload": {},
                    },
                    {
                        "schedule_id": "daily.calendar_next",
                        "event_type": "schedule.calendar_next",
                        "source": "scheduler",
                        "enabled": True,
                        "payload": {"max_results": 5},
                    },
                ],
            )
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            events = scheduler.create_events_for_all_enabled()

            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].event_type, "schedule.gmail_check")
            self.assertEqual(events[1].event_type, "schedule.calendar_next")

    def test_create_events_for_enabled_by_prefix_filters_enabled_schedules(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(
                tmpdir,
                [
                    {
                        "schedule_id": "maintenance.artifact_index_rebuild",
                        "event_type": "maintenance.artifact_index_rebuild",
                        "source": "scheduler",
                        "enabled": True,
                        "payload": {},
                    },
                    {
                        "schedule_id": "schedule.gmail_check",
                        "event_type": "schedule.gmail_check",
                        "source": "scheduler",
                        "enabled": True,
                        "payload": {},
                    },
                    {
                        "schedule_id": "maintenance.disabled",
                        "event_type": "maintenance.disabled",
                        "source": "scheduler",
                        "enabled": False,
                        "payload": {},
                    },
                ],
            )
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            events = scheduler.create_events_for_enabled_by_prefix("maintenance.")

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].event_type, "maintenance.artifact_index_rebuild")

    def test_create_events_for_enabled_by_prefix_rejects_empty_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_schedules(tmpdir, [])
            scheduler = SchedulerStub(tmpdir / "schedules.json")

            with self.assertRaises(SchedulerError):
                scheduler.create_events_for_enabled_by_prefix("")


if __name__ == "__main__":
    unittest.main()
