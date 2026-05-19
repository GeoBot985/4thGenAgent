from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


EVENT_LEDGER_NAME = "events.jsonl"


def build_operator_snapshot(runtime_root: str = "runtime_data") -> dict:
    events, errors = _load_event_ledger_with_errors(runtime_root, limit=50)
    active_event = select_active_event(events)

    active_frame = None
    if isinstance(active_event, dict) and active_event.get("linked_frame_id"):
        frame_id = str(active_event.get("linked_frame_id", ""))
        active_frame = load_taskframe(frame_id, runtime_root)
        if active_frame is None and _taskframe_file_exists(frame_id, runtime_root):
            errors.append(f"Malformed TaskFrame artifact: {frame_id}")

    normalized_frame = normalize_frame_for_ui(active_frame)
    outputs = dict(normalized_frame.get("outputs", {})) if isinstance(normalized_frame, dict) else {}
    validations = list(normalized_frame.get("validations", [])) if isinstance(normalized_frame, dict) else []
    pending_actions = list(normalized_frame.get("pending_actions", [])) if isinstance(normalized_frame, dict) else []
    evidence = list(normalized_frame.get("evidence", [])) if isinstance(normalized_frame, dict) else []

    trace_lines = _build_trace_lines(active_event, normalized_frame, events, validations, pending_actions, evidence, errors)

    snapshot = {
        "ok": True,
        "events": events,
        "frames_by_id": _load_frames_by_id(events, runtime_root),
        "active_event": active_event,
        "active_frame": normalized_frame,
        "outputs": outputs,
        "validations": validations,
        "pending_actions": pending_actions,
        "trace_lines": trace_lines,
        "errors": errors,
    }
    return snapshot


def load_event_ledger(runtime_root: str = "runtime_data", limit: int = 50) -> list[dict]:
    events, _ = _load_event_ledger_with_errors(runtime_root, limit=limit)
    return events


def select_active_event(events: list[dict]) -> dict | None:
    newest = events[-1] if events else None
    for event in reversed(events):
        if isinstance(event, dict) and event.get("linked_frame_id"):
            return dict(event)
    return dict(newest) if isinstance(newest, dict) else None


def group_events_for_queue(events: list[dict], frames_by_id: dict[str, dict]) -> dict[str, list[dict]]:
    groups = {
        "Incoming Events": [],
        "Waiting for Execute": [],
        "Failed": [],
        "Completed": [],
    }
    for event in events:
        if not isinstance(event, dict):
            continue
        group_name = _queue_group_for_event(event, frames_by_id)
        groups.setdefault(group_name, []).append(dict(event))
    return groups


def build_order_management_summary(outputs: dict) -> dict:
    """Extract order-specific summary fields from a frame's outputs dict."""
    if not isinstance(outputs, dict):
        return {}
    result: dict = {}
    order_validation = outputs.get("order_validation")
    if isinstance(order_validation, dict):
        result["order_valid"] = order_validation.get("valid")
        result["order_total"] = order_validation.get("order_total")
        result["failure_reasons"] = order_validation.get("failure_reasons", [])
    payment_status = outputs.get("payment_status")
    if isinstance(payment_status, dict):
        result["payment_status"] = payment_status.get("payment_status")
        result["can_release"] = payment_status.get("can_release")
        result["paid_amount"] = payment_status.get("paid_amount")
    delayed_orders = outputs.get("delayed_orders")
    if isinstance(delayed_orders, list):
        result["delayed_count"] = len(delayed_orders)
        result["delayed_orders"] = [o.get("order_ref") for o in delayed_orders if isinstance(o, dict)]
    return result


def build_event_sources_panel() -> dict:
    try:
        from runtime.event_source_registry import list_event_source_contracts, validate_all_event_source_contracts

        contracts = list_event_source_contracts()
        validation = validate_all_event_source_contracts()
    except Exception as exc:
        return {"ok": False, "contracts": [], "validation": {}, "error": str(exc)}
    return {
        "ok": True,
        "contracts": contracts,
        "validation": validation,
        "count": len(contracts),
    }


