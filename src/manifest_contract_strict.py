from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from runtime.command_parser import CommandParseError, parse_command
from runtime.tool_registry import build_tool_registry

try:
    from src.manifest_authoring_feedback import _KNOWN_VALIDATION_TYPES as _AUTHORING_VALIDATION_TYPES
except Exception:  # pragma: no cover - fallback for minimal environments
    _AUTHORING_VALIDATION_TYPES = {
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
        "one_of_steps_completed",
        "all_steps_completed",
        "no_step_failed",
        "no_errors",
        "required_input_exists",
        "required_event_field_exists",
        "output_has_fields",
        "output_field_equals",
        "output_field_in",
        "output_in_allowed_values",
        "llm_call_exists",
        "llm_call_ok",
        "memory_key_exists",
        "memory_output_found",
        "memory_output_missing",
    }

KNOWN_VALIDATION_TYPES = set(_AUTHORING_VALIDATION_TYPES)
ALLOWED_TRIGGER_TYPES = {"manual", "event", "schedule", "command"}
ALLOWED_STEP_KINDS = {"tool", "llm", "validate", "validate_required_inputs", "maintenance"}
REQUIRED_TOP_LEVEL = ("manifest_id", "name", "version", "trigger", "inputs", "steps", "validations", "completion", "side_effect_policy")
IMPLICIT_EVENT_INPUTS = {"event_id", "event_type", "event_source", "source", "received_at"}


def normalize_manifest_contract(manifest: dict) -> dict:
    normalized = copy.deepcopy(manifest or {})
    if not isinstance(normalized, dict):
        return {}

    if "manifest_id" not in normalized and isinstance(normalized.get("id"), str):
        normalized["manifest_id"] = normalized["id"]

    trigger = normalized.get("trigger")
    if not isinstance(trigger, dict):
        trigger = {}
    if not trigger and isinstance(normalized.get("trigger_type"), str):
        trigger = {"type": normalized.get("trigger_type")}
    elif isinstance(trigger, dict) and not trigger.get("type") and isinstance(normalized.get("trigger_type"), str):
        trigger = dict(trigger)
        trigger["type"] = normalized.get("trigger_type")
    normalized["trigger"] = trigger

    normalized["inputs"] = _normalize_inputs(normalized.get("inputs"))
    normalized["steps"] = _normalize_steps(normalized.get("steps"))
    normalized["validations"] = list(normalized.get("validations") or []) if isinstance(normalized.get("validations"), list) else []
    normalized["completion"] = _normalize_completion(normalized.get("completion"))
    normalized["side_effect_policy"] = _normalize_side_effect_policy(normalized)

    if "live_execution" in normalized and not isinstance(normalized.get("live_execution"), dict):
        normalized["live_execution"] = {}

    return normalized


def validate_manifest_strict(
    manifest: dict,
    *,
    manifest_path: str = "",
    active_catalog: bool = True,
    event_routes: dict | None = None,
    tool_registry: dict | None = None,
) -> dict:
    original = manifest if isinstance(manifest, dict) else {}
    normalized = normalize_manifest_contract(original)
    findings: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    manifest_id = str(normalized.get("manifest_id", "")).strip() or str(original.get("id", "")).strip() or _manifest_id_from_path(manifest_path)
    legacy_manifest = _has_legacy_manifest_fields(original)

    _check_top_level(original, normalized, findings, warnings, errors, legacy_manifest)
    step_analysis = _check_steps(normalized, findings, warnings, errors, legacy_manifest)
    input_analysis = _check_inputs(
        normalized,
        step_analysis,
        findings,
        warnings,
        errors,
        legacy_manifest,
        event_routes=event_routes,
    )
    validation_analysis = _check_validations(normalized, step_analysis, input_analysis, findings, warnings, errors)
    completion_analysis = _check_completion(normalized, step_analysis, input_analysis, findings, warnings, errors, legacy_manifest)
    _check_side_effect_policy(normalized, step_analysis, completion_analysis, findings, warnings, errors, legacy_manifest)
    _check_active_fixture_constraints(normalized, manifest_path, findings, warnings, errors)

    if active_catalog:
        _check_event_routes(
            normalized,
            step_analysis,
            input_analysis,
            findings,
            warnings,
            errors,
            event_routes=event_routes,
            manifest_path=manifest_path,
            legacy_manifest=legacy_manifest,
        )
        _check_tool_registry(
            normalized,
            step_analysis,
            findings,
            warnings,
            errors,
            tool_registry=tool_registry,
            manifest_path=manifest_path,
        )

    _apply_status_policies(normalized, step_analysis, completion_analysis, findings, warnings, errors, legacy_manifest)

    status = "FAIL" if errors else "WARN" if warnings or findings else "PASS"
    return {
        "ok": not errors,
        "status": status,
        "manifest_id": manifest_id,
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
    }


