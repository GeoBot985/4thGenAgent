from __future__ import annotations

import json
from typing import Any


def classify_workbench_failure(error: dict | str, step: dict | None = None) -> dict:
    error_dict = error if isinstance(error, dict) else {}
    error_text = _failure_text(error)
    step_dict = step if isinstance(step, dict) else {}
    step_text = " ".join(
        part
        for part in (
            _string(step_dict.get("step_id") or step_dict.get("id")),
            _string(step_dict.get("kind")),
            _string(step_dict.get("command")),
            _string(step_dict.get("action")),
            _string(step_dict.get("output_alias") or step_dict.get("result_ref")),
        )
        if part
    )
    haystack = " ".join(
        part
        for part in (
            error_text,
            json.dumps(error_dict, ensure_ascii=False, sort_keys=True) if error_dict else "",
            step_text,
        )
        if part
    ).lower()

    if any(token in haystack for token in ("fixture data not available", "fixture_missing")):
        return {
            "category": "fixture_missing",
            "title": "Fixture data not available",
            "reason": "Fixture data was not available for this tool or range.",
            "summary": "Fixture data not available for this tool or range.",
            "recommended_action": "Add local fixture data for this range or rerun with live external reads enabled.",
            "raw_error": error,
            "step_id": _string(step_dict.get("step_id") or step_dict.get("id")),
            "tool": _step_tool_name(step_dict),
        }

    if any(token in haystack for token in ("missing required inputs", "required input", "required inputs")):
        return {
            "category": "missing_required_input",
            "title": "Missing required input",
            "reason": "One or more required test inputs were missing.",
            "summary": "One or more required test inputs were missing.",
            "recommended_action": "Provide the missing inputs and rerun the dry-run test.",
            "raw_error": error,
            "step_id": _string(step_dict.get("step_id") or step_dict.get("id")),
            "tool": _step_tool_name(step_dict),
        }

    if any(token in haystack for token in ("manifest validation failed", "manifest not found", "unable to read manifest", "invalid manifest", "manifest load")):
        return {
            "category": "manifest_validation_failure",
            "title": "Manifest validation failed",
            "reason": error_text or "The manifest could not be loaded or validated.",
            "summary": error_text or "The manifest could not be loaded or validated.",
            "recommended_action": "Fix the manifest structure or select a valid manifest and rerun the workbench.",
            "raw_error": error,
            "step_id": _string(step_dict.get("step_id") or step_dict.get("id")),
            "tool": _step_tool_name(step_dict),
        }

    if any(token in haystack for token in ("invalid_grant", "expired or revoked", "expired", "revoked", "unauthorized", "401", "403", "credentials", "token", "oauth")):
        tool_name = _step_tool_name(step_dict)
        if "sheet" in tool_name or "spreadsheet" in haystack or "google" in haystack:
            title = "Google Sheets authentication failed"
            reason = "Google Sheets token expired or revoked."
            summary = "The worker could not read the spreadsheet because the Google token is expired or revoked."
        else:
            title = "External authentication failed"
            reason = "The external authentication token is expired or revoked."
            summary = "The external read failed because the authentication token is expired or revoked."
        return {
            "category": "external_auth_failure",
            "title": title,
            "reason": reason,
            "summary": summary,
            "recommended_action": "Refresh the Google authentication token or rerun using fixture dry-run mode.",
            "raw_error": error,
            "step_id": _string(step_dict.get("step_id") or step_dict.get("id")),
            "tool": tool_name,
        }

    if any(token in haystack for token in ("connection", "timeout", "dns", "network", "service unavailable", "unavailable", "unreachable")):
        return {
            "category": "external_dependency_unavailable",
            "title": "External dependency unavailable",
            "reason": error_text or "An external dependency could not be reached.",
            "summary": error_text or "An external dependency could not be reached.",
            "recommended_action": "Retry later or rerun using fixture dry-run mode.",
            "raw_error": error,
            "step_id": _string(step_dict.get("step_id") or step_dict.get("id")),
            "tool": _step_tool_name(step_dict),
        }

    if any(token in haystack for token in ("validation", "failed validation", "business rule", "rule failed", "reply validation", "data validation")) or _step_state(step_dict).startswith("FAILED_VALIDATION"):
        return {
            "category": "business_validation_failure",
            "title": "Business validation failed",
            "reason": error_text or "A business rule or validation failed.",
            "summary": error_text or "A business rule or validation failed.",
            "recommended_action": "Review the failed validation and adjust the test inputs or business data.",
            "raw_error": error,
            "step_id": _string(step_dict.get("step_id") or step_dict.get("id")),
            "tool": _step_tool_name(step_dict),
        }

    if any(token in haystack for token in ("tool", "step", "execution", "toolfunctionerror", "toolimporterror", "toolresulterror")):
        return {
            "category": "tool_execution_failure",
            "title": "Tool execution failed",
            "reason": error_text or "The tool step failed during execution.",
            "summary": error_text or "The tool step failed during execution.",
            "recommended_action": "Inspect the tool error and rerun the dry-run test.",
            "raw_error": error,
            "step_id": _string(step_dict.get("step_id") or step_dict.get("id")),
            "tool": _step_tool_name(step_dict),
        }

    return {
        "category": "unknown_failure",
        "title": "Unknown failure",
        "reason": error_text or "The workbench could not determine the failure type.",
        "summary": error_text or "The workbench could not determine the failure type.",
        "recommended_action": "Inspect the raw error and step metadata.",
        "raw_error": error,
        "step_id": _string(step_dict.get("step_id") or step_dict.get("id")),
        "tool": _step_tool_name(step_dict),
    }


