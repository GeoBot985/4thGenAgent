from __future__ import annotations

import re
from typing import Any


STORY_TYPES = {"customer_status", "report_generation", "procurement", "accounting", "unknown"}

STEP_LABELS = {
    "customer_status": {
        "extract_order_ref": "Read the customer message",
        "classify_message": "Understood this is an order-status question",
        "validate_order_ref": "Checked that the order number is valid",
        "lookup_customer": "Found the customer record",
        "lookup_order": "Found the order record",
        "read_payment": "Checked payment records",
        "lookup_shipment": "Checked shipment records",
        "build_order_context": "Built the order status facts",
        "draft_reply": "Prepared a customer reply",
        "validate_reply": "Checked the reply against the facts",
    },
    "report_generation": {
        "read_business_data": "Read business data",
        "check_source_records": "Checked source records",
        "build_report_summary": "Built report summary",
        "generate_report": "Generated report artifact",
        "prepare_evidence_pack": "Prepared evidence pack",
    },
    "procurement": {
        "check_inventory": "Checked inventory records",
        "build_reorder_plan": "Built a reorder plan",
        "draft_supplier_message": "Prepared supplier communication",
        "prepare_evidence_pack": "Prepared evidence pack",
    },
    "accounting": {
        "read_sheets": "Read accounting data",
        "reconcile_payments": "Reconciled payment records",
        "build_exception_summary": "Built exception summary",
        "prepare_evidence_pack": "Prepared evidence pack",
    },
}

FAILED_STATES = {"FAILED", "FAILED_VALIDATION", "FAILED_EXECUTION", "FAILED_COMPLETION"}


def _story_card(title: str, kind: str, body: str = "", items: list[str] | None = None) -> dict:
    return {
        "title": title,
        "kind": kind,
        "body": body,
        "items": items or [],
    }


def _story_actions(
    *,
    show_approve: bool,
    show_reject: bool,
    show_open_business_report: bool,
    show_create_open_run_report: bool,
) -> dict[str, bool]:
    return {
        "show_approve": show_approve,
        "show_reject": show_reject,
        "show_open_business_report": show_open_business_report,
        "show_create_open_run_report": show_create_open_run_report,
    }


def _report_paths(business_html: str = "", business_markdown: str = "", business_evidence: str = "", run_html: str = "", run_markdown: str = "", run_evidence: str = "") -> dict:
    return {
        "business_report": {
            "exists": bool(business_html),
            "html_path": business_html,
            "markdown_path": business_markdown,
            "evidence_path": business_evidence,
        },
        "run_report": {
            "exists": bool(run_html),
            "html_path": run_html,
            "markdown_path": run_markdown,
            "evidence_bundle_path": run_evidence,
        },
    }


def build_demo_story(
    snapshot: dict,
    current_run: dict | None = None,
    selected_scenario: dict | None = None,
) -> dict:
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    current_run = current_run if isinstance(current_run, dict) else {}
    selected_scenario = selected_scenario if isinstance(selected_scenario, dict) else {}

    selected_type = _detect_story_type(
        scenario=selected_scenario,
        frame=current_run.get("snapshot", {}).get("active_frame") if isinstance(current_run.get("snapshot"), dict) else current_run,
        fallback_text=" ".join(
            _clean_value(value)
            for value in (
                selected_scenario.get("id"),
                selected_scenario.get("manifest_id"),
                selected_scenario.get("category"),
                selected_scenario.get("label"),
                selected_scenario.get("name"),
                selected_scenario.get("description"),
                selected_scenario.get("scenario_type"),
            )
        ),
    )

    run_frame = _run_frame(current_run)
    run_event = _run_event(current_run, snapshot)
    run_type = _detect_story_type(scenario=current_run, fallback_text=" ".join(_frame_text_values(run_frame, current_run, run_event))) if current_run else "unknown"
    if run_frame:
        if selected_scenario and selected_type != "unknown" and run_type != "unknown" and not _story_types_compatible(selected_type, run_type):
            return _finalize_story(_placeholder_story(selected_scenario, selected_type), current_run, selected_scenario)
        story_type = selected_type if selected_type != "unknown" else run_type
        compatible = selected_type == "unknown" or run_type == "unknown" or selected_type == run_type
        return _finalize_story(_build_story_for_type(story_type, run_frame, run_event, current_run, selected_scenario, compatible), current_run, selected_scenario)

    if selected_scenario:
        return _finalize_story(_placeholder_story(selected_scenario, selected_type), current_run, selected_scenario)

    snapshot_frame = snapshot.get("active_frame") if isinstance(snapshot.get("active_frame"), dict) else {}
    if snapshot_frame:
        snapshot_run_type = _detect_story_type(scenario=snapshot, frame=snapshot_frame, fallback_text=" ".join(_frame_text_values(snapshot_frame, snapshot, snapshot.get("active_event") if isinstance(snapshot.get("active_event"), dict) else {})))
        if selected_scenario and selected_type != "unknown" and snapshot_run_type != "unknown" and not _story_types_compatible(selected_type, snapshot_run_type):
            return _finalize_story(_placeholder_story(selected_scenario, selected_type), current_run, selected_scenario)
        story_type = selected_type if selected_type != "unknown" else snapshot_run_type
        compatible = selected_type == "unknown" or snapshot_run_type == "unknown" or selected_type == snapshot_run_type
        return _finalize_story(_build_story_for_type(story_type, snapshot_frame, snapshot.get("active_event") if isinstance(snapshot.get("active_event"), dict) else {}, current_run, selected_scenario, compatible), current_run, selected_scenario)

    return _finalize_story(_empty_story(), current_run, selected_scenario)


def humanize_step_id(step_id: str) -> str:
    return step_id.replace("_", " ").strip().capitalize()


def _build_story_for_type(
    story_type: str,
    frame: dict,
    event: dict,
    current_run: dict,
    selected_scenario: dict,
    compatible: bool,
) -> dict:
    story_type = story_type if story_type in STORY_TYPES else "unknown"
    state = _state(frame, current_run)
    has_frame = bool(frame)
    pending_action_count = _pending_action_count(frame, current_run)
    failed_validation = state.startswith("FAILED") or (has_frame and pending_action_count == 0 and _looks_like_validation_stop(frame))
    mode = _story_mode(state, has_frame, failed_validation)

    if story_type == "report_generation":
        return _build_report_story(frame, event, current_run, state, has_frame, mode, failed_validation, compatible, selected_scenario)
    if story_type == "procurement":
        return _build_procurement_story(frame, event, current_run, state, has_frame, mode, failed_validation, compatible, selected_scenario)
    if story_type == "accounting":
        return _build_accounting_story(frame, event, current_run, state, has_frame, mode, failed_validation, compatible, selected_scenario)
    return _build_customer_status_story(frame, event, current_run, state, has_frame, mode, failed_validation, compatible, selected_scenario)


