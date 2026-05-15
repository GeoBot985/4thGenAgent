from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.manifest_authoring_feedback import (
    analyze_manifest_static,
    classify_smoke_failure,
    explain_manifest_failure,
    write_repair_guidance_report,
)
from src.manifest_template_generator import build_manifest_from_template


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_manifest(manifest_id: str = "test.valid") -> dict:
    return build_manifest_from_template("manual_read_tool", manifest_id, "Test Valid Manifest")


def _smoke_fail(classification: str, errors: list[str] | None = None) -> dict:
    return {
        "ok": False,
        "status": "FAIL",
        "classification": classification,
        "manifest_id": "test.fail",
        "errors": errors or [f"Simulated {classification} error"],
        "checks": [{"id": "test_check", "ok": False, "message": "failed"}],
    }


# ---------------------------------------------------------------------------
# test_no_findings_for_valid_generated_manifest
# ---------------------------------------------------------------------------

def test_no_findings_for_valid_generated_manifest() -> None:
    manifest = _valid_manifest("test.no_findings")
    guidance = explain_manifest_failure(manifest=manifest)
    assert guidance["status"] == "NO_FINDINGS"
    assert guidance["findings"] == []
    assert guidance["severity"] == "info"


# ---------------------------------------------------------------------------
# test_missing_required_field_gets_repair_guidance
# ---------------------------------------------------------------------------

def test_missing_required_field_gets_repair_guidance() -> None:
    manifest = _valid_manifest("test.missing_field")
    del manifest["validations"]
    guidance = explain_manifest_failure(manifest=manifest)
    assert guidance["status"] == "HAS_FINDINGS"
    ids = [f["id"] for f in guidance["findings"]]
    assert "missing_required_top_level_field" in ids


# ---------------------------------------------------------------------------
# test_invalid_json_exception_gets_repair_guidance
# ---------------------------------------------------------------------------

def test_invalid_json_exception_gets_repair_guidance() -> None:
    try:
        json.loads("{invalid json{{")
    except Exception as exc:
        exception = exc
    guidance = explain_manifest_failure(exception=exception)
    assert guidance["status"] == "HAS_FINDINGS"
    ids = [f["id"] for f in guidance["findings"]]
    assert "json_parse_error" in ids
    assert any("JSON" in f["suggested_fix"] or "json" in f["suggested_fix"].lower() for f in guidance["findings"])


# ---------------------------------------------------------------------------
# test_command_parse_error_gets_command_guidance
# ---------------------------------------------------------------------------

def test_command_parse_error_gets_command_guidance() -> None:
    manifest = _valid_manifest("test.bad_command")
    manifest["steps"] = [{"id": "bad", "command": "not_a_valid_command_at_all"}]
    findings = analyze_manifest_static(manifest)
    ids = [f["id"] for f in findings]
    assert "command_parse_error" in ids
    cmd_finding = next(f for f in findings if f["id"] == "command_parse_error")
    assert "command" in cmd_finding["location"].lower()
    assert "[t:" in cmd_finding["suggested_fix"] or "[q:" in cmd_finding["suggested_fix"]


# ---------------------------------------------------------------------------
# test_unknown_tool_smoke_result_gets_tool_guidance
# ---------------------------------------------------------------------------

def test_unknown_tool_smoke_result_gets_tool_guidance() -> None:
    smoke = _smoke_fail("TOOL_NOT_REGISTERED", ["Tool not registered: xyz/bad"])
    findings = classify_smoke_failure(smoke)
    assert any(f["id"] == "unknown_tool" for f in findings)
    tool_finding = next(f for f in findings if f["id"] == "unknown_tool")
    assert tool_finding["severity"] == "error"
    assert "registered" in tool_finding["suggested_fix"].lower()


# ---------------------------------------------------------------------------
# test_completion_output_missing_detected
# ---------------------------------------------------------------------------

