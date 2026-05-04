from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import SchedulerError
from .events import RuntimeEvent, create_event


class SchedulerStub:
    def __init__(self, schedules_path: str | Path = "manifests/schedules.json"):
        self.schedules_path = Path(schedules_path)

    def load_schedules(self) -> list[dict[str, Any]]:
        if not self.schedules_path.is_file():
            raise SchedulerError(f"Schedule file not found: {self.schedules_path}")

        try:
            raw = json.loads(self.schedules_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise SchedulerError(f"Unable to read schedule file: {self.schedules_path}") from exc
        except json.JSONDecodeError as exc:
            raise SchedulerError(f"Invalid JSON in schedule file: {self.schedules_path}") from exc

        if not isinstance(raw, dict):
            raise SchedulerError("Schedule file root must be a JSON object.")

        schedules = raw.get("schedules")
        if not isinstance(schedules, list):
            raise SchedulerError("schedules must be a list.")

        normalized: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for index, schedule in enumerate(schedules):
            if not isinstance(schedule, dict):
                raise SchedulerError(f"Schedule {index} must be an object.")

            schedule_id = schedule.get("schedule_id")
            event_type = schedule.get("event_type")
            source = schedule.get("source")
            payload = schedule.get("payload", {})
            enabled = bool(schedule.get("enabled", True))
            mode = schedule.get("mode", "manual_tick")

            if not isinstance(schedule_id, str) or not schedule_id.strip():
                raise SchedulerError(f"Schedule {index} is missing schedule_id.")
            if schedule_id in seen_ids:
                raise SchedulerError(f"Duplicate schedule_id: {schedule_id}")
            if not isinstance(event_type, str) or not event_type.strip():
                raise SchedulerError(f"Schedule {schedule_id} is missing event_type.")
            if not isinstance(source, str) or not source.strip():
                raise SchedulerError(f"Schedule {schedule_id} is missing source.")
            if not isinstance(payload, dict):
                raise SchedulerError(f"Schedule {schedule_id} payload must be a dict.")

            normalized.append(
                {
                    **schedule,
                    "schedule_id": schedule_id,
                    "event_type": event_type,
                    "source": source,
                    "payload": dict(payload),
                    "enabled": enabled,
                    "mode": mode if isinstance(mode, str) and mode.strip() else "manual_tick",
                }
            )
            seen_ids.add(schedule_id)

        return normalized

    def list_enabled_schedules(self) -> list[dict[str, Any]]:
        return [schedule for schedule in self.load_schedules() if schedule.get("enabled", True)]

    def create_event_for_schedule(self, schedule_id: str) -> RuntimeEvent:
        if not isinstance(schedule_id, str) or not schedule_id.strip():
            raise SchedulerError("schedule_id must be a non-empty string.")

        for schedule in self.load_schedules():
            if schedule["schedule_id"] != schedule_id:
                continue
            if not schedule.get("enabled", True):
                raise SchedulerError(f"Schedule is disabled: {schedule_id}")
            return create_event(
                event_type=schedule["event_type"],
                source=schedule["source"],
                payload=dict(schedule.get("payload", {})),
                metadata={
                    "schedule_id": schedule_id,
                    "mode": schedule.get("mode", "manual_tick"),
                    "description": schedule.get("description", ""),
                },
            )

        raise SchedulerError(f"Unknown schedule: {schedule_id}")

    def create_events_for_all_enabled(self) -> list[RuntimeEvent]:
        return [self.create_event_for_schedule(schedule["schedule_id"]) for schedule in self.list_enabled_schedules()]

    def create_events_for_enabled_by_prefix(self, prefix: str) -> list[RuntimeEvent]:
        if not isinstance(prefix, str) or not prefix.strip():
            raise SchedulerError("prefix must be a non-empty string.")
        prefix = prefix.strip()
        events: list[RuntimeEvent] = []
        for schedule in self.list_enabled_schedules():
            schedule_id = str(schedule.get("schedule_id", ""))
            event_type = str(schedule.get("event_type", ""))
            if schedule_id.startswith(prefix) or event_type.startswith(prefix):
                events.append(self.create_event_for_schedule(schedule_id))
        return events