def _build_customer_status_story(
    frame: dict,
    event: dict,
    current_run: dict,
    state: str,
    has_frame: bool,
    mode: str,
    failed_validation: bool,
    compatible: bool,
    selected_scenario: dict,
) -> dict:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    inputs = frame.get("inputs") if isinstance(frame.get("inputs"), dict) else {}
    outputs = frame.get("outputs") if isinstance(frame.get("outputs"), dict) else {}
    customer = _customer_label(frame, payload, outputs)
    order = _order_label(frame, payload, inputs, outputs)
    message = _message_text(payload, inputs)
    worker_steps = _customer_worker_steps(frame, state, message, order, failed_validation, compatible)
    show_prepared_reply = has_frame and not failed_validation and compatible and bool(_draft_reply(outputs))
    show_approval_actions = state in {"WAITING_FOR_EXECUTE", "WAITING_FOR_APPROVAL"} and not failed_validation and compatible
    draft_reply = _draft_reply(outputs) if show_prepared_reply else ""
    facts = _customer_facts(frame, outputs, customer, order) if show_prepared_reply else []
    outcome_title, outcome_text, failed_check, safe_outcome = _customer_outcome(mode, state, draft_reply, facts, failed_validation)
    return {
        "story_type": "customer_status",
        "mode": mode,
        "headline": _customer_headline(mode, state, has_frame, compatible),
        "subheadline": _customer_subheadline(mode, state, has_frame, compatible),
        "request_title": "Customer request",
        "worker_title": "What the worker checked",
        "outcome_title": outcome_title,
        "outcome_text": outcome_text,
        "failed_check": failed_check,
        "safe_outcome": safe_outcome,
        "show_prepared_reply": show_prepared_reply,
        "show_approval_actions": show_approval_actions,
        "customer": customer,
        "order": order,
        "message": message,
        "worker_steps": worker_steps,
        "draft_reply": draft_reply,
        "facts": facts,
        "decision_title": "Decision needed" if show_approval_actions else ("No approval needed." if failed_validation else "Review status"),
        "decision_text": _customer_decision_text(mode, state, has_frame, compatible, failed_validation),
        "can_approve": show_approval_actions,
        "can_reject": show_approval_actions,
        "can_create_audit_pack": has_frame,
        "can_open_audit_pack": _can_open_audit_pack(current_run),
        "show_report_actions": True,
        "can_open_report": bool(_can_open_audit_pack(current_run)),
        "can_open_business_report": False,
        "can_open_run_report": bool(_can_open_audit_pack(current_run)),
        "can_create_open_run_report": has_frame,
        "report_text": "",
        "report_title": "",
        "request_text": _customer_request_text(customer, order, message),
        "business_report_html_path": "",
        "business_report_markdown_path": "",
        "business_report_evidence_bundle_path": "",
        "run_report_html_path": _clean_value(current_run.get("report_result", {}).get("run_report_html_path")) if isinstance(current_run.get("report_result"), dict) else "",
        "run_report_markdown_path": _clean_value(current_run.get("report_result", {}).get("run_report_markdown_path")) if isinstance(current_run.get("report_result"), dict) else "",
        "run_report_evidence_bundle_path": _clean_value(current_run.get("report_result", {}).get("run_report_evidence_bundle_path")) if isinstance(current_run.get("report_result"), dict) else "",
    }


def _build_report_story(
    frame: dict,
    event: dict,
    current_run: dict,
    state: str,
    has_frame: bool,
    mode: str,
    failed_validation: bool,
    compatible: bool,
    selected_scenario: dict,
) -> dict:
    outputs = frame.get("outputs") if isinstance(frame.get("outputs"), dict) else {}
    report_result = current_run.get("report_result") if isinstance(current_run.get("report_result"), dict) else {}
    request_text = _report_request_text(selected_scenario, frame, compatible)
    worker_steps = _report_worker_steps(frame, state, failed_validation, compatible)
    business_report_html_path = _report_path(report_result, "business_report_html_path", "")
    business_report_markdown_path = _report_path(report_result, "business_report_markdown_path", "")
    business_report_evidence_bundle_path = _report_path(report_result, "business_report_evidence_bundle_path", "")
    run_report_html_path = _report_path(report_result, "run_report_html_path", _report_path(report_result, "html_path", ""))
    run_report_markdown_path = _report_path(report_result, "run_report_markdown_path", _report_path(report_result, "markdown_path", ""))
    run_report_evidence_bundle_path = _report_path(report_result, "run_report_evidence_bundle_path", _report_path(report_result, "evidence_bundle_path", ""))
    report_generated = compatible and bool(business_report_html_path or run_report_html_path)
    headline = "Report generated successfully" if report_generated else "Selected demo is waiting to run."
    if mode == "failed_validation":
        headline = "Worker stopped — validation failed"
    elif not compatible:
        headline = "Selected demo is waiting to run."
    if report_generated:
        subheadline = "The worker generated a business report and prepared audit evidence."
    elif mode == "failed_validation":
        subheadline = "No business report artifact was found for this run."
    else:
        subheadline = "Click Start demo to generate this report."
    outcome_title = "Business report generated" if report_generated else "No business report artifact was found for this run."
    if mode == "failed_validation":
        outcome_title = "Why the worker stopped"
    if report_generated:
        outcome_text = "\n".join(
            [
                "Business report generated",
                f"File: {business_report_html_path or run_report_html_path}",
                "Also created:",
                "- Markdown report",
                "- Evidence bundle",
                "",
                "Run report generated",
                f"File: {run_report_html_path}",
                "This report shows:",
                "- manifest steps",
                "- step results",
                "- validations",
                "- evidence",
                "- pending actions",
            ]
        )
    elif mode == "failed_validation":
        outcome_text = "The worker could not safely generate this report.\n\nReason:\nRequired business validation failed.\n\nNo report was generated.\nNo audit evidence was sent."
    else:
        outcome_text = "No business report artifact was found for this run."
    return {
        "story_type": "report_generation",
        "mode": "report_generated" if report_generated and mode != "failed_validation" else mode,
        "headline": headline,
        "subheadline": subheadline,
        "request_title": "Report request",
        "worker_title": "What the worker checked",
        "outcome_title": outcome_title,
        "outcome_text": outcome_text,
        "failed_check": "Required business validation failed." if mode == "failed_validation" else "",
        "safe_outcome": "No business report artifact was found for this run." if mode == "failed_validation" else "",
        "show_prepared_reply": False,
        "show_approval_actions": False,
        "draft_reply": "",
        "worker_steps": worker_steps,
        "facts": _report_facts(frame, outputs, report_generated),
        "decision_title": "Report actions",
        "decision_text": "Open the business report or run report. The worker prepared audit evidence for review." if report_generated else "Click Start demo to generate this report.",
        "can_approve": False,
        "can_reject": False,
        "can_create_audit_pack": has_frame,
        "can_open_audit_pack": bool(run_report_html_path and compatible),
        "show_report_actions": True,
        "can_open_report": bool(run_report_html_path and compatible),
        "can_open_business_report": bool(business_report_html_path and compatible),
        "can_open_run_report": bool(run_report_html_path and compatible),
        "can_create_open_run_report": has_frame,
        "report_text": outcome_text,
        "report_title": "Business report generated" if report_generated else "Run report",
        "request_text": request_text,
        "business_report_html_path": business_report_html_path,
        "business_report_markdown_path": business_report_markdown_path,
        "business_report_evidence_bundle_path": business_report_evidence_bundle_path,
        "run_report_html_path": run_report_html_path,
        "run_report_markdown_path": run_report_markdown_path,
        "run_report_evidence_bundle_path": run_report_evidence_bundle_path,
    }