def _check_top_level(
    original: dict[str, Any],
    normalized: dict[str, Any],
    findings: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    legacy_manifest: bool,
) -> None:
    for field in REQUIRED_TOP_LEVEL:
        if field == "version":
            continue
        if field in original:
            continue
        if field == "manifest_id" and original.get("id"):
            _add_finding(findings, "legacy_manifest_id", "warning", "manifest.id", "Legacy field 'id' was normalised to manifest_id.", "Use manifest_id in active manifests.")
            warnings.append("Legacy field 'id' normalised to manifest_id.")
            continue
        if field == "trigger" and original.get("trigger_type"):
            _add_finding(findings, "legacy_trigger_type", "warning", "trigger_type", "Legacy field 'trigger_type' was normalised to trigger.type.", "Use trigger.type in active manifests.")
            warnings.append("Legacy field 'trigger_type' normalised to trigger.type.")
            continue
        if field == "inputs" and isinstance(original.get("inputs"), list):
            _add_finding(findings, "legacy_inputs_list", "warning", "inputs", "Legacy list-style inputs were normalised to canonical required/optional inputs.", "Use inputs.required/inputs.optional in active manifests.")
            warnings.append("Legacy list-style inputs normalised.")
            continue
        if field == "completion" and isinstance(original.get("completion"), dict):
            if any(alias in original["completion"] for alias in ("required_outputs", "required_pending_actions", "required_state")):
                _add_finding(findings, "legacy_completion_aliases", "warning", "completion", "Legacy completion aliases were normalised.", "Use success_outputs/success_pending_actions/required_state.")
                warnings.append("Legacy completion aliases normalised.")
            continue
        if field == "side_effect_policy":
            _add_finding(findings, "missing_side_effect_policy", "warning" if legacy_manifest else "error", "side_effect_policy", "Manifest is missing side_effect_policy.", "Add side_effect_policy to the manifest.")
            (warnings if legacy_manifest else errors).append("Manifest is missing side_effect_policy.")
            continue
        _add_finding(findings, f"missing_{field}", "error", field, f"Missing required top-level field: {field}.", f"Add {field} to the manifest.")
        errors.append(f"Missing required top-level field: {field}.")

    version = normalized.get("version")
    if "version" not in original or version is None or version == "":
        if legacy_manifest:
            _add_finding(findings, "legacy_missing_version", "warning", "version", "Legacy manifest is missing version.", "Add version to the manifest.")
            warnings.append("Legacy manifest is missing version.")
        else:
            _add_finding(findings, "missing_version", "error", "version", "Manifest version must be present.", "Set manifest.version.")
            errors.append("Manifest version must be present.")
    elif not isinstance(version, (str, int, float)):
        _add_finding(findings, "invalid_version", "error", "version", "Manifest version must be present.", "Set manifest.version.")
        errors.append("Manifest version must be present.")


def _check_steps(
    manifest: dict[str, Any],
    findings: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    legacy_manifest: bool,
) -> dict[str, Any]:
    steps = manifest.get("steps")
    step_aliases: dict[str, str] = {}
    step_kinds: dict[str, str] = {}
    step_output_aliases: set[str] = set()
    side_effect_steps: list[dict[str, Any]] = []

    if not isinstance(steps, list) or not steps:
        _add_finding(findings, "missing_steps", "error", "steps", "Manifest steps must be a non-empty list.", "Add at least one step.")
        errors.append("Manifest steps must be a non-empty list.")
        return {"step_aliases": step_aliases, "step_kinds": step_kinds, "step_output_aliases": step_output_aliases, "side_effect_steps": side_effect_steps, "step_ids": []}

    seen_ids: set[str] = set()
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            _add_finding(findings, "invalid_step_object", "error", f"steps[{idx}]", "Each step must be an object.", "Use an object with id/kind/command.")
            errors.append(f"Step {idx} must be an object.")
            continue

        step_id = str(step.get("id") or step.get("step_id") or "").strip()
        if not step_id:
            _add_finding(findings, "missing_step_id", "error", f"steps[{idx}]", "Every step must have a unique id.", "Add a step.id field.")
            errors.append(f"Step {idx} is missing an id.")
            continue
        if step_id in seen_ids:
            _add_finding(findings, "duplicate_step_id", "error", f"steps[{idx}].id", f"Duplicate step id: {step_id}.", "Rename the duplicate step id.")
            errors.append(f"Duplicate step id: {step_id}.")
        seen_ids.add(step_id)
        step_aliases[step_id] = step_id

        command = str(step.get("command") or "").strip()
        if not command:
            _add_finding(findings, "missing_step_command", "error", f"steps[{idx}].command", f"Step '{step_id}' is missing command.", "Add a command string.")
            errors.append(f"Step '{step_id}' is missing command.")
            continue

        parsed_kind, parsed_alias = _parse_step_command(command, idx, findings, warnings, errors)
        declared_kind = str(step.get("kind") or "").strip()
        if declared_kind:
            if declared_kind not in ALLOWED_STEP_KINDS and declared_kind not in {"inspection", "approval", "cleanup", "memory", "llm", "tool", "pending"}:
                _add_finding(findings, "unknown_step_kind", "error", f"steps[{idx}].kind", f"Unknown step kind '{declared_kind}'.", "Use tool, llm, validate, validate_required_inputs, or maintenance.")
                errors.append(f"Unknown step kind '{declared_kind}'.")
        else:
            if legacy_manifest or (step.get("step_id") is not None and step.get("id") is None):
                _add_finding(findings, "legacy_step_kind", "warning", f"steps[{idx}].kind", f"Step '{step_id}' uses inferred kind '{parsed_kind}'.", "Add an explicit kind to the step.")
                warnings.append(f"Step '{step_id}' uses inferred kind '{parsed_kind}'.")
            else:
                _add_finding(findings, "missing_step_kind", "error", f"steps[{idx}].kind", f"Step '{step_id}' is missing kind.", "Add an explicit kind to the step.")
                errors.append(f"Step '{step_id}' is missing kind.")

        effective_kind = declared_kind or parsed_kind
        step_kinds[step_id] = effective_kind

        if parsed_alias:
            if parsed_alias in step_output_aliases:
                _add_finding(findings, "duplicate_output_alias", "warning", f"steps[{idx}].command", f"Output alias '{parsed_alias}' is reused.", "Make the branch conditions mutually exclusive or use a distinct alias.")
                warnings.append(f"Output alias '{parsed_alias}' is reused.")
            step_output_aliases.add(parsed_alias)
        elif effective_kind in {"tool", "llm"}:
            _add_finding(findings, "missing_output_alias", "error", f"steps[{idx}].command", f"Step '{step_id}' must write an output alias.", "Use [t:... -> alias] or [q:... -> alias].")
            errors.append(f"Step '{step_id}' must write an output alias.")

        if _looks_like_side_effect_step(step, command, parsed_kind):
            side_effect_steps.append({"step_id": step_id, "command": command, "kind": effective_kind, "output_alias": parsed_alias})

    return {
        "step_aliases": step_aliases,
        "step_kinds": step_kinds,
        "step_output_aliases": step_output_aliases,
        "side_effect_steps": side_effect_steps,
        "step_ids": list(seen_ids),
    }


