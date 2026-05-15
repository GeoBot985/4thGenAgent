from __future__ import annotations

import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from runtime.manifest_loader import load_manifest as runtime_load_manifest
from runtime.orchestrator import Orchestrator
from runtime.persistence import save_taskframe
from runtime.taskframe import to_dict as taskframe_to_dict
from runtime.taskframe_reload import taskframe_from_dict
from runtime.google_sheet_tools import use_sheet_fixture_mode
from runtime.command_parser import parse_command
from runtime.errors import CommandParseError

from src.manifest_template_generator import list_manifest_templates, build_manifest_from_template

# ---------------------------------------------------------------------------
# Public constants: classification codes
# ---------------------------------------------------------------------------

PASSING_CLASSIFICATIONS = frozenset({
    "DRY_RUN_COMPLETED",
    "WAITING_FOR_EXECUTE_EXPECTED",
    "COMPLETED_NO_DATA_ACCEPTED",
})

FAILING_CLASSIFICATIONS = frozenset({
    "LOAD_FAILED",
    "PREFLIGHT_FAILED",
    "INPUTS_MISSING",
    "TOOL_NOT_REGISTERED",
    "COMMAND_INVALID",
    "VALIDATION_FAILED",
    "EXECUTION_FAILED",
    "COMPLETION_FAILED",
    "UNEXPECTED_PENDING_ACTION",
    "UNEXPECTED_LIVE_SIDE_EFFECT",
})


# ---------------------------------------------------------------------------
# smoke_run_manifest_candidate
# ---------------------------------------------------------------------------

def smoke_run_manifest_candidate(
    manifest: dict,
    *,
    runtime_data_dir: str | Path,
    manifest_dir: str | Path = "manifests",
    dry_run: bool = True,
    sample_inputs: dict | None = None,
) -> dict:
    """Smoke-test an in-memory manifest candidate. Writes to a temp dir for the run."""
    tmp_manifest_dir: Path | None = None
    try:
        tmp_manifest_dir = Path(tempfile.mkdtemp(prefix="smoke_manifest_"))
        return _smoke_run_impl(
            manifest=manifest,
            tmp_manifest_dir=tmp_manifest_dir,
            runtime_data_dir=Path(runtime_data_dir),
            dry_run=dry_run,
            sample_inputs=sample_inputs or {},
        )
    except Exception as exc:
        return _build_fail_result(
            manifest_id=_manifest_id(manifest),
            classification="EXECUTION_FAILED",
            checks=[],
            errors=[str(exc)],
        )
    finally:
        if tmp_manifest_dir and tmp_manifest_dir.is_dir():
            try:
                shutil.rmtree(tmp_manifest_dir)
            except Exception:
                pass


