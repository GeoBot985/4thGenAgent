from __future__ import annotations

from typing import Any
import re

from src.operator_artifacts import build_artifact_state


STATE_LABELS = {
    "WAITING_FOR_EXECUTE": "Waiting for approval",
    "COMPLETED": "Completed",
    "FAILED_VALIDATION": "Failed validation",
    "FAILED_EXECUTION": "Execution failed",
    "FAILED_COMPLETION": "Could not complete",
}


STEP_LABELS = {
    "validate_input": "Checked the request has enough information",
    "extract_order_id": "Extracted the order number",
    "lookup_order": "Checked the order record",
    "validate_customer_owns_order": "Confirmed the customer owns the order",
    "draft_status_reply": "Drafted the customer reply",
    "validate_draft_reply": "Checked the reply against business facts",
    "prepare_pending_send": "Prepared the message for approval",
    # Order management
    "validate_new": "Validated new order (customer, items, stock)",
    "prepare_stock_reservation": "Prepared stock reservation for approval",
    "check_payment_status": "Checked payment status for order",
    "prepare_release_paid_order": "Prepared paid-order release for approval",
    "detect_delayed_orders": "Scanned for delayed shipments",
    "prepare_shipment_status_update": "Prepared shipment status update for approval",
}


CHANNEL_LABELS = {
    "callcenter": "Call centre",
    "callcentre": "Call centre",
    "phone": "Phone",
    "email": "Email",
    "web": "Web",
    "chat": "Chat",
}


def build_demo_view(snapshot: dict, current_run: dict | None = None, artifact_state: dict | None = None) -> dict:
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    current_run = current_run if isinstance(current_run, dict) else {}
    artifact_state = artifact_state if isinstance(artifact_state, dict) else _build_artifact_state(current_run, snapshot)
    frame = _active_frame(snapshot)
    event = _active_event(snapshot)

    scenario_title = _scenario_title(snapshot, current_run, frame)
    incoming_request = _incoming_request(event, frame)
    worker_steps = _worker_steps(frame, incoming_request)
    business_result = _business_result(frame, incoming_request)
    approval = _approval(frame)
    evidence_summary = _evidence_summary(frame)
    guided_flow = _guided_flow(frame, artifact_state, current_run)
    next_action = _next_action(frame, artifact_state)
    current_run_summary = _current_run_summary(scenario_title, frame, artifact_state, approval)
    technical_refs = {
        "frame_id": _string(frame.get("frame_id")),
        "manifest_id": _string(frame.get("manifest_id")),
        "state": _string(frame.get("state")),
    }

    return {
        "scenario_title": scenario_title,
        "scenario_summary": _scenario_summary(current_run, frame, approval, worker_steps),
        "incoming_request": incoming_request,
        "worker_steps": worker_steps,
        "business_result": business_result,
        "approval": approval,
        "evidence_summary": evidence_summary,
        "guided_flow": guided_flow,
        "next_action": next_action,
        "current_run_summary": current_run_summary,
        "artifact_state": _present_artifact_state(frame, artifact_state),
        "technical_refs": technical_refs,
    }


def humanize_state(state: str) -> str:
    state = _string(state)
    if not state:
        return ""
    if state in STATE_LABELS:
        return STATE_LABELS[state]
    return _sentence_case(state)


def humanize_step_id(step_id: str) -> str:
    step_id = _string(step_id)
    if not step_id:
        return ""
    if step_id in STEP_LABELS:
        return STEP_LABELS[step_id]
    return _sentence_case(step_id)


def _active_frame(snapshot: dict) -> dict:
    frame = snapshot.get("active_frame", {})
    return frame if isinstance(frame, dict) else {}


def _active_event(snapshot: dict) -> dict:
    event = snapshot.get("active_event", {})
    return event if isinstance(event, dict) else {}


