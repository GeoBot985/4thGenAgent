from __future__ import annotations

import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"critical": 0, "error": 1, "warning": 2, "info": 3}

# ---------------------------------------------------------------------------
# Known validation types (from runtime/validation.py VALIDATION_HANDLERS)
# ---------------------------------------------------------------------------

_KNOWN_VALIDATION_TYPES = {
    "output_exists",
    "output_not_empty",
    "pending_action_exists",
    "step_completed",
    "step_staged",
    "step_status",
    "step_duration_under",
    "step_timed_out",
    "step_not_timed_out",
    "attempt_count_equals",
    "attempt_count_less_than_or_equal",
    "condition_true",
    "condition_false",
    "one_of_steps_completed",
    "at_least_one_step_completed",
    "no_step_failed",
    "no_errors",
    "required_input_exists",
    "required_event_field_exists",
    "output_has_fields",
    "output_field_equals",
    "output_field_in",
    "output_in_allowed_values",
}

# ---------------------------------------------------------------------------
# Repair rule catalogue: smoke classification → repair finding metadata
# ---------------------------------------------------------------------------

_REPAIR_RULES: dict[str, dict] = {
    "LOAD_FAILED": {
        "id": "manifest_load_failed",
        "severity": "error",
        "location": "manifest",
        "summary": "The manifest could not be loaded by the runtime loader.",
        "suggested_fix": "Fix the JSON syntax or schema error first. Run Validate to see the specific error.",
        "example": "",
    },
    "PREFLIGHT_FAILED": {
        "id": "preflight_failed",
        "severity": "error",
        "location": "manifest",
        "summary": "The manifest failed a preflight check.",
        "suggested_fix": "Review the failed preflight check output and correct the offending manifest field.",
        "example": "",
    },
    "INPUTS_MISSING": {
        "id": "sample_inputs_missing",
        "severity": "error",
        "location": "inputs",
        "summary": "The manifest declares required inputs that were not provided for the smoke run.",
        "suggested_fix": "Add sample inputs to the template metadata, or remove unused input declarations from the manifest.",
        "example": '"inputs": ["message"]  →  also provide  sample_inputs={"message": "test"}',
    },
    "TOOL_NOT_REGISTERED": {
        "id": "unknown_tool",
        "severity": "error",
        "location": "steps[?].command",
        "summary": "The manifest references a tool that is not registered.",
        "suggested_fix": (
            "Use an existing registered tool command, or add the tool to the tool registry before using it in a manifest. "
            "Check the manifest tool reference for the correct namespace/action."
        ),
        "example": "[t:g/check -> result] max_results=5",
    },
    "COMMAND_INVALID": {
        "id": "command_invalid",
        "severity": "error",
        "location": "steps[?].command",
        "summary": "A step command could not be parsed.",
        "suggested_fix": (
            "Correct the command prefix and syntax. "
            "Tool commands: [t:namespace/action -> alias]. "
            "LLM commands: [q:action -> alias]. "
            "Validation commands: [validate:rule_id]."
        ),
        "example": "[t:g/check -> result] max_results=5",
    },
    "VALIDATION_FAILED": {
        "id": "validation_failed",
        "severity": "error",
        "location": "validations",
        "summary": "One or more validation rules failed.",
        "suggested_fix": (
            "Align the validation rule with the actual outputs produced by the steps. "
            "Check that output aliases in validations match step output aliases."
        ),
        "example": '{"id": "result_exists", "type": "output_exists", "output": "result"}',
    },
    "EXECUTION_FAILED": {
        "id": "execution_failed",
        "severity": "error",
        "location": "steps",
        "summary": "A step failed during execution.",
        "suggested_fix": (
            "Check tool arguments, required inputs, and the output alias. "
            "Verify that any input references (e.g. $inputs.message) are declared in the inputs list."
        ),
        "example": "[t:g/check -> result] max_results=5",
    },
    "COMPLETION_FAILED": {
        "id": "completion_failed",
        "severity": "error",
        "location": "completion",
        "summary": "The manifest completion criteria were not satisfied.",
        "suggested_fix": (
            "Align the completion criteria with the outputs actually produced by the steps. "
            "Ensure success_outputs lists aliases that steps actually write."
        ),
        "example": '"completion": {"success_outputs": ["result"]}',
    },
    "UNEXPECTED_PENDING_ACTION": {
        "id": "unexpected_pending_action",
        "severity": "warning",
        "location": "completion",
        "summary": "The manifest produced a pending action that was not expected by the smoke runner.",
        "suggested_fix": (
            "If this manifest intentionally stages a side effect for approval, use the approval_side_effect template. "
            "Set completion.allow_pending_approval: true and add a pending_action_exists validation."
        ),
        "example": '"completion": {"allow_pending_approval": true, "success_pending_actions": ["sent_msg"]}',
    },
    "UNEXPECTED_LIVE_SIDE_EFFECT": {
        "id": "live_side_effect_blocked",
        "severity": "critical",
        "location": "live_execution",
        "summary": "The manifest has live_execution.enabled set to true, which is blocked by the smoke runner.",
        "suggested_fix": (
            "Disable live_execution.enabled. "
            "Use pending actions with requires_approval: true to stage side effects for approval first. "
            "Never enable live execution in authoring or smoke-test context."
        ),
        "example": '"live_execution": {"enabled": false, "requires_approval": true}',
    },
    "SHAPE_INVALID": {
        "id": "shape_invalid",
        "severity": "error",
        "location": "manifest",
        "summary": "The manifest is missing required top-level fields.",
        "suggested_fix": (
            "Ensure the manifest has all required fields: "
            "manifest_id, name, version, trigger, inputs, steps, validations, completion."
        ),
        "example": "",
    },
    "TASKFRAME_ERROR": {
        "id": "taskframe_error",
        "severity": "error",
        "location": "manifest",
        "summary": "An unexpected error occurred during TaskFrame creation or execution.",
        "suggested_fix": (
            "Check the error details in the smoke report. "
            "Ensure the manifest is structurally valid and all referenced tools are registered."
        ),
        "example": "",
    },
}

