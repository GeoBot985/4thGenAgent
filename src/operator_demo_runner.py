from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from runtime.events import create_event
from runtime.failure_summary import build_failure_summary
import os

from runtime.llm_adapter import FakeLLMAdapter
from runtime.persistence import get_summary_path
from runtime.runtime_engine import RuntimeEngine
from runtime.taskframe import to_dict as taskframe_to_dict
from runtime.taskframe_reload import load_taskframe

from src.operator_approval_pack import build_approval_pack_view
from src.operator_data import build_operator_snapshot
from src.operator_playback import build_playback_timeline


DEMO_MANIFESTS = [
    {
        "selection_id": "customer_message_status_check",
        "label": "Customer Message Status Check",
        "event_type": "customer_message",
        "source": "callcenter",
        "payload": {
            "event_id": "evt-demo-customer-001",
            "customer_id": "CUST-1001",
            "message": "Where is my order ORD-10042?",
            "channel": "callcenter",
            "received_at": "2026-05-01T10:00:00Z",
        },
        "fake_llm_responses": {
            "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
            "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
            "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit. Estimated delivery is 2026-05-03.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
            "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}',
        },
    },
    {"selection_id": "mock_ping", "label": "Mock Ping", "event_type": "mock_ping", "source": "external", "payload": {}},
    {
        "selection_id": "customer_status_llm_e2e",
        "label": "Customer Status - LLM Assisted E2E",
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_ui",
        "payload": {"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?", "channel": "callcenter"},
        "uses_llm": True,
        "fake_llm_responses": {
            "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
            "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
            "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit. Estimated delivery is 2026-05-03.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
            "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}',
        },
    },
]

NEGATIVE_DEMOS = [
    {"selection_id": "customer_status_missing_customer", "label": "Customer Status - Missing Customer", "event_type": "manual.customer_status_llm_e2e", "source": "operator_ui", "payload": {"customer_id": "CUST-9999", "message": "Where is my order ORD-99999?", "channel": "callcentre"}, "uses_llm": True},
    {"selection_id": "customer_status_missing_order", "label": "Customer Status - Missing Order", "event_type": "manual.customer_status_llm_e2e", "source": "operator_ui", "payload": {"customer_id": "CUST-1001", "message": "Where is my order ORD-99999?", "channel": "callcentre"}, "uses_llm": True},
    {
        "selection_id": "customer_status_wrong_customer_order",
        "label": "Customer Status - Wrong Customer/Order Pairing",
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_ui",
        "payload": {"customer_id": "CUST-1001", "message": "Where is order ORD-10044?", "channel": "callcentre"},
        "uses_llm": True,
        "fake_llm_responses": {
            "extract_order_ref": '{"order_ref": "ORD-10044", "confidence": "high", "reason": "Detected explicit order reference."}',
            "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
            "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10044 has shipped and is currently in transit.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
            "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}',
        },
    },
    {
        "selection_id": "customer_status_unsupported_intent",
        "label": "Customer Status - Unsupported Intent",
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_ui",
        "payload": {"customer_id": "CUST-1002", "message": "I want a refund for order ORD-10043.", "channel": "callcentre"},
        "uses_llm": True,
        "fake_llm_responses": {
            "extract_order_ref": '{"order_ref": "ORD-10043", "confidence": "high", "reason": "Detected explicit order reference."}',
            "classify_customer_message": '{"label": "refund", "confidence": "high", "reason": "Refund request."}',
            "draft_customer_status_reply": '{"reply": "Your order ORD-10043 is being processed.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
            "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}',
        },
    },
    {
        "selection_id": "customer_status_bad_llm_reply",
        "label": "Customer Status - Bad LLM Reply",
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_ui",
        "payload": {"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?", "channel": "callcentre", "test_llm_mode": "bad_reply"},
        "uses_llm": True,
        "fake_llm_responses": {
            "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
            "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
            "draft_customer_status_reply": '{"reply": "Your order ORD-10042 is delayed, so we will refund you 50%.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": true}',
            "compare_reply_to_facts": '{"ok": false, "matches_facts": false, "unsupported_claims": ["Promised refund not present in facts."], "missing_required_facts": [], "reason": "Reply contains unsupported compensation."}',
        },
    },
]