def _scenario_title(snapshot: dict, current_run: dict, frame: dict) -> str:
    for candidate in (
        current_run.get("label"),
        current_run.get("scenario_title"),
        current_run.get("scenario_name"),
        snapshot.get("scenario_title"),
        frame.get("scenario_title"),
    ):
        value = _string(candidate)
        if value:
            return value

    manifest_id = _string(frame.get("manifest_id"))
    if manifest_id:
        lowered = manifest_id.lower()
        if "customer" in lowered and "status" in lowered:
            return "Customer Order Status"
        if "supplier_invoice" in lowered:
            return "Supplier Invoice Matching"
        if "procurement" in lowered:
            return "Procurement Reorder"
        if "accounting" in lowered:
            return "Accounting Reconciliation"
        if "demo" in lowered:
            return _sentence_case(manifest_id.replace(".", " "))
        return _sentence_case(manifest_id.replace(".", " "))
    return "Autonomous Business Worker Demo"


def _scenario_summary(current_run: dict, frame: dict, approval: dict, worker_steps: list[dict]) -> str:
    for candidate in (
        current_run.get("scenario_summary"),
        current_run.get("summary", {}).get("summary_text") if isinstance(current_run.get("summary", {}), dict) else "",
    ):
        value = _string(candidate)
        if value:
            return value

    parts = []
    if worker_steps:
        done_count = sum(1 for item in worker_steps if item.get("status") == "done")
        parts.append(f"The worker completed {done_count} visible step{'' if done_count == 1 else 's'}.")
    if approval.get("required"):
        parts.append("The result is waiting for human approval before a side effect can happen.")
    else:
        parts.append("The result is ready with no approval gate required.")
    manifest_id = _string(frame.get("manifest_id"))
    if manifest_id:
        parts.append(f"Scenario source: {humanize_step_id(manifest_id)}.")
        if "supplier_invoice" in manifest_id.lower():
            parts.append("Workflow family: supplier invoice matching.")
    return " ".join(parts).strip()