def _check_inputs(
    manifest: dict[str, Any],
    step_analysis: dict[str, Any],
    findings: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    legacy_manifest: bool,
    *,
    event_routes: dict | None = None,
) -> dict[str, Any]:
    inputs = manifest.get("inputs")
    required: list[str] = []
    optional: list[str] = []
    audit_only: list[str] = []
    trigger = manifest.get("trigger") if isinstance(manifest.get("trigger"), dict) else {}
    trigger_type = str(trigger.get("type") or "").strip().lower()

    if isinstance(inputs, dict):
        required = _string_list(inputs.get("required"))
        optional = _string_list(inputs.get("optional"))
        audit_only = _string_list(inputs.get("audit_only"))
    elif isinstance(inputs, list):
        required = _string_list(inputs)
    else:
        _add_finding(findings, "invalid_inputs", "error", "inputs", "inputs must be a list or object.", "Set inputs to {required: [], optional: []}.")
        errors.append("inputs must be a list or object.")
        return {"required": required, "optional": optional, "audit_only": audit_only, "declared": set(), "used": set()}

    declared = set(required) | set(optional) | set(audit_only)
    if len(declared) != len(required) + len(optional) + len(audit_only):
        _add_finding(findings, "duplicate_input_name", "error", "inputs", "Duplicate input names are not allowed.", "Remove duplicate input names.")
        errors.append("Duplicate input names are not allowed.")

    overlap = (set(required) & set(optional)) | (set(required) & set(audit_only)) | (set(optional) & set(audit_only))
    if overlap:
        _add_finding(findings, "duplicate_required_and_optional_input", "error", "inputs", f"Input names overlap: {sorted(overlap)}.", "Separate required, optional, and audit_only inputs.")
        errors.append(f"Input names overlap: {sorted(overlap)}.")

    used_inputs = _collect_input_refs(manifest, step_analysis)
    route_inputs = _collect_route_inputs(manifest, event_routes) if trigger_type == "event" else set()
    undeclared_exempt = set(IMPLICIT_EVENT_INPUTS) if trigger_type == "event" else set()
    undeclared = sorted({item for item in used_inputs if item not in declared and item not in audit_only and item not in undeclared_exempt})
    if undeclared:
        _add_finding(findings, "input_not_declared", "error", "steps", f"Inputs are referenced but not declared: {undeclared}.", "Declare the inputs under inputs.required or inputs.optional.")
        errors.append(f"Inputs are referenced but not declared: {undeclared}.")

    used_for_required = set(used_inputs) | set(route_inputs)
    if trigger_type == "event":
        used_for_required.update(IMPLICIT_EVENT_INPUTS)

    for req in required:
        if req not in used_for_required and req not in audit_only:
            severity = "warning"
            _add_finding(findings, "required_input_not_used", severity, "inputs.required", f"Required input '{req}' is declared but not used.", "Use the input in at least one step or mark it audit_only.")
            warnings.append(f"Required input '{req}' is declared but not used.")

    return {"required": required, "optional": optional, "audit_only": audit_only, "declared": declared, "used": used_inputs}


