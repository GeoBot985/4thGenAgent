from __future__ import annotations

import tkinter as tk

import pytest

from src.demo_story_presenter import build_demo_story
from src.operator_reports import create_or_open_run_report
from src.operator_ui import build_operator_ui


def _report_snapshot() -> dict:
    return {
        "active_event": {
            "payload": {
                "customer_name": "Alex",
                "message": "Where is my order ORD-10042?",
            }
        },
        "active_frame": {
            "state": "WAITING_FOR_EXECUTE",
            "scenario_id": "report_generation_happy_path",
            "manifest_id": "report_generation_happy_path",
            "inputs": {
                "customer_name": "Alex",
                "message": "Where is my order ORD-10042?",
            },
            "outputs": {
                "report_artifact": "reports/report_generation_happy_path.md",
                "summary": "Business report generated successfully.",
                "evidence_bundle_path": "evidence/report_generation_happy_path.zip",
            },
            "steps": [
                {"step_id": "read_business_data", "ok": True},
                {"step_id": "check_source_records", "ok": True},
                {"step_id": "build_report_summary", "ok": True},
                {"step_id": "generate_report", "ok": True},
                {"step_id": "prepare_evidence_pack", "ok": True},
            ],
            "pending_actions": [],
        },
    }


def _report_selected_scenario() -> dict:
    return {
        "id": "report_generation_happy_path",
        "label": "Report Generation - Happy Path Report",
        "category": "reporting",
        "description": "Runs happy path and generates markdown/html/evidence bundle.",
    }


def _report_run_result(frame_id: str = "frame_1") -> dict:
    return {
        "ok": True,
        "frame_id": frame_id,
        "markdown_path": f"runtime_data/outputs/reports/{frame_id}_run_report.md",
        "html_path": f"runtime_data/outputs/reports/{frame_id}_run_report.html",
        "evidence_bundle_path": f"runtime_data/outputs/evidence/{frame_id}_evidence_bundle.json",
        "business_report_markdown_path": f"runtime_data/outputs/reports/report_generation_happy_path_{frame_id}.md",
        "business_report_html_path": f"runtime_data/outputs/reports/report_generation_happy_path_{frame_id}.html",
        "business_report_evidence_bundle_path": f"runtime_data/outputs/evidence/{frame_id}_evidence_bundle.json",
        "run_report_markdown_path": f"runtime_data/outputs/reports/{frame_id}_run_report.md",
        "run_report_html_path": f"runtime_data/outputs/reports/{frame_id}_run_report.html",
        "run_report_evidence_bundle_path": f"runtime_data/outputs/evidence/{frame_id}_evidence_bundle.json",
    }


def _build_console(tmp_path):
    root = tk.Tk()
    root.withdraw()
    build_operator_ui(root, runtime_root=str(tmp_path))
    return root, root.operator_console


def test_report_generation_demo_exposes_business_report_path():
    story = build_demo_story(
        _report_snapshot(),
        {"state": "WAITING_FOR_EXECUTE", "snapshot": _report_snapshot(), "scenario_id": "report_generation_happy_path", "report_result": _report_run_result()},
        _report_selected_scenario(),
    )

    assert story["business_report_html_path"].endswith("report_generation_happy_path_frame_1.html")
    assert story["business_report_markdown_path"].endswith("report_generation_happy_path_frame_1.md")
    assert story["business_report_evidence_bundle_path"].endswith("frame_1_evidence_bundle.json")
    assert story["run_report_html_path"].endswith("frame_1_run_report.html")
    assert story["run_report_markdown_path"].endswith("frame_1_run_report.md")


def test_demo_view_does_not_claim_report_ready_without_path():
    story = build_demo_story(
        _report_snapshot(),
        {"state": "WAITING_FOR_EXECUTE", "snapshot": _report_snapshot(), "scenario_id": "report_generation_happy_path"},
        _report_selected_scenario(),
    )

    assert story["outcome_text"] == "No business report artifact was found for this run."
    assert "Business report generated" not in story["outcome_text"]