def test_completion_output_missing_detected() -> None:
    manifest = _valid_manifest("test.completion_missing")
    # Completion expects 'reply' but step writes 'result'
    manifest["completion"]["success_outputs"] = ["reply"]
    findings = analyze_manifest_static(manifest)
    ids = [f["id"] for f in findings]
    assert "completion_output_missing" in ids
    f = next(f for f in findings if f["id"] == "completion_output_missing")
    assert "reply" in f["message"]
    assert "result" in f["suggested_fix"] or "alias" in f["suggested_fix"]


# ---------------------------------------------------------------------------
# test_validation_output_missing_detected
# ---------------------------------------------------------------------------

def test_validation_output_missing_detected() -> None:
    manifest = _valid_manifest("test.val_missing")
    manifest["validations"].append({
        "id": "missing_output_check",
        "type": "output_exists",
        "output": "nonexistent_alias",
    })
    findings = analyze_manifest_static(manifest)
    ids = [f["id"] for f in findings]
    assert "validation_references_missing_output" in ids
    f = next(f for f in findings if f["id"] == "validation_references_missing_output")
    assert "nonexistent_alias" in f["message"]


# ---------------------------------------------------------------------------
# test_input_declared_but_not_used_warning
# ---------------------------------------------------------------------------

def test_input_declared_but_not_used_warning() -> None:
    manifest = _valid_manifest("test.unused_input")
    manifest["inputs"] = ["unused_param"]
    findings = analyze_manifest_static(manifest)
    ids = [f["id"] for f in findings]
    assert "input_declared_but_not_used" in ids
    f = next(f for f in findings if f["id"] == "input_declared_but_not_used")
    assert f["severity"] == "warning"
    assert "unused_param" in f["message"]


# ---------------------------------------------------------------------------
# test_input_used_but_not_declared_error
# ---------------------------------------------------------------------------

def test_input_used_but_not_declared_error() -> None:
    manifest = _valid_manifest("test.undeclared_input")
    manifest["inputs"] = []
    manifest["steps"] = [{"id": "step1", "command": "[t:g/check -> result] query=$inputs.mystery_field"}]
    findings = analyze_manifest_static(manifest)
    ids = [f["id"] for f in findings]
    assert "input_used_but_not_declared" in ids
    f = next(f for f in findings if f["id"] == "input_used_but_not_declared")
    assert f["severity"] == "error"
    assert "mystery_field" in f["message"]


# ---------------------------------------------------------------------------
# test_live_execution_enabled_is_critical
# ---------------------------------------------------------------------------

def test_live_execution_enabled_is_critical() -> None:
    manifest = _valid_manifest("test.live_exec")
    manifest["live_execution"] = {"enabled": True, "allowed_tools": [], "requires_approval": False}
    findings = analyze_manifest_static(manifest)
    ids = [f["id"] for f in findings]
    assert "live_execution_enabled" in ids
    f = next(f for f in findings if f["id"] == "live_execution_enabled")
    assert f["severity"] == "critical"
    assert "pending" in f["suggested_fix"].lower() or "approval" in f["suggested_fix"].lower()


# ---------------------------------------------------------------------------
# test_side_effect_failure_recommends_pending_approval
# ---------------------------------------------------------------------------

def test_side_effect_failure_recommends_pending_approval() -> None:
    smoke = _smoke_fail("UNEXPECTED_LIVE_SIDE_EFFECT")
    findings = classify_smoke_failure(smoke)
    assert any(f["id"] == "live_side_effect_blocked" for f in findings)
    f = next(f for f in findings if f["id"] == "live_side_effect_blocked")
    assert f["severity"] == "critical"
    assert "approval" in f["suggested_fix"].lower() or "pending" in f["suggested_fix"].lower()


# ---------------------------------------------------------------------------
# test_repair_guidance_report_writes_json_and_markdown
# ---------------------------------------------------------------------------