def _check_validations(
    manifest: dict[str, Any],
    step_analysis: dict[str, Any],
    input_analysis: dict[str, Any],
    findings: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
) -> dict[str, Any]:
    validations = manifest.get("validations") or []
    step_outputs = set(step_analysis.get("step_output_aliases", set()))
    declared_inputs = set(input_analysis.get("declared", set()))
    used_inputs = set(input_analysis.get("used", set()))
    external_inputs = declared_inputs | used_inputs
    validation_ids: set[str] = set()

    if not isinstance(validations, list):
        _add_finding(findings, "invalid_validations", "error", "validations", "validations must be a list.", "Set validations to an array.")
        errors.append("validations must be a list.")
        return {"validation_ids": validation_ids}

    for idx, validation in enumerate(validations):
        if not isinstance(validation, dict):
            _add_finding(findings, "invalid_validation_object", "error", f"validations[{idx}]", "Each validation must be an object.", "Use an object with id/type.")
            errors.append(f"Validation {idx} must be an object.")
            continue
        validation_id = str(validation.get("id") or "").strip()
        validation_type = str(validation.get("type") or "").strip()
        if not validation_id:
            _add_finding(findings, "missing_validation_id", "error", f"validations[{idx}].id", "Validation must have an id.", "Add validation.id.")
            errors.append(f"Validation {idx} is missing an id.")
            continue
        if validation_id in validation_ids:
            _add_finding(findings, "duplicate_validation_id", "error", f"validations[{idx}].id", f"Duplicate validation id: {validation_id}.", "Rename the duplicate validation id.")
            errors.append(f"Duplicate validation id: {validation_id}.")
        validation_ids.add(validation_id)
        if not validation_type:
            _add_finding(findings, "missing_validation_type", "error", f"validations[{idx}].type", f"Validation '{validation_id}' is missing type.", "Add validation.type.")
            errors.append(f"Validation '{validation_id}' is missing type.")
            continue
        if validation_type not in KNOWN_VALIDATION_TYPES:
            _add_finding(findings, "unknown_validation_type", "error", f"validations[{idx}].type", f"Validation '{validation_id}' uses unknown type '{validation_type}'.", "Use a validation type from the contract list.")
            errors.append(f"Validation '{validation_id}' uses unknown type '{validation_type}'.")
            continue

        if validation_type == "output_exists":
            output = str(validation.get("output") or "").strip()
            if not output:
                _add_finding(findings, "validation_missing_output", "error", f"validations[{idx}].output", f"Validation '{validation_id}' requires output.", "Add validation.output.")
                errors.append(f"Validation '{validation_id}' requires output.")
            elif output not in step_outputs and output not in external_inputs:
                _add_finding(findings, "validation_references_missing_output", "error", f"validations[{idx}].output", f"Validation '{validation_id}' expects output '{output}', but no step writes it.", "Write the output in a step or declare it as an accepted external input.")
                errors.append(f"Validation '{validation_id}' expects output '{output}', but no step writes it.")

        if validation_type == "pending_action_exists":
            output = str(validation.get("output") or "").strip()
            tool = str(validation.get("tool") or "").strip()
            if not output and not tool:
                _add_finding(findings, "validation_missing_pending_reference", "error", f"validations[{idx}]", f"Validation '{validation_id}' requires tool and/or output.", "Add validation.tool or validation.output.")
                errors.append(f"Validation '{validation_id}' requires tool and/or output.")
            if output and output not in step_outputs:
                _add_finding(findings, "validation_references_missing_pending_action", "error", f"validations[{idx}].output", f"Validation '{validation_id}' expects pending output '{output}', but no step writes it.", "Stage the pending action under that output alias.")
                errors.append(f"Validation '{validation_id}' expects pending output '{output}', but no step writes it.")

        if validation_type == "output_field_equals":
            if not str(validation.get("output") or "").strip() or not str(validation.get("field") or "").strip():
                _add_finding(findings, "validation_field_equals_missing_fields", "error", f"validations[{idx}]", f"Validation '{validation_id}' requires output and field.", "Add output, field, and value.")
                errors.append(f"Validation '{validation_id}' requires output and field.")

    return {"validation_ids": validation_ids}