def _build_procurement_story(
    frame: dict,
    event: dict,
    current_run: dict,
    state: str,
    has_frame: bool,
    mode: str,
    failed_validation: bool,
    compatible: bool,
    selected_scenario: dict,
) -> dict:
    outputs = frame.get("outputs") if isinstance(frame.get("outputs"), dict) else {}
    request_text = _generic_request_text(selected_scenario, "Procurement request", frame, event, compatible)
    worker_steps = _generic_worker_steps(frame, "procurement", state, failed_validation, compatible)
    report_generated = _report_generated(current_run.get("report_result") if isinstance(current_run.get("report_result"), dict) else {}, outputs)
    return {
        "story_type": "procurement",
        "mode": mode,
        "headline": "Procurement ready" if compatible else "Selected demo is waiting to run.",
        "subheadline": "The worker prepared procurement evidence and draft outputs." if compatible else "Click Start demo to run this scenario.",
        "request_title": "Procurement request",
        "worker_title": "What the worker checked",
        "outcome_title": "Prepared procurement action",
        "outcome_text": "The worker prepared procurement outputs and audit evidence." if compatible else "Click Start demo to generate this procurement run.",
        "failed_check": "Required business validation failed." if failed_validation else "",
        "safe_outcome": "No procurement action was prepared." if failed_validation else "",
        "show_prepared_reply": False,
        "show_approval_actions": False,
        "draft_reply": "",
        "worker_steps": worker_steps,
        "facts": _generic_facts(frame, outputs),
        "decision_title": "Procurement actions",
        "decision_text": "Review the prepared procurement outputs and audit evidence." if compatible else "Click Start demo to run this scenario.",
        "can_approve": False,
        "can_reject": False,
        "can_create_audit_pack": has_frame,
        "can_open_audit_pack": report_generated and compatible,
        "show_report_actions": True,
        "can_open_report": False,
        "can_open_business_report": False,
        "can_open_run_report": bool(_can_open_audit_pack(current_run)),
        "can_create_open_run_report": has_frame,
        "report_text": "",
        "report_title": "",
        "request_text": request_text,
        "business_report_html_path": "",
        "business_report_markdown_path": "",
        "business_report_evidence_bundle_path": "",
        "run_report_html_path": "",
        "run_report_markdown_path": "",
        "run_report_evidence_bundle_path": "",
    }


def _build_accounting_story(
    frame: dict,
    event: dict,
    current_run: dict,
    state: str,
    has_frame: bool,
    mode: str,
    failed_validation: bool,
    compatible: bool,
    selected_scenario: dict,
) -> dict:
    outputs = frame.get("outputs") if isinstance(frame.get("outputs"), dict) else {}
    request_text = _generic_request_text(selected_scenario, "Accounting request", frame, event, compatible)
    worker_steps = _generic_worker_steps(frame, "accounting", state, failed_validation, compatible)
    report_generated = _report_generated(current_run.get("report_result") if isinstance(current_run.get("report_result"), dict) else {}, outputs)
    return {
        "story_type": "accounting",
        "mode": mode,
        "headline": "Accounting ready" if compatible else "Selected demo is waiting to run.",
        "subheadline": "The worker reconciled business records and prepared evidence." if compatible else "Click Start demo to run this scenario.",
        "request_title": "Accounting request",
        "worker_title": "What the worker checked",
        "outcome_title": "Prepared reconciliation result",
        "outcome_text": "The worker prepared accounting outputs and audit evidence." if compatible else "Click Start demo to generate this accounting run.",
        "failed_check": "Required business validation failed." if failed_validation else "",
        "safe_outcome": "No accounting output was prepared." if failed_validation else "",
        "show_prepared_reply": False,
        "show_approval_actions": False,
        "draft_reply": "",
        "worker_steps": worker_steps,
        "facts": _generic_facts(frame, outputs),
        "decision_title": "Accounting actions",
        "decision_text": "Review the prepared accounting outputs and audit evidence." if compatible else "Click Start demo to run this scenario.",
        "can_approve": False,
        "can_reject": False,
        "can_create_audit_pack": has_frame,
        "can_open_audit_pack": report_generated and compatible,
        "show_report_actions": True,
        "can_open_report": False,
        "can_open_business_report": False,
        "can_open_run_report": bool(_can_open_audit_pack(current_run)),
        "can_create_open_run_report": has_frame,
        "report_text": "",
        "report_title": "",
        "request_text": request_text,
        "business_report_html_path": "",
        "business_report_markdown_path": "",
        "business_report_evidence_bundle_path": "",
        "run_report_html_path": "",
        "run_report_markdown_path": "",
        "run_report_evidence_bundle_path": "",
    }


def _story_types_compatible(selected_type: str, frame_type: str) -> bool:
    if selected_type == "unknown" or frame_type == "unknown":
        return True
    return selected_type == frame_type


def _story_is_compatible(story_type: str, frame: dict, current_run: dict, selected_scenario: dict) -> bool:
    if story_type == "unknown":
        return True
    frame_type = _detect_story_type(frame=frame, fallback_text=" ".join(_frame_text_values(frame, current_run, current_run.get("snapshot", {}).get("active_event") if isinstance(current_run.get("snapshot"), dict) else {})))
    if frame_type == "unknown":
        return True
    return story_type == frame_type


