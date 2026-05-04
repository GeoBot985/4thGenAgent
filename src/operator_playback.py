from __future__ import annotations

from typing import Any

from src.operator_data import build_selected_detail, load_manifest, normalize_manifest_for_ui


STEP_SEQUENCE = [
    ("validate_input", "step"),
    ("extract_order_id", "step"),
    ("lookup_order", "step"),
    ("validate_customer_owns_order", "step"),
    ("draft_status_reply", "step"),
    ("validate_draft_reply", "step"),
    ("prepare_pending_send", "step"),
]


def build_playback_timeline(snapshot: dict) -> list[dict]:
    active_event = snapshot.get("active_event") if isinstance(snapshot, dict) else None
    active_frame = snapshot.get("active_frame") if isinstance(snapshot, dict) else None
    timeline: list[dict[str, Any]] = []
    manifest = normalize_manifest_for_ui(load_manifest(_string(active_frame, "manifest_id"))) if isinstance(active_frame, dict) else None

    event_id = _string(active_event, "event_id")
    source = _string(active_event, "source")
    event_type = _string(active_event, "event_type")
    route_id = _route_id(snapshot)
    manifest_id = _string(active_frame, "manifest_id")
    frame_id = _string(active_frame, "frame_id")
    frame_state = _string(active_frame, "state")

    timeline.append(
        {
            "kind": "event",
            "title": "event_received",
            "step_id": "event_received",
            "status": "complete",
            "reveal": {"event": {"event_id": event_id, "source": source, "event_type": event_type}},
            "detail": build_selected_detail(snapshot, {"step_id": "event_received"}),
        }
    )
    timeline.append(
        {
            "kind": "route",
            "title": "route_resolved",
            "step_id": "route_resolved",
            "status": "complete",
            "reveal": {"route": {"route_id": route_id, "manifest_id": manifest_id}},
            "detail": build_selected_detail(snapshot, {"step_id": "route_resolved"}),
        }
    )
    timeline.append(
        {
            "kind": "frame",
            "title": "taskframe_created",
            "step_id": "taskframe_created",
            "status": "complete",
            "reveal": {"frame": {"frame_id": frame_id, "state": frame_state}},
            "detail": build_selected_detail(snapshot, {"step_id": "taskframe_created"}),
        }
    )

    revealed_outputs: dict[str, Any] = {}
    revealed_validations: list[dict] = []
    revealed_pending: list[dict] = []

    for step_id, kind in STEP_SEQUENCE:
        status = "complete"
        reveal: dict[str, Any] = {}
        if step_id == "validate_input":
            revealed_validations = _validation_items(active_frame, step_id)
            reveal = {"validations": revealed_validations}
        elif step_id == "extract_order_id":
            if isinstance(active_frame, dict) and "order_id" in active_frame.get("outputs", {}):
                revealed_outputs["order_id"] = active_frame["outputs"].get("order_id")
            reveal = {"outputs": dict(revealed_outputs)}
        elif step_id == "lookup_order":
            if isinstance(active_frame, dict):
                for name in ("order", "customer", "shipment", "payment", "business_lookups"):
                    if name in active_frame.get("outputs", {}):
                        revealed_outputs[name] = active_frame["outputs"].get(name)
            reveal = {"outputs": dict(revealed_outputs), "evidence": _business_evidence(active_frame)}
        elif step_id == "validate_customer_owns_order":
            revealed_validations = _validation_items(active_frame, step_id)
            reveal = {"validations": revealed_validations}
        elif step_id == "draft_status_reply":
            if isinstance(active_frame, dict):
                for name in ("draft_reply",):
                    if name in active_frame.get("outputs", {}) and name not in revealed_outputs:
                        revealed_outputs[name] = active_frame["outputs"].get(name)
            reveal = {"outputs": dict(revealed_outputs)}
        elif step_id == "validate_draft_reply":
            revealed_validations = _validation_items(active_frame, step_id)
            reveal = {"validations": revealed_validations}
        elif step_id == "prepare_pending_send":
            revealed_pending = _pending_actions(active_frame)
            reveal = {"pending_actions": revealed_pending}
        timeline.append({"kind": kind, "title": step_id, "step_id": step_id, "status": status, "reveal": reveal, "detail": build_selected_detail(snapshot, {"step_id": step_id})})

    timeline.append(
        {
            "kind": "complete",
            "title": "complete",
            "step_id": "complete",
            "status": _string(active_frame, "state") or "complete",
            "reveal": {
                "outputs": dict(active_frame.get("outputs", {})) if isinstance(active_frame, dict) else {},
                "validations": _validation_items(active_frame, None),
                "pending_actions": _pending_actions(active_frame),
                "evidence": _business_evidence(active_frame),
            },
            "detail": build_selected_detail(snapshot, {"step_id": "complete"}),
        }
    )
    return timeline