def list_demo_manifests() -> list[dict]:
    return [deepcopy(item) for item in (DEMO_MANIFESTS + NEGATIVE_DEMOS)]


def run_demo_manifest(selection_id: str, runtime_data_dir: str = "runtime_data", use_local_llm: bool = True) -> dict:
    try:
        demo = next(item for item in (DEMO_MANIFESTS + NEGATIVE_DEMOS) if item["selection_id"] == selection_id)
    except StopIteration:
        return {"ok": False, "frame_id": "", "manifest_id": "", "state": "FAILED", "summary": {}, "snapshot": {}, "timeline": [], "error": f"Unknown demo manifest: {selection_id}"}
    return run_demo_definition(demo, runtime_data_dir=runtime_data_dir, use_local_llm=use_local_llm)


def run_demo_definition(
    demo: dict,
    runtime_data_dir: str = "runtime_data",
    use_local_llm: bool = True,
    llm_adapter=None,
    allow_test_fake_llm: bool = False,
) -> dict:
    try:
        if allow_test_fake_llm or _allow_test_fake_llm():
            use_local_llm = False
        if llm_adapter is not None:
            adapter = llm_adapter
        else:
            adapter = _build_demo_adapter(demo, use_local_llm, allow_test_fake_llm=allow_test_fake_llm)
        engine = RuntimeEngine(runtime_data_dir=runtime_data_dir, llm_adapter=adapter)
        event = create_event(demo["event_type"], demo["source"], payload=dict(demo["payload"]))
        frame = engine.handle_event(event, dry_run=True)
        frame_id = getattr(frame, "frame_id", "")
        manifest_id = getattr(frame, "manifest_id", "")
        state = getattr(frame, "state", "FAILED")
        summary = _load_summary(frame_id, runtime_data_dir)
        snapshot = build_operator_snapshot(runtime_data_dir)
        timeline = build_playback_timeline(snapshot)
        approval_pack = _build_approval_pack(frame_id, runtime_data_dir, snapshot)
        failure_summary = _build_failure_summary(frame, frame_id, state)
        _write_approval_pack_report(frame_id, approval_pack, runtime_data_dir)
        return {
            "ok": True,
            "frame_id": frame_id,
            "manifest_id": manifest_id,
            "state": state,
            "summary": summary,
            "snapshot": snapshot,
            "timeline": timeline,
            "approval_pack": approval_pack,
            "failure_summary": failure_summary,
            "llm": {"provider": getattr(engine.llm_adapter, "provider", ""), "model": getattr(engine.llm_adapter, "model", "")} if use_local_llm or bool(demo.get("uses_llm")) else {},
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "frame_id": "",
            "manifest_id": "",
            "state": "FAILED",
            "summary": {},
            "snapshot": {},
            "timeline": [],
            "approval_pack": {"ok": False, "frame_id": "", "manifest_id": "", "state": "", "pending_action_count": 0, "approval_packs": [], "error": str(exc)},
            "failure_summary": {"ok": False, "frame_id": "", "manifest_id": "", "state": "FAILED", "failed_step_id": "", "failure_type": "runtime_error", "failure_message": str(exc), "blocking_errors": [str(exc)], "failed_validations": [], "pending_action_count": 0, "executed_action_count": 0, "safe_to_retry": False, "operator_explanation": str(exc)},
            "error": str(exc),
        }


def _load_summary(frame_id: str, runtime_data_dir: str) -> dict[str, Any]:
    if not frame_id:
        return {}
    path = get_summary_path(frame_id, runtime_data_dir)
    if not path.is_file():
        return {}
    try:
        from runtime.persistence import read_json

        summary = read_json(path)
        return summary if isinstance(summary, dict) else {}
    except Exception:
        return {}


