from __future__ import annotations

import json
from pathlib import Path

from runtime.run_report import generate_demo_run_report


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_run(tmp_path: Path, frame_id: str, frame: dict, outputs: dict | None = None, audit: list[dict] | None = None) -> Path:
    run_dir = tmp_path / "runs" / frame_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_dir / "taskframe.json", frame)
    _write_json(run_dir / "outputs.json", outputs or {})
    _write_json(run_dir / "audit.json", audit or [])
    return run_dir


def _customer_happy_frame(frame_id: str) -> tuple[dict, dict, list[dict]]:
    frame = {
        "frame_id": frame_id,
        "manifest_id": "customer.message_status_check",
        "state": "WAITING_FOR_EXECUTE",
        "current_step_id": "prepare_pending_send",
        "trigger": {"event_id": "evt-1", "event_type": "manual.customer_status_llm_e2e", "source": "operator_ui"},
        "inputs": {"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?"},
        "steps": [
            {"step_id": "extract_order_ref", "command": "extract", "status": "COMPLETED", "output_alias": "order_ref"},
            {"step_id": "lookup_customer", "command": "lookup customer", "status": "COMPLETED", "output_alias": "customer"},
            {"step_id": "lookup_order", "command": "lookup order", "status": "COMPLETED", "output_alias": "order"},
            {"step_id": "lookup_shipment", "command": "lookup shipment", "status": "COMPLETED", "output_alias": "shipment"},
            {"step_id": "draft_reply", "command": "draft reply", "status": "COMPLETED", "output_alias": "draft_reply"},
            {"step_id": "prepare_pending_send", "command": "prepare approval", "status": "COMPLETED", "output_alias": "customer_reply_send"},
        ],
        "outputs": {
            "order_ref": "ORD-10042",
            "customer": {"customer_id": "CUST-1001", "name": "Alex"},
            "order": {"order_id": "ORD-10042", "status": "shipped"},
            "shipment": {"tracking_reference": "TRK-778899", "status": "shipped"},
            "draft_reply": {"body": "Hi Alex, your order ORD-10042 has shipped and is currently in transit."},
            "customer_reply_send": {"body": "Hi Alex, your order ORD-10042 has shipped and is currently in transit."},
        },
        "validations": [
            {"step_id": "validate_customer", "ok": True, "message": "Customer ownership verified."},
            {"step_id": "validate_reply", "ok": True, "message": "Reply matches the facts."},
        ],
        "pending_actions": [
            {
                "action_type": "send_customer_message",
                "status": "PENDING_APPROVAL",
                "risk_class": "Side effect, approval required",
                "dry_run": True,
                "body": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.",
            }
        ],
        "executed_actions": [],
        "tool_calls": [{"step_id": "lookup_order", "tool": "customer/order lookup", "ok": True}],
        "llm_calls": [{"step_id": "draft_reply", "action": "draft_customer_status_reply", "ok": True}],
        "evidence": [
            {"step_id": "lookup_customer", "dataset": "customer", "found": True},
            {"step_id": "lookup_order", "dataset": "order", "found": True},
            {"step_id": "lookup_shipment", "dataset": "shipment", "found": True},
        ],
        "errors": [],
        "audit": [],
        "completion_gate_result": {"status": "WAITING_FOR_EXECUTE"},
        "final_response": "",
    }
    outputs = frame["outputs"]
    audit = [
        {"timestamp": "2026-05-12T10:00:00Z", "event_type": "STEP_COMPLETED", "message": "Lookup completed."},
        {"timestamp": "2026-05-12T10:00:01Z", "event_type": "PENDING_ACTION_STAGED", "message": "Send customer message staged."},
    ]
    return frame, outputs, audit