def build_playback_view(snapshot: dict, timeline: list[dict], index: int) -> dict:
    active_frame = snapshot.get("active_frame") if isinstance(snapshot, dict) else None
    active_event = snapshot.get("active_event") if isinstance(snapshot, dict) else None
    total = len(timeline)
    max_index = max(0, min(index, total - 1)) if total else 0
    visible = timeline[: max_index + 1] if timeline else []

    outputs: dict[str, Any] = {}
    validations: list[dict] = []
    pending_actions: list[dict] = []
    evidence: list[dict] = []
    selected_detail: dict[str, Any] = {}
    current_title = ""
    current_step_id = ""
    playback_status = "idle"
    if timeline:
        current = timeline[max_index]
        current_title = current.get("title", "")
        current_step_id = current.get("step_id", "")
        playback_status = "running" if index < total - 1 else "complete"
        selected_detail = current.get("detail", {}) if isinstance(current.get("detail", {}), dict) else {}
    if index < 0:
        playback_status = "idle"

    for item in visible:
        reveal = item.get("reveal", {})
        if not isinstance(reveal, dict):
            continue
        outputs.update({key: value for key, value in reveal.get("outputs", {}).items()}) if isinstance(reveal.get("outputs"), dict) else None
        validations.extend([dict(v) for v in reveal.get("validations", []) if isinstance(v, dict)]) if isinstance(reveal.get("validations"), list) else None
        if isinstance(reveal.get("pending_actions"), list):
            pending_actions = [dict(v) for v in reveal.get("pending_actions", []) if isinstance(v, dict)]
        if isinstance(reveal.get("evidence"), list):
            evidence = [dict(v) for v in reveal.get("evidence", []) if isinstance(v, dict)]

    if index >= total - 1 and isinstance(active_frame, dict):
        outputs = dict(active_frame.get("outputs", {}))
        validations = [dict(item) for item in active_frame.get("validations", []) if isinstance(item, dict)]
        pending_actions = [dict(item) for item in active_frame.get("pending_actions", []) if isinstance(item, dict)]
        evidence = [dict(item) for item in active_frame.get("evidence", []) if isinstance(item, dict)]
        playback_status = "complete"
        selected_detail = build_selected_detail(snapshot, {"step_id": "complete"})

    return {
        "status": playback_status,
        "index": max_index + 1 if timeline else 0,
        "total": total,
        "current": current_title,
        "current_step_id": current_step_id,
        "event": active_event if max_index >= 0 else None,
        "route": {"route_id": _route_id(snapshot), "manifest_id": _string(active_frame, "manifest_id")},
        "frame": active_frame,
        "outputs": outputs,
        "validations": validations,
        "pending_actions": pending_actions,
        "evidence": evidence,
        "selected_detail": selected_detail,
        "visible_steps": [item.get("title", "") for item in visible],
    }


def _step_ids(active_frame: dict | None) -> list[str]:
    if not isinstance(active_frame, dict):
        return [item[0] for item in STEP_SEQUENCE]
    steps = active_frame.get("steps", [])
    if isinstance(steps, list) and steps:
        ids = [str(item.get("step_id") or item.get("id") or "") for item in steps if isinstance(item, dict)]
        ids = [item for item in ids if item]
        if ids:
            return ids
    return [item[0] for item in STEP_SEQUENCE]


def _validation_items(active_frame: dict | None, step_id: str | None) -> list[dict]:
    if not isinstance(active_frame, dict):
        return []
    validations = active_frame.get("validations", [])
    if not isinstance(validations, list):
        return []
    items = []
    for item in validations:
        if not isinstance(item, dict):
            continue
        if step_id and str(item.get("step_id") or item.get("validation_id") or "") != step_id:
            continue
        items.append(dict(item))
    return items