def _incoming_request(event: dict, frame: dict) -> dict:
    payload = event.get("payload", {}) if isinstance(event, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    inputs = frame.get("inputs", {}) if isinstance(frame, dict) else {}
    if not isinstance(inputs, dict):
        inputs = {}

    message = _string(payload.get("message") or inputs.get("message"))
    order_id = _extract_order_id(
        _string(
            payload.get("order_id")
            or payload.get("order_ref")
            or inputs.get("order_id")
            or inputs.get("order_ref")
            or message
        )
    )
    return {
        "channel": _channel_label(payload.get("channel") or inputs.get("channel")),
        "customer_id": _string(payload.get("customer_id") or inputs.get("customer_id")),
        "message": message,
        "order_id": order_id,
    }


def _worker_steps(frame: dict, incoming_request: dict) -> list[dict]:
    steps = _step_records(frame)
    pending_actions = frame.get("pending_actions", []) if isinstance(frame, dict) else []
    pending_exists = isinstance(pending_actions, list) and bool(pending_actions)
    current_step_id = _string(frame.get("current_step_id"))
    state = _string(frame.get("state"))

    worker_steps: list[dict[str, str]] = []
    for index, step in enumerate(steps):
        step_id = _step_id(step)
        label = humanize_step_id(step_id)
        status = _step_status(step, index, len(steps), current_step_id, state, pending_exists)
        if label:
            worker_steps.append({"label": label, "status": status})

    if not worker_steps and incoming_request.get("message"):
        worker_steps = [
            {"label": "Understood the customer request", "status": "done"},
            {"label": "Checked the order record", "status": "done" if state == "COMPLETED" else "current"},
        ]

    if pending_exists:
        worker_steps.append({"label": "Waiting for approval before sending", "status": "attention"})
    return worker_steps


def _business_result(frame: dict, incoming_request: dict) -> dict:
    outputs = frame.get("outputs", {}) if isinstance(frame, dict) else {}
    if not isinstance(outputs, dict):
        outputs = {}

    order = outputs.get("order", {}) if isinstance(outputs.get("order", {}), dict) else {}
    shipment = outputs.get("shipment", {}) if isinstance(outputs.get("shipment", {}), dict) else {}
    draft_reply = outputs.get("draft_reply", {}) if isinstance(outputs.get("draft_reply", {}), dict) else {}
    customer = outputs.get("customer", {}) if isinstance(outputs.get("customer", {}), dict) else {}

    order_id = _string(outputs.get("order_id") or incoming_request.get("order_id") or order.get("order_id"))
    status = _string(order.get("status") or outputs.get("order_status") or frame.get("state"))
    tracking = _string(
        shipment.get("tracking_reference")
        or shipment.get("tracking_ref")
        or shipment.get("tracking_number")
        or outputs.get("tracking_reference")
    )
    estimated_delivery = _string(
        shipment.get("estimated_delivery")
        or shipment.get("estimated_delivery_date")
        or outputs.get("estimated_delivery")
    )
    body = _string(draft_reply.get("body") or draft_reply.get("reply") or outputs.get("draft_reply_body"))
    if not body and order_id:
        body = f"Your order {order_id} has a status of {status or 'unknown'}."
    if body and tracking and "Tracking" not in body:
        body = f"{body}\nTracking reference: {tracking}."

    facts = []
    if order_id:
        facts.append(f"Order {order_id} exists")
    if status:
        facts.append(f"Order status is {status}")
    if tracking:
        facts.append("Tracking reference found")
    if customer.get("customer_id") or incoming_request.get("customer_id"):
        facts.append("Customer ownership verified")
    if estimated_delivery:
        facts.append(f"Estimated delivery {estimated_delivery}")

    if not facts and body:
        facts.append("Draft reply prepared from verified business data")

    title = "Draft reply ready" if body else "Business result ready"
    if status and status.lower() not in {"", "unknown"} and title == "Business result ready":
        title = f"{_sentence_case(status)} result ready"

    return {"title": title, "body": body, "facts": facts}


def _approval(frame: dict) -> dict:
    pending_actions = frame.get("pending_actions", []) if isinstance(frame, dict) else []
    pending = pending_actions[0] if isinstance(pending_actions, list) and pending_actions and isinstance(pending_actions[0], dict) else {}
    required = bool(pending)
    action_type = _string(pending.get("action_type") or pending.get("tool") or pending.get("action"))
    if not action_type and required:
        action_type = "send_customer_message"
    status = _string(pending.get("status") or frame.get("state"))
    frame_state = _string(frame.get("state"))
    if required and (status == "WAITING_FOR_EXECUTE" or frame_state == "WAITING_FOR_EXECUTE"):
        label = "Waiting for approval before sending customer message"
    else:
        label = "Approval required before sending customer message" if required else "No approval required"
    if "supplier_invoice" in _string(frame.get("manifest_id")).lower():
        if required and (status == "WAITING_FOR_EXECUTE" or frame_state == "WAITING_FOR_EXECUTE"):
            label = "Waiting for approval before posting supplier invoice ledger entry"
        else:
            label = "Approval required before posting supplier invoice ledger entry" if required else "No approval required"
    return {
        "required": required,
        "label": label,
        "action_type": action_type,
        "status": status,
    }


def _evidence_summary(frame: dict) -> list[str]:
    evidence_items = frame.get("evidence", []) if isinstance(frame, dict) else []
    summaries: list[str] = []
    if isinstance(evidence_items, list):
        for item in evidence_items:
            if not isinstance(item, dict):
                continue
            if item.get("kind") == "business_lookup":
                for dataset in item.get("datasets", []):
                    if not isinstance(dataset, dict):
                        continue
                    label = _string(dataset.get("dataset"))
                    if label:
                        suffix = "completed" if dataset.get("found") else "missing"
                        summaries.append(f"{_sentence_case(label)} lookup {suffix}")
            elif item.get("title"):
                summaries.append(_string(item.get("title")))
    if not summaries:
        if frame.get("outputs"):
            summaries.append("Evidence bundle available")
        else:
            summaries.append("No evidence bundle found")
    return _dedupe(summaries)


def _step_records(frame: dict) -> list[dict]:
    steps = frame.get("steps", []) if isinstance(frame, dict) else []
    if not isinstance(steps, list):
        return []
    records: list[dict] = []
    for item in steps:
        if isinstance(item, dict):
            records.append(dict(item))
        elif isinstance(item, str):
            records.append({"step_id": item})
    return records


def _step_id(step: dict) -> str:
    return _string(step.get("step_id") or step.get("id"))


def _step_status(step: dict, index: int, total: int, current_step_id: str, state: str, pending_exists: bool) -> str:
    explicit = _string(step.get("status")).lower()
    if explicit in {"done", "current", "attention", "failed", "pending"}:
        return explicit
    ok = step.get("ok")
    if ok is True:
        return "done"
    if ok is False:
        return "failed"
    step_id = _step_id(step)
    if current_step_id and step_id == current_step_id:
        return "current"
    if pending_exists and index >= max(0, total - 1):
        return "attention" if state == "WAITING_FOR_EXECUTE" else "pending"
    if state == "COMPLETED":
        return "done"
    if index < max(0, total - 1):
        return "done"
    return "pending"


def _channel_label(channel: Any) -> str:
    value = _string(channel)
    if not value:
        return ""
    return CHANNEL_LABELS.get(value.lower(), _sentence_case(value))


def _extract_order_id(value: str) -> str:
    if not value:
        return ""
    match = re.search(r"\b(ORD-\d+)\b", value, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return value


def _sentence_case(value: str) -> str:
    value = _string(value).replace("_", " ").replace("-", " ").strip()
    if not value:
        return ""
    lowered = value.lower()
    return lowered[:1].upper() + lowered[1:]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _build_artifact_state(current_run: dict, snapshot: dict) -> dict:
    report_result = current_run.get("report_result", {}) if isinstance(current_run, dict) else {}
    frame = _active_frame(snapshot)
    frame_id = _string(frame.get("frame_id") or current_run.get("frame_id"))
    try:
        return build_artifact_state(frame_id, report_result if isinstance(report_result, dict) else {})
    except Exception:
        return {
            "frame_id": frame_id,
            "report_frame_id": _string(report_result.get("frame_id")),
            "has_active_run": bool(frame_id),
            "report_generated": bool(_string(report_result.get("markdown_path")) or _string(report_result.get("html_path"))),
            "evidence_generated": bool(_string(report_result.get("evidence_bundle_path"))),
            "paths": {
                "report_markdown": _string(report_result.get("markdown_path")),
                "report_html": _string(report_result.get("html_path")),
                "evidence_bundle": _string(report_result.get("evidence_bundle_path")),
                "taskframe_json": "",
                "output_dir": "",
            },
            "messages": [],
            "report_result": dict(report_result) if isinstance(report_result, dict) else {},
        }


def _present_artifact_state(frame: dict, artifact_state: dict) -> dict:
    artifact_state = artifact_state if isinstance(artifact_state, dict) else {}
    messages = list(artifact_state.get("messages", [])) if isinstance(artifact_state.get("messages", []), list) else []
    if not _string(frame.get("frame_id")):
        messages = ["No run yet. Run a demo to produce evidence."]
    elif messages and "Artifacts do not belong to the current run." in messages:
        messages = ["Artifacts do not belong to the current run.", "Generate evidence again for this run."]
    elif not artifact_state.get("report_generated") and not artifact_state.get("evidence_generated"):
        messages = ["No evidence pack has been generated for this run yet."]
    return {
        "report_generated": bool(artifact_state.get("report_generated")),
        "evidence_generated": bool(artifact_state.get("evidence_generated")),
        "message": " ".join(messages).strip(),
    }


def _guided_flow(frame: dict, artifact_state: dict, current_run: dict) -> list[dict]:
    state = _string(frame.get("state"))
    has_run = bool(_string(frame.get("frame_id")))
    approval_required = bool(frame.get("pending_actions"))
    artifact_ready = bool(artifact_state.get("report_generated") or artifact_state.get("evidence_generated"))
    openable = artifact_ready and not _artifact_stale(frame, artifact_state)

    if not has_run:
        return [
            {"step": 1, "label": "Select demo", "status": "ready"},
            {"step": 2, "label": "Run automation", "status": "next"},
            {"step": 3, "label": "Review result", "status": "waiting"},
            {"step": 4, "label": "Approve or reject", "status": "waiting"},
            {"step": 5, "label": "Generate evidence", "status": "waiting"},
            {"step": 6, "label": "Open evidence", "status": "waiting"},
        ]

    step3_status = "current" if state and state != "COMPLETED" else "complete"
    step4_status = "attention" if state == "WAITING_FOR_EXECUTE" else "waiting"
    step5_status = "complete" if artifact_ready else "available"
    step6_status = "complete" if openable else "waiting"
    if state.startswith("FAILED"):
        step3_status = "needs attention"
        step4_status = "unavailable"
        step5_status = "available"
        step6_status = "waiting"

    return [
        {"step": 1, "label": "Select demo", "status": "complete"},
        {"step": 2, "label": "Run automation", "status": "complete"},
        {"step": 3, "label": "Review result", "status": step3_status},
        {"step": 4, "label": "Approve or reject", "status": step4_status if approval_required else "waiting"},
        {"step": 5, "label": "Generate evidence", "status": step5_status},
        {"step": 6, "label": "Open evidence", "status": step6_status},
    ]


def _next_action(frame: dict, artifact_state: dict) -> dict:
    state = _string(frame.get("state"))
    has_run = bool(_string(frame.get("frame_id")))
    if not has_run:
        return {"label": "Run selected demo", "primary_button": "Run selected demo", "secondary_button": "Select a demo"}
    if state == "WAITING_FOR_EXECUTE":
        return {
            "label": "Approve or reject the prepared message",
            "primary_button": "Approve & execute dry run",
            "secondary_button": "Reject",
        }
    if state.startswith("FAILED"):
        return {"label": "Generate a failure report", "primary_button": "Generate failure report", "secondary_button": "Start over"}
    if artifact_state.get("report_generated") or artifact_state.get("evidence_generated"):
        return {
            "label": "Open evidence for this run",
            "primary_button": "Open evidence for this run",
            "secondary_button": "Generate evidence for this run",
        }
    return {
        "label": "Generate evidence for this run",
        "primary_button": "Generate evidence for this run",
        "secondary_button": "Start over",
    }


def _current_run_summary(scenario_title: str, frame: dict, artifact_state: dict, approval: dict) -> str:
    frame_id = _string(frame.get("frame_id"))
    frame_short = frame_id if not frame_id or len(frame_id) <= 12 else f"{frame_id[:12]}..."
    state = _string(frame.get("state"))
    if not state:
        state = "READY_TO_RUN"
    status = humanize_state(state) or "Ready to run"
    approval_text = "Required" if approval.get("required") else "Not required"
    evidence_text = "Generated" if artifact_state.get("evidence_generated") else "Not generated"
    return (
        f"Current run: {scenario_title} | "
        f"Status: {status} | "
        f"Approval: {approval_text} | "
        f"Evidence: {evidence_text} | "
        f"Frame: {frame_short or '—'}"
    )


def _artifact_stale(frame: dict, artifact_state: dict) -> bool:
    frame_id = _string(frame.get("frame_id"))
    artifact_frame_id = _string(artifact_state.get("frame_id"))
    return bool(frame_id and artifact_frame_id and frame_id != artifact_frame_id)


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()