def _customer_failed_frame(frame_id: str) -> tuple[dict, dict, list[dict]]:
    frame = {
        "frame_id": frame_id,
        "manifest_id": "customer.message_status_check",
        "state": "FAILED_VALIDATION",
        "current_step_id": "lookup_customer",
        "trigger": {"event_id": "evt-2", "event_type": "manual.customer_status_llm_e2e", "source": "operator_ui"},
        "inputs": {"customer_id": "CUST-9999", "message": "Where is my order ORD-99999?"},
        "steps": [
            {"step_id": "extract_order_ref", "command": "extract", "status": "COMPLETED", "output_alias": "order_ref"},
            {"step_id": "lookup_customer", "command": "lookup customer", "status": "FAILED", "output_alias": "customer", "error": "Customer record could not be confirmed."},
            {"step_id": "lookup_order", "command": "lookup order", "status": "SKIPPED", "output_alias": "order"},
            {"step_id": "draft_reply", "command": "draft reply", "status": "SKIPPED", "output_alias": "draft_reply"},
        ],
        "outputs": {"order_ref": "ORD-99999"},
        "validations": [
            {"step_id": "validate_customer", "ok": False, "message": "Customer record could not be confirmed."}
        ],
        "pending_actions": [],
        "executed_actions": [],
        "tool_calls": [],
        "llm_calls": [],
        "evidence": [
            {"step_id": "lookup_customer", "dataset": "customer", "found": False},
            {"step_id": "lookup_order", "dataset": "order", "found": False},
        ],
        "errors": [{"type": "validation", "message": "Customer record could not be confirmed."}],
        "audit": [],
        "completion_gate_result": {"status": "FAILED_VALIDATION"},
        "final_response": "",
    }
    return frame, frame["outputs"], [{"timestamp": "2026-05-12T10:00:02Z", "event_type": "VALIDATION_FAILED", "message": "Validation stopped the workflow."}]


def _report_generation_frame(frame_id: str) -> tuple[dict, dict, list[dict]]:
    frame = {
        "frame_id": frame_id,
        "manifest_id": "report.generation_demo",
        "state": "COMPLETED",
        "current_step_id": "prepare_evidence_pack",
        "trigger": {"event_id": "evt-3", "event_type": "manual.report_generation", "source": "operator_ui"},
        "inputs": {"report_type": "business_overview"},
        "steps": [
            {"step_id": "read_business_data", "command": "read data", "status": "COMPLETED", "output_alias": "source_data"},
            {"step_id": "check_source_records", "command": "check records", "status": "COMPLETED", "output_alias": "record_check"},
            {"step_id": "build_report_summary", "command": "build summary", "status": "COMPLETED", "output_alias": "report_summary"},
            {"step_id": "generate_report_artifact", "command": "generate artifact", "status": "COMPLETED", "output_alias": "report_artifact"},
            {"step_id": "prepare_evidence_pack", "command": "prepare evidence", "status": "COMPLETED", "output_alias": "evidence_pack"},
        ],
        "outputs": {
            "source_data": {"rows": 12},
            "record_check": {"ok": True},
            "report_summary": {"summary": "Customer workflow verified."},
            "report_artifact": {"html_path": "golden_demo_report.html"},
            "evidence_pack": {"bundle": "golden_demo_evidence_bundle.json"},
        },
        "validations": [{"step_id": "validate_report", "ok": True, "message": "Report artifact generated."}],
        "pending_actions": [],
        "executed_actions": [],
        "tool_calls": [{"step_id": "read_business_data", "tool": "report/read", "ok": True}],
        "llm_calls": [{"step_id": "build_report_summary", "action": "draft_report_summary", "ok": True}],
        "evidence": [
            {"step_id": "read_business_data", "dataset": "source_data", "found": True},
            {"step_id": "prepare_evidence_pack", "dataset": "evidence_pack", "found": True},
        ],
        "errors": [],
        "audit": [],
        "completion_gate_result": {"status": "COMPLETED"},
        "final_response": "",
    }
    return frame, frame["outputs"], [{"timestamp": "2026-05-12T10:00:03Z", "event_type": "REPORT_GENERATED", "message": "Report artifact created."}]


def test_demo_run_report_creates_html_markdown_and_evidence_bundle(tmp_path):
    frame_id = "frame_demo_customer_happy"
    frame, outputs, audit = _customer_happy_frame(frame_id)
    _write_run(tmp_path, frame_id, frame, outputs, audit)

    report = generate_demo_run_report(tmp_path, frame_id, scenario={"id": "customer_status_happy_path", "label": "Customer Status - Happy Path"})

    assert report["ok"] is True
    assert Path(report["html_path"]).is_file()
    assert Path(report["markdown_path"]).is_file()
    assert Path(report["evidence_bundle_path"]).is_file()
    assert Path(report["html_path"]).name == f"{frame_id}_run_report.html"
    assert Path(report["markdown_path"]).name == f"{frame_id}_run_report.md"
    assert Path(report["evidence_bundle_path"]).name == f"{frame_id}_evidence_bundle.json"


def test_demo_run_report_contains_manifest_steps_in_order(tmp_path):
    frame_id = "frame_demo_customer_order"
    frame, outputs, audit = _customer_happy_frame(frame_id)
    _write_run(tmp_path, frame_id, frame, outputs, audit)

    report = generate_demo_run_report(tmp_path, frame_id, scenario={"id": "customer_status_happy_path", "label": "Customer Status - Happy Path"})
    text = Path(report["html_path"]).read_text(encoding="utf-8")

    assert text.index("Extract order reference") < text.index("Check customer record") < text.index("Check order record")
    assert text.index("Check order record") < text.index("Prepare customer reply")


