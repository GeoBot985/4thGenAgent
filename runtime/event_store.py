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
from .event_queue import (
    STATUS_RECEIVED,
    STATUS_ROUTE_RESOLVED,
    STATUS_ROUTE_NOT_FOUND,
    STATUS_FRAME_CREATED,
    STATUS_RUNNING,
    STATUS_DUPLICATE_EVENT,
    STATUS_FAILED_EXECUTION,
    STATUS_REPLAYED_DRY_RUN,
    build_queue_record,
    build_event_fingerprint,
    frame_state_to_event_status,
    update_queue_record,
    write_queue_record,
    load_queue_record,
)
from .event_failure_reason import derive_event_failure_reason
from .event_source_registry import validate_event_against_source_contract


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
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    if getattr(backend, "backend_name", "filesystem") != "filesystem":
        backend.append_event(record)


def list_events(limit: int = 50, runtime_data_dir: str | Path = "runtime_data") -> list[dict[str, Any]]:
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    if getattr(backend, "backend_name", "filesystem") != "filesystem":
        return backend.list_events(limit=limit if limit is not None else 10_000_000)
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
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    if getattr(backend, "backend_name", "filesystem") != "filesystem":
        return backend.get_event(event_id)
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
    strict_source_contracts: bool = False,
    strict_manifest_preflight: bool = False,
) -> dict[str, Any]:
    timestamp = utc_now()
    event_record = _normalize_event_record(event_data, timestamp)

    # Write initial RECEIVED queue record
    _q = build_queue_record(event_record, status=STATUS_RECEIVED)
    write_queue_record(_q, runtime_data_dir)

    ok, errors = validate_event(event_record)
    if not ok:
        event_record["status"] = "INVALID_EVENT"
        event_record["duplicate"] = False
        event_record["route_id"] = None
        event_record["manifest_id"] = None
        event_record["linked_frame_id"] = None
        event_record["ledger_recorded_at"] = utc_now()
        event_record["errors"] = list(errors)
        append_event(event_record, runtime_data_dir)
        _failure = derive_event_failure_reason(event_record)
        write_queue_record(update_queue_record(_q, status=STATUS_FAILED_EXECUTION, errors=list(errors), failure_code=_failure["failure_code"], failure_reason=_failure["failure_reason"]), runtime_data_dir)
        return _result(False, "INVALID_EVENT", event_record.get("event_id"), None, None, None, {}, list(errors))

    # Source contract validation (non-blocking by default; blocking when strict_source_contracts=True)
    _contract_result = validate_event_against_source_contract(event_record)
    if strict_source_contracts and not bool(_contract_result.get("contract_found", False)):
        _contract_errors = [f"No source contract registered for source '{event_record.get('source', '')}'."]
        event_record["status"] = "SOURCE_CONTRACT_MISSING"
        event_record["duplicate"] = False
        event_record["route_id"] = None
        event_record["manifest_id"] = None
        event_record["linked_frame_id"] = None
        event_record["ledger_recorded_at"] = utc_now()
        event_record["errors"] = _contract_errors
        append_event(event_record, runtime_data_dir)
        write_queue_record(update_queue_record(_q, status=STATUS_FAILED_EXECUTION, errors=_contract_errors, failure_code="EVENT_VALIDATION_FAILED", failure_reason="Event source contract is missing."), runtime_data_dir)
        return _result(False, "SOURCE_CONTRACT_MISSING", event_record.get("event_id"), None, None, None, {}, _contract_errors)
    if strict_source_contracts and bool(_contract_result.get("contract_found", False)) and not _contract_result.get("ok"):
        _contract_errors = _contract_result.get("errors", [])
        event_record["status"] = "SOURCE_CONTRACT_VIOLATION"
        event_record["duplicate"] = False
        event_record["route_id"] = None
        event_record["manifest_id"] = None
        event_record["linked_frame_id"] = None
        event_record["ledger_recorded_at"] = utc_now()
        event_record["errors"] = _contract_errors
        append_event(event_record, runtime_data_dir)
        write_queue_record(update_queue_record(_q, status=STATUS_FAILED_EXECUTION, errors=_contract_errors, failure_code="EVENT_VALIDATION_FAILED", failure_reason="Event payload does not satisfy source contract requirements."), runtime_data_dir)
        return _result(False, "SOURCE_CONTRACT_VIOLATION", event_record.get("event_id"), None, None, None, {}, _contract_errors)

    event_id = str(event_record.get("event_id", "")).strip()
    duplicate = is_duplicate_event(event_id, runtime_data_dir)
    if duplicate:
        indexed = get_indexed_event(event_id, runtime_data_dir) or {}
        event_record["status"] = "DUPLICATE_EVENT"
        event_record["duplicate"] = True
        event_record["route_id"] = indexed.get("route_id")
        event_record["manifest_id"] = indexed.get("manifest_id")
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
        existing_q = load_queue_record(event_id, runtime_data_dir)
        if existing_q is None:
            existing_q = build_queue_record(event_record, status=STATUS_DUPLICATE_EVENT, duplicate=True, duplicate_of_event_id=event_id, route_id=indexed.get("route_id"), manifest_id=indexed.get("manifest_id"), linked_frame_id=indexed.get("linked_frame_id"))
        else:
            existing_q = update_queue_record(existing_q, status=STATUS_DUPLICATE_EVENT, duplicate=True, duplicate_of_event_id=event_id)
        write_queue_record(existing_q, runtime_data_dir)
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
        event_record["route_id"] = None
        event_record["manifest_id"] = None
        event_record["linked_frame_id"] = None
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
        write_queue_record(update_queue_record(_q, status=STATUS_ROUTE_NOT_FOUND, failure_code="ROUTE_NOT_FOUND", failure_reason="No event route matched this source and event type."), runtime_data_dir)
        return _result(False, "NO_ROUTE", event_record.get("event_id"), None, None, None, {}, [])

    write_queue_record(update_queue_record(_q, status=STATUS_ROUTE_RESOLVED, route_id=route.get("route_id"), manifest_id=route.get("manifest_id")), runtime_data_dir)
    event_record["route_id"] = route.get("route_id")
    event_record["manifest_id"] = route.get("manifest_id")

    mapped_inputs, mapping_errors = map_event_inputs(event_record, route)
    if mapping_errors:
        event_record["status"] = "ROUTE_MAPPING_FAILED"
        event_record["errors"] = list(mapping_errors)
        event_record["duplicate"] = False
        event_record["linked_frame_id"] = None
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
        _failure = derive_event_failure_reason(event_record)
        write_queue_record(update_queue_record(_q, status=STATUS_FAILED_EXECUTION, errors=list(mapping_errors), failure_code=_failure["failure_code"], failure_reason=_failure["failure_reason"], route_id=route.get("route_id"), manifest_id=route.get("manifest_id")), runtime_data_dir)
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
        event_record["linked_frame_id"] = None
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
        write_queue_record(update_queue_record(_q, status=STATUS_FAILED_EXECUTION, errors=[f"Manifest not found: {manifest_id}"], failure_code="MANIFEST_NOT_FOUND", failure_reason=f"Manifest '{manifest_id}' could not be found.", route_id=route.get("route_id"), manifest_id=manifest_id), runtime_data_dir)
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
        if strict_manifest_preflight:
            from src.manifest_contract_strict import validate_manifest_strict

            manifest_validation = validate_manifest_strict(
                getattr(manifest, "raw", manifest if isinstance(manifest, dict) else {}),
                manifest_path=str(getattr(manifest, "manifest_path", "")),
                active_catalog=True,
                event_routes={"routes": routes},
            )
            if not manifest_validation.get("ok", False):
                manifest_errors = list(manifest_validation.get("errors", []))
                event_record["status"] = "MANIFEST_PREFLIGHT_FAILED"
                event_record["errors"] = manifest_errors
                event_record["duplicate"] = False
                event_record["linked_frame_id"] = None
                event_record["ledger_recorded_at"] = utc_now()
                append_event(event_record, runtime_data_dir)
                upsert_event_index(
                    {
                        "event_id": event_id,
                        "status": "MANIFEST_PREFLIGHT_FAILED",
                        "linked_frame_id": None,
                        "route_id": route.get("route_id"),
                        "manifest_id": manifest_id,
                    },
                    runtime_data_dir,
                )
                write_queue_record(update_queue_record(_q, status=STATUS_FAILED_EXECUTION, errors=manifest_errors, failure_code="MANIFEST_PREFLIGHT_FAILED", failure_reason="Manifest preflight validation failed.", route_id=route.get("route_id"), manifest_id=manifest_id), runtime_data_dir)
                return _result(
                    False,
                    "MANIFEST_PREFLIGHT_FAILED",
                    event_record.get("event_id"),
                    route.get("route_id"),
                    manifest_id,
                    None,
                    mapped_inputs,
                    manifest_errors,
                )
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
        write_queue_record(update_queue_record(_q, status=STATUS_FRAME_CREATED, route_id=route.get("route_id"), manifest_id=manifest_id, linked_frame_id=frame.frame_id), runtime_data_dir)
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
        write_queue_record(update_queue_record(_q, status=STATUS_FAILED_EXECUTION, errors=[str(exc)], failure_code="TASKFRAME_CREATION_FAILED", failure_reason=str(exc), route_id=route.get("route_id"), manifest_id=manifest_id), runtime_data_dir)
        return _result(False, "FAILED", event_record.get("event_id"), route.get("route_id"), manifest_id, None, mapped_inputs, [str(exc)])