def _customer_headline(mode: str, state: str, has_frame: bool, compatible: bool) -> str:
    if not has_frame or not compatible:
        return "Selected demo is waiting to run."
    if mode == "failed_validation":
        return "Worker stopped — validation failed"
    if mode == "completed":
        return "Demo completed"
    if state in {"READY", "RUNNING"}:
        return "Worker is processing the request"
    if state in {"WAITING_FOR_EXECUTE", "WAITING_FOR_APPROVAL"}:
        return "Draft reply ready — approval required"
    return "Demo ready"


def _customer_subheadline(mode: str, state: str, has_frame: bool, compatible: bool) -> str:
    if not has_frame or not compatible:
        return "Click Start demo to run this scenario."
    if mode == "failed_validation":
        return "No customer message was prepared or sent."
    if mode == "completed":
        return "No live customer message was sent in demo mode."
    return "No live customer message will be sent in demo mode."


def _customer_decision_text(mode: str, state: str, has_frame: bool, compatible: bool, failed_validation: bool) -> str:
    if not has_frame or not compatible:
        return "Click Start demo to run this scenario."
    if failed_validation:
        return "The worker stopped before preparing a customer reply."
    if state in {"WAITING_FOR_EXECUTE", "WAITING_FOR_APPROVAL"}:
        return "Approve this prepared reply?"
    if mode == "completed":
        return "The demo finished. Review the prepared reply and audit pack."
    return "Review the prepared reply and decide whether to continue."


def _customer_outcome(mode: str, state: str, draft_reply: str, facts: list[str], failed_validation: bool) -> tuple[str, str, str, str]:
    if failed_validation:
        return (
            "Why the worker stopped",
            "\n".join(
                [
                    "The worker could not safely answer this customer request.",
                    "",
                    "Reason:",
                    "Customer/order validation failed.",
                    "",
                    "No reply was prepared.",
                    "No message was sent.",
                ]
            ),
            "Customer record could not be confirmed.",
            "No customer reply was prepared or sent.",
        )
    lines = ["Prepared reply:", "", draft_reply or "No customer reply was prepared."]
    if facts:
        lines.extend(["", "Facts confirmed:"])
        lines.extend(f"- {fact}" for fact in facts if fact)
    return "Prepared customer reply", "\n".join(lines), "", ""


def _customer_request_text(customer: str, order: str, message: str) -> str:
    lines = []
    if customer:
        lines.append(f"Customer: {customer}")
    if order:
        lines.append(f"Order: {order}")
    if message:
        if lines:
            lines.append("")
        lines.append(f"Message: {message}")
    return "\n".join(lines) if lines else "No customer request available."


def _customer_label(frame: dict, payload: dict, outputs: dict) -> str:
    candidates = (
        outputs.get("customer_name"),
        outputs.get("customer", {}).get("name") if isinstance(outputs.get("customer"), dict) else "",
        outputs.get("customer", {}).get("display_name") if isinstance(outputs.get("customer"), dict) else "",
        payload.get("customer_name"),
        payload.get("customer"),
        frame.get("inputs", {}).get("customer_name") if isinstance(frame.get("inputs"), dict) else "",
        frame.get("inputs", {}).get("customer") if isinstance(frame.get("inputs"), dict) else "",
        payload.get("customer_id"),
        frame.get("inputs", {}).get("customer_id") if isinstance(frame.get("inputs"), dict) else "",
    )
    for candidate in candidates:
        value = _clean_value(candidate)
        if value:
            return value
    return ""


def _order_label(frame: dict, payload: dict, inputs: dict, outputs: dict) -> str:
    candidates = (
        outputs.get("order_id"),
        outputs.get("order_ref"),
        inputs.get("order_id"),
        inputs.get("order_ref"),
        payload.get("order_id"),
        payload.get("order_ref"),
        payload.get("message"),
        inputs.get("message"),
    )
    for candidate in candidates:
        value = _extract_order_ref(_clean_value(candidate))
        if value:
            return value
    return ""


def _message_text(payload: dict, inputs: dict) -> str:
    for candidate in (
        payload.get("message"),
        inputs.get("message"),
        payload.get("text"),
        inputs.get("text"),
    ):
        value = _clean_value(candidate)
        if value:
            return value
    return ""


def _report_request_text(selected_scenario: dict, frame: dict, compatible: bool) -> str:
    label = _clean_value(selected_scenario.get("label") or selected_scenario.get("name") or selected_scenario.get("scenario_title"))
    description = _clean_value(selected_scenario.get("description") or selected_scenario.get("scenario_summary"))
    if not compatible:
        return "Selected demo is waiting to run.\nClick Start demo to generate this report."
    lines = [f"Report: {label}" if label else "Report request"]
    if description:
        lines.append(description)
    lines.append("Generate the selected business report.")
    return "\n".join(lines)


def _generic_request_text(selected_scenario: dict, fallback_title: str, frame: dict, event: dict, compatible: bool) -> str:
    label = _clean_value(selected_scenario.get("label") or selected_scenario.get("name") or selected_scenario.get("scenario_title"))
    description = _clean_value(selected_scenario.get("description") or selected_scenario.get("scenario_summary"))
    if not compatible:
        return f"Selected demo is waiting to run.\nClick Start demo to run this scenario."
    lines = [f"{fallback_title}: {label}" if label else fallback_title]
    if description:
        lines.append(description)
    return "\n".join(lines)


def _customer_worker_steps(frame: dict, state: str, message: str, order: str, failed_validation: bool, compatible: bool) -> list[dict[str, str]]:
    steps = frame.get("steps") if isinstance(frame.get("steps"), list) else []
    rendered: list[dict[str, str]] = []
    for index, item in enumerate(steps):
        if not isinstance(item, dict):
            continue
        step_id = str(item.get("step_id") or item.get("id") or "").strip()
        if not step_id:
            continue
        status = _step_status(item, index, len(steps), state)
        rendered.append({"label": _customer_step_label(step_id, status, order, message), "status": status})
    if rendered:
        if failed_validation and not any(step.get("status") == "not_reached" for step in rendered):
            rendered.append({"label": "Stopped before checking shipment and payment", "status": "not_reached"})
        return rendered
    if message:
        if failed_validation:
            return [
                {"label": "Read the customer message", "status": "done"},
                {"label": f"Found order number {order}" if order else "Found the order number", "status": "done"},
                {"label": "Understood this is an order-status question", "status": "done"},
                {"label": "Could not confirm the customer record", "status": "failed"},
                {"label": "Stopped before checking shipment and payment", "status": "not_reached"},
            ]
        return [
            {"label": "Read the customer message", "status": "done"},
            {"label": f"Found order number {order}" if order else "Found the order number", "status": "done"},
            {"label": "Understood this is an order-status question", "status": "current" if state in {"READY", "RUNNING"} else "done"},
            {"label": "Prepared a customer reply", "status": "done" if state in {"WAITING_FOR_EXECUTE", "WAITING_FOR_APPROVAL", "COMPLETED"} else "current"},
        ]
    if not compatible:
        return [{"label": "Selected demo is waiting to run", "status": "current"}]
    return []