def _write_approval_pack_report(frame_id: str, approval_pack: dict, runtime_data_dir: str) -> None:
    if not frame_id or not isinstance(approval_pack, dict):
        return
    frame_dir = Path(runtime_data_dir) / "runs" / frame_id / "reports"
    frame_dir.mkdir(parents=True, exist_ok=True)
    markdown = _approval_pack_markdown(approval_pack)
    failure_summary = approval_pack.get("failure_summary", {}) if isinstance(approval_pack, dict) else {}
    if isinstance(failure_summary, dict) and str(failure_summary.get("state", "")).startswith("FAILED"):
        markdown = "\n".join([markdown, "", _failure_summary_markdown(failure_summary)])
    (frame_dir / "approval_pack_report.md").write_text(markdown, encoding="utf-8")
    (frame_dir / "approval_pack_report.html").write_text(f"<pre>{markdown}</pre>", encoding="utf-8")


def _approval_pack_markdown(approval_pack: dict) -> str:
    lines = ["# Approval Pack Report", "", f"Frame ID: {approval_pack.get('frame_id', '')}", f"Manifest ID: {approval_pack.get('manifest_id', '')}", f"State: {approval_pack.get('state', '')}", "", "## Pending Actions", ""]
    packs = approval_pack.get("approval_packs", [])
    if not packs:
        lines.append("No pending approval actions for this TaskFrame.")
    else:
        for pack in packs:
            if not isinstance(pack, dict):
                continue
            lines.extend([f"### Action {pack.get('action_id', '')}", f"Tool: {pack.get('tool', '')}", f"Status: {pack.get('status', '')}", f"Risk: {pack.get('risk_class', '')}", f"Human Summary: {pack.get('human_summary', '')}", f"Arguments: {pack.get('args', {})}", f"Guardrails: {pack.get('guardrails', [])}", ""])
    return "\n".join(lines)


def _failure_summary_markdown(failure_summary: dict) -> str:
    return "\n".join([
        "## Failure Summary",
        "",
        f"- State: {failure_summary.get('state', '')}",
        f"- Failed Step: {failure_summary.get('failed_step_id', '')}",
        f"- Failure Type: {failure_summary.get('failure_type', '')}",
        f"- Failure Message: {failure_summary.get('failure_message', '')}",
        f"- Pending Actions: {failure_summary.get('pending_action_count', 0)}",
        f"- Executed Actions: {failure_summary.get('executed_action_count', 0)}",
        "",
        "### Failed Validations",
        "",
        *([f"- {item.get('validation_id', '')}: {item.get('message', '')}" for item in failure_summary.get("failed_validations", []) if isinstance(item, dict)] or ["- None"]),
        "",
        "### Runtime Errors",
        "",
        *([f"- {error}" for error in failure_summary.get("blocking_errors", []) if error] or ["- None"]),
    ])


def _build_demo_adapter(demo: dict, use_local_llm: bool, *, allow_test_fake_llm: bool = False):
    if use_local_llm:
        from runtime.llm_config import build_llm_adapter

        return build_llm_adapter()
    responses = demo.get("fake_llm_responses")
    if isinstance(responses, dict) and responses and (allow_test_fake_llm or _allow_test_fake_llm()):
        return FakeLLMAdapter(responses)
    return None


def _allow_test_fake_llm() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _build_approval_pack(frame_id: str, runtime_data_dir: str, snapshot: dict) -> dict:
    try:
        loaded = load_taskframe(frame_id, runtime_data_dir)
        frame_dict = taskframe_to_dict(loaded)
    except Exception:
        frame_dict = snapshot.get("active_frame", {}) if isinstance(snapshot, dict) else {}
    return build_approval_pack_view(frame_dict if isinstance(frame_dict, dict) else {})


def _build_failure_summary(frame, frame_id: str, state: str) -> dict:
    try:
        frame_dict = taskframe_to_dict(frame)
    except Exception:
        frame_dict = {}
    summary = build_failure_summary(frame_dict if isinstance(frame_dict, dict) else {})
    if frame_id and not summary.get("frame_id"):
        summary["frame_id"] = frame_id
    if not str(state).startswith("FAILED"):
        summary["failure_type"] = ""
        summary["failure_message"] = ""
        summary["blocking_errors"] = []
        summary["failed_validations"] = []
        summary["failed_step_id"] = ""
    return summary