def intake_and_run_event(
    event_data: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
    manifest_dir: str | Path = "manifests",
    routes_path: str = "config/event_routes.json",
    strict_source_contracts: bool = False,
    strict_manifest_preflight: bool = False,
) -> dict[str, Any]:
    intake_result = intake_event(
        event_data,
        runtime_data_dir=runtime_data_dir,
        manifest_dir=manifest_dir,
        routes_path=routes_path,
        strict_source_contracts=strict_source_contracts,
        strict_manifest_preflight=strict_manifest_preflight,
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
    frame_errors = [error.get("message", "") for error in frame.errors if isinstance(error, dict) and error.get("message")]
    combined_errors = list(intake_result.get("errors", [])) + frame_errors

    # Update queue record with final frame state
    _event_id = intake_result.get("event_id")
    if _event_id:
        _qr = load_queue_record(_event_id, runtime_data_dir)
        if _qr is not None:
            final_queue_status = frame_state_to_event_status(frame.state)
            _failure = derive_event_failure_reason({}, {"state": frame.state, "errors": list(frame.errors), "completion_gate_result": frame.completion_gate_result})
            write_queue_record(update_queue_record(_qr, status=final_queue_status, linked_frame_id=frame.frame_id, errors=combined_errors if not frame.state.startswith("COMPLETED") else [], failure_code=_failure.get("failure_code", "") if not frame.state.startswith("COMPLETED") else "", failure_reason=_failure.get("failure_reason", "") if not frame.state.startswith("COMPLETED") else ""), runtime_data_dir)

    return {
        "ok": frame.state in {"COMPLETED", "WAITING_FOR_EXECUTE", "COMPLETED_NO_DATA"},
        "status": frame.state,
        "event_id": intake_result.get("event_id"),
        "route_id": intake_result.get("route_id"),
        "manifest_id": intake_result.get("manifest_id"),
        "frame_id": frame.frame_id,
        "outputs": dict(frame.outputs),
        "errors": combined_errors,
    }


def _normalize_event_record(event_data: dict[str, Any], received_at: str) -> dict[str, Any]:
    event = dict(event_data or {}) if isinstance(event_data, dict) else {}
    event.setdefault("event_id", "")
    event.setdefault("source", "")
    event.setdefault("event_type", "")
    event.setdefault("payload", {})
    event.setdefault("received_at", received_at)
    event.setdefault("status", "RECEIVED")
    event.setdefault("route_id", None)
    event.setdefault("manifest_id", None)
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