def _report_worker_steps(frame: dict, state: str, failed_validation: bool, compatible: bool) -> list[dict[str, str]]:
    steps = frame.get("steps") if isinstance(frame.get("steps"), list) else []
    rendered: list[dict[str, str]] = []
    for index, item in enumerate(steps):
        if not isinstance(item, dict):
            continue
        step_id = str(item.get("step_id") or item.get("id") or "").strip()
        if not step_id:
            continue
        rendered.append({"label": _report_step_label(step_id, index, len(steps), state, failed_validation), "status": _step_status(item, index, len(steps), state)})
    if rendered:
        return rendered
    if not compatible:
        return [{"label": "Selected demo is waiting to run", "status": "current"}]
    if failed_validation:
        return [
            {"label": "Read business data", "status": "done"},
            {"label": "Checked source records", "status": "done"},
            {"label": "Could not generate report artifact", "status": "failed"},
            {"label": "Stopped before preparing evidence pack", "status": "not_reached"},
        ]
    return [
        {"label": "Read business data", "status": "done"},
        {"label": "Checked source records", "status": "done"},
        {"label": "Built report summary", "status": "done"},
        {"label": "Generated report artifact", "status": "done" if state in {"WAITING_FOR_EXECUTE", "WAITING_FOR_APPROVAL", "COMPLETED"} else "current"},
        {"label": "Prepared evidence pack", "status": "done" if state in {"WAITING_FOR_EXECUTE", "WAITING_FOR_APPROVAL", "COMPLETED"} else "pending"},
    ]


def _generic_worker_steps(frame: dict, story_type: str, state: str, failed_validation: bool, compatible: bool) -> list[dict[str, str]]:
    steps = frame.get("steps") if isinstance(frame.get("steps"), list) else []
    rendered: list[dict[str, str]] = []
    for index, item in enumerate(steps):
        if not isinstance(item, dict):
            continue
        step_id = str(item.get("step_id") or item.get("id") or "").strip()
        if not step_id:
            continue
        rendered.append({"label": _step_label(story_type, step_id, index, len(steps), state, failed_validation), "status": _step_status(item, index, len(steps), state)})
    if rendered:
        return rendered
    if not compatible:
        return [{"label": "Selected demo is waiting to run", "status": "current"}]
    return []


def _customer_step_label(step_id: str, status: str, order: str, message: str) -> str:
    if status == "failed":
        if "customer" in step_id or "ownership" in step_id:
            return "Could not confirm the customer record"
        if "order" in step_id:
            return f"Could not confirm order {order}" if order else "Could not confirm the order record"
        if "reply" in step_id:
            return "Could not prepare a customer reply"
        return "Validation failed"
    if status == "not_reached":
        if "shipment" in step_id or "payment" in step_id:
            return "Stopped before checking shipment and payment"
        return "Stopped before continuing"
    if step_id == "extract_order_ref":
        return "Read the customer message"
    if step_id == "classify_message":
        return "Understood this is an order-status question"
    if step_id == "lookup_order" and order:
        return f"Found order number {order}"
    label = STEP_LABELS["customer_status"].get(step_id)
    if label:
        return label
    return humanize_step_id(step_id)


def _report_step_label(step_id: str, index: int, total: int, state: str, failed_validation: bool) -> str:
    base = STEP_LABELS["report_generation"].get(step_id)
    if failed_validation:
        if "report" in step_id:
            return "Could not generate report artifact"
        if "evidence" in step_id:
            return "Stopped before preparing evidence pack"
    if base:
        return base
    if "report" in step_id and state in {"WAITING_FOR_EXECUTE", "WAITING_FOR_APPROVAL", "COMPLETED"}:
        return "Generated report artifact"
    if "evidence" in step_id:
        return "Prepared evidence pack"
    return humanize_step_id(step_id)


def _step_label(story_type: str, step_id: str, index: int, total: int, state: str, failed_validation: bool) -> str:
    labels = STEP_LABELS.get(story_type, {})
    if failed_validation:
        if story_type == "customer_status":
            return _customer_step_label(step_id, "failed", "", "")
        if story_type == "report_generation":
            return _report_step_label(step_id, index, total, state, True)
        if story_type in {"procurement", "accounting"}:
            return "Validation failed" if index == total - 1 else humanize_step_id(step_id)
    if story_type == "customer_status":
        return _customer_step_label(step_id, "done" if state in {"WAITING_FOR_EXECUTE", "WAITING_FOR_APPROVAL", "COMPLETED"} else "current", "", "")
    if story_type == "report_generation":
        return _report_step_label(step_id, index, total, state, False)
    label = labels.get(step_id)
    return label or humanize_step_id(step_id)


def _step_status(step: dict, index: int, total: int, state: str) -> str:
    status = str(step.get("status", "") or "").upper()
    ok = step.get("ok")
    if ok is False or status in FAILED_STATES:
        return "failed"
    if status in {"CURRENT", "IN_PROGRESS"}:
        return "current"
    if status in {"PENDING", "WAITING", "READY"}:
        return "attention" if index == total - 1 and state in {"WAITING_FOR_EXECUTE", "WAITING_FOR_APPROVAL"} else "pending"
    if state in {"COMPLETED", "WAITING_FOR_EXECUTE", "WAITING_FOR_APPROVAL"} or ok is True:
        return "done"
    if index < total - 1:
        return "done"
    return "current"