def test_open_run_report_auto_creates_missing_report(tmp_path, monkeypatch):
    calls: list[tuple[str, str]] = []
    opened: list[str] = []

    def fake_generate(runtime_root, frame_id, scenario=None):
        calls.append((str(runtime_root), frame_id))
        return _report_run_result(frame_id)

    monkeypatch.setattr("src.operator_reports.generate_demo_run_report", fake_generate)
    monkeypatch.setattr("src.operator_reports.open_report_html", lambda path: opened.append(path))

    result = create_or_open_run_report(str(tmp_path), "frame_42", scenario={"id": "report_generation_happy_path", "label": "Report Generation - Happy Path"})

    assert calls == [(str(tmp_path), "frame_42")]
    assert opened == [f"runtime_data/outputs/reports/frame_42_run_report.html"]
    assert result["frame_id"] == "frame_42"
    assert result["opened"] is True


def test_run_report_status_is_bound_to_active_frame(tmp_path, monkeypatch):
    try:
        root, console = _build_console(tmp_path)
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")

    monkeypatch.setattr(
        "src.operator_ui.create_or_open_run_report",
        lambda runtime_root, frame_id, scenario=None: {
            "ok": True,
            "frame_id": frame_id,
            "markdown_path": f"runtime_data/outputs/reports/{frame_id}_run_report.md",
            "html_path": f"runtime_data/outputs/reports/{frame_id}_run_report.html",
            "evidence_bundle_path": f"runtime_data/outputs/evidence/{frame_id}_evidence_bundle.json",
            "opened": True,
            "error": "",
            "report_result": _report_run_result(frame_id),
        },
    )
    monkeypatch.setattr("src.operator_ui.open_report_html", lambda path: None)

    try:
        console.view_mode_var.set("Demo")
        console.active_frame_id = "frame_a"
        console.current_run = {"frame_id": "frame_a", "scenario_id": "report_generation_happy_path"}
        console.on_create_open_run_report()
        assert console.report_status["frame_id"] == "frame_a"
        assert console.current_run["report_result"]["frame_id"] == "frame_a"

        console.active_frame_id = "frame_b"
        console.current_run = {"frame_id": "frame_b", "scenario_id": "report_generation_happy_path"}
        console.active_report_result = None
        console.on_create_open_run_report()
        assert console.report_status["frame_id"] == "frame_b"
        assert console.current_run["report_result"]["frame_id"] == "frame_b"
    finally:
        root.destroy()


def test_report_buttons_use_clear_business_vs_run_labels(tmp_path):
    try:
        root, console = _build_console(tmp_path)
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")

    try:
        console.view_mode_var.set("Demo")
        console.active_frame_id = "frame_1"
        console.current_run = {
            "frame_id": "frame_1",
            "scenario_id": "report_generation_happy_path",
            "label": "Report Generation - Happy Path",
            "report_result": _report_run_result("frame_1"),
        }
        console.last_snapshot = _report_snapshot()
        console._render_demo_story_view()

        assert console.primary_demo_action_button.cget("text") == "Approve & execute dry run"
        assert "pending action" in console.primary_demo_action_helper_label.cget("text").lower()
        assert console.demo_advanced_actions_frame.winfo_manager() == ""

        console.current_run = {
            "frame_id": "frame_1",
            "scenario_id": "customer_status_happy_path",
            "label": "Customer Status - Happy Path",
        }
        console.selected_demo_id.set("customer_status_happy_path")
        console.demo_var.set("Customer Status - Happy Path")
        console._render_demo_story_view()

        assert console.primary_demo_action_button.cget("text") in {"Start demo", "Create run report", "Approve & execute dry run", "Open run report"}
        assert console.primary_demo_action_helper_label.cget("text")
    finally:
        root.destroy()
