from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.taskframe import json_safe


class FilesystemPersistenceBackend:
    backend_name = "filesystem"

    def __init__(self, runtime_data_dir: str | Path = "runtime_data"):
        self.runtime_data_dir = Path(runtime_data_dir)

    def save_taskframe(self, frame: dict[str, Any]) -> None:
        from runtime.persistence import (
            get_audit_path,
            get_frame_dir,
            get_outputs_path,
            get_summary_path,
            get_taskframe_path,
            write_json_atomic,
        )

        frame_id = str(frame.get("frame_id", "") or "")
        if not frame_id:
            raise ValueError("frame_id is required.")
        get_frame_dir(frame_id, self.runtime_data_dir).mkdir(parents=True, exist_ok=True)
        write_json_atomic(get_taskframe_path(frame_id, self.runtime_data_dir), frame)
        write_json_atomic(get_audit_path(frame_id, self.runtime_data_dir), list(frame.get("audit") or []))
        write_json_atomic(get_outputs_path(frame_id, self.runtime_data_dir), dict(frame.get("outputs") or {}))
        write_json_atomic(get_summary_path(frame_id, self.runtime_data_dir), _summary_from_frame_dict(frame))

    def load_taskframe(self, frame_id: str) -> dict[str, Any] | None:
        from runtime.persistence import get_taskframe_path

        path = get_taskframe_path(frame_id, self.runtime_data_dir)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return dict(data) if isinstance(data, dict) else None

    def list_taskframes(self, limit: int = 100) -> list[dict[str, Any]]:
        runs_dir = self.runtime_data_dir / "runs"
        if not runs_dir.is_dir():
            return []
        rows: list[dict[str, Any]] = []
        for path in runs_dir.glob("*/taskframe.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(data, dict):
                rows.append(data)
        rows.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
        return rows[: int(limit)]

    def append_event(self, event: dict[str, Any]) -> None:
        events_dir = self.runtime_data_dir / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        with (events_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(json_safe(event), ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        for event in reversed(self.list_events(limit=10_000_000)):
            if str(event.get("event_id", "")) == event_id:
                return event
        return None

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        path = self.runtime_data_dir / "events" / "events.jsonl"
        return _read_jsonl(path, limit)

    def save_queue_record(self, record: dict[str, Any]) -> None:
        events_dir = self.runtime_data_dir / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        with (events_dir / "event_queue.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(json_safe(record), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        index_path = events_dir / "event_queue_index.json"
        index: dict[str, Any] = {}
        if index_path.is_file():
            try:
                raw = json.loads(index_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    index = raw
            except (json.JSONDecodeError, OSError):
                pass
        event_id = str(record.get("event_id", "") or "")
        if event_id:
            index[event_id] = json_safe(record)
        index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    def get_queue_record(self, event_id: str) -> dict[str, Any] | None:
        index_path = self.runtime_data_dir / "events" / "event_queue_index.json"
        if not index_path.is_file():
            return None
        try:
            raw = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        item = raw.get(event_id) if isinstance(raw, dict) else None
        return dict(item) if isinstance(item, dict) else None

    def list_queue_records(self, limit: int = 100, **filters: Any) -> list[dict[str, Any]]:
        index_path = self.runtime_data_dir / "events" / "event_queue_index.json"
        if not index_path.is_file():
            return []
        try:
            raw = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        records = [dict(v) for v in raw.values()] if isinstance(raw, dict) else []
        for key in ("status", "source", "event_type"):
            value = filters.get(key)
            if value:
                records = [r for r in records if r.get(key) == value]
        records.sort(key=lambda item: str(item.get("received_at") or item.get("updated_at") or ""), reverse=True)
        return records[: int(limit)]

    def save_durable_queue_record(self, record: dict[str, Any]) -> None:
        queue_dir = self.runtime_data_dir / "queue"
        queue_dir.mkdir(parents=True, exist_ok=True)
        with (queue_dir / "durable_queue.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(json_safe(record), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        index_path = queue_dir / "durable_queue_index.json"
        index: dict[str, Any] = {}
        if index_path.is_file():
            try:
                raw = json.loads(index_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    index = raw
            except (json.JSONDecodeError, OSError):
                pass
        queue_id = str(record.get("queue_id", "") or "")
        if queue_id:
            index[queue_id] = json_safe(record)
        index_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def get_durable_queue_record(self, queue_id: str) -> dict[str, Any] | None:
        index_path = self.runtime_data_dir / "queue" / "durable_queue_index.json"
        if not index_path.is_file():
            return None
        try:
            raw = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        item = raw.get(queue_id) if isinstance(raw, dict) else None
        return dict(item) if isinstance(item, dict) else None

    def list_durable_queue_records(self, limit: int = 100, **filters: Any) -> list[dict[str, Any]]:
        index_path = self.runtime_data_dir / "queue" / "durable_queue_index.json"
        if not index_path.is_file():
            return []
        try:
            raw = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        records = [dict(v) for v in raw.values()] if isinstance(raw, dict) else []
        for key in ("status", "source", "event_type"):
            value = filters.get(key)
            if value:
                records = [r for r in records if r.get(key) == value]
        records.sort(
            key=lambda r: (int(r.get("priority", 100) or 100), str(r.get("available_at") or r.get("created_at") or ""))
        )
        return records[: int(limit)]

    def append_run_ledger_record(self, record: dict[str, Any]) -> None:
        runs_dir = self.runtime_data_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(json_safe(record), ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def list_run_ledger_records(self, limit: int = 100) -> list[dict[str, Any]]:
        return _read_jsonl(self.runtime_data_dir / "runs" / "index.jsonl", limit)

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "backend": self.backend_name,
            "runtime_data_dir": str(self.runtime_data_dir),
            "taskframe_count": _count_files(self.runtime_data_dir / "runs", "*/taskframe.json"),
            "event_count": _count_lines(self.runtime_data_dir / "events" / "events.jsonl"),
            "run_ledger_count": _count_lines(self.runtime_data_dir / "runs" / "index.jsonl"),
        }


def _read_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows[-int(limit):]


def _summary_from_frame_dict(frame: dict[str, Any]) -> dict[str, Any]:
    steps = list(frame.get("steps") or [])
    validations = list(frame.get("validations") or [])
    completion = frame.get("completion_gate_result")
    return json_safe({
        "frame_id": frame.get("frame_id", ""),
        "manifest_id": frame.get("manifest_id", ""),
        "state": frame.get("state", ""),
        "created_at": frame.get("created_at", ""),
        "updated_at": frame.get("updated_at", ""),
        "current_step_id": frame.get("current_step_id"),
        "step_count": len(steps),
        "completed_steps": sum(1 for step in steps if isinstance(step, dict) and step.get("status") == "COMPLETED"),
        "failed_steps": sum(1 for step in steps if isinstance(step, dict) and step.get("status") == "FAILED"),
        "skipped_steps": sum(1 for step in steps if isinstance(step, dict) and step.get("status") == "SKIPPED"),
        "pending_action_count": len(list(frame.get("pending_actions") or [])),
        "executed_action_count": len(list(frame.get("executed_actions") or [])),
        "error_count": len(list(frame.get("errors") or [])),
        "validation_count": len(validations),
        "validation_failed_count": sum(1 for item in validations if isinstance(item, dict) and item.get("ok") is False),
        "output_keys": sorted(dict(frame.get("outputs") or {}).keys()),
        "completion_status": str(completion.get("status", "")) if isinstance(completion, dict) else "",
    })


def _count_files(root: Path, pattern: str) -> int:
    if not root.is_dir():
        return 0
    return sum(1 for _ in root.glob(pattern))


def _count_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count
