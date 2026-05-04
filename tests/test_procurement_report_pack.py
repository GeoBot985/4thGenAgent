import json
from pathlib import Path

from runtime.run_report import generate_operator_run_report
from src.operator_approval_actions import approve_pending_action, execute_approved_pending_actions_dry_run
from src.operator_scenario_runner import run_scenario
from runtime.taskframe_reload import load_taskframe


def _run_completed_procurement_frame():
    result = run_scenario("procurement_low_stock_happy_path", runtime_data_dir="runtime_data", reset_dataset=True)
    frame_id = result["frame_id"]
    frame = load_taskframe(frame_id, "runtime_data")
    action_id = frame.pending_actions[0]["action_id"]
    approve_pending_action(frame_id, action_id, approved_by="pytest", reason="approve")
    execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir="runtime_data")
    return frame_id


def test_procurement_report_generation_creates_markdown_html_and_evidence_bundle():
    frame_id = _run_completed_procurement_frame()
    report = generate_operator_run_report("runtime_data", frame_id)
    assert report["ok"] is True
    assert Path(report["markdown_path"]).is_file()
    assert Path(report["html_path"]).is_file()
    assert Path(report["evidence_bundle_path"]).is_file()


def test_procurement_report_contains_draft_po_id():
    frame_id = _run_completed_procurement_frame()
    report = generate_operator_run_report("runtime_data", frame_id)
    markdown = Path(report["markdown_path"]).read_text(encoding="utf-8")
    frame = load_taskframe(frame_id, "runtime_data")
    assert frame.outputs["draft_po"]["po_id"] in markdown


def test_procurement_report_contains_supplier_name():
    frame_id = _run_completed_procurement_frame()
    report = generate_operator_run_report("runtime_data", frame_id)
    markdown = Path(report["markdown_path"]).read_text(encoding="utf-8")
    frame = load_taskframe(frame_id, "runtime_data")
    assert frame.outputs["selected_supplier"]["supplier"]["name"] in markdown


def test_procurement_report_contains_dry_run_execution_when_completed():
    frame_id = _run_completed_procurement_frame()
    report = generate_operator_run_report("runtime_data", frame_id)
    markdown = Path(report["markdown_path"]).read_text(encoding="utf-8")
    assert "supplier/send_message" in markdown
    assert "dry_run" in markdown.lower()


def test_procurement_evidence_bundle_contains_outputs_tool_calls_llm_calls_actions():
    frame_id = _run_completed_procurement_frame()
    report = generate_operator_run_report("runtime_data", frame_id)
    bundle = json.loads(Path(report["evidence_bundle_path"]).read_text(encoding="utf-8"))
    serialized = json.dumps(bundle)
    assert "outputs" in bundle
    assert "tool_calls" in bundle
    assert "llm_calls" in bundle
    assert "pending_actions" in bundle
    assert "executed_actions" in bundle
    assert "supplier_message_send" in serialized