def _pending_actions(active_frame: dict | None) -> list[dict]:
    if not isinstance(active_frame, dict):
        return []
    pending = active_frame.get("pending_actions", [])
    if not isinstance(pending, list):
        return []
    return [dict(item) for item in pending if isinstance(item, dict)]


def _business_evidence(active_frame: dict | None) -> list[dict]:
    if not isinstance(active_frame, dict):
        return []
    evidence = active_frame.get("evidence", [])
    if not isinstance(evidence, list):
        return []
    items: list[dict] = []
    for entry in evidence:
        if not isinstance(entry, dict):
            continue
        if entry.get("kind") == "business_lookup":
            for dataset in entry.get("datasets", []):
                if isinstance(dataset, dict):
                    items.append({"dataset": dataset.get("dataset"), "query": dataset.get("query", {}), "found": bool(dataset.get("found"))})
    return items


def _event_detail(active_event: dict | None) -> dict:
    if not isinstance(active_event, dict):
        return {}
    payload = active_event.get("payload", {})
    return {
        "event_id": active_event.get("event_id", ""),
        "source": active_event.get("source", ""),
        "event_type": active_event.get("event_type", ""),
        "received_at": active_event.get("received_at", ""),
        "status": active_event.get("status", ""),
        "duplicate": bool(active_event.get("duplicate", False)),
        "linked_frame_id": active_event.get("linked_frame_id", ""),
        "payload": payload if isinstance(payload, dict) else payload,
    }


def _route_detail(snapshot: dict, active_event: dict | None, active_frame: dict | None, manifest: dict | None) -> dict:
    route = {}
    if isinstance(active_event, dict):
        route = {
            "route_id": _route_id(snapshot),
            "source": _string(active_event, "source"),
            "event_type": _string(active_event, "event_type"),
            "manifest_id": _string(active_frame, "manifest_id"),
            "input_map": active_event.get("input_map", {}),
            "mapped_inputs": active_frame.get("inputs", {}) if isinstance(active_frame, dict) else {},
        }
    if manifest and isinstance(manifest, dict):
        route["manifest_id"] = manifest.get("id", route.get("manifest_id", ""))
    return route


def _manifest_detail(manifest: dict | None) -> dict:
    if not isinstance(manifest, dict):
        return {}
    return {
        "manifest_id": manifest.get("id", ""),
        "name": manifest.get("name", ""),
        "trigger_type": manifest.get("trigger_type", ""),
        "side_effect": bool(manifest.get("side_effect", False)),
        "required_inputs": manifest.get("inputs", {}).get("required", []) if isinstance(manifest.get("inputs"), dict) else [],
        "step_count": len(manifest.get("steps", [])) if isinstance(manifest.get("steps"), list) else 0,
        "completion_requirements": manifest.get("completion", {}),
    }


def _manifest_step_detail(manifest: dict | None, step_id: str) -> dict:
    if not isinstance(manifest, dict):
        return {}
    steps = manifest.get("steps", [])
    if not isinstance(steps, list):
        return {}
    for item in steps:
        if not isinstance(item, dict):
            continue
        if item.get("step_id") == step_id:
            return dict(item)
    return {}


def _output_entries(outputs: dict, keys: tuple[str, ...]) -> list[dict]:
    entries: list[dict] = []
    for key in keys:
        if key not in outputs:
            continue
        entries.append({"name": key, "value": outputs.get(key)})
    return entries


def _route_id(snapshot: dict) -> str:
    active_event = snapshot.get("active_event") if isinstance(snapshot, dict) else None
    if isinstance(active_event, dict):
        route_id = active_event.get("route_id")
        if isinstance(route_id, str) and route_id:
            return route_id
    active_frame = snapshot.get("active_frame") if isinstance(snapshot, dict) else None
    if isinstance(active_frame, dict):
        trigger = active_frame.get("trigger")
        if isinstance(trigger, dict):
            route_id = trigger.get("route_id")
            if isinstance(route_id, str) and route_id:
                return route_id
    return ""


def _string(frame: dict | None, key: str) -> str:
    if not isinstance(frame, dict):
        return ""
    value = frame.get(key)
    return value if isinstance(value, str) else str(value or "")