_REQUIRED_TOP_LEVEL = ("manifest_id", "name", "version", "trigger", "inputs", "steps", "validations", "completion")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def explain_manifest_failure(
    *,
    manifest: dict | None = None,
    validation_result: dict | tuple | None = None,
    smoke_result: dict | None = None,
    exception: Exception | None = None,
) -> dict:
    findings: list[dict] = []

    # 1. Handle JSON parse exception
    if exception is not None:
        findings.append(_make_finding(
            id="json_parse_error",
            severity="error",
            location="manifest (editor text)",
            message=f"The editor text could not be parsed as JSON: {exception}",
            suggested_fix="Fix the JSON syntax. Common issues: trailing commas, unquoted keys, mismatched brackets.",
            example='{"manifest_id": "example.id", "name": "My Manifest", ...}',
            source="exception",
        ))

    # 2. Static manifest analysis
    if isinstance(manifest, dict):
        findings.extend(analyze_manifest_static(manifest))

    # 3. Validation result findings
    if validation_result is not None:
        findings.extend(_findings_from_validation_result(validation_result))

    # 4. Smoke result findings
    if isinstance(smoke_result, dict):
        findings.extend(classify_smoke_failure(smoke_result))

    findings = _deduplicate(findings)
    findings = _sort_findings(findings)

    if not findings:
        return {
            "ok": True,
            "status": "NO_FINDINGS",
            "severity": "info",
            "summary": "No repair guidance was generated.",
            "findings": [],
            "next_action": "Run validation or smoke test again after editing.",
        }

    top_severity = findings[0]["severity"]
    count = len(findings)
    if count == 1:
        summary = findings[0]["message"]
    else:
        summary = f"{count} issues found. Top issue: {findings[0]['message']}"

    next_action = _derive_next_action(findings)
    return {
        "ok": True,
        "status": "HAS_FINDINGS",
        "severity": top_severity,
        "summary": summary,
        "findings": findings,
        "next_action": next_action,
    }