def _check_completion(
    manifest: dict[str, Any],
    step_analysis: dict[str, Any],
    input_analysis: dict[str, Any],
    findings: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    legacy_manifest: bool,
) -> dict[str, Any]:
    completion = manifest.get("completion")
    if not isinstance(completion, dict):
        _add_finding(findings, "invalid_completion", "error", "completion", "completion must be an object.", "Define a completion object.")
        errors.append("completion must be an object.")
        return {"success_outputs": [], "success_pending_actions": [], "success_executed_actions": [], "required_state": ""}

    success_outputs = _string_list(completion.get("success_outputs"))
    success_pending = _string_list(completion.get("success_pending_actions"))
    success_executed = _string_list(completion.get("success_executed_actions"))
    acceptable_empty = _string_list(completion.get("acceptable_empty_outputs"))
    required_state = str(completion.get("required_state") or "").strip()
    allow_pending = bool(completion.get("allow_pending_approval", False))

    if not any([success_outputs, success_pending, success_executed, acceptable_empty]):
        _add_finding(findings, "completion_empty", "error", "completion", "Completion must define at least one success contract.", "Add success_outputs, success_pending_actions, success_executed_actions, or acceptable_empty_outputs.")
        errors.append("Completion must define at least one success contract.")

    step_outputs = set(step_analysis.get("step_output_aliases", set()))
    for idx, alias in enumerate(success_outputs):
        if alias not in step_outputs and alias not in set(input_analysis.get("declared", set())):
            if alias not in acceptable_empty:
                _add_finding(findings, "completion_output_missing", "error", f"completion.success_outputs[{idx}]", f"Completion expects output '{alias}', but no step writes it.", "Change completion.success_outputs or write the output in a step.")
                errors.append(f"Completion expects output '{alias}', but no step writes it.")

    for idx, alias in enumerate(success_pending):
        if alias not in step_outputs:
            _add_finding(findings, "completion_pending_action_missing", "error", f"completion.success_pending_actions[{idx}]", f"Completion expects pending action alias '{alias}', but no step writes it.", "Stage the pending action under that output alias.")
            errors.append(f"Completion expects pending action alias '{alias}', but no step writes it.")

    for idx, alias in enumerate(success_executed):
        if alias not in step_outputs:
            _add_finding(findings, "completion_executed_action_missing", "error", f"completion.success_executed_actions[{idx}]", f"Completion expects executed action alias '{alias}', but no step writes it.", "Execute or stage the action under that output alias.")
            errors.append(f"Completion expects executed action alias '{alias}', but no step writes it.")

    if required_state == "WAITING_FOR_EXECUTE" and not success_pending:
        _add_finding(findings, "waiting_for_execute_requires_pending_actions", "error", "completion.required_state", "WAITING_FOR_EXECUTE requires success_pending_actions.", "Add success_pending_actions to completion.")
        errors.append("WAITING_FOR_EXECUTE requires success_pending_actions.")

    if allow_pending and not success_pending:
        _add_finding(findings, "allow_pending_approval_requires_success_pending_actions", "error", "completion.allow_pending_approval", "allow_pending_approval=true requires success_pending_actions.", "Add success_pending_actions to completion.")
        errors.append("allow_pending_approval=true requires success_pending_actions.")

    unresolved_pending = [item for item in success_pending if item not in step_outputs]
    if required_state == "COMPLETED" and unresolved_pending:
        _add_finding(findings, "completed_state_rejects_unresolved_pending_action", "error", "completion.required_state", "COMPLETED cannot have unresolved required pending actions.", "Resolve the pending actions or change the required state.")
        errors.append("COMPLETED cannot have unresolved required pending actions.")

    return {
        "success_outputs": success_outputs,
        "success_pending_actions": success_pending,
        "success_executed_actions": success_executed,
        "acceptable_empty_outputs": acceptable_empty,
        "required_state": required_state,
        "allow_pending_approval": allow_pending,
    }


def _check_side_effect_policy(
    manifest: dict[str, Any],
    step_analysis: dict[str, Any],
    completion_analysis: dict[str, Any],
    findings: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    legacy_manifest: bool,
) -> None:
    side_effect_policy = manifest.get("side_effect_policy")
    side_effect_steps = list(step_analysis.get("side_effect_steps", []))
    has_side_effects = bool(side_effect_steps) or bool(manifest.get("side_effect", False))
    requires_approval = bool(completion_analysis.get("success_pending_actions")) or bool(completion_analysis.get("allow_pending_approval"))
    if isinstance(side_effect_policy, dict):
        has_side_effects = bool(side_effect_policy.get("has_side_effects", has_side_effects))
        requires_approval = bool(side_effect_policy.get("requires_approval", requires_approval))
        live_allowed = bool(side_effect_policy.get("live_execution_allowed", False))
        if live_allowed:
            _add_finding(findings, "live_execution_enabled", "critical", "side_effect_policy.live_execution_allowed", "live_execution.enabled=true is blocked in active manifests.", "Disable live execution.")
            errors.append("live_execution.enabled=true is blocked in active manifests.")
        allowed_tools = set(_string_list(side_effect_policy.get("allowed_side_effect_tools")))
    else:
        allowed_tools = set()
        live_allowed = bool((manifest.get("live_execution") or {}).get("enabled", False))

    if has_side_effects and not requires_approval:
        _add_finding(findings, "side_effect_without_pending_completion", "critical" if not legacy_manifest else "error", "completion", "Side-effect workflows must be approval-gated.", "Add allow_pending_approval=true and success_pending_actions.")
        (errors if not legacy_manifest else warnings).append("Side-effect workflows must be approval-gated.")

    if has_side_effects and side_effect_policy is not None and not bool(side_effect_policy.get("has_side_effects", False)):
        _add_finding(findings, "side_effect_policy_mismatch", "error", "side_effect_policy.has_side_effects", "Side-effect tool steps exist but side_effect_policy.has_side_effects=false.", "Set side_effect_policy.has_side_effects=true.")
        errors.append("Side-effect tool steps exist but side_effect_policy.has_side_effects=false.")

    for item in side_effect_steps:
        tool = str(item.get("tool") or "").strip()
        if tool and allowed_tools and tool not in allowed_tools:
            _add_finding(findings, "side_effect_tool_not_allowed", "error", "steps", f"Side-effect tool '{tool}' is not listed in side_effect_policy.allowed_side_effect_tools.", "Add the tool to allowed_side_effect_tools or remove the side-effect step.")
            errors.append(f"Side-effect tool '{tool}' is not listed in side_effect_policy.allowed_side_effect_tools.")

    if completion_analysis.get("required_state") == "WAITING_FOR_EXECUTE" and not completion_analysis.get("success_pending_actions"):
        _add_finding(findings, "waiting_for_execute_without_pending_actions", "error", "completion", "WAITING_FOR_EXECUTE requires pending actions.", "Add success_pending_actions.")
        errors.append("WAITING_FOR_EXECUTE requires pending actions.")