def _customer_facts(frame: dict, outputs: dict, customer: str, order: str) -> list[str]:
    facts: list[str] = []
    order_data = outputs.get("order") if isinstance(outputs.get("order"), dict) else {}
    shipment = outputs.get("shipment") if isinstance(outputs.get("shipment"), dict) else {}
    validations = frame.get("validations") if isinstance(frame.get("validations"), list) else []
    if order or order_data:
        facts.append("Order exists")
    if customer or any(_validation_matches(item, {"customer", "ownership"}) for item in validations if isinstance(item, dict)):
        facts.append("Customer ownership verified")
    status = _clean_value(order_data.get("status") or outputs.get("order_status") or shipment.get("status"))
    if status:
        facts.append(f"Shipment status: {status}")
    estimated = _clean_value(shipment.get("estimated_delivery") or shipment.get("estimated_delivery_date") or outputs.get("estimated_delivery"))
    if estimated:
        facts.append(f"Estimated delivery: {estimated}")
    tracking = _clean_value(shipment.get("tracking_reference") or shipment.get("tracking_ref") or outputs.get("tracking_reference"))
    if tracking:
        facts.append(f"Tracking reference: {tracking}")
    return facts


def _report_facts(frame: dict, outputs: dict, report_generated: bool) -> list[str]:
    facts: list[str] = []
    if not report_generated:
        return facts
    if outputs:
        if outputs.get("summary") or outputs.get("report_summary"):
            facts.append("Report summary prepared")
        if outputs.get("report_artifact") or outputs.get("report") or report_generated:
            facts.append("Business report generated")
        if outputs.get("evidence_bundle") or outputs.get("evidence_bundle_path") or outputs.get("evidence"):
            facts.append("Evidence pack prepared")
    if not facts and report_generated:
        facts.append("Business report generated")
    return facts


def _generic_facts(frame: dict, outputs: dict) -> list[str]:
    facts: list[str] = []
    for key in sorted(outputs.keys()):
        if key.endswith("_status") or key.endswith("_summary") or key.endswith("_result"):
            facts.append(humanize_step_id(key))
    return facts[:4]


def _draft_reply(outputs: dict) -> str:
    draft = outputs.get("draft_reply")
    if isinstance(draft, dict):
        return _clean_value(draft.get("body") or draft.get("reply") or draft.get("text"))
    return _clean_value(draft)


def _report_generated(report_result: dict, outputs: dict) -> bool:
    if isinstance(report_result, dict):
        if any(
            _clean_value(report_result.get(key))
            for key in ("business_report_markdown_path", "business_report_html_path", "business_report_evidence_bundle_path", "run_report_markdown_path", "run_report_html_path", "run_report_evidence_bundle_path", "markdown_path", "html_path", "evidence_bundle_path")
        ):
            return True
    return bool(any(_clean_value(outputs.get(key)) for key in ("report_artifact", "report_summary", "report")))


def _report_path(report_result: dict, key: str, fallback: str = "") -> str:
    if isinstance(report_result, dict):
        value = _clean_value(report_result.get(key))
        if value:
            return value
    return _clean_value(fallback)


def _can_open_audit_pack(current_run: dict) -> bool:
    report_result = current_run.get("report_result") if isinstance(current_run.get("report_result"), dict) else {}
    if not report_result:
        return False
    if report_result.get("ok") is False:
        return False
    for key in ("markdown_path", "html_path", "evidence_bundle_path"):
        if _clean_value(report_result.get(key)):
            return True
    return False


def _state(frame: dict, current_run: dict) -> str:
    for candidate in (frame.get("state"), current_run.get("state"), current_run.get("target_frame_state")):
        value = str(candidate or "").strip().upper()
        if value:
            return value
    return ""


def _pending_action_count(frame: dict, current_run: dict) -> int:
    for source in (frame, current_run):
        pending = source.get("pending_actions")
        if isinstance(pending, list):
            return len(pending)
        snapshot = source.get("snapshot") if isinstance(source.get("snapshot"), dict) else {}
        pending = snapshot.get("pending_actions")
        if isinstance(pending, list):
            return len(pending)
    return 0


def _looks_like_validation_stop(frame: dict) -> bool:
    validations = frame.get("validations")
    if not isinstance(validations, list):
        return False
    for item in validations:
        if not isinstance(item, dict):
            continue
        if item.get("ok") is False:
            return True
        text = " ".join(_clean_value(item.get(key)) for key in ("step_id", "validation_id", "label", "message")).lower()
        if "validat" in text or "customer" in text or "order" in text:
            return True
    return False


def _run_frame(current_run: dict) -> dict:
    snapshot = current_run.get("snapshot") if isinstance(current_run.get("snapshot"), dict) else {}
    frame = snapshot.get("active_frame") if isinstance(snapshot.get("active_frame"), dict) else {}
    if frame:
        return frame
    frame = current_run.get("active_frame") if isinstance(current_run.get("active_frame"), dict) else {}
    if frame:
        return frame
    if current_run.get("state") or current_run.get("frame_id"):
        return current_run
    return {}


def _run_event(current_run: dict, snapshot: dict) -> dict:
    run_snapshot = current_run.get("snapshot") if isinstance(current_run.get("snapshot"), dict) else {}
    event = run_snapshot.get("active_event") if isinstance(run_snapshot.get("active_event"), dict) else {}
    if event:
        return event
    return snapshot.get("active_event") if isinstance(snapshot.get("active_event"), dict) else {}


def _placeholder_story(selected_scenario: dict, selected_type: str) -> dict:
    label = _clean_value(selected_scenario.get("label") or selected_scenario.get("name") or selected_scenario.get("scenario_title"))
    headline = f"Selected demo: {label}" if label else "Selected demo"
    summary = _clean_value(selected_scenario.get("description") or selected_scenario.get("scenario_summary"))
    if selected_type == "report_generation":
        headline = "Selected demo is waiting to run."
        summary = "Click Start demo to generate this report."
    elif selected_type in {"procurement", "accounting"}:
        headline = "Selected demo is waiting to run."
    subheadline = "Click Start demo to run this scenario."
    if selected_type == "report_generation":
        subheadline = "Click Start demo to generate this report."
    elif summary:
        subheadline = f"{summary} Click Start demo to run this scenario."
    return {
        "story_type": selected_type if selected_type in STORY_TYPES else "unknown",
        "mode": "idle",
        "headline": headline,
        "subheadline": subheadline,
        "request_title": "Report request" if selected_type == "report_generation" else "Selected demo",
        "worker_title": "What the worker checked" if selected_type == "report_generation" else "Selected demo",
        "outcome_title": "Run report" if selected_type == "report_generation" else "Selected demo",
        "outcome_text": "No business report artifact was found for this run." if selected_type == "report_generation" else "Click Start demo to run this scenario.",
        "failed_check": "",
        "safe_outcome": "",
        "show_prepared_reply": False,
        "show_approval_actions": False,
        "draft_reply": "",
        "customer": "",
        "order": "",
        "message": "",
        "worker_steps": [],
        "facts": [],
        "decision_title": "Report actions" if selected_type == "report_generation" else "Selected demo",
        "decision_text": "Click Start demo to generate this report." if selected_type == "report_generation" else "Click Start demo to run this scenario.",
        "can_approve": False,
        "can_reject": False,
        "can_create_audit_pack": False,
        "can_open_audit_pack": False,
        "show_report_actions": False,
        "can_open_report": False,
        "can_open_business_report": False,
        "can_open_run_report": False,
        "can_create_open_run_report": selected_type == "report_generation",
        "report_text": "No business report artifact was found for this run." if selected_type == "report_generation" else "",
        "report_title": "Run report" if selected_type == "report_generation" else "",
        "request_text": "Selected demo is waiting to run.\nClick Start demo to generate this report." if selected_type == "report_generation" else "Click Start demo to run this scenario.",
        "business_report_html_path": "",
        "business_report_markdown_path": "",
        "business_report_evidence_bundle_path": "",
        "run_report_html_path": "",
        "run_report_markdown_path": "",
        "run_report_evidence_bundle_path": "",
    }