def analyze_manifest_static(manifest: dict) -> list[dict]:
    if not isinstance(manifest, dict):
        return [_make_finding(
            id="shape_invalid",
            severity="error",
            location="manifest",
            message="Manifest is not a dict.",
            suggested_fix="Provide a valid manifest dict.",
            source="static_manifest_check",
        )]

    findings: list[dict] = []

    # --- Required top-level fields ---
    for field in _REQUIRED_TOP_LEVEL:
        if field not in manifest:
            findings.append(_make_finding(
                id="missing_required_top_level_field",
                severity="error",
                location=field,
                message=f"Missing required top-level field: '{field}'.",
                suggested_fix=f"Add the '{field}' field to the manifest.",
                source="static_manifest_check",
            ))

    # --- manifest_id ---
    manifest_id = str(manifest.get("manifest_id") or manifest.get("id") or "").strip()
    if not manifest_id and "manifest_id" in manifest:
        findings.append(_make_finding(
            id="invalid_manifest_id",
            severity="error",
            location="manifest_id",
            message="manifest_id is present but empty.",
            suggested_fix="Set manifest_id to a non-empty dot-separated identifier, e.g. 'example.my_manifest'.",
            source="static_manifest_check",
        ))

    # --- Steps ---
    steps = manifest.get("steps")
    step_aliases: set[str] = set()
    step_ids: set[str] = set()

    if steps is None:
        pass  # already caught by required field check
    elif not isinstance(steps, list) or len(steps) == 0:
        findings.append(_make_finding(
            id="missing_or_empty_steps",
            severity="error",
            location="steps",
            message="The manifest has no steps.",
            suggested_fix="Add at least one step with a valid command.",
            example='{"id": "read_data", "command": "[t:g/check -> result] max_results=5"}',
            source="static_manifest_check",
        ))
    else:
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                findings.append(_make_finding(
                    id="shape_invalid",
                    severity="error",
                    location=f"steps[{idx}]",
                    message=f"Step {idx} is not a dict.",
                    suggested_fix="Each step must be a JSON object with 'id' and 'command'.",
                    source="static_manifest_check",
                ))
                continue

            step_id = str(step.get("id") or step.get("step_id") or "").strip()
            if not step_id:
                findings.append(_make_finding(
                    id="shape_invalid",
                    severity="error",
                    location=f"steps[{idx}].id",
                    message=f"Step {idx} is missing an 'id'.",
                    suggested_fix="Add a unique string id to each step.",
                    source="static_manifest_check",
                ))
            elif step_id in step_ids:
                findings.append(_make_finding(
                    id="duplicate_step_id",
                    severity="error",
                    location=f"steps[{idx}].id",
                    message=f"Duplicate step id '{step_id}'.",
                    suggested_fix="Each step must have a unique id.",
                    source="static_manifest_check",
                ))
            else:
                step_ids.add(step_id)

            command = str(step.get("command") or "").strip()
            if not command:
                findings.append(_make_finding(
                    id="step_missing_command",
                    severity="error",
                    location=f"steps[{idx}].command",
                    message=f"Step '{step_id or idx}' has no command.",
                    suggested_fix="Add a valid command string, e.g. '[t:g/check -> result] max_results=5'.",
                    source="static_manifest_check",
                ))
            else:
                cmd_stripped = command.lstrip()
                # Detect tool/LLM commands missing the -> output alias entirely
                if (cmd_stripped.startswith("[t:") or cmd_stripped.startswith("[q:")) and "->" not in command:
                    findings.append(_make_finding(
                        id="step_missing_output_alias",
                        severity="warning",
                        location=f"steps[{idx}].command",
                        message=f"Step '{step_id or idx}' tool/LLM command is missing an output alias (->).",
                        suggested_fix=(
                            "Add '-> alias_name' to the command to capture the output. "
                            "Example: [t:g/check -> result] max_results=5"
                        ),
                        example="[t:g/check -> result] max_results=5",
                        source="static_manifest_check",
                    ))
                else:
                    alias, parse_err = _try_extract_alias(command)
                    if parse_err:
                        findings.append(_make_finding(
                            id="command_parse_error",
                            severity="error",
                            location=f"steps[{idx}].command",
                            message=f"Step '{step_id or idx}' command could not be parsed: {parse_err}",
                            suggested_fix=(
                                "Correct the command syntax. "
                                "Tool: [t:namespace/action -> alias]. "
                                "LLM: [q:action -> alias]. "
                                "Validate: [validate:rule_id]."
                            ),
                            example="[t:g/check -> result] max_results=5",
                            source="static_manifest_check",
                        ))
                    elif alias:
                        step_aliases.add(alias)
                    else:
                        # validate or maintenance commands have no alias — fine
                        pass

    # --- Inputs ---
    inputs_raw = manifest.get("inputs") or []
    declared_inputs: set[str] = set()
    if isinstance(inputs_raw, list):
        for item in inputs_raw:
            name = str(item).strip()
            if name:
                declared_inputs.add(name)

    # Collect all command text for $inputs.X reference checking
    command_texts: list[str] = []
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                cmd = str(step.get("command") or "")
                if cmd:
                    command_texts.append(cmd)
    all_commands_text = " ".join(command_texts)

    referenced_inputs: set[str] = set(re.findall(r"\$inputs\.(\w+)", all_commands_text))

    for inp in declared_inputs:
        if inp not in referenced_inputs:
            findings.append(_make_finding(
                id="input_declared_but_not_used",
                severity="warning",
                location=f"inputs",
                message=f"Input '{inp}' is declared but not referenced in any step command.",
                suggested_fix=f"Remove '{inp}' from inputs if unused, or reference it in a command as $inputs.{inp}.",
                source="static_manifest_check",
            ))

    for inp in referenced_inputs:
        if inp not in declared_inputs:
            findings.append(_make_finding(
                id="input_used_but_not_declared",
                severity="error",
                location="inputs",
                message=f"Command references $inputs.{inp}, but '{inp}' is not declared in inputs.",
                suggested_fix=f"Add '{inp}' to the inputs list.",
                example=f'"inputs": ["{inp}"]',
                source="static_manifest_check",
            ))

    # --- Validations ---
    validations = manifest.get("validations") or []
    if isinstance(validations, list):
        for vidx, val in enumerate(validations):
            if not isinstance(val, dict):
                continue
            vtype = str(val.get("type") or "").strip()
            if vtype and vtype not in _KNOWN_VALIDATION_TYPES:
                findings.append(_make_finding(
                    id="unknown_validation_type",
                    severity="error",
                    location=f"validations[{vidx}].type",
                    message=f"Validation '{val.get('id', vidx)}' uses unknown type '{vtype}'.",
                    suggested_fix=f"Use a known validation type: {', '.join(sorted(_KNOWN_VALIDATION_TYPES)[:8])}...",
                    source="static_manifest_check",
                ))
            if vtype == "output_exists":
                output = str(val.get("output") or "").strip()
                if output and step_aliases and output not in step_aliases:
                    findings.append(_make_finding(
                        id="validation_references_missing_output",
                        severity="error",
                        location=f"validations[{vidx}].output",
                        message=f"Validation '{val.get('id', vidx)}' expects output '{output}', but no step writes '{output}'.",
                        suggested_fix=(
                            f"Change the validation output to an existing alias ({', '.join(sorted(step_aliases))}), "
                            f"or update a step command to write '{output}'."
                        ),
                        source="static_manifest_check",
                    ))

    # --- Completion ---
    completion = manifest.get("completion")
    if isinstance(completion, dict):
        success_outputs = completion.get("success_outputs") or []
        if isinstance(success_outputs, list):
            for cidx, alias in enumerate(success_outputs):
                alias = str(alias).strip()
                if alias and step_aliases and alias not in step_aliases:
                    acceptable = completion.get("acceptable_empty_outputs") or []
                    if alias not in acceptable:
                        findings.append(_make_finding(
                            id="completion_output_missing",
                            severity="error",
                            location=f"completion.success_outputs[{cidx}]",
                            message=f"Completion expects output '{alias}', but no step writes '{alias}'.",
                            suggested_fix=(
                                f"Change the completion output to an existing alias ({', '.join(sorted(step_aliases))}), "
                                f"or update a step command to write '{alias}'."
                            ),
                            example=f"[t:g/check -> {alias}] max_results=5",
                            source="static_manifest_check",
                        ))

        success_pending = completion.get("success_pending_actions") or []
        success_executed = completion.get("success_executed_actions") or []
        has_completion_data = bool(success_outputs or success_pending or success_executed)
        if not has_completion_data and not completion.get("acceptable_empty_outputs"):
            findings.append(_make_finding(
                id="completion_empty_without_acceptable_empty",
                severity="warning",
                location="completion",
                message="Completion block has no success outputs or pending actions defined.",
                suggested_fix="Add success_outputs, success_pending_actions, or acceptable_empty_outputs to the completion block.",
                example='"completion": {"success_outputs": ["result"]}',
                source="static_manifest_check",
            ))

    # --- live_execution check ---
    live = manifest.get("live_execution")
    if isinstance(live, dict) and live.get("enabled") is True:
        findings.append(_make_finding(
            id="live_execution_enabled",
            severity="critical",
            location="live_execution",
            message="live_execution.enabled is true. Smoke-tested and authored manifests must not enable live execution.",
            suggested_fix=(
                "Set live_execution.enabled to false. "
                "Use pending actions with requires_approval: true to stage side effects."
            ),
            example='"live_execution": {"enabled": false, "requires_approval": true}',
            source="static_manifest_check",
        ))

    # --- side effect commands without pending expectation ---
    if isinstance(steps, list) and isinstance(completion, dict):
        has_side_effect_cmd = any(
            _command_looks_like_side_effect(str(step.get("command") or ""))
            for step in steps
            if isinstance(step, dict)
        )
        has_pending_approval = completion.get("allow_pending_approval") or completion.get("success_pending_actions")
        has_pending_validation = any(
            isinstance(v, dict) and v.get("type") == "pending_action_exists"
            for v in (manifest.get("validations") or [])
        )
        if has_side_effect_cmd and not has_pending_approval and not has_pending_validation:
            findings.append(_make_finding(
                id="side_effect_command_without_pending_expectation",
                severity="warning",
                location="completion",
                message="A step command appears to stage a side effect, but completion does not expect a pending action.",
                suggested_fix=(
                    "Add 'allow_pending_approval: true' and 'success_pending_actions' to completion, "
                    "and add a 'pending_action_exists' validation. "
                    "Use the approval_side_effect template as reference."
                ),
                example='"completion": {"allow_pending_approval": true, "success_pending_actions": ["sent_msg"]}',
                source="static_manifest_check",
            ))

    # --- event trigger without route note ---
    trigger = manifest.get("trigger")
    if isinstance(trigger, dict) and trigger.get("type") == "event":
        findings.append(_make_finding(
            id="event_trigger_without_route_note",
            severity="info",
            location="trigger",
            message="This manifest uses an event trigger. Event routes are not registered automatically.",
            suggested_fix=(
                "Register an event route manually in config/event_routes.json. "
                "See manifest_building_manual.md Section 13 for the route snippet format."
            ),
            source="static_manifest_check",
        ))

    return findings