def _check_event_routes(
    manifest: dict[str, Any],
    step_analysis: dict[str, Any],
    input_analysis: dict[str, Any],
    findings: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    *,
    event_routes: dict | None,
    manifest_path: str,
    legacy_manifest: bool,
) -> None:
    trigger = manifest.get("trigger") if isinstance(manifest.get("trigger"), dict) else {}
    trigger_type = str(trigger.get("type") or "").strip().lower()
    if trigger_type != "event":
        return

    routes = _load_routes(event_routes)
    catalog_aliases = _load_manifest_catalog_aliases(manifest_path)
    manifest_id = str(manifest.get("manifest_id") or "").strip()
    matching_routes = [route for route in routes if str(route.get("manifest_id", "")).strip() == manifest_id and bool(route.get("enabled", True))]
    if not matching_routes:
        _add_finding(findings, "event_trigger_without_route", "error", "trigger", f"Event-triggered manifest '{manifest_id}' has no registered route.", "Add a route to config/event_routes.json.")
        errors.append(f"Event-triggered manifest '{manifest_id}' has no registered route.")

    required_inputs = set(input_analysis.get("required", []))
    for route in matching_routes:
        route_manifest_id = str(route.get("manifest_id", "")).strip()
        if route_manifest_id and route_manifest_id not in catalog_aliases:
            _add_finding(findings, "route_missing_manifest", "error", f"config/event_routes.json:{route.get('route_id', '')}", f"Route '{route.get('route_id', '')}' references missing manifest '{route_manifest_id}'.", "Point the route at an existing manifest.")
            errors.append(f"Route '{route.get('route_id', '')}' references missing manifest '{route_manifest_id}'.")
        input_map = route.get("input_map", {})
        if not isinstance(input_map, dict):
            _add_finding(findings, "route_input_map_missing", "error", f"config/event_routes.json:{route.get('route_id', '')}", f"Route '{route.get('route_id', '')}' has no input_map.", "Add input_map entries for required inputs.")
            errors.append(f"Route '{route.get('route_id', '')}' has no input_map.")
            continue
        mapped_inputs = {str(value).split(".", 1)[-1] for value in input_map.values() if isinstance(value, str)}
        missing_inputs = sorted(required_inputs - mapped_inputs - IMPLICIT_EVENT_INPUTS)
        if missing_inputs:
            _add_finding(findings, "route_missing_required_input_mapping", "error", f"config/event_routes.json:{route.get('route_id', '')}", f"Route '{route.get('route_id', '')}' does not map required inputs: {missing_inputs}.", "Map every required manifest input in input_map.")
            errors.append(f"Route '{route.get('route_id', '')}' does not map required inputs: {missing_inputs}.")

    route_pairs: set[tuple[str, str]] = set()
    for route in routes:
        pair = (str(route.get("source", "")).strip(), str(route.get("event_type", "")).strip())
        if pair in route_pairs and bool(route.get("enabled", True)):
            _add_finding(findings, "duplicate_source_event_type_route", "error", "config/event_routes.json", f"Duplicate enabled route source/event_type pair: {pair}.", "Keep each source/event_type pair unique.")
            errors.append(f"Duplicate enabled route source/event_type pair: {pair}.")
        route_pairs.add(pair)


def _load_manifest_catalog_aliases(manifest_path: str) -> set[str]:
    aliases: set[str] = set()
    candidates: list[Path] = []
    if manifest_path:
        path = Path(manifest_path)
        if path.is_file():
            candidates.append(path)
            parent = path.parent
            candidates.extend(sorted(parent.glob("*.manifest.json")))
            config_manifests = parent.parent / "config" / "manifests"
            if config_manifests.is_dir():
                candidates.extend(sorted(config_manifests.glob("*.json")))
        elif path.is_dir():
            candidates.extend(sorted(path.glob("*.manifest.json")))
    else:
        for base in (Path("manifests"), Path("config") / "manifests"):
            if base.is_dir():
                candidates.extend(sorted(base.glob("*.manifest.json")))
                candidates.extend(sorted(base.glob("*.json")))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(raw, dict):
            for key in ("manifest_id", "id"):
                value = str(raw.get(key) or "").strip()
                if value:
                    aliases.add(value)
    return aliases