def load_taskframe(frame_id: str, runtime_root: str = "runtime_data") -> dict | None:
    if not isinstance(frame_id, str) or not frame_id.strip():
        return None

    try:
        from runtime.taskframe_reload import load_taskframe as load_runtime_taskframe

        frame = load_runtime_taskframe(frame_id, runtime_root)
        return _frame_to_mapping(frame)
    except Exception:
        pass

    root = Path(runtime_root)
    candidates = [
        root / "taskframes" / f"{frame_id}.json",
        root / "frames" / f"{frame_id}.json",
        root / "taskframe" / f"{frame_id}.json",
        root / "runs" / frame_id / "taskframe.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if isinstance(data, dict):
            return dict(data)
    return None


def normalize_frame_for_ui(frame: dict | None) -> dict | None:
    if frame is None:
        return None
    data = _frame_to_mapping(frame)
    if not data:
        return None
    return {
        "frame_id": _string_value(data.get("frame_id"), "—"),
        "state": _string_value(data.get("state"), "—"),
        "manifest_id": _string_value(data.get("manifest_id"), "—"),
        "trigger": _dict_value(data.get("trigger")),
        "inputs": _dict_value(data.get("inputs")),
        "steps": _list_value(data.get("steps")),
        "current_step_id": _string_value(data.get("current_step_id"), ""),
        "outputs": _dict_value(data.get("outputs")),
        "validations": _list_value(data.get("validations")),
        "pending_actions": _list_value(data.get("pending_actions")),
        "executed_actions": _list_value(data.get("executed_actions")),
        "evidence": _list_value(data.get("evidence")),
        "errors": _list_value(data.get("errors")),
        "raw": data,
    }


def load_manifest(manifest_id: str, config_root: str = "config") -> dict | None:
    if not isinstance(manifest_id, str) or not manifest_id.strip():
        return None
    manifest_dir = Path(config_root) / "manifests"
    if not manifest_dir.is_dir():
        return None
    for path in sorted(manifest_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("id") == manifest_id:
            return dict(data)
    return None


def normalize_manifest_for_ui(manifest: dict | None) -> dict | None:
    if manifest is None:
        return None
    data = _frame_to_mapping(manifest)
    if not data:
        return None
    steps = []
    for item in _list_value(data.get("steps")):
        if isinstance(item, dict):
            steps.append(dict(item))
        elif isinstance(item, str):
            steps.append({"step_id": item})
    return {
        "id": _string_value(data.get("id"), "—"),
        "name": _string_value(data.get("name"), "—"),
        "trigger_type": _string_value(data.get("trigger_type"), "—"),
        "side_effect": bool(data.get("side_effect", False)),
        "inputs": _dict_value(data.get("inputs")),
        "steps": steps,
        "completion": _dict_value(data.get("completion")),
        "raw": data,
    }


def find_manifest_step(manifest: dict | None, step_id: str) -> dict:
    if not isinstance(manifest, dict) or not isinstance(step_id, str) or not step_id:
        return {}
    for item in _list_value(manifest.get("steps")):
        if isinstance(item, dict) and _string_value(item.get("step_id"), "") == step_id:
            return dict(item)
    return {}


def find_runtime_step(frame: dict | None, step_id: str) -> dict:
    if not isinstance(frame, dict) or not isinstance(step_id, str) or not step_id:
        return {}
    for item in _list_value(frame.get("steps")):
        if isinstance(item, dict) and _string_value(item.get("step_id") or item.get("id"), "") == step_id:
            return dict(item)
    return {}


def collect_step_outputs(frame: dict | None, step_id: str, manifest_step: dict | None) -> dict:
    if not isinstance(frame, dict):
        return {}
    outputs = _dict_value(frame.get("outputs"))
    if not outputs:
        return {}
    keys = []
    if isinstance(manifest_step, dict):
        for key in ("output", "output_alias", "outputs", "output_key"):
            value = manifest_step.get(key)
            if isinstance(value, str) and value:
                keys.append(value)
            elif isinstance(value, list):
                keys.extend([item for item in value if isinstance(item, str)])
    if not keys:
        defaults = {
            "extract_order_id": ["order_id"],
            "lookup_order": ["order", "customer", "shipment", "payment", "business_lookups"],
            "draft_status_reply": ["draft_reply"],
        }
        keys = defaults.get(step_id, [])
    collected = {key: outputs[key] for key in keys if key in outputs}
    if step_id == "lookup_order" and "business_lookups" in outputs:
        collected.setdefault("business_lookups", outputs.get("business_lookups"))
    return collected


def collect_step_validations(frame: dict | None, step_id: str) -> list[dict]:
    if not isinstance(frame, dict):
        return []
    items = []
    for item in _list_value(frame.get("validations")):
        if isinstance(item, dict) and (not step_id or _string_value(item.get("step_id") or item.get("validation_id"), "") == step_id):
            items.append(dict(item))
    return items


def collect_step_evidence(frame: dict | None, step_id: str) -> list[dict]:
    if not isinstance(frame, dict):
        return []
    items = []
    for item in _list_value(frame.get("evidence")):
        if isinstance(item, dict) and (not step_id or _string_value(item.get("step_id"), "") == step_id):
            if item.get("kind") == "business_lookup":
                for dataset in _list_value(item.get("datasets")):
                    if isinstance(dataset, dict):
                        items.append({"dataset": dataset.get("dataset"), "query": _dict_value(dataset.get("query")), "found": bool(dataset.get("found"))})
                continue
            items.append(dict(item))
    return items


def collect_step_errors(frame: dict | None, step_id: str) -> list[dict]:
    if not isinstance(frame, dict):
        return []
    items = []
    for item in _list_value(frame.get("errors")):
        if isinstance(item, dict):
            if not step_id or _string_value(item.get("step_id"), "") == step_id:
                items.append(dict(item))
        elif isinstance(item, str):
            items.append({"message": item, "step_id": step_id or ""})
    return items


def build_selected_detail(snapshot: dict, timeline_item: dict) -> dict:
    active_event = snapshot.get("active_event") if isinstance(snapshot, dict) else None
    active_frame = snapshot.get("active_frame") if isinstance(snapshot, dict) else None
    manifest = normalize_manifest_for_ui(load_manifest(active_frame.get("manifest_id", ""), "config")) if isinstance(active_frame, dict) else None
    item = timeline_item if isinstance(timeline_item, dict) else {}
    step_id = _string_value(item.get("step_id"), "")
    manifest_step = find_manifest_step(manifest, step_id)
    runtime_step = find_runtime_step(active_frame, step_id)
    if not manifest_step and step_id in {"event_received", "route_resolved", "taskframe_created", "complete"}:
        manifest_step = {}
    return {
        "event": _event_detail(active_event),
        "route": _route_detail(snapshot, active_event, active_frame, manifest),
        "manifest": _manifest_detail(manifest),
        "manifest_step": _manifest_step_detail_for_ui(manifest_step, runtime_step),
        "runtime_step_result": _runtime_step_result_for_ui(active_frame, step_id, manifest_step, runtime_step),
    }


def _load_event_ledger_with_errors(runtime_root: str, limit: int = 50) -> tuple[list[dict], list[str]]:
    ledger_path = Path(runtime_root) / "events" / EVENT_LEDGER_NAME
    if not ledger_path.is_file():
        return [], []

    events: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        with ledger_path.open("r", encoding="utf-8") as handle:
            for line_no, raw in enumerate(handle, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"Malformed event ledger line {line_no}: {exc.msg}")
                    continue
                if not isinstance(record, dict):
                    errors.append(f"Malformed event ledger line {line_no}: expected JSON object.")
                    continue
                events.append(_normalize_event(record))
    except Exception as exc:
        errors.append(f"Unable to read event ledger: {ledger_path} ({type(exc).__name__})")
        return [], errors

    if limit is not None and limit >= 0:
        events = events[-int(limit) :]
    return events, errors


def _normalize_event(event: dict[str, Any]) -> dict:
    status = _string_value(event.get("status"), "RECEIVED")
    duplicate = bool(event.get("duplicate", False))
    return {
        "event_id": _string_value(event.get("event_id"), ""),
        "source": _string_value(event.get("source"), ""),
        "event_type": _string_value(event.get("event_type"), ""),
        "status": status,
        "linked_frame_id": _string_value(event.get("linked_frame_id"), "") or None,
        "received_at": _string_value(event.get("received_at"), ""),
        "ledger_recorded_at": _string_value(event.get("ledger_recorded_at"), ""),
        "duplicate": duplicate,
    }


def _build_trace_lines(
    active_event: dict | None,
    frame: dict | None,
    events: list[dict],
    validations: list[dict],
    pending_actions: list[dict],
    evidence: list[dict],
    errors: list[str],
) -> list[str]:
    lines = [
        "[RUNTIME]",
        "status: ready",
        "mode: operator",
        "",
        "[EVENT]",
        f"event_id: {_string_value(active_event.get('event_id') if isinstance(active_event, dict) else '', '') if active_event else ''}",
        f"source: {_string_value(active_event.get('source') if isinstance(active_event, dict) else '', '') if active_event else ''}",
        f"event_type: {_string_value(active_event.get('event_type') if isinstance(active_event, dict) else '', '') if active_event else ''}",
        f"event_status: {_string_value(active_event.get('status') if isinstance(active_event, dict) else '', '') if active_event else ''}",
        "",
        "[ROUTE]",
        f"route_id: {_route_id_from_event(active_event, frame)}",
        f"manifest_id: {_string_value(frame.get('manifest_id'), '') if isinstance(frame, dict) else ''}",
        "",
        "[TASKFRAME]",
    ]
    if frame is None:
        lines.append("No TaskFrame loaded.")
    else:
        lines.extend(
            [
                f"frame_id: {_string_value(frame.get('frame_id'), '')}",
                f"state: {_string_value(frame.get('state'), '')}",
            ]
        )
    lines.extend(
        [
        "",
        "[VALIDATIONS]",
        ]
    )
    if validations:
        for item in validations:
            if not isinstance(item, dict):
                continue
            step_id = _string_value(item.get("step_id") or item.get("validation_id"), "unknown")
            ok = item.get("ok")
            status = "ok" if ok is True else "failed" if ok is False else "unknown"
            lines.append(f"{step_id}: {status}")
    else:
        lines.append("No validation data.")
    lines.append("")
    lines.append("[EVIDENCE]")
    if evidence:
        for item in evidence:
            if not isinstance(item, dict):
                continue
            kind = _string_value(item.get("kind"), "evidence")
            step_id = _string_value(item.get("step_id"), "unknown")
            if kind == "business_lookup":
                datasets = item.get("datasets", [])
                lines.append(f"{step_id}: business_lookup")
                if isinstance(datasets, list):
                    for dataset in datasets:
                        if isinstance(dataset, dict):
                            ds_name = _string_value(dataset.get("dataset"), "dataset")
                            found = "found" if dataset.get("found") else "missing"
                            query = dataset.get("query", {})
                            lines.append(f"  {ds_name}: {found} | query={query}")
                continue
            lines.append(f"{step_id}: {kind}")
    else:
        lines.append("No evidence data.")
    lines.append("")
    lines.append("[PENDING ACTIONS]")
    if pending_actions:
        for item in pending_actions:
            if not isinstance(item, dict):
                continue
            action_type = _string_value(item.get("action_type"), "unknown")
            status = _string_value(item.get("status"), "unknown")
            lines.append(f"{action_type}: {status}")
    else:
        lines.append("No pending actions.")
    lines.append("")
    lines.append("[ERRORS]")
    combined_errors = list(errors)
    if frame and isinstance(frame, dict) and frame.get("errors"):
        for item in frame.get("errors", []):
            if isinstance(item, dict):
                combined_errors.append(_string_value(item.get("message"), ""))
            else:
                combined_errors.append(_string_value(item, ""))
    if combined_errors:
        lines.extend(combined_errors)
    else:
        lines.append("No errors.")
    return lines


def _route_id_from_event(active_event: dict | None, frame: dict | None) -> str:
    if isinstance(active_event, dict):
        route_id = _string_value(active_event.get("route_id"), "")
        if route_id:
            return route_id
    if isinstance(frame, dict):
        trigger = frame.get("trigger")
        if isinstance(trigger, dict):
            route_id = _string_value(trigger.get("route_id"), "")
            if route_id:
                return route_id
    return ""


def _event_detail(active_event: dict | None) -> dict:
    if not isinstance(active_event, dict):
        return {}
    payload = active_event.get("payload", {})
    created_at = _string_value(active_event.get("created_at"), "")
    return {
        "event_id": _string_value(active_event.get("event_id"), ""),
        "source": _string_value(active_event.get("source"), ""),
        "event_type": _string_value(active_event.get("event_type"), ""),
        "received_at": _string_value(active_event.get("received_at"), ""),
        "created_at": created_at,
        "status": _string_value(active_event.get("status"), ""),
        "duplicate": bool(active_event.get("duplicate", False)),
        "linked_frame_id": _string_value(active_event.get("linked_frame_id"), ""),
        "payload": payload if isinstance(payload, dict) else payload,
    }


def _route_detail(snapshot: dict, active_event: dict | None, active_frame: dict | None, manifest: dict | None) -> dict:
    route = {}
    if isinstance(active_event, dict):
        route = {
            "route_id": _route_id_from_event(active_event, active_frame),
            "event_type": _string_value(active_event.get("event_type"), ""),
            "source": _string_value(active_event.get("source"), ""),
            "manifest_id": _string_value(active_frame.get("manifest_id") if isinstance(active_frame, dict) else None, ""),
            "enabled": True,
            "input_map": active_event.get("input_map", {}),
            "mapped_inputs": _dict_value(active_frame.get("inputs")) if isinstance(active_frame, dict) else {},
        }
    if manifest and isinstance(manifest, dict):
        route["manifest_id"] = _string_value(manifest.get("id"), route.get("manifest_id", ""))
    return route


def _manifest_detail(manifest: dict | None) -> dict:
    if not isinstance(manifest, dict):
        return {}
    inputs = manifest.get("inputs", {})
    completion = manifest.get("completion", {})
    steps = _list_value(manifest.get("steps"))
    return {
        "manifest_id": _string_value(manifest.get("id"), ""),
        "id": _string_value(manifest.get("id"), ""),
        "name": _string_value(manifest.get("name"), ""),
        "trigger": _string_value(manifest.get("trigger_type"), ""),
        "inputs": _dict_value(inputs),
        "completion_requirements": _dict_value(completion),
        "validation_count": len(_list_value(completion.get("required_validations"))),
        "step_count": len(steps),
        "side_effect_policy": bool(manifest.get("side_effect", False)),
    }


def _manifest_step_detail_for_ui(manifest_step: dict, runtime_step: dict) -> dict:
    if not manifest_step and not runtime_step:
        return {}
    detail = dict(manifest_step) if isinstance(manifest_step, dict) else {}
    runtime_step_id = _string_value(runtime_step.get("step_id"), "") if isinstance(runtime_step, dict) else ""
    if "command" not in detail:
        step_id = _string_value(detail.get("step_id"), runtime_step_id)
        detail["command"] = detail.get("kind") or step_id
    if "action" not in detail:
        step_id = _string_value(detail.get("step_id"), runtime_step_id)
        detail["action"] = detail.get("kind", step_id)
    if "step_id" not in detail and runtime_step_id:
        detail["step_id"] = runtime_step_id
    legacy_kind_map = {
        "extract_order_id": "extract_order_ref",
        "lookup_order": "mock_order_lookup",
        "draft_status_reply": "draft_customer_status_reply",
        "validate_draft_reply": "validate_customer_status_reply",
        "prepare_pending_send": "prepare_pending_customer_message",
    }
    if not detail.get("kind") and runtime_step_id in legacy_kind_map:
        detail["kind"] = legacy_kind_map[runtime_step_id]
    for key in ("namespace", "output_alias", "when", "retry_policy", "timeout_seconds", "validation", "validation_config"):
        detail.setdefault(key, detail.get(key, ""))
    if isinstance(runtime_step, dict):
        for key in ("status", "outputs", "validations", "evidence", "errors", "duration", "attempts"):
            if key in runtime_step:
                detail.setdefault(key, runtime_step.get(key))
    return detail


def _runtime_step_result_for_ui(active_frame: dict | None, step_id: str, manifest_step: dict, runtime_step: dict) -> dict:
    if not isinstance(active_frame, dict):
        return {}
    outputs = collect_step_outputs(active_frame, step_id, manifest_step)
    validations = collect_step_validations(active_frame, step_id)
    evidence = collect_step_evidence(active_frame, step_id)
    errors = collect_step_errors(active_frame, step_id)
    pending_actions = []
    for item in _list_value(active_frame.get("pending_actions")):
        if isinstance(item, dict) and (not step_id or _string_value(item.get("step_id"), "") == step_id):
            pending_actions.append(dict(item))
    step_state = _string_value(runtime_step.get("status"), _string_value(active_frame, "state"))
    return {
        "status": step_state,
        "outputs": outputs,
        "validations": validations,
        "evidence": evidence,
        "pending_actions": pending_actions,
        "errors": errors,
        "duration": runtime_step.get("duration", ""),
        "attempts": runtime_step.get("attempts", ""),
    }


def _taskframe_file_exists(frame_id: str, runtime_root: str) -> bool:
    root = Path(runtime_root)
    for path in (
        root / "taskframes" / f"{frame_id}.json",
        root / "frames" / f"{frame_id}.json",
        root / "taskframe" / f"{frame_id}.json",
        root / "runs" / frame_id / "taskframe.json",
    ):
        if path.is_file():
            return True
    return False


def _load_frames_by_id(events: list[dict], runtime_root: str | Path) -> dict[str, dict]:
    frames_by_id: dict[str, dict] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        frame_id = str(event.get("linked_frame_id") or "").strip()
        if not frame_id or frame_id in frames_by_id:
            continue
        frame = load_taskframe(frame_id, runtime_root=str(runtime_root))
        if frame is not None:
            frames_by_id[frame_id] = frame
    return frames_by_id


def _queue_group_for_event(event: dict, frames_by_id: dict[str, dict]) -> str:
    frame_id = str(event.get("linked_frame_id") or "").strip()
    if frame_id and frame_id in frames_by_id:
        state = str(frames_by_id[frame_id].get("state", "")).strip()
        if state:
            if state == "WAITING_FOR_EXECUTE":
                return "Waiting for Execute"
            if state.startswith("FAILED"):
                return "Failed"
            if state in {"COMPLETED", "COMPLETED_NO_DATA", "DUPLICATE_EVENT"}:
                return "Completed"
    status = str(event.get("status", "")).upper()
    if status == "WAITING_FOR_EXECUTE":
        return "Waiting for Execute"
    if status.startswith("FAILED") or status in {"NO_ROUTE", "ROUTE_MAPPING_FAILED", "MANIFEST_NOT_FOUND"}:
        return "Failed"
    if status in {"COMPLETED", "COMPLETED_NO_DATA", "DUPLICATE_EVENT"}:
        return "Completed"
    return "Incoming Events"


def build_footer_text(snapshot: dict, playback_status: str) -> str:
    active_frame = snapshot.get("active_frame") if isinstance(snapshot, dict) else None
    frame_id = "none"
    pending_count = 0
    if isinstance(active_frame, dict):
        frame_id = str(active_frame.get("frame_id") or "none")
        pending = active_frame.get("pending_actions", [])
        if isinstance(pending, list):
            pending_count = len(pending)
    status = playback_status if playback_status in {"running", "paused", "complete"} else "idle"
    if frame_id == "none":
        return "Runtime: ready | Active Frame: none | Pending Actions: 0 | Playback: idle"
    return f"Runtime: ready | Active Frame: {frame_id} | Pending Actions: {pending_count} | Playback: {status}"


def _frame_to_mapping(frame: Any) -> dict[str, Any]:
    if frame is None:
        return {}
    if isinstance(frame, dict):
        return dict(frame)
    if is_dataclass(frame):
        return asdict(frame)
    if isinstance(frame, Mapping):
        return dict(frame)
    if hasattr(frame, "to_dict") and callable(getattr(frame, "to_dict")):
        try:
            value = frame.to_dict()
            return dict(value) if isinstance(value, Mapping) else {}
        except Exception:
            return {}
    if hasattr(frame, "__dict__"):
        return dict(vars(frame))
    return {}


def _dict_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _list_value(value: Any) -> list:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _string_value(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)