def classify_smoke_failure(smoke_result: dict) -> list[dict]:
    findings: list[dict] = []
    classification = str(smoke_result.get("classification") or "").strip()
    errors = smoke_result.get("errors") or []
    checks = smoke_result.get("checks") or []

    rule = _REPAIR_RULES.get(classification)
    if rule is None:
        return findings

    # Build a message that incorporates smoke error detail where available
    base_message = rule["summary"]
    error_detail = "; ".join(str(e) for e in errors[:2]) if errors else ""
    if error_detail:
        message = f"{base_message} Detail: {error_detail}"
    else:
        message = base_message

    # Try to narrow the location from check results
    location = rule["location"]
    failed_checks = [c for c in checks if isinstance(c, dict) and c.get("status") != "PASS"]
    if failed_checks:
        first_check = failed_checks[0]
        check_name = str(first_check.get("name") or "")
        if check_name:
            location = check_name

    findings.append(_make_finding(
        id=rule["id"],
        severity=rule["severity"],
        location=location,
        message=message,
        suggested_fix=rule["suggested_fix"],
        example=rule.get("example", ""),
        source="smoke_result",
    ))
    return findings


def write_repair_guidance_report(
    guidance: dict,
    *,
    runtime_data_dir: str | Path = "runtime_data",
    report_name: str = "manifest_repair_guidance",
) -> dict:
    import json as _json

    out_dir = Path(runtime_data_dir) / "generated_manifest_smoke"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "json_path": "", "markdown_path": ""}

    json_path = out_dir / f"{report_name}.json"
    md_path = out_dir / f"{report_name}.md"

    try:
        json_path.write_text(_json.dumps(guidance, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": str(exc), "json_path": "", "markdown_path": ""}

    try:
        md_path.write_text(_build_markdown_report(guidance), encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": str(exc), "json_path": str(json_path), "markdown_path": ""}

    return {
        "ok": True,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_finding(
    *,
    id: str,
    severity: str,
    location: str = "",
    message: str = "",
    suggested_fix: str = "",
    example: str = "",
    source: str = "static_manifest_check",
) -> dict:
    return {
        "id": id,
        "severity": severity,
        "location": location,
        "message": message,
        "suggested_fix": suggested_fix,
        "example": example,
        "source": source,
    }


def _sort_findings(findings: list[dict]) -> list[dict]:
    return sorted(
        findings,
        key=lambda f: (_SEVERITY_ORDER.get(f.get("severity", "info"), 99), f.get("location", ""), f.get("id", "")),
    )


def _deduplicate(findings: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for f in findings:
        key = (f.get("id"), f.get("location"), f.get("message", "")[:80])
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def _try_extract_alias(command: str) -> tuple[str | None, str | None]:
    try:
        from runtime.command_parser import parse_command
        parsed = parse_command(command)
        return parsed.output_alias, None
    except Exception as exc:
        return None, str(exc)


def _command_looks_like_side_effect(command: str) -> bool:
    lower = command.lower()
    # [t:wa/send ...], [t:customer/send ...], [t:supplier/send ...] etc.
    side_effect_patterns = ["/send", "/write", "/submit", "wa/", "customer/send", "supplier/send"]
    return any(p in lower for p in side_effect_patterns)


def _findings_from_validation_result(validation_result: Any) -> list[dict]:
    findings: list[dict] = []

    # Normalise to (ok, errors_list)
    if isinstance(validation_result, tuple):
        ok = bool(validation_result[0]) if len(validation_result) > 0 else True
        errors = list(validation_result[1]) if len(validation_result) > 1 else []
    elif isinstance(validation_result, dict):
        ok = bool(validation_result.get("ok", True))
        errors = list(validation_result.get("errors") or [])
    else:
        return findings

    if ok:
        return findings

    for err in errors:
        err_str = str(err)
        finding_id, loc = _classify_validation_error(err_str)
        findings.append(_make_finding(
            id=finding_id,
            severity="error",
            location=loc,
            message=err_str,
            suggested_fix=_suggested_fix_for_validation_error(err_str),
            source="validation_result",
        ))
    return findings


def _classify_validation_error(err: str) -> tuple[str, str]:
    lower = err.lower()
    if "manifest_id" in lower and ("required" in lower or "empty" in lower):
        return "invalid_manifest_id", "manifest_id"
    if "duplicate" in lower or "already exists" in lower:
        return "duplicate_manifest_id", "manifest_id"
    if "missing required" in lower:
        field = _extract_field_name(err)
        return "missing_required_top_level_field", field or "manifest"
    if "command" in lower and ("parse" in lower or "invalid" in lower or "unknown" in lower):
        return "command_parse_error", "steps[?].command"
    if "runtime validation" in lower:
        return "manifest_load_failed", "manifest"
    return "validation_error", "manifest"


def _suggested_fix_for_validation_error(err: str) -> str:
    lower = err.lower()
    if "duplicate" in lower or "already exists" in lower:
        return "Choose a different manifest_id that does not already exist in the catalog."
    if "manifest_id" in lower:
        return "Set manifest_id to a non-empty dot-separated identifier."
    if "missing required" in lower:
        return "Add the missing field to the manifest."
    if "command" in lower:
        return "Fix the command syntax. Example: [t:g/check -> result] max_results=5"
    return "Review the validation error and fix the manifest accordingly."


def _extract_field_name(err: str) -> str:
    m = re.search(r"field[:\s]+([a-zA-Z_]+)", err, re.IGNORECASE)
    if m:
        return m.group(1)
    return ""


def _derive_next_action(findings: list[dict]) -> str:
    if not findings:
        return "Run validation or smoke test again after editing."
    top = findings[0]
    sid = top.get("id", "")
    if sid == "live_execution_enabled":
        return "Disable live_execution.enabled before saving or smoke-testing this manifest."
    if sid in ("command_parse_error", "command_invalid"):
        return "Fix the command syntax, then run Validate or Smoke test again."
    if sid in ("manifest_load_failed", "json_parse_error"):
        return "Fix the JSON/schema error first, then run Validate again."
    if sid == "duplicate_manifest_id":
        return "Choose a unique manifest_id, then save again."
    if sid in ("unknown_tool",):
        return "Replace the unregistered tool command with a registered one, then run Smoke test again."
    if sid in ("completion_output_missing", "completion_failed"):
        return "Align completion.success_outputs with the output aliases written by your steps."
    if sid in ("validation_references_missing_output", "validation_failed"):
        return "Fix the validation output reference to match a step output alias, then run Smoke test again."
    return "Address the findings above, then run Validate or Smoke test again."


def _build_markdown_report(guidance: dict) -> str:
    lines = [
        "# Manifest Repair Guidance",
        "",
        f"Status: {guidance.get('status', 'UNKNOWN')}  ",
        f"Severity: {guidance.get('severity', 'info')}",
        "",
        "## Summary",
        "",
        guidance.get("summary", ""),
        "",
    ]
    findings = guidance.get("findings") or []
    if findings:
        lines += [
            "## Findings",
            "",
            "| Severity | Finding | Location | Suggested Fix |",
            "|---|---|---|---|",
        ]
        for f in findings:
            sev = f.get("severity", "")
            fid = f.get("id", "")
            loc = f.get("location", "")
            fix = f.get("suggested_fix", "").replace("|", "/")
            lines.append(f"| {sev} | {fid} | {loc} | {fix} |")
        lines.append("")
    lines += [
        "## Next Action",
        "",
        guidance.get("next_action", ""),
    ]
    return "\n".join(lines)