def test_repair_guidance_report_writes_json_and_markdown(tmp_path: Path) -> None:
    manifest = _valid_manifest("test.report_write")
    manifest["completion"]["success_outputs"] = ["nonexistent"]
    guidance = explain_manifest_failure(manifest=manifest)
    report = write_repair_guidance_report(guidance, runtime_data_dir=tmp_path / "runtime")
    assert report["ok"], report.get("error")
    assert Path(report["json_path"]).is_file()
    assert Path(report["markdown_path"]).is_file()
    md = Path(report["markdown_path"]).read_text(encoding="utf-8")
    assert "Manifest Repair Guidance" in md
    assert "HAS_FINDINGS" in md or "PASS" in md or "error" in md.lower()


# ---------------------------------------------------------------------------
# test_guidance_result_has_standard_finding_shape
# ---------------------------------------------------------------------------

def test_guidance_result_has_standard_finding_shape() -> None:
    manifest = _valid_manifest("test.finding_shape")
    manifest["completion"]["success_outputs"] = ["missing_alias"]
    guidance = explain_manifest_failure(manifest=manifest)
    assert guidance["status"] == "HAS_FINDINGS"
    for f in guidance["findings"]:
        assert "id" in f
        assert "severity" in f
        assert "location" in f
        assert "message" in f
        assert "suggested_fix" in f
        assert "source" in f
        assert f["severity"] in {"critical", "error", "warning", "info"}


# ---------------------------------------------------------------------------
# test_multiple_findings_are_sorted_by_severity
# ---------------------------------------------------------------------------

def test_multiple_findings_are_sorted_by_severity() -> None:
    _SEV_ORDER = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    manifest = _valid_manifest("test.sorting")
    # Add live_execution (critical) + unused input (warning) + completion mismatch (error)
    manifest["live_execution"] = {"enabled": True, "allowed_tools": []}
    manifest["inputs"] = ["unused_x"]
    manifest["completion"]["success_outputs"] = ["nonexistent_y"]
    guidance = explain_manifest_failure(manifest=manifest)
    assert guidance["status"] == "HAS_FINDINGS"
    severities = [f["severity"] for f in guidance["findings"]]
    orders = [_SEV_ORDER[s] for s in severities]
    assert orders == sorted(orders), f"Findings not sorted by severity: {severities}"


# ---------------------------------------------------------------------------
# UI-facing tests (source inspection — no Tkinter)
# ---------------------------------------------------------------------------

def test_repair_guidance_button_exists() -> None:
    import inspect
    from src import operator_ui
    source = inspect.getsource(operator_ui)
    assert "Repair Guidance" in source
    assert "on_workbench_repair_guidance" in source
    assert "_show_repair_guidance_dialog" in source


def test_repair_guidance_handles_invalid_json() -> None:
    import inspect
    from src import operator_ui
    source = inspect.getsource(operator_ui)
    assert "parse_exception" in source
    assert "explain_manifest_failure" in source


def test_repair_guidance_uses_last_smoke_result() -> None:
    import inspect
    from src import operator_ui
    source = inspect.getsource(operator_ui)
    assert "workbench_last_smoke_result" in source


def test_repair_guidance_report_paths_are_displayed() -> None:
    import inspect
    from src import operator_ui
    source = inspect.getsource(operator_ui)
    assert "write_repair_guidance_report" in source
    assert "markdown_path" in source


# ---------------------------------------------------------------------------
# Smoke runner integration
# ---------------------------------------------------------------------------

def test_failing_smoke_result_can_include_repair_guidance_summary(tmp_path: Path) -> None:
    from src.generated_manifest_smoke_runner import smoke_run_manifest_candidate
    manifest = _valid_manifest("test.repair_summary")
    manifest["steps"] = [{"id": "bad", "command": "not_valid_command"}]
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=tmp_path / "runtime")
    assert not result.get("ok")
    assert "repair_guidance" in result
    rg = result["repair_guidance"]
    assert "status" in rg
    assert "finding_count" in rg
    assert "top_finding_ids" in rg