def _empty_story() -> dict:
    return {
        "story_type": "unknown",
        "mode": "idle",
        "headline": "Select a demo to begin",
        "subheadline": "Click Start demo to run this scenario.",
        "request_title": "Selected demo",
        "worker_title": "Selected demo",
        "outcome_title": "Selected demo",
        "outcome_text": "Click Start demo to run this scenario.",
        "failed_check": "",
        "safe_outcome": "",
        "show_prepared_reply": False,
        "show_approval_actions": False,
        "draft_reply": "",
        "customer": "",
        "order": "",
        "message": "",
        "worker_steps": [],
        "facts": [],
        "decision_title": "Selected demo",
        "decision_text": "Click Start demo to run this scenario.",
        "can_approve": False,
        "can_reject": False,
        "can_create_audit_pack": False,
        "can_open_audit_pack": False,
        "show_report_actions": False,
        "can_open_report": False,
        "can_open_business_report": False,
        "can_open_run_report": False,
        "can_create_open_run_report": False,
        "report_text": "",
        "report_title": "",
        "request_text": "Click Start demo to run this scenario.",
        "business_report_html_path": "",
        "business_report_markdown_path": "",
        "business_report_evidence_bundle_path": "",
        "run_report_html_path": "",
        "run_report_markdown_path": "",
        "run_report_evidence_bundle_path": "",
    }


def _finalize_story(story: dict, current_run: dict | None, selected_scenario: dict | None) -> dict:
    story = story if isinstance(story, dict) else {}
    current_run = current_run if isinstance(current_run, dict) else {}
    selected_scenario = selected_scenario if isinstance(selected_scenario, dict) else {}
    story_type = _clean_value(story.get("story_type")) or "unknown"
    story["scenario_type"] = story_type
    story["actions"] = _story_actions(
        show_approve=bool(story.get("can_approve")),
        show_reject=bool(story.get("can_reject")),
        show_open_business_report=bool(story.get("can_open_business_report")),
        show_create_open_run_report=bool(story.get("can_create_open_run_report", False)),
    )
    business_report_html_path = _clean_value(story.get("business_report_html_path"))
    business_report_markdown_path = _clean_value(story.get("business_report_markdown_path"))
    business_report_evidence_bundle_path = _clean_value(story.get("business_report_evidence_bundle_path"))
    run_report_html_path = _clean_value(story.get("run_report_html_path"))
    run_report_markdown_path = _clean_value(story.get("run_report_markdown_path"))
    run_report_evidence_bundle_path = _clean_value(story.get("run_report_evidence_bundle_path"))
    story["business_report"] = {
        "exists": bool(business_report_html_path),
        "html_path": business_report_html_path,
        "markdown_path": business_report_markdown_path,
        "evidence_path": business_report_evidence_bundle_path,
    }
    story["run_report"] = {
        "exists": bool(run_report_html_path),
        "html_path": run_report_html_path,
        "markdown_path": run_report_markdown_path,
        "evidence_bundle_path": run_report_evidence_bundle_path,
    }
    story["cards"] = _build_story_cards(story, current_run, selected_scenario)
    return story


