from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.generated_manifest_smoke_runner import (
    PASSING_CLASSIFICATIONS,
    smoke_run_manifest_candidate,
    smoke_run_manifest_file,
    write_smoke_report,
)
from src.manifest_template_generator import build_manifest_from_template


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _runtime_dir(tmp_path: Path) -> Path:
    d = tmp_path / "runtime_data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_tool_manifest(manifest_id: str = "smoke.read_test") -> dict:
    return build_manifest_from_template("manual_read_tool", manifest_id, "Smoke Read Test")


def _llm_manifest(manifest_id: str = "smoke.llm_test") -> dict:
    return build_manifest_from_template(
        "manual_llm_helper", manifest_id, "Smoke LLM Test",
        inputs=["message"],
    )


def _approval_manifest(manifest_id: str = "smoke.approval_test") -> dict:
    return build_manifest_from_template("approval_side_effect", manifest_id, "Smoke Approval Test")


# ---------------------------------------------------------------------------
# test_smoke_run_manifest_candidate_loads_manifest
# ---------------------------------------------------------------------------

def test_smoke_run_manifest_candidate_loads_manifest(tmp_path: Path) -> None:
    manifest = _read_tool_manifest()
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))
    checks = {c["id"]: c for c in result.get("checks", [])}
    assert "manifest_loads" in checks, f"manifest_loads check missing. Checks: {list(checks)}"
    assert checks["manifest_loads"]["ok"], checks["manifest_loads"]["message"]


# ---------------------------------------------------------------------------
# test_smoke_run_manifest_candidate_creates_taskframe
# ---------------------------------------------------------------------------

def test_smoke_run_manifest_candidate_creates_taskframe(tmp_path: Path) -> None:
    manifest = _read_tool_manifest("smoke.taskframe_test")
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))
    checks = {c["id"]: c for c in result.get("checks", [])}
    assert "taskframe_created" in checks
    assert checks["taskframe_created"]["ok"], checks["taskframe_created"]["message"]


# ---------------------------------------------------------------------------
# test_smoke_run_manual_read_tool_passes
# ---------------------------------------------------------------------------

def test_smoke_run_manual_read_tool_passes(tmp_path: Path) -> None:
    manifest = _read_tool_manifest("smoke.read_pass")
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))
    assert result.get("classification") in PASSING_CLASSIFICATIONS, (
        f"Expected passing classification, got {result.get('classification')}. Errors: {result.get('errors')}"
    )


# ---------------------------------------------------------------------------
# test_smoke_run_approval_template_waits_for_execute
# ---------------------------------------------------------------------------

def test_smoke_run_approval_template_waits_for_execute(tmp_path: Path) -> None:
    manifest = _approval_manifest("smoke.approval_wait")
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))
    assert result.get("classification") == "WAITING_FOR_EXECUTE_EXPECTED", (
        f"Expected WAITING_FOR_EXECUTE_EXPECTED, got {result.get('classification')}. "
        f"State: {result.get('state')}. Errors: {result.get('errors')}"
    )
    assert result.get("pending_action_count", 0) >= 1 or result.get("state") == "WAITING_FOR_EXECUTE", (
        "Approval template should have staged a pending action"
    )


# ---------------------------------------------------------------------------
# test_smoke_run_rejects_live_execution_enabled_template
# ---------------------------------------------------------------------------

def test_smoke_run_rejects_live_execution_enabled_template(tmp_path: Path) -> None:
    manifest = _read_tool_manifest("smoke.live_exec_bad")
    manifest["live_execution"] = {"enabled": True, "allowed_tools": ["g/send"], "requires_approval": False}
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))
    assert not result.get("ok")
    assert result.get("classification") == "UNEXPECTED_LIVE_SIDE_EFFECT"


# ---------------------------------------------------------------------------
# test_smoke_run_invalid_command_returns_command_invalid
# ---------------------------------------------------------------------------

def test_smoke_run_invalid_command_returns_command_invalid(tmp_path: Path) -> None:
    manifest = _read_tool_manifest("smoke.bad_cmd")
    manifest["steps"] = [{"id": "bad_step", "command": "not_a_valid_command_at_all"}]
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))
    assert not result.get("ok")
    assert result.get("classification") == "COMMAND_INVALID"


# ---------------------------------------------------------------------------
# test_smoke_run_unknown_tool_returns_tool_not_registered
# ---------------------------------------------------------------------------

def test_smoke_run_unknown_tool_returns_tool_not_registered(tmp_path: Path) -> None:
    manifest = _read_tool_manifest("smoke.unknown_tool")
    manifest["steps"] = [
        {"id": "step_one", "command": "[t:nonexistent/action -> result] arg=1"},
    ]
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))
    assert not result.get("ok")
    assert result.get("classification") == "TOOL_NOT_REGISTERED"


# ---------------------------------------------------------------------------
# test_smoke_result_contains_checks
# ---------------------------------------------------------------------------

def test_smoke_result_contains_checks(tmp_path: Path) -> None:
    manifest = _read_tool_manifest("smoke.checks_test")
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))
    checks = result.get("checks", [])
    assert isinstance(checks, list) and len(checks) > 0
    check_ids = {c["id"] for c in checks}
    assert "manifest_loads" in check_ids
    assert "taskframe_created" in check_ids


# ---------------------------------------------------------------------------
# test_smoke_result_contains_failure_analysis
# ---------------------------------------------------------------------------

def test_smoke_result_contains_failure_analysis(tmp_path: Path) -> None:
    manifest = _read_tool_manifest("smoke.fail_analysis")
    manifest["steps"] = [{"id": "bad", "command": "not_a_command"}]
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))
    assert not result.get("ok")
    assert result.get("classification") in {"COMMAND_INVALID", "LOAD_FAILED", "PREFLIGHT_FAILED"}
    assert isinstance(result.get("errors"), list) and result["errors"]
    assert "suggested_fix" in result
    assert result["suggested_fix"]


# ---------------------------------------------------------------------------
# test_write_smoke_report_creates_json_and_markdown
# ---------------------------------------------------------------------------

def test_write_smoke_report_creates_json_and_markdown(tmp_path: Path) -> None:
    manifest = _read_tool_manifest("smoke.report_test")
    smoke_result = smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))
    report = write_smoke_report(smoke_result, runtime_data_dir=_runtime_dir(tmp_path))
    assert report.get("ok"), report.get("error")
    assert Path(report["json_path"]).is_file()
    assert Path(report["markdown_path"]).is_file()
    md_content = Path(report["markdown_path"]).read_text(encoding="utf-8")
    assert "Smoke" in md_content or "Generated Manifest" in md_content


# ---------------------------------------------------------------------------
# test_smoke_run_file_uses_existing_manifest_path
# ---------------------------------------------------------------------------

def test_smoke_run_file_uses_existing_manifest_path(tmp_path: Path) -> None:
    manifest = _read_tool_manifest("smoke.file_test")
    manifest_path = tmp_path / "smoke_file_test.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = smoke_run_manifest_file(manifest_path, runtime_data_dir=_runtime_dir(tmp_path))
    assert result.get("classification") in PASSING_CLASSIFICATIONS, (
        f"Unexpected classification: {result.get('classification')}. Errors: {result.get('errors')}"
    )


def test_smoke_run_file_missing_path_returns_load_failed(tmp_path: Path) -> None:
    result = smoke_run_manifest_file(tmp_path / "does_not_exist.json", runtime_data_dir=_runtime_dir(tmp_path))
    assert not result.get("ok")
    assert result.get("classification") == "LOAD_FAILED"