def test_demo_run_report_contains_step_outputs(tmp_path):
    frame_id = "frame_demo_customer_outputs"
    frame, outputs, audit = _customer_happy_frame(frame_id)
    _write_run(tmp_path, frame_id, frame, outputs, audit)

    report = generate_demo_run_report(tmp_path, frame_id, scenario={"id": "customer_status_happy_path", "label": "Customer Status - Happy Path"})
    markdown = Path(report["markdown_path"]).read_text(encoding="utf-8")

    assert "ORD-10042" in markdown
    assert "TRK-778899" in markdown
    assert "Hi Alex, your order ORD-10042 has shipped" in markdown


def test_failed_run_report_shows_safe_stop_not_prepared_reply(tmp_path):
    frame_id = "frame_demo_customer_failed"
    frame, outputs, audit = _customer_failed_frame(frame_id)
    _write_run(tmp_path, frame_id, frame, outputs, audit)

    report = generate_demo_run_report(tmp_path, frame_id, scenario={"id": "customer_status_missing_customer", "label": "Customer Status - Missing Customer"})
    text = Path(report["html_path"]).read_text(encoding="utf-8")

    assert "Stopped safely" in text
    assert "No message was sent" in text
    assert "No approval action was created because the workflow stopped safely." in text
    assert "Prepared reply" not in text


def test_pending_approval_report_shows_pending_action(tmp_path):
    frame_id = "frame_demo_customer_pending"
    frame, outputs, audit = _customer_happy_frame(frame_id)
    _write_run(tmp_path, frame_id, frame, outputs, audit)

    report = generate_demo_run_report(tmp_path, frame_id, scenario={"id": "customer_status_happy_path", "label": "Customer Status - Happy Path"})
    text = Path(report["html_path"]).read_text(encoding="utf-8")

    assert "Pending Action" in text
    assert "Send customer message" in text
    assert "PENDING_APPROVAL" in text


def test_report_generation_run_uses_report_wording(tmp_path):
    frame_id = "frame_demo_report_generation"
    frame, outputs, audit = _report_generation_frame(frame_id)
    _write_run(tmp_path, frame_id, frame, outputs, audit)

    report = generate_demo_run_report(
        tmp_path,
        frame_id,
        scenario={"id": "report_generation_happy_path", "label": "Report Generation - Happy Path"},
    )
    text = Path(report["html_path"]).read_text(encoding="utf-8")

    assert "Business report generated" in text
    assert "Run report generated" in text
    assert "Evidence bundle" in text
    assert "Prepared customer reply" not in text


def test_report_generation_does_not_use_customer_reply_wording(tmp_path):
    frame_id = "frame_demo_report_generation_no_reply"
    frame, outputs, audit = _report_generation_frame(frame_id)
    _write_run(tmp_path, frame_id, frame, outputs, audit)

    report = generate_demo_run_report(
        tmp_path,
        frame_id,
        scenario={"id": "report_generation_happy_path", "label": "Report Generation - Happy Path"},
    )
    text = Path(report["markdown_path"]).read_text(encoding="utf-8")

    assert "Prepared customer reply" not in text
    assert "Approve this prepared reply?" not in text
    assert "No live customer message will be sent" not in text


def test_report_is_bound_to_requested_frame_id(tmp_path):
    frame_a = "frame_customer_bound"
    customer_frame, customer_outputs, customer_audit = _customer_happy_frame(frame_a)
    _write_run(tmp_path, frame_a, customer_frame, customer_outputs, customer_audit)

    frame_b = "frame_report_bound"
    report_frame, report_outputs, report_audit = _report_generation_frame(frame_b)
    _write_run(tmp_path, frame_b, report_frame, report_outputs, report_audit)

    report = generate_demo_run_report(
        tmp_path,
        frame_b,
        scenario={"id": "report_generation_happy_path", "label": "Report Generation - Happy Path"},
    )
    text = Path(report["html_path"]).read_text(encoding="utf-8")

    assert report["frame_id"] == frame_b
    assert Path(report["html_path"]).name.startswith(frame_b)
    assert Path(report["evidence_bundle_path"]).name.startswith(frame_b)
    assert "Customer Status - Happy Path" not in text
    assert "Customer Status" not in text or "Report Generation - Happy Path" in text