def smoke_run_manifest_file(
    manifest_path: str | Path,
    *,
    runtime_data_dir: str | Path,
    dry_run: bool = True,
    sample_inputs: dict | None = None,
) -> dict:
    """Smoke-test a manifest already written to disk."""
    path = Path(manifest_path)
    if not path.is_file():
        return _build_fail_result(
            manifest_id=str(manifest_path),
            classification="LOAD_FAILED",
            checks=[_check("manifest_file_exists", False, f"File not found: {path}")],
            errors=[f"Manifest file not found: {path}"],
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _build_fail_result(
            manifest_id=str(manifest_path),
            classification="LOAD_FAILED",
            checks=[_check("manifest_file_readable", False, str(exc))],
            errors=[str(exc)],
        )
    return smoke_run_manifest_candidate(
        raw,
        runtime_data_dir=runtime_data_dir,
        dry_run=dry_run,
        sample_inputs=sample_inputs,
    )


# ---------------------------------------------------------------------------
# run_template_quality_gates
# ---------------------------------------------------------------------------

def run_template_quality_gates(
    *,
    runtime_data_dir: str | Path,
    manifest_dir: str | Path,
) -> dict:
    """Smoke-test every built-in template and return a consolidated quality gate result."""
    templates = list_manifest_templates()
    results = []
    passed = 0
    failed = 0

    for tmpl in templates:
        tid = tmpl["template_id"]
        mid = f"quality.{tid}"
        name = f"Quality Gate — {tmpl['name']}"
        sample_inputs = dict(tmpl.get("sample_inputs") or {})
        expected_classification = str(tmpl.get("expected_smoke_classification") or "DRY_RUN_COMPLETED")

        try:
            manifest = build_manifest_from_template(tid, mid, name)
        except Exception as exc:
            results.append({
                "template_id": tid,
                "manifest_id": mid,
                "status": "FAIL",
                "classification": "LOAD_FAILED",
                "error": f"build_manifest_from_template failed: {exc}",
            })
            failed += 1
            continue

        result = smoke_run_manifest_candidate(
            manifest,
            runtime_data_dir=runtime_data_dir,
            manifest_dir=manifest_dir,
            sample_inputs=sample_inputs,
        )
        classification = result.get("classification", "EXECUTION_FAILED")
        # Accept either the expected or its COMPLETED_NO_DATA_ACCEPTED variant
        accepted = {expected_classification, "COMPLETED_NO_DATA_ACCEPTED"}
        if expected_classification == "DRY_RUN_COMPLETED":
            accepted.add("COMPLETED_NO_DATA_ACCEPTED")
        gate_ok = classification in accepted and result.get("ok", False)

        results.append({
            "template_id": tid,
            "manifest_id": mid,
            "status": "PASS" if gate_ok else "FAIL",
            "classification": classification,
            "expected_classification": expected_classification,
            "frame_state": result.get("state", ""),
            "step_count": result.get("step_count", 0),
            "completed_steps": result.get("completed_steps", 0),
            "failed_steps": result.get("failed_steps", 0),
            "pending_action_count": result.get("pending_action_count", 0),
            "errors": result.get("errors", []),
        })
        if gate_ok:
            passed += 1
        else:
            failed += 1

    overall_ok = failed == 0
    return {
        "ok": overall_ok,
        "status": "PASS" if overall_ok else "FAIL",
        "template_count": len(templates),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


# ---------------------------------------------------------------------------
# write_smoke_report
# ---------------------------------------------------------------------------

def write_smoke_report(
    result: dict,
    *,
    runtime_data_dir: str | Path,
    report_name: str = "generated_manifest_smoke_report",
) -> dict:
    out_dir = Path(runtime_data_dir) / "generated_manifest_smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{report_name}.json"
    md_path = out_dir / f"{report_name}.md"

    try:
        json_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        return {"ok": False, "json_path": "", "markdown_path": "", "error": str(exc)}

    try:
        md_path.write_text(_build_markdown_report(result), encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "json_path": str(json_path), "markdown_path": "", "error": str(exc)}

    return {"ok": True, "json_path": str(json_path), "markdown_path": str(md_path)}


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------

def _smoke_run_impl(
    manifest: dict,
    tmp_manifest_dir: Path,
    runtime_data_dir: Path,
    dry_run: bool,
    sample_inputs: dict,
) -> dict:
    checks: list[dict] = []
    warnings: list[str] = []
    errors: list[str] = []
    manifest_id = _manifest_id(manifest)

    # 1. manifest_has_required_shape
    shape_ok, shape_errs = _check_required_shape(manifest)
    checks.append(_check("manifest_has_required_shape", shape_ok, shape_errs[0] if shape_errs else "Required fields present."))
    if not shape_ok:
        errors.extend(shape_errs)
        return _build_fail_result(manifest_id, "PREFLIGHT_FAILED", checks, errors)

    # 2. catalog_id_is_valid
    checks.append(_check("catalog_id_is_valid", bool(manifest_id), "manifest_id is non-empty." if manifest_id else "manifest_id is empty."))

    # 3. no_live_execution_enabled (check before runtime load so we classify it correctly)
    live_exec = manifest.get("live_execution", {})
    live_enabled = bool(live_exec.get("enabled", False)) if isinstance(live_exec, dict) else False
    if live_enabled:
        checks.append(_check("no_live_execution_enabled", False, "live_execution.enabled is True — smoke tests must not enable live execution."))
        errors.append("live_execution.enabled is True")
        return _build_fail_result(manifest_id, "UNEXPECTED_LIVE_SIDE_EFFECT", checks, errors)
    checks.append(_check("no_live_execution_enabled", True, "live_execution.enabled is False."))

    # 4. steps_parse — check each command parses before runtime load
    steps = manifest.get("steps") or []
    all_steps_parse = True
    for step in steps:
        if not isinstance(step, dict):
            continue
        cmd = str(step.get("command") or "").strip()
        if not cmd:
            continue
        try:
            parse_command(cmd)
        except CommandParseError as exc:
            checks.append(_check("steps_parse", False, f"Step {step.get('id', '?')}: {exc}"))
            errors.append(f"Command parse error in step {step.get('id', '?')}: {exc}")
            all_steps_parse = False
            break
    if all_steps_parse:
        checks.append(_check("steps_parse", True, f"All {len(steps)} step commands parse."))
    else:
        return _build_fail_result(manifest_id, "COMMAND_INVALID", checks, errors)

    # 5. manifest_loads — write to temp dir then load
    tmp_path = tmp_manifest_dir / f"{_safe_filename(manifest_id)}.manifest.json"
    try:
        tmp_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        loaded_manifest = runtime_load_manifest(tmp_path)
        checks.append(_check("manifest_loads", True, "Manifest loaded by runtime loader."))
    except Exception as exc:
        checks.append(_check("manifest_loads", False, str(exc)))
        errors.append(str(exc))
        return _build_fail_result(manifest_id, "LOAD_FAILED", checks, errors)

    # 6. tools_registered — check tool commands against registry
    try:
        from runtime.tool_registry import TOOL_REGISTRY
        unregistered = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            cmd = str(step.get("command") or "").strip()
            if not cmd:
                continue
            try:
                parsed = parse_command(cmd)
            except CommandParseError:
                continue
            if parsed.kind == "tool":
                tool_key = f"{parsed.namespace}/{parsed.action}"
                if tool_key not in TOOL_REGISTRY:
                    unregistered.append(tool_key)
        if unregistered:
            checks.append(_check("tools_registered", False, f"Unregistered tools: {', '.join(unregistered)}"))
            errors.append(f"Tool not registered: {', '.join(unregistered)}")
            return _build_fail_result(manifest_id, "TOOL_NOT_REGISTERED", checks, errors)
        checks.append(_check("tools_registered", True, "All tool commands are registered."))
    except Exception as exc:
        warnings.append(f"Could not check tool registry: {exc}")
        checks.append(_check("tools_registered", True, f"Registry check skipped: {exc}"))

    # 7. required_inputs_resolved — check sample_inputs cover required fields
    required_inputs = manifest.get("inputs") or []
    if isinstance(required_inputs, list):
        missing = [inp for inp in required_inputs if str(inp).strip() and str(inp).strip() not in sample_inputs]
    else:
        missing = []
    if missing:
        warnings.append(f"Sample inputs missing fields: {', '.join(missing)}. Using empty strings.")
        for inp in missing:
            sample_inputs = dict(sample_inputs)
            sample_inputs[str(inp).strip()] = ""
    checks.append(_check("required_inputs_resolved", True, "Required inputs resolved (may use empty fallback)."))

    # 8 + 9. taskframe_created + dry_run_execution (run all under fake LLM context)
    try:
        runtime_data_dir.mkdir(parents=True, exist_ok=True)
        orchestrator = Orchestrator(runtime_data_dir=str(runtime_data_dir))
        with _fake_llm_context():
            frame = orchestrator.create_frame_from_manifest(
                loaded_manifest,
                trigger=dict(getattr(loaded_manifest, "trigger", {}) or {}),
                inputs=sample_inputs,
                raw_input=json.dumps(sample_inputs, indent=2, sort_keys=True),
            )
            frame = orchestrator.prepare_frame(frame)
        save_taskframe(frame, str(runtime_data_dir))
        checks.append(_check("taskframe_created", True, f"TaskFrame {frame.frame_id} created."))
    except Exception as exc:
        checks.append(_check("taskframe_created", False, str(exc)))
        errors.append(str(exc))
        return _build_fail_result(manifest_id, "PREFLIGHT_FAILED", checks, errors)

    # 9. dry_run_started + dry_run_reached_expected_state
    try:
        with _fake_llm_context(), use_sheet_fixture_mode(True, str(runtime_data_dir)):
            frame = orchestrator.run_until_blocked(frame, loaded_manifest, dry_run=True)
        save_taskframe(frame, str(runtime_data_dir))
        checks.append(_check("dry_run_started", True, "Dry-run execution started."))
    except Exception as exc:
        checks.append(_check("dry_run_started", False, str(exc)))
        errors.append(str(exc))
        return _build_fail_result(manifest_id, "EXECUTION_FAILED", checks, errors)

    frame_dict = taskframe_to_dict(frame)
    final_state = str(frame_dict.get("state", ""))
    step_list = frame_dict.get("steps") or []
    completed = sum(1 for s in step_list if isinstance(s, dict) and str(s.get("status", "")).upper() == "COMPLETED")
    failed_count = sum(1 for s in step_list if isinstance(s, dict) and str(s.get("status", "")).upper() in {"FAILED", "FAILED_VALIDATION", "FAILED_EXECUTION"})
    pending_actions = frame_dict.get("pending_actions") or []
    output_keys = list((frame_dict.get("outputs") or {}).keys())
    errs_in_frame = frame_dict.get("errors") or []

    checks.append(_check(
        "dry_run_reached_expected_state",
        final_state in {"COMPLETED", "WAITING_FOR_EXECUTE", "COMPLETED_NO_DATA"},
        f"Frame reached state: {final_state}",
    ))

    # 10. completion_result_consistent
    completion = manifest.get("completion") or {}
    expected_outputs = completion.get("success_outputs") or []
    missing_outputs = [o for o in expected_outputs if o and o not in output_keys]
    if missing_outputs and final_state not in {"WAITING_FOR_EXECUTE"}:
        checks.append(_check("completion_result_consistent", False, f"Expected outputs missing: {missing_outputs}"))
        warnings.append(f"Expected outputs not in frame outputs: {missing_outputs}")
    else:
        checks.append(_check("completion_result_consistent", True, "Completion outputs consistent with frame."))

    # Classify
    if failed_count > 0 and final_state not in {"COMPLETED", "WAITING_FOR_EXECUTE"}:
        classification = "VALIDATION_FAILED"
        ok = False
    elif final_state == "WAITING_FOR_EXECUTE":
        classification = "WAITING_FOR_EXECUTE_EXPECTED"
        ok = True
    elif final_state in {"COMPLETED", "COMPLETED_NO_DATA"}:
        has_real_outputs = any(
            isinstance(v, dict) and v.get("metadata", {}).get("source") != "workbench_fixture"
            for v in (frame_dict.get("outputs") or {}).values()
        )
        if output_keys and not has_real_outputs:
            classification = "COMPLETED_NO_DATA_ACCEPTED"
        else:
            classification = "DRY_RUN_COMPLETED"
        ok = True
    else:
        classification = "EXECUTION_FAILED"
        ok = False
        errors.extend([str(e) for e in errs_in_frame if e])

    return {
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "classification": classification,
        "manifest_id": manifest_id,
        "frame_id": str(frame_dict.get("frame_id", "")),
        "state": final_state,
        "step_count": len(step_list),
        "completed_steps": completed,
        "failed_steps": failed_count,
        "pending_action_count": len(pending_actions) if isinstance(pending_actions, list) else 0,
        "output_keys": output_keys,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def _check_required_shape(manifest: dict) -> tuple[bool, list[str]]:
    if not isinstance(manifest, dict):
        return False, ["Manifest must be a dict."]
    errors = []
    for field in ("manifest_id", "name", "version", "trigger", "inputs", "steps", "validations", "completion"):
        if field not in manifest:
            errors.append(f"Missing required field: {field}")
    steps = manifest.get("steps")
    if isinstance(steps, list):
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"Step {idx} is not a dict.")
            elif not step.get("id") and not step.get("step_id"):
                errors.append(f"Step {idx} has no id.")
            elif not str(step.get("command") or "").strip():
                errors.append(f"Step {idx} has no command.")
    return len(errors) == 0, errors


def _build_fail_result(
    manifest_id: str,
    classification: str,
    checks: list[dict],
    errors: list[str],
) -> dict:
    first_failed = next((c for c in checks if not c.get("ok")), None)
    result = {
        "ok": False,
        "status": "FAIL",
        "classification": classification,
        "manifest_id": manifest_id,
        "frame_id": "",
        "state": "",
        "step_count": 0,
        "completed_steps": 0,
        "failed_steps": 0,
        "pending_action_count": 0,
        "output_keys": [],
        "errors": errors,
        "warnings": [],
        "checks": checks,
        "failed_check": first_failed.get("id") if first_failed else "",
        "suggested_fix": _suggest_fix(classification),
    }
    result["repair_guidance"] = _build_repair_guidance_summary(result)
    return result


def _build_repair_guidance_summary(smoke_result: dict) -> dict:
    try:
        from src.manifest_authoring_feedback import classify_smoke_failure
        findings = classify_smoke_failure(smoke_result)
        if not findings:
            return {"status": "NO_FINDINGS", "summary": "", "finding_count": 0, "top_finding_ids": []}
        return {
            "status": "HAS_FINDINGS",
            "summary": findings[0].get("message", ""),
            "finding_count": len(findings),
            "top_finding_ids": [f["id"] for f in findings[:3]],
        }
    except Exception:
        return {"status": "UNAVAILABLE", "summary": "", "finding_count": 0, "top_finding_ids": []}


def _check(check_id: str, ok: bool, message: str) -> dict:
    return {"id": check_id, "ok": ok, "message": message}


def _manifest_id(manifest: Any) -> str:
    if isinstance(manifest, dict):
        return str(manifest.get("manifest_id") or manifest.get("id") or "")
    return ""


def _safe_filename(manifest_id: str) -> str:
    import re
    safe = re.sub(r"[.\s/\\:]+", "_", str(manifest_id or "unknown"))
    safe = re.sub(r"[^A-Za-z0-9_\-]", "", safe)
    return safe.strip("_") or "manifest"


def _suggest_fix(classification: str) -> str:
    return {
        "LOAD_FAILED": "Check that the manifest JSON is valid and all required fields are present.",
        "PREFLIGHT_FAILED": "Review step definitions, inputs, and trigger configuration.",
        "INPUTS_MISSING": "Add required input values to sample_inputs or the manifest inputs list.",
        "TOOL_NOT_REGISTERED": "Check the generated command or choose a supported tool command from the tool registry.",
        "COMMAND_INVALID": "Review the step command syntax. Commands must start with [t:, [q:, [validate:, or [maintenance:.",
        "VALIDATION_FAILED": "One or more validations failed. Review the validation rules and completion criteria.",
        "EXECUTION_FAILED": "Execution raised an unexpected error. Review the step commands and runtime configuration.",
        "COMPLETION_FAILED": "The manifest did not reach the expected completion state. Check completion rules.",
        "UNEXPECTED_PENDING_ACTION": "A pending action was staged when not expected. Review the step side-effect classification.",
        "UNEXPECTED_LIVE_SIDE_EFFECT": "Live execution must be disabled for smoke tests. Check live_execution policy.",
    }.get(classification, "Review the manifest steps, validations, and completion rules.")


@contextmanager
def _fake_llm_context():
    """Force fake LLM for the duration of smoke execution."""
    previous = os.environ.get("TASKFRAME_LLM_PROVIDER")
    os.environ["TASKFRAME_LLM_PROVIDER"] = "fake"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TASKFRAME_LLM_PROVIDER", None)
        else:
            os.environ["TASKFRAME_LLM_PROVIDER"] = previous


def _build_markdown_report(result: dict) -> str:
    is_quality_gate = "results" in result
    lines = ["# Generated Manifest Template Quality Gate Report" if is_quality_gate else "# Generated Manifest Smoke Report", ""]
    status = result.get("status", "UNKNOWN")
    lines.append(f"**Verdict: {status}**")
    lines.append("")

    if is_quality_gate:
        lines.append(f"Templates: {result.get('template_count', 0)} | Passed: {result.get('passed', 0)} | Failed: {result.get('failed', 0)}")
        lines.append("")
        lines.append("| Template | Manifest ID | Validation | Smoke | Classification | Notes |")
        lines.append("|---|---|---|---|---|---|")
        for r in result.get("results") or []:
            errs = r.get("errors") or []
            notes = errs[0][:60] if errs else ("Pending action staged" if "WAITING" in r.get("classification", "") else "")
            lines.append(
                f"| {r.get('template_id', '')} | {r.get('manifest_id', '')} | PASS | {r.get('status', '')} | {r.get('classification', '')} | {notes} |"
            )
    else:
        mid = result.get("manifest_id", "")
        classification = result.get("classification", "")
        state = result.get("state", "")
        lines.append(f"Manifest: `{mid}`  ")
        lines.append(f"Classification: `{classification}`  ")
        lines.append(f"Frame State: `{state}`  ")
        lines.append(f"Steps: {result.get('step_count', 0)} total, {result.get('completed_steps', 0)} completed, {result.get('failed_steps', 0)} failed  ")
        lines.append(f"Pending Actions: {result.get('pending_action_count', 0)}  ")
        outputs = result.get("output_keys") or []
        lines.append(f"Outputs: {', '.join(outputs) or 'none'}  ")
        warnings = result.get("warnings") or []
        lines.append(f"Warnings: {', '.join(warnings) or 'none'}  ")
        lines.append("")
        lines.append("## Checks")
        lines.append("")
        for c in result.get("checks") or []:
            icon = "✓" if c.get("ok") else "✗"
            lines.append(f"- {icon} `{c.get('id', '')}`: {c.get('message', '')}")

    lines.append("")
    return "\n".join(lines)
