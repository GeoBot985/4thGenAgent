from __future__ import annotations

from typing import Any


def validate_scenario_result(scenario: dict, result: dict) -> dict:
    expected = scenario.get("expected", {}) if isinstance(scenario, dict) else {}
    checks: list[dict[str, Any]] = []

    def add_check(check_id: str, ok: bool, expected_value: Any = "", actual: Any = "", message: str = "", level: str = "required") -> None:
        checks.append({"id": check_id, "level": level, "ok": bool(ok), "expected": expected_value, "actual": actual, "message": message})

    state = str(result.get("state", "")) if isinstance(result, dict) else ""
    snapshot = result.get("snapshot", {}) if isinstance(result, dict) else {}
    approval_pack = result.get("approval_pack", {}) if isinstance(result, dict) else {}
    failure_summary = result.get("failure_summary", {}) if isinstance(result, dict) else {}
    report_result = result.get("report_result", {}) if isinstance(result, dict) else {}
    summary = result.get("summary", {}) if isinstance(result, dict) else {}

    if "final_state" in expected:
        add_check("final_state", state == expected["final_state"], expected["final_state"], state)
    if "state_prefix" in expected:
        add_check("state_prefix", state.startswith(str(expected["state_prefix"])), expected["state_prefix"], state)

    outputs = snapshot.get("outputs", {}) if isinstance(snapshot, dict) else {}
    for alias in expected.get("required_outputs", []) or []:
        actual = alias in outputs or alias in (summary.get("output_keys", []) if isinstance(summary, dict) else [])
        add_check(f"required_output:{alias}", actual, True, actual)
    for alias in expected.get("forbidden_outputs", []) or []:
        actual = alias in outputs
        add_check(f"forbidden_output:{alias}", not actual, False, actual)

    for path, expected_value in (expected.get("expected_output_values", {}) or {}).items():
        actual = _resolve_path(result, path)
        if actual is None:
            actual = _resolve_path(snapshot, f"outputs.{path}")
        add_check(f"expected_output_value:{path}", actual == expected_value, expected_value, actual)

    pending_actual = len(result.get("snapshot", {}).get("pending_actions", []) or [])
    executed_actual = len(result.get("snapshot", {}).get("executed_actions", []) or []) or sum(1 for item in (result.get("snapshot", {}).get("pending_actions", []) or []) if isinstance(item, dict) and str(item.get("status", "")).upper() == "EXECUTED")
    add_check("pending_action_count", pending_actual == expected.get("pending_action_count", pending_actual), expected.get("pending_action_count", pending_actual), pending_actual)
    add_check("executed_action_count", executed_actual == expected.get("executed_action_count", executed_actual), expected.get("executed_action_count", executed_actual), executed_actual)

    if "pending_action_status" in expected:
        actual = any((item.get("status") == expected["pending_action_status"]) for item in (approval_pack.get("approval_packs", []) or []) if isinstance(item, dict))
        add_check("pending_action_status", actual, expected["pending_action_status"], [item.get("status") for item in (approval_pack.get("approval_packs", []) or []) if isinstance(item, dict)])
    for tool in expected.get("required_pending_tools", []) or []:
        actual = any(tool in str(item.get("tool", "")) for item in (approval_pack.get("approval_packs", []) or []) if isinstance(item, dict))
        add_check(f"required_pending_tool:{tool}", actual, tool, [item.get("tool") for item in (approval_pack.get("approval_packs", []) or []) if isinstance(item, dict)])
    for action in expected.get("required_llm_actions", []) or []:
        actual = any(str(call.get("action", "")) == action for call in (result.get("snapshot", {}).get("llm_calls", []) or []) if isinstance(call, dict))
        add_check(f"required_llm_action:{action}", actual, action, [call.get("action") for call in (result.get("snapshot", {}).get("llm_calls", []) or []) if isinstance(call, dict)])
    for tool in expected.get("required_executed_tools", []) or []:
        actual = any(str(item.get("tool", "")) == tool for item in (result.get("snapshot", {}).get("executed_actions", []) or []) if isinstance(item, dict))
        add_check(f"required_executed_tool:{tool}", actual, tool, [item.get("tool") for item in (result.get("snapshot", {}).get("executed_actions", []) or []) if isinstance(item, dict)])

    must_have_failure = bool(expected.get("must_have_failure", False))
    failure_message = str(failure_summary.get("failure_message", "")) if isinstance(failure_summary, dict) else ""
    state_failed = state.startswith("FAILED")
    if must_have_failure:
        add_check("must_have_failure", bool(state_failed and failure_message), must_have_failure, {"state": state, "failure_message": failure_message})

    must_have_approval_pack = bool(expected.get("must_have_approval_pack", False))
    approval_ok = bool(approval_pack.get("ok", False)) and int(approval_pack.get("pending_action_count", 0) or 0) > 0
    if must_have_approval_pack:
        add_check("must_have_approval_pack", approval_ok, must_have_approval_pack, approval_ok)

    must_have_report = bool(expected.get("must_have_report", False))
    report_ok = bool(report_result.get("ok", False)) and bool(report_result.get("markdown_path")) and bool(report_result.get("html_path"))
    if must_have_report:
        add_check("must_have_report", report_ok, must_have_report, report_ok)

    must_have_evidence_bundle = bool(expected.get("must_have_evidence_bundle", False))
    evidence_ok = bool(report_result.get("evidence_bundle_path")) if isinstance(report_result, dict) else False
    if must_have_evidence_bundle:
        add_check("must_have_evidence_bundle", evidence_ok, must_have_evidence_bundle, evidence_ok)

    if expected.get("dataset_validation_ok") is not None:
        actual = bool(result.get("dataset_validation", {}).get("ok", False)) if isinstance(result, dict) else False
        add_check("dataset_validation_ok", actual == bool(expected.get("dataset_validation_ok")), expected.get("dataset_validation_ok"), actual)

    failed_count = sum(1 for item in checks if item["ok"] is False and item["level"] == "required")
    warn_count = sum(1 for item in checks if item["ok"] is False and item["level"] != "required")
    passed_count = sum(1 for item in checks if item["ok"])
    verdict = "PASS"
    if failed_count:
        verdict = "FAIL"
    elif warn_count:
        verdict = "WARN"
    return {
        "verdict": verdict,
        "passed": verdict == "PASS",
        "check_count": len(checks),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "warn_count": warn_count,
        "checks": checks,
    }


def _resolve_path(result: dict, path: str) -> Any:
    current: Any = result
    for part in str(path).split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current