def _check_tool_registry(
    manifest: dict[str, Any],
    step_analysis: dict[str, Any],
    findings: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    *,
    tool_registry: dict | None,
    manifest_path: str,
) -> None:
    registry = tool_registry or build_tool_registry(include_external=True, config_path="config/enabled_toolpacks.json")
    steps = manifest.get("steps") or []
    completion = manifest.get("completion") or {}
    side_effect_policy = manifest.get("side_effect_policy") or {}
    allow_pending = bool(completion.get("allow_pending_approval", False))
    has_pending = bool(completion.get("success_pending_actions"))

    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        command = str(step.get("command") or "").strip()
        if not command:
            continue
        try:
            parsed = parse_command(command)
        except CommandParseError as exc:
            _add_finding(findings, "command_parse_error", "error", f"steps[{idx}].command", str(exc), "Fix the command syntax.")
            errors.append(str(exc))
            continue

        if parsed.kind != "tool":
            continue
        if parsed.namespace is None:
            continue
        key = f"{parsed.namespace}/{parsed.action}"
        spec = registry.get(key)
        if spec is None:
            _add_finding(findings, "unknown_tool", "error", f"steps[{idx}].command", f"Tool command '{key}' is not registered.", "Register the tool or change the command.")
            errors.append(f"Tool command '{key}' is not registered.")
            continue
        if bool(spec.get("side_effect", False)):
            requires_approval = bool(spec.get("requires_approval", False))
            if not requires_approval:
                _add_finding(findings, "side_effect_tool_requires_approval", "critical", f"steps[{idx}].command", f"Side-effect tool '{key}' must require approval.", "Mark the tool as requires_approval and stage it through a pending action.")
                errors.append(f"Side-effect tool '{key}' must require approval.")
            if not has_pending and not allow_pending:
                _add_finding(findings, "side_effect_tool_requires_pending_completion", "critical", "completion", f"Side-effect tool '{key}' is used but completion does not expect a pending action.", "Add success_pending_actions and allow_pending_approval.")
                errors.append(f"Side-effect tool '{key}' is used but completion does not expect a pending action.")
        if spec.get("source") == "external_toolpack":
            if not bool(spec.get("governance_required", True)):
                _add_finding(findings, "external_tool_governance_missing", "error", f"steps[{idx}].command", f"External tool '{key}' must be governed.", "Enable toolpack governance for the external tool.")
                errors.append(f"External tool '{key}' must be governed.")


def _apply_status_policies(
    manifest: dict[str, Any],
    step_analysis: dict[str, Any],
    completion_analysis: dict[str, Any],
    findings: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    legacy_manifest: bool,
) -> None:
    live_execution = manifest.get("live_execution") if isinstance(manifest.get("live_execution"), dict) else {}
    if bool(live_execution.get("enabled", False)):
        _add_finding(findings, "live_execution_enabled", "critical", "live_execution.enabled", "Active manifests must not enable live execution.", "Disable live_execution.enabled.")
        errors.append("Active manifests must not enable live execution.")

    if completion_analysis.get("required_state") == "WAITING_FOR_EXECUTE" and not completion_analysis.get("success_pending_actions"):
        _add_finding(findings, "waiting_for_execute_requires_pending_actions", "error", "completion.required_state", "WAITING_FOR_EXECUTE requires success_pending_actions.", "Add success_pending_actions.")
        errors.append("WAITING_FOR_EXECUTE requires success_pending_actions.")

    if completion_analysis.get("success_pending_actions") and not bool(completion_analysis.get("allow_pending_approval", False)):
        _add_finding(findings, "pending_actions_without_allow_pending", "error", "completion.allow_pending_approval", "success_pending_actions requires allow_pending_approval=true.", "Set allow_pending_approval=true.")
        errors.append("success_pending_actions requires allow_pending_approval=true.")


def _check_active_fixture_constraints(
    manifest: dict[str, Any],
    manifest_path: str,
    findings: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
) -> None:
    manifest_id = str(manifest.get("manifest_id") or "").strip()
    name = Path(manifest_path).name.lower() if manifest_path else ""
    if manifest_id.startswith("live.") or name.startswith("live_"):
        _add_finding(findings, "live_manifest_not_active", "critical", "manifest", "Live fixture manifests are not part of the active strict catalog.", "Exclude live_* manifests from active catalog checks.")
        errors.append("Live fixture manifests are not part of the active strict catalog.")


def _parse_step_command(
    command: str,
    idx: int,
    findings: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
) -> tuple[str, str]:
    try:
        parsed = parse_command(command)
        return parsed.kind, str(parsed.output_alias or "")
    except CommandParseError as exc:
        raw = command.strip()
        if raw.startswith("[t:") or raw.startswith("[q:"):
            header = raw[1 : raw.find("]")] if "]" in raw else raw[1:]
            kind = "llm" if raw.startswith("[q:") else "tool"
            if "->" not in header:
                _add_finding(findings, "missing_output_alias", "error", f"steps[{idx}].command", f"Step command '{command}' must write an output alias.", "Use [t:... -> alias] or [q:... -> alias].")
                errors.append(f"Step command '{command}' must write an output alias.")
                return kind, ""
        _add_finding(findings, "invalid_step_command", "error", f"steps[{idx}].command", str(exc), "Fix the command syntax.")
        errors.append(str(exc))
        return "unknown", ""


def _normalize_inputs(inputs: Any) -> dict[str, list[str]]:
    if isinstance(inputs, dict):
        required = _string_list(inputs.get("required"))
        optional = _string_list(inputs.get("optional"))
        audit_only = _string_list(inputs.get("audit_only"))
        return {"required": required, "optional": optional, "audit_only": audit_only}
    if isinstance(inputs, list):
        return {"required": _string_list(inputs), "optional": [], "audit_only": []}
    return {"required": [], "optional": [], "audit_only": []}