def build_failure_summary(frame: dict) -> dict:
    if not isinstance(frame, dict):
        frame = {}
    errors = _as_list(frame.get("errors"))
    validations = _as_list(frame.get("validations"))
    state = str(frame.get("state", "") or "")
    if not state.startswith("FAILED"):
        return {
            "ok": True,
            "frame_id": frame.get("frame_id", ""),
            "manifest_id": frame.get("manifest_id", ""),
            "state": state,
            "failed_step_id": "",
            "failure_type": "",
            "failure_message": "",
            "blocking_errors": [],
            "failed_validations": [],
            "pending_action_count": len(_as_list(frame.get("pending_actions"))),
            "executed_action_count": len(_as_list(frame.get("executed_actions"))),
            "safe_to_retry": True,
            "operator_explanation": "",
        }
    failed_validations = [item for item in validations if isinstance(item, dict) and item.get("ok") is False]
    if not failed_validations:
        failed_validations = [
            {
                "validation_id": item.get("validation_id", ""),
                "type": item.get("type", ""),
                "ok": False,
                "message": item.get("message", "") or item.get("error", ""),
                "data": item.get("data", {}),
            }
            for item in errors
            if isinstance(item, dict) and (item.get("type") or item.get("message") or item.get("data"))
        ]
    failed_step = _find_failed_step(frame)
    failure_message = _failure_message(frame, failed_step, errors, failed_validations)
    failure_error = _primary_failure_error(frame, failed_step, errors, failed_validations)
    step_record = _find_failed_step_record(frame, failed_step)
    diagnostics = classify_workbench_failure(failure_error or failure_message or frame, step_record)
    safe_outcome = "Workflow stopped before any side effect was created." if state.startswith("FAILED") else ""
    return {
        "ok": True,
        "frame_id": frame.get("frame_id", ""),
        "manifest_id": frame.get("manifest_id", ""),
        "state": state,
        "failed_step_id": failed_step,
        "failure_type": _failure_type(frame, failed_step, failed_validations),
        "failure_category": diagnostics.get("category", ""),
        "failure_title": diagnostics.get("title", ""),
        "failure_message": failure_message,
        "failure_reason": diagnostics.get("reason", ""),
        "failure_summary": diagnostics.get("summary", ""),
        "recommended_action": diagnostics.get("recommended_action", ""),
        "safe_outcome": safe_outcome,
        "blocking_errors": errors,
        "failed_validations": failed_validations,
        "pending_action_count": len(_as_list(frame.get("pending_actions"))),
        "executed_action_count": len(_as_list(frame.get("executed_actions"))),
        "safe_to_retry": state not in {"FAILED_EXECUTION", "FAILED_VALIDATION", "FAILED_COMPLETION"},
        "operator_explanation": _operator_explanation(state, diagnostics.get("summary", failure_message), diagnostics.get("recommended_action", "")),
    }


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _find_failed_step(frame: dict) -> str:
    for key in ("steps", "manifest_steps"):
        for step in _as_list(frame.get(key)):
            if isinstance(step, dict) and str(step.get("status", "")).upper().startswith("FAILED"):
                return str(step.get("step_id") or step.get("id") or "")
    return str(frame.get("current_step_id", "") or "")


def _failure_type(frame: dict, failed_step: str, failed_validations: list[dict]) -> str:
    if _as_list(frame.get("errors")):
        return "validation_failed" if frame.get("state") == "FAILED_VALIDATION" else "execution_failed"
    if failed_validations:
        return "validation_failed"
    return "failed"


def _failure_message(frame: dict, failed_step: str, errors: list[dict], failed_validations: list[dict]) -> str:
    if errors:
        for error in errors:
            if isinstance(error, dict) and error.get("message"):
                return str(error.get("message"))
            if isinstance(error, dict) and error.get("data"):
                return str(error.get("data"))
    if failed_validations:
        first = failed_validations[0]
        return str(first.get("message") or first.get("validation_id") or "Validation failed.")
    if failed_step:
        return f"Step failed: {failed_step}"
    return ""


def _operator_explanation(state: str, failure_message: str, recommended_action: str = "") -> str:
    if not failure_message and not recommended_action:
        return ""
    if state == "FAILED_VALIDATION":
        return f"The runtime blocked the reply because {failure_message.lower()}".strip()
    if state == "FAILED_EXECUTION":
        if recommended_action:
            return f"{failure_message} {recommended_action}".strip()
        return f"The runtime stopped during execution because {failure_message.lower()}".strip()
    return f"{failure_message} {recommended_action}".strip()


def _primary_failure_error(frame: dict, failed_step: str, errors: list[dict], failed_validations: list[dict]) -> dict | str:
    for error in errors:
        if isinstance(error, dict):
            if failed_step and _string(error.get("step_id")) == failed_step:
                return error
    if errors:
        return errors[0]
    if failed_validations:
        return failed_validations[0]
    return ""


def _find_failed_step_record(frame: dict, failed_step: str) -> dict:
    if not failed_step:
        return {}
    for key in ("steps", "manifest_steps"):
        for step in _as_list(frame.get(key)):
            if isinstance(step, dict) and _string(step.get("step_id") or step.get("id")) == failed_step:
                return dict(step)
    return {}


def _failure_text(error: dict | str) -> str:
    if isinstance(error, dict):
        for key in ("message", "error", "summary", "reason", "title"):
            value = error.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        try:
            return json.dumps(error, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(error)
    if error is None:
        return ""
    return str(error)


def _step_state(step: dict) -> str:
    if not isinstance(step, dict):
        return ""
    return _string(step.get("status"))


def _step_tool_name(step: dict) -> str:
    if not isinstance(step, dict):
        return ""
    for key in ("tool", "namespace", "action", "kind"):
        value = step.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _string(step.get("step_id") or step.get("id"))


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)