def _build_story_cards(story: dict, current_run: dict, selected_scenario: dict) -> list[dict]:
    story_type = _clean_value(story.get("story_type"))
    cards: list[dict] = []
    if story_type == "report_generation":
        cards.append(_story_card(str(story.get("request_title", "Report request")), "request", str(story.get("request_text", ""))))
        cards.append(
            _story_card(
                str(story.get("worker_title", "What the worker checked")),
                "steps",
                "",
                [f"{step.get('label', '')}" for step in story.get("worker_steps", []) if isinstance(step, dict) and step.get("label")],
            )
        )
        outcome_items = [str(item) for item in story.get("facts", []) if str(item)]
        if story.get("show_prepared_reply") and story.get("draft_reply"):
            outcome_items = [f"Prepared reply: {story.get('draft_reply')}"] + outcome_items
        cards.append(_story_card(str(story.get("outcome_title", "Generated report")), "outcome", str(story.get("outcome_text", "")), outcome_items))
        decision_items = [str(story.get("subheadline", ""))] if story.get("subheadline") else []
        if story.get("business_report_html_path"):
            decision_items.append(f"Business report: {story.get('business_report_html_path')}")
        if story.get("business_report_markdown_path"):
            decision_items.append(f"Markdown: {story.get('business_report_markdown_path')}")
        if story.get("business_report_evidence_bundle_path"):
            decision_items.append(f"Evidence: {story.get('business_report_evidence_bundle_path')}")
        if story.get("run_report_html_path"):
            decision_items.append(f"Run report: {story.get('run_report_html_path')}")
        if story.get("run_report_markdown_path"):
            decision_items.append(f"Run markdown: {story.get('run_report_markdown_path')}")
        if story.get("run_report_evidence_bundle_path"):
            decision_items.append(f"Run evidence: {story.get('run_report_evidence_bundle_path')}")
        cards.append(_story_card(str(story.get("decision_title", "Report actions")), "decision", str(story.get("decision_text", "")), decision_items))
        report_items = []
        if story.get("business_report_html_path"):
            report_items.extend(
                [
                    "Business report generated",
                    f"HTML: {story.get('business_report_html_path')}",
                    f"Markdown: {story.get('business_report_markdown_path')}",
                    f"Evidence: {story.get('business_report_evidence_bundle_path')}",
                ]
            )
        else:
            report_items.append("No business report artifact was found for this run.")
        if story.get("run_report_html_path"):
            report_items.extend(
                [
                    "Run report",
                    f"HTML: {story.get('run_report_html_path')}",
                    "This report shows:",
                    "- manifest steps",
                    "- step outcomes",
                    "- validations",
                    "- evidence",
                    "- pending actions",
                ]
            )
        else:
            report_items.append("Run report has not been created yet.")
        cards.append(_story_card("Report details", "report", "", report_items))
        return cards

    if story_type in {"customer_status", "procurement", "accounting"}:
        request_kind = "request"
        worker_kind = "steps"
        outcome_kind = "outcome"
        decision_kind = "decision"
        cards.append(_story_card(str(story.get("request_title", "Selected demo")), request_kind, str(story.get("request_text", ""))))
        cards.append(
            _story_card(
                str(story.get("worker_title", "What the worker checked")),
                worker_kind,
                "",
                [f"{step.get('label', '')}" for step in story.get("worker_steps", []) if isinstance(step, dict) and step.get("label")],
            )
        )
        outcome_items = [str(item) for item in story.get("facts", []) if str(item)]
        if story.get("show_prepared_reply") and story.get("draft_reply"):
            outcome_items.insert(0, f"Prepared reply: {story.get('draft_reply')}")
        if story.get("failed_check"):
            outcome_items.append(f"Failed check: {story.get('failed_check')}")
        if story.get("safe_outcome"):
            outcome_items.append(f"Safe outcome: {story.get('safe_outcome')}")
        cards.append(_story_card(str(story.get("outcome_title", "Selected demo")), outcome_kind, str(story.get("outcome_text", "")), outcome_items))
        decision_items = [str(story.get("decision_text", ""))] if story.get("decision_text") else []
        if story.get("run_report_html_path"):
            decision_items.append(f"Run report: {story.get('run_report_html_path')}")
        if story.get("business_report_html_path"):
            decision_items.append(f"Business report: {story.get('business_report_html_path')}")
        cards.append(_story_card(str(story.get("decision_title", "Selected demo")), decision_kind, str(story.get("decision_text", "")), decision_items))
        report_items = []
        if story.get("business_report_html_path"):
            report_items.extend(
                [
                    "Business report generated",
                    f"HTML: {story.get('business_report_html_path')}",
                    f"Markdown: {story.get('business_report_markdown_path')}",
                    f"Evidence: {story.get('business_report_evidence_bundle_path')}",
                ]
            )
        if story.get("run_report_html_path"):
            report_items.extend(
                [
                    "Run report",
                    f"HTML: {story.get('run_report_html_path')}",
                    f"Markdown: {story.get('run_report_markdown_path')}",
                    f"Evidence: {story.get('run_report_evidence_bundle_path')}",
                ]
            )
        cards.append(_story_card("Report details", "report", "", report_items))
        return cards

    cards.append(_story_card(str(story.get("request_title", "Selected demo")), "request", str(story.get("request_text", ""))))
    cards.append(_story_card(str(story.get("worker_title", "Selected demo")), "steps", "", [step.get("label", "") for step in story.get("worker_steps", []) if isinstance(step, dict) and step.get("label")]))
    cards.append(_story_card(str(story.get("outcome_title", "Selected demo")), "outcome", str(story.get("outcome_text", "")), [str(item) for item in story.get("facts", []) if str(item)]))
    cards.append(_story_card(str(story.get("decision_title", "Selected demo")), "decision", str(story.get("decision_text", ""))))
    return cards


def _story_mode(state: str, has_frame: bool, failed_validation: bool) -> str:
    if not has_frame:
        return "idle"
    if failed_validation:
        return "failed_validation"
    if state == "COMPLETED":
        return "completed"
    return "success_pending_approval"


def _detect_story_type(
    *,
    scenario: dict | None = None,
    frame: dict | None = None,
    fallback_text: str = "",
) -> str:
    candidates: list[str] = []
    if isinstance(scenario, dict):
        candidates.extend(
            _clean_value(value)
            for value in (
                scenario.get("scenario_type"),
                scenario.get("id"),
                scenario.get("manifest_id"),
                scenario.get("category"),
                scenario.get("label"),
                scenario.get("name"),
                scenario.get("description"),
                scenario.get("event_type"),
            )
        )
    if isinstance(frame, dict):
        candidates.extend(
            _clean_value(value)
            for value in (
                frame.get("scenario_type"),
                frame.get("manifest_id"),
                frame.get("name"),
                frame.get("label"),
                frame.get("state"),
                frame.get("event_type"),
            )
        )
        candidates.extend(_frame_text_values(frame, {}, {}))
    if fallback_text:
        candidates.append(fallback_text)
    text = " ".join(candidate for candidate in candidates if candidate).lower()
    if any(token in text for token in ("report_generation", "report generation", "reporting", "generate report", "markdown_path", "html_path", "evidence_bundle", "report_result")):
        return "report_generation"
    if any(token in text for token in ("procurement", "supplier", "reorder", "stock", "purchase order", "po_", "low_stock", "supplier_message")):
        return "procurement"
    if any(token in text for token in ("accounting", "reconciliation", "ledger", "invoice", "payments_sheet", "recon_", "sheet")):
        return "accounting"
    if any(token in text for token in ("customer_status", "customer status", "order", "shipment", "customer", "draft_reply", "reply_validation")):
        return "customer_status"
    return "unknown"


def _frame_text_values(frame: dict, current_run: dict, event: dict) -> list[str]:
    values: list[str] = []
    for source in (frame, current_run, event):
        if not isinstance(source, dict):
            continue
        for key in ("scenario_id", "manifest_id", "state", "event_type", "label", "name", "category", "description", "summary"):
            values.append(_clean_value(source.get(key)))
        for key in ("inputs", "outputs", "validations", "pending_actions"):
            value = source.get(key)
            if isinstance(value, dict):
                values.extend(_clean_value(v) for v in value.values())
                values.extend(_clean_value(k) for k in value.keys())
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        values.extend(_clean_value(v) for v in item.values())
                        values.extend(_clean_value(k) for k in item.keys())
    return [value for value in values if value]


def _story_types_compatible(selected_type: str, frame_type: str) -> bool:
    if selected_type == "unknown" or frame_type == "unknown":
        return True
    return selected_type == frame_type


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _validation_matches(item: dict, keywords: set[str]) -> bool:
    text = " ".join(_clean_value(item.get(key)) for key in ("step_id", "validation_id", "label", "message"))
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _extract_order_ref(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"\b([A-Z]{2,}-?\d{3,})\b", text)
    if match:
        return match.group(1)
    return text.strip()