def _normalize_steps(steps: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(steps, list):
        return normalized
    for step in steps:
        if not isinstance(step, dict):
            continue
        copied = copy.deepcopy(step)
        if "id" not in copied and isinstance(copied.get("step_id"), str):
            copied["id"] = copied["step_id"]
        if "kind" not in copied and isinstance(copied.get("command"), str):
            try:
                copied["kind"] = parse_command(copied["command"]).kind
            except Exception:
                copied["kind"] = ""
        normalized.append(copied)
    return normalized


def _normalize_completion(completion: Any) -> dict[str, Any]:
    if not isinstance(completion, dict):
        return {}
    copied = copy.deepcopy(completion)
    alias_map = {
        "required_outputs": "success_outputs",
        "required_pending_actions": "success_pending_actions",
        "required_executed_actions": "success_executed_actions",
    }
    for legacy, canonical in alias_map.items():
        if legacy in copied and canonical not in copied:
            copied[canonical] = copied[legacy]
    if "required_state" not in copied and isinstance(copied.get("state"), str):
        copied["required_state"] = copied["state"]
    return copied


def _normalize_side_effect_policy(manifest: dict[str, Any]) -> dict[str, Any]:
    policy = manifest.get("side_effect_policy")
    if isinstance(policy, dict):
        copied = copy.deepcopy(policy)
    else:
        copied = {}
    copied.setdefault("has_side_effects", bool(manifest.get("side_effect", False)))
    copied.setdefault("requires_approval", bool(copied.get("has_side_effects", False)))
    copied.setdefault("live_execution_allowed", bool((manifest.get("live_execution") or {}).get("enabled", False)))
    copied.setdefault("allowed_side_effect_tools", [])
    return copied


def _collect_input_refs(
    manifest: dict[str, Any],
    step_analysis: dict[str, Any],
) -> set[str]:
    refs: set[str] = set()
    for step in manifest.get("steps") or []:
        if not isinstance(step, dict):
            continue
        command = str(step.get("command") or "")
        refs.update(_extract_input_refs(command))
        when = step.get("when")
        if isinstance(when, dict):
            refs.update(_extract_input_refs(json.dumps(when, sort_keys=True)))
    return refs


def _collect_route_inputs(manifest: dict[str, Any], event_routes: dict | None) -> set[str]:
    routes = _load_routes(event_routes)
    manifest_ids = _manifest_aliases(manifest)
    route_inputs: set[str] = set()
    for route in routes:
        if str(route.get("manifest_id", "")).strip() not in manifest_ids:
            continue
        input_map = route.get("input_map", {})
        if not isinstance(input_map, dict):
            continue
        for value in input_map.values():
            if isinstance(value, str) and value.strip():
                route_inputs.add(value.strip().split(".", 1)[-1])
    return route_inputs


def _manifest_aliases(manifest: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for key in ("manifest_id", "id"):
        value = str(manifest.get(key) or "").strip()
        if value:
            aliases.add(value)
    return aliases


def _extract_input_refs(text: str) -> set[str]:
    refs: set[str] = set()
    for token in text.split("$inputs.")[1:]:
        name = ""
        for ch in token:
            if ch.isalnum() or ch in {"_", "-"}:
                name += ch
            else:
                break
        if name:
            refs.add(name)
    return refs


def _looks_like_side_effect_step(step: dict[str, Any], command: str, parsed_kind: str) -> bool:
    side_effect_tools = {
        "wa/send",
        "g/send",
        "sheet/write_rows",
        "customer/prepare_message_action",
        "supplier/prepare_message_action",
        "sheet/prepare_write_rows",
        "gb/book",
        "gb/cancel",
    }
    if parsed_kind != "tool":
        return False
    try:
        parsed = parse_command(command)
        tool = f"{parsed.namespace}/{parsed.action}" if parsed.namespace else ""
        return tool in side_effect_tools or bool(step.get("side_effect", False))
    except Exception:
        return bool(step.get("side_effect", False))


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                result.append(text)
        return result
    return []


def _load_routes(event_routes: dict | None) -> list[dict[str, Any]]:
    if isinstance(event_routes, dict):
        routes = event_routes.get("routes", [])
        return list(routes) if isinstance(routes, list) else []
    path = Path("config/event_routes.json")
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    routes = raw.get("routes", [])
    return list(routes) if isinstance(routes, list) else []


def _has_legacy_manifest_fields(manifest: dict[str, Any]) -> bool:
    return any(key in manifest for key in ("id", "trigger_type", "side_effect")) or isinstance(manifest.get("inputs"), list) or any(isinstance(step, dict) and "step_id" in step for step in (manifest.get("steps") or []))


def _manifest_id_from_path(path: str) -> str:
    if not path:
        return ""
    name = Path(path).name
    return name.replace(".manifest.json", "").replace(".json", "")


def _add_finding(
    findings: list[dict[str, Any]],
    finding_id: str,
    severity: str,
    location: str,
    message: str,
    suggested_fix: str,
) -> None:
    findings.append(
        {
            "id": finding_id,
            "severity": severity,
            "location": location,
            "message": message,
            "suggested_fix": suggested_fix,
        }
    )
