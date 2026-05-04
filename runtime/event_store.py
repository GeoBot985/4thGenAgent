from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .events import RuntimeEvent, event_to_dict, validate_event
from .manifest_catalog import load_event_routes, manifest_exists, map_event_inputs, resolve_event_route
from .manifest_loader import load_manifest_by_id
from .orchestrator import Orchestrator
from .persistence import PersistenceManager, ensure_dir
from .taskframe_reload import load_manifest_for_frame, load_taskframe
from .taskframe import utc_now
from .taskframe import json_safe


EVENTS_DIR_NAME = "events"
EVENTS_FILE_NAME = "events.jsonl"
EVENT_INDEX_FILE = "event_index.json"


def get_events_dir(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / EVENTS_DIR_NAME


def get_events_path(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return get_events_dir(runtime_data_dir) / EVENTS_FILE_NAME


def get_event_index_path(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return get_events_dir(runtime_data_dir) / EVENT_INDEX_FILE


def load_event_index(path: str = "runtime_data/events/event_index.json") -> dict[str, Any]:
    index_path = Path(path)
    if not index_path.is_file():
        return {}
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read event index file: {index_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in event index file: {index_path}") from exc
    if not isinstance(raw, dict):
        raise ValueError("Event index file root must be a JSON object.")
    return raw


def save_event_index(index: dict[str, Any], path: str = "runtime_data/events/event_index.json") -> None:
    index_path = Path(path)
    ensure_dir(index_path.parent)
    with index_path.open("w", encoding="utf-8") as handle:
        json.dump(json_safe(index if isinstance(index, dict) else {}), handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def get_indexed_event(event_id: str, runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any] | None:
    if not isinstance(event_id, str) or not event_id.strip():
        return None
    index = load_event_index(str(get_event_index_path(runtime_data_dir)))
    event = index.get(event_id)
    return event if isinstance(event, dict) else None


def is_duplicate_event(event_id: str, runtime_data_dir: str | Path = "runtime_data") -> bool:
    return get_indexed_event(event_id, runtime_data_dir) is not None


def upsert_event_index(event: dict[str, Any], runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    event_id = str(event.get("event_id", "")).strip()
    if not event_id:
        raise ValueError("event_id is required for event index updates.")
    index = load_event_index(str(get_event_index_path(runtime_data_dir)))
    record = dict(index.get(event_id, {}))
    now = utc_now()
    if not record:
        record = {
            "event_id": event_id,
            "status": str(event.get("status", "")),
            "linked_frame_id": event.get("linked_frame_id"),
            "route_id": event.get("route_id"),
            "manifest_id": event.get("manifest_id"),
            "first_seen_at": now,
            "last_seen_at": now,
            "seen_count": 1,
        }
    else:
        record["status"] = str(event.get("status", record.get("status", "")))
        record["linked_frame_id"] = event.get("linked_frame_id", record.get("linked_frame_id"))
        record["route_id"] = event.get("route_id", record.get("route_id"))
        record["manifest_id"] = event.get("manifest_id", record.get("manifest_id"))
        record["last_seen_at"] = now
        record["seen_count"] = int(record.get("seen_count", 0) or 0) + 1
        record.setdefault("first_seen_at", now)
    index[event_id] = record
    save_event_index(index, str(get_event_index_path(runtime_data_dir)))
    return record


def append_event(event: RuntimeEvent | dict[str, Any], runtime_data_dir: str | Path = "runtime_data") -> None:
    record = event_to_dict(event)
    ensure_dir(get_events_dir(runtime_data_dir))
    with get_events_path(runtime_data_dir).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(json_safe(record), ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def list_events(limit: int = 50, runtime_data_dir: str | Path = "runtime_data") -> list[dict[str, Any]]:
    path = get_events_path(runtime_data_dir)
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                events.append(item)
    if limit is None:
        return events
    return events[-int(limit) :]


def get_event(event_id: str, runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any] | None:
    if not isinstance(event_id, str) or not event_id.strip():
        return None
    events = list_events(limit=10_000_000, runtime_data_dir=runtime_data_dir)
    for event in reversed(events):
        if str(event.get("event_id", "")) == event_id:
            return event
    return None


def intake_event(
    event_data: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
    manifest_dir: str | Path = "manifests",
    routes_path: str = "config/event_routes.json",
) -> dict[str, Any]:
    timestamp = utc_now()
    event_record = _normalize_event_record(event_data, timestamp)
    ok, errors = validate_event(event_record)
    if not ok:
        event_record["status"] = "INVALID_EVENT"
        event_record["duplicate"] = False
        event_record["ledger_recorded_at"] = utc_now()
        event_record["errors"] = list(errors)
        append_event(event_record, runtime_data_dir)
        return _result(False, "INVALID_EVENT", event_record.get("event_id"), None, None, None, {}, list(errors))

    event_id = str(event_record.get("event_id", "")).strip()
    duplicate = is_duplicate_event(event_id, runtime_data_dir)
    if duplicate:
        indexed = get_indexed_event(event_id, runtime_data_dir) or {}
        event_record["status"] = "DUPLICATE_EVENT"
        event_record["duplicate"] = True
        event_record["linked_frame_id"] = indexed.get("linked_frame_id")
        event_record["ledger_recorded_at"] = utc_now()
        append_event(event_record, runtime_data_dir)
        upsert_event_index(
            {
                "event_id": event_id,
                "status": "DUPLICATE_EVENT",
                "linked_frame_id": indexed.get("linked_frame_id"),
                "route_id": indexed.get("route_id"),
                "manifest_id": indexed.get("manifest_id"),
            },
            runtime_data_dir,
        )
        return _result(
            True,
            "DUPLICATE_EVENT",
            event_id,
            indexed.get("route_id"),
            indexed.get("manifest_id"),
            indexed.get("linked_frame_id"),
            {},
            [],
        )

    routes = load_event_routes(routes_path)
    route = resolve_event_route(event_record, routes)
    if route is None:
        event_record["status"] = "NO_ROUTE"
        event_record["duplicate"] = False
        event_record["ledger_recorded_at"] = utc_now()
        append_event(event_record, runtime_data_dir)
        upsert_event_index(
            {
                "event_id": event_id,
                "status": "NO_ROUTE",
                "linked_frame_id": None,
                "route_id": None,
                "manifest_id": None,
            },
            runtime_data_dir,
        )
        return _result(False, "NO_ROUTE", event_record.get("event_id"), None, None, None, {}, [])

    mapped_inputs, mapping_errors = map_event_inputs(event_record, route)
    if mapping_errors:
        event_record["status"] = "ROUTE_MAPPING_FAILED"
        event_record["errors"] = list(mapping_errors)
        event_record["duplicate"] = False
        event_record["ledger_recorded_at"] = utc_now()
        append_event(event_record, runtime_data_dir)
        upsert_event_index(
            {
                "event_id": event_id,
                "status": "ROUTE_MAPPING_FAILED",
                "linked_frame_id": None,
                "route_id": route.get("route_id"),
                "manifest_id": route.get("manifest_id"),
            },
            runtime_data_dir,
        )
        return _result(
            False,
            "ROUTE_MAPPING_FAILED",
            event_record.get("event_id"),
            route.get("route_id"),
            route.get("manifest_id"),
            None,
            mapped_inputs,
            list(mapping_errors),
        )

    manifest_id = str(route.get("manifest_id", "")).strip()
    if not manifest_exists(manifest_id, manifest_dir):
        event_record["status"] = "MANIFEST_NOT_FOUND"
        event_record["errors"] = [f"Manifest not found: {manifest_id}"]
        event_record["duplicate"] = False
        event_record["ledger_recorded_at"] = utc_now()
        append_event(event_record, runtime_data_dir)
        upsert_event_index(
            {
                "event_id": event_id,
                "status": "MANIFEST_NOT_FOUND",
                "linked_frame_id": None,
                "route_id": route.get("route_id"),
                "manifest_id": manifest_id,
            },
            runtime_data_dir,
        )
        return _result(
            False,
            "MANIFEST_NOT_FOUND",
            event_record.get("event_id"),
            route.get("route_id"),
            manifest_id,
            None,
            mapped_inputs,
            [f"Manifest not found: {manifest_id}"],
        )

    try:
        manifest = load_manifest_by_id(manifest_id, manifest_dir)
        orchestrator = Orchestrator(runtime_data_dir=runtime_data_dir, manifest_dir=manifest_dir)
        trigger = {
            "kind": "event",
            "event_id": event_record["event_id"],
            "source": event_record["source"],
            "event_type": event_record["event_type"],
            "route_id": route.get("route_id"),
        }
        frame = orchestrator.create_frame_from_manifest(
            manifest,
            trigger=trigger,
            inputs=mapped_inputs,
            raw_input=json.dumps(event_record, sort_keys=True),
        )
        PersistenceManager(runtime_data_dir).save_snapshot(frame)
        event_record["status"] = "FRAME_CREATED"
        event_record["linked_frame_id"] = frame.frame_id
        event_record["duplicate"] = False
        event_record["ledger_recorded_at"] = utc_now()
        append_event(event_record, runtime_data_dir)
        upsert_event_index(
            {
                "event_id": event_id,
                "status": "FRAME_CREATED",
                "linked_frame_id": frame.frame_id,
                "route_id": route.get("route_id"),
                "manifest_id": manifest_id,
            },
            runtime_data_dir,
        )
        return _result(True, "FRAME_CREATED", event_record["event_id"], route.get("route_id"), manifest_id, frame.frame_id, mapped_inputs, [])
    except Exception as exc:
        event_record["status"] = "FAILED"
        event_record["errors"] = [str(exc)]
        event_record["duplicate"] = False
        event_record["ledger_recorded_at"] = utc_now()
        append_event(event_record, runtime_data_dir)
        upsert_event_index(
            {
                "event_id": event_id,
                "status": "FAILED",
                "linked_frame_id": None,
                "route_id": route.get("route_id"),
                "manifest_id": manifest_id,
            },
            runtime_data_dir,
        )
        return _result(False, "FAILED", event_record.get("event_id"), route.get("route_id"), manifest_id, None, mapped_inputs, [str(exc)])


def intake_and_run_event(
    event_data: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
    manifest_dir: str | Path = "manifests",
    routes_path: str = "config/event_routes.json",
) -> dict[str, Any]:
    intake_result = intake_event(
        event_data,
        runtime_data_dir=runtime_data_dir,
        manifest_dir=manifest_dir,
        routes_path=routes_path,
    )
    if intake_result.get("status") != "FRAME_CREATED" or not intake_result.get("frame_id"):
        frame_id = intake_result.get("frame_id")
        outputs: dict[str, Any] = {}
        if isinstance(frame_id, str) and frame_id:
            try:
                frame = load_taskframe(frame_id, runtime_data_dir)
                outputs = dict(frame.outputs)
            except Exception:
                outputs = {}
        return {
            "ok": bool(intake_result.get("ok")),
            "status": str(intake_result.get("status", "FAILED")),
            "event_id": intake_result.get("event_id"),
            "route_id": intake_result.get("route_id"),
            "manifest_id": intake_result.get("manifest_id"),
            "frame_id": intake_result.get("frame_id"),
            "outputs": outputs,
            "errors": list(intake_result.get("errors", [])),
        }

    frame_id = str(intake_result["frame_id"])
    frame = load_taskframe(frame_id, runtime_data_dir)
    manifest = load_manifest_for_frame(frame, manifest_dir)
    orchestrator = Orchestrator(runtime_data_dir=runtime_data_dir, manifest_dir=manifest_dir)
    try:
        frame = orchestrator.prepare_frame(frame)
        frame = orchestrator.run_until_blocked(frame, manifest, dry_run=True)
    except Exception as exc:
        PersistenceManager(runtime_data_dir).save_snapshot(frame)
        return {
            "ok": False,
            "status": getattr(frame, "state", "FAILED"),
            "event_id": intake_result.get("event_id"),
            "route_id": intake_result.get("route_id"),
            "manifest_id": intake_result.get("manifest_id"),
            "frame_id": intake_result.get("frame_id"),
            "outputs": dict(getattr(frame, "outputs", {})),
            "errors": [str(exc)],
        }

    PersistenceManager(runtime_data_dir).save_snapshot(frame)
    return {
        "ok": frame.state in {"COMPLETED", "WAITING_FOR_EXECUTE"},
        "status": frame.state,
        "event_id": intake_result.get("event_id"),
        "route_id": intake_result.get("route_id"),
        "manifest_id": intake_result.get("manifest_id"),
        "frame_id": frame.frame_id,
        "outputs": dict(frame.outputs),
        "errors": list(intake_result.get("errors", [])) + [error.get("message", "") for error in frame.errors if isinstance(error, dict) and error.get("message")],
    }


def _normalize_event_record(event_data: dict[str, Any], received_at: str) -> dict[str, Any]:
    event = dict(event_data or {}) if isinstance(event_data, dict) else {}
    event.setdefault("event_id", "")
    event.setdefault("source", "")
    event.setdefault("event_type", "")
    event.setdefault("payload", {})
    event.setdefault("received_at", received_at)
    event.setdefault("status", "RECEIVED")
    event.setdefault("linked_frame_id", None)
    event.setdefault("duplicate", False)
    event.setdefault("ledger_recorded_at", "")
    if not isinstance(event.get("payload"), dict):
        event["payload"] = event.get("payload")
    return event


def _result(
    ok: bool,
    status: str,
    event_id: str | None,
    route_id: str | None,
    manifest_id: str | None,
    frame_id: str | None,
    inputs: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "event_id": event_id if isinstance(event_id, str) and event_id else None,
        "route_id": route_id if isinstance(route_id, str) and route_id else None,
        "manifest_id": manifest_id,
        "frame_id": frame_id,
        "inputs": dict(inputs),
        "errors": list(errors),
    }
