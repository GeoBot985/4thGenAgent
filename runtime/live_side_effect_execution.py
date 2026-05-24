from __future__ import annotations

"""
Spec 155 — Live Side-Effect Approval Execution Model v1.

Only sheet/write_rows is executable in v1. Gmail send, calendar mutations,
and RPA remain blocked regardless of profile configuration.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .live_execution_ledger import (
    LEDGER_STATUS_BLOCKED,
    LEDGER_STATUS_EXECUTED,
    LEDGER_STATUS_EXECUTING,
    LEDGER_STATUS_FAILED,
    append_ledger_entry,
    build_ledger_entry,
    is_idempotency_key_in_ledger,
)
from .live_execution_reports import (
    append_live_audit_event,
    build_live_execution_report,
    write_live_execution_report as _write_base_report,
)

# ---------------------------------------------------------------------------
# v1 policy constants
# ---------------------------------------------------------------------------

V1_EXECUTABLE_TOOLS: frozenset[str] = frozenset({"sheet/write_rows"})

V1_BLOCKED_TOOLS: frozenset[str] = frozenset({
    "gmail/send",
    "gmail/draft_send",
    "calendar/create",
    "calendar/update",
    "calendar/delete",
    "rpa/run",
    "rpa/click",
    "rpa/type",
    "rpa/navigate",
})

CONTROLLED_LIVE_WRITE_PROFILE_ID = "controlled_live_write"

# Error codes
PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"
TOOL_NOT_V1_EXECUTABLE = "TOOL_NOT_V1_EXECUTABLE"
TOOL_EXPLICITLY_BLOCKED = "TOOL_EXPLICITLY_BLOCKED"
WORKER_IDENTITY_MISSING = "WORKER_IDENTITY_MISSING"
APPROVAL_IDENTITY_MISSING = "APPROVAL_IDENTITY_MISSING"
APPROVAL_TIMESTAMP_MISSING = "APPROVAL_TIMESTAMP_MISSING"
TARGET_REF_MISSING = "TARGET_REF_MISSING"
PAYLOAD_HASH_MISSING = "PAYLOAD_HASH_MISSING"
ROLLBACK_PLAN_MISSING = "ROLLBACK_PLAN_MISSING"
LEDGER_DUPLICATE = "LEDGER_DUPLICATE"
CONFIRMATION_PHRASE_WRONG = "CONFIRMATION_PHRASE_WRONG"
PROFILE_NOT_LIVE_WRITE = "PROFILE_NOT_LIVE_WRITE"
PROFILE_SIDE_EFFECTS_DISABLED = "PROFILE_SIDE_EFFECTS_DISABLED"


# ---------------------------------------------------------------------------
# Confirmation phrase
# ---------------------------------------------------------------------------

def live_side_effect_confirmation_phrase(frame_id: str, action_id: str, tool: str = "sheet/write_rows") -> str:
    return f"EXECUTE LIVE {tool} {frame_id} {action_id}"


# ---------------------------------------------------------------------------
# Extended pending action helpers
# ---------------------------------------------------------------------------

EXTENDED_PENDING_ACTION_FIELDS: dict[str, Any] = {
    "target_ref": "",
    "prepared_payload_hash": "",
    "rollback_plan": {},
    "worker_identity": "",
}


def normalize_extended_pending_action(action: dict[str, Any]) -> dict[str, Any]:
    result = dict(action)
    for key, default in EXTENDED_PENDING_ACTION_FIELDS.items():
        result.setdefault(key, default)
    return result


# ---------------------------------------------------------------------------
# Core: build_live_side_effect_preflight (15+ checks)
# ---------------------------------------------------------------------------

def build_live_side_effect_preflight(
    *,
    pending_action: dict[str, Any],
    profile_name: str,
    profile_data: dict[str, Any] | None = None,
    typed_confirmation: str | None = None,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """
    Run the full 15-check Spec 155 preflight gate.

    Returns a dict with:
      ok             — True only when all checks pass
      blocked        — True when execution must not proceed
      error_code     — first failing error code (or None)
      checks         — list of individual check results
      failed_checks  — list of failed check dicts
      confirmation_phrase — expected phrase for this action
    """
    action = normalize_extended_pending_action(pending_action)
    checks: list[dict[str, Any]] = []
    error_code: str | None = None

    frame_id = str(action.get("frame_id") or "")
    action_id = str(action.get("action_id") or "")
    tool = str(action.get("tool") or "").strip()

    expected_confirmation = live_side_effect_confirmation_phrase(frame_id, action_id, tool or "sheet/write_rows")

    def add(name: str, passed: bool, code: str, message: str = "") -> None:
        nonlocal error_code
        checks.append({
            "name": name,
            "ok": passed,
            "error_code": code if not passed else None,
            "message": message,
        })
        if not passed and error_code is None:
            error_code = code

    # 1. Profile must be controlled_live_write
    profile_id_ok = profile_name == CONTROLLED_LIVE_WRITE_PROFILE_ID
    add("profile_is_controlled_live_write", profile_id_ok, PROFILE_NOT_LIVE_WRITE,
        "" if profile_id_ok else f"Profile must be '{CONTROLLED_LIVE_WRITE_PROFILE_ID}' (got: {profile_name!r}).")

    # 2. Profile must allow live side effects
    pd = dict(profile_data or {})
    side_effects_ok = bool(pd.get("allow_live_side_effects", False))
    add("profile_allows_live_side_effects", side_effects_ok, PROFILE_SIDE_EFFECTS_DISABLED,
        "" if side_effects_ok else "Profile does not allow live side effects.")

    # 3. Tool must be in V1 executable set
    tool_v1_ok = tool in V1_EXECUTABLE_TOOLS
    add("tool_is_v1_executable", tool_v1_ok, TOOL_NOT_V1_EXECUTABLE,
        "" if tool_v1_ok else f"Tool '{tool}' is not executable in v1 (allowed: {sorted(V1_EXECUTABLE_TOOLS)}).")

    # 4. Tool must not be in blocked list
    tool_not_blocked = tool not in V1_BLOCKED_TOOLS
    add("tool_not_blocked", tool_not_blocked, TOOL_EXPLICITLY_BLOCKED,
        "" if tool_not_blocked else f"Tool '{tool}' is explicitly blocked in v1.")

    # 5. Pending action must be APPROVED
    action_status = str(action.get("status") or "").upper()
    action_approved = action_status == "APPROVED"
    add("pending_action_approved", action_approved, "PENDING_ACTION_NOT_APPROVED",
        "" if action_approved else f"Pending action must be APPROVED (current: {action_status}).")

    # 6. Approval identity (approved_by) must be present
    approved_by = str(action.get("approved_by") or "").strip()
    add("approval_identity_present", bool(approved_by), APPROVAL_IDENTITY_MISSING,
        "" if approved_by else "approved_by is required for live side-effect execution.")

    # 7. Approval timestamp (approved_at) must be present
    approved_at = str(action.get("approved_at") or "").strip()
    add("approval_timestamp_present", bool(approved_at), APPROVAL_TIMESTAMP_MISSING,
        "" if approved_at else "approved_at is required for live side-effect execution.")

    # 8. Worker identity must be present
    worker_identity = str(action.get("worker_identity") or "").strip()
    add("worker_identity_present", bool(worker_identity), WORKER_IDENTITY_MISSING,
        "" if worker_identity else "worker_identity is required for live side-effect execution.")

    # 9. Idempotency key must be present
    idempotency_key = str(action.get("idempotency_key") or "").strip()
    add("idempotency_key_present", bool(idempotency_key), "IDEMPOTENCY_KEY_REQUIRED",
        "" if idempotency_key else "idempotency_key is required for live side-effect execution.")

    # 10. Idempotency key must not already be in ledger
    if idempotency_key:
        already_executed = is_idempotency_key_in_ledger(idempotency_key, runtime_data_dir=runtime_data_dir)
        add("idempotency_key_not_in_ledger", not already_executed, LEDGER_DUPLICATE,
            "" if not already_executed else f"Idempotency key '{idempotency_key}' already executed (in ledger).")

    # 11. Prepared payload hash must be present
    payload_hash = str(action.get("prepared_payload_hash") or "").strip()
    add("prepared_payload_hash_present", bool(payload_hash), PAYLOAD_HASH_MISSING,
        "" if payload_hash else "prepared_payload_hash is required.")

    # 12. Target ref must be present
    target_ref = str(action.get("target_ref") or "").strip()
    add("target_ref_present", bool(target_ref), TARGET_REF_MISSING,
        "" if target_ref else "target_ref is required (e.g. spreadsheet ID).")

    # 13. Business ref must be present
    business_ref = str(action.get("business_ref") or "").strip()
    add("business_ref_present", bool(business_ref), "BUSINESS_REF_MISSING",
        "" if business_ref else "business_ref is required for live side-effect execution.")

    # 14. Rollback plan must be present (non-empty dict)
    rollback_plan = action.get("rollback_plan")
    rollback_ok = isinstance(rollback_plan, dict) and bool(rollback_plan)
    add("rollback_plan_present", rollback_ok, ROLLBACK_PLAN_MISSING,
        "" if rollback_ok else "rollback_plan must be a non-empty dict (display-only metadata).")

    # 15. Typed confirmation must match (when supplied)
    if typed_confirmation is not None:
        confirmation_ok = str(typed_confirmation).strip() == expected_confirmation
        add("typed_confirmation_matches", confirmation_ok, CONFIRMATION_PHRASE_WRONG,
            "" if confirmation_ok else (
                f"Typed confirmation wrong. Expected: {expected_confirmation!r}, "
                f"received: {typed_confirmation!r}."
            ))

    failed = [c for c in checks if not c["ok"]]
    ok = len(failed) == 0

    return {
        "ok": ok,
        "blocked": not ok,
        "error_code": error_code,
        "checks": checks,
        "failed_checks": failed,
        "tool": tool,
        "profile": profile_name,
        "frame_id": frame_id,
        "action_id": action_id,
        "idempotency_key": idempotency_key,
        "confirmation_phrase": expected_confirmation,
    }


# ---------------------------------------------------------------------------
# Core: execute_approved_live_side_effect
# ---------------------------------------------------------------------------

def execute_approved_live_side_effect(
    *,
    pending_action: dict[str, Any],
    profile_name: str,
    profile_data: dict[str, Any] | None = None,
    typed_confirmation: str,
    runtime_data_dir: str | Path = "runtime_data",
    dry_run_fallback: bool = False,
) -> dict[str, Any]:
    """
    Execute an approved live side effect after full preflight.

    In v1, only sheet/write_rows is supported. No actual Google API call is
    made here — the caller provides the execution result. This function
    enforces the approval gate, writes the ledger, and records evidence.

    When dry_run_fallback=True, simulates the execution without making any
    external API call. Used for release verification and testing.
    """
    action = normalize_extended_pending_action(pending_action)
    frame_id = str(action.get("frame_id") or "")
    action_id = str(action.get("action_id") or "")
    tool = str(action.get("tool") or "").strip()
    idempotency_key = str(action.get("idempotency_key") or "").strip()
    business_ref = str(action.get("business_ref") or "").strip()
    target_ref = str(action.get("target_ref") or "").strip()
    payload_hash = str(action.get("prepared_payload_hash") or "").strip()
    approved_by = str(action.get("approved_by") or "").strip()
    worker_identity = str(action.get("worker_identity") or "").strip()
    rollback_plan = action.get("rollback_plan") or {}

    # Run preflight with confirmation
    preflight = build_live_side_effect_preflight(
        pending_action=action,
        profile_name=profile_name,
        profile_data=profile_data,
        typed_confirmation=typed_confirmation,
        runtime_data_dir=runtime_data_dir,
    )

    if not preflight["ok"]:
        blocked_entry = build_ledger_entry(
            frame_id=frame_id,
            action_id=action_id,
            tool=tool,
            idempotency_key=idempotency_key,
            business_ref=business_ref,
            target_ref=target_ref,
            prepared_payload_hash=payload_hash,
            approved_by=approved_by,
            worker_identity=worker_identity,
            status=LEDGER_STATUS_BLOCKED,
            profile=profile_name,
            rollback_plan=rollback_plan,
            error=preflight.get("error_code") or "PREFLIGHT_BLOCKED",
        )
        append_ledger_entry(blocked_entry, runtime_data_dir=runtime_data_dir)
        return {
            "ok": False,
            "blocked": True,
            "executed": False,
            "error_code": preflight.get("error_code") or PREFLIGHT_BLOCKED,
            "preflight": preflight,
            "ledger_entry": blocked_entry,
        }

    # Record EXECUTING (in-flight marker)
    executing_entry = build_ledger_entry(
        frame_id=frame_id,
        action_id=action_id,
        tool=tool,
        idempotency_key=idempotency_key,
        business_ref=business_ref,
        target_ref=target_ref,
        prepared_payload_hash=payload_hash,
        approved_by=approved_by,
        worker_identity=worker_identity,
        status=LEDGER_STATUS_EXECUTING,
        profile=profile_name,
        rollback_plan=rollback_plan,
    )
    append_ledger_entry(executing_entry, runtime_data_dir=runtime_data_dir)

    # Execute
    if dry_run_fallback:
        execution_result = {
            "ok": True,
            "type": "dry_run_simulation",
            "tool": tool,
            "rows_written": 0,
            "target_ref": target_ref,
            "note": "dry_run_fallback=True — no external API call made.",
        }
        execution_error = ""
        execution_ok = True
    else:
        try:
            execution_result, execution_error, execution_ok = _call_sheet_write_rows(action)
        except Exception as exc:
            execution_result = {}
            execution_error = str(exc)
            execution_ok = False

    ledger_status = LEDGER_STATUS_EXECUTED if execution_ok else LEDGER_STATUS_FAILED
    final_entry = build_ledger_entry(
        frame_id=frame_id,
        action_id=action_id,
        tool=tool,
        idempotency_key=idempotency_key,
        business_ref=business_ref,
        target_ref=target_ref,
        prepared_payload_hash=payload_hash,
        approved_by=approved_by,
        worker_identity=worker_identity,
        status=ledger_status,
        profile=profile_name,
        rollback_plan=rollback_plan,
        execution_result=execution_result,
        error=execution_error,
    )
    append_ledger_entry(final_entry, runtime_data_dir=runtime_data_dir)

    # Build and write audit event
    audit_event = build_live_execution_audit_event(
        frame_id=frame_id,
        action_id=action_id,
        tool=tool,
        idempotency_key=idempotency_key,
        approved_by=approved_by,
        worker_identity=worker_identity,
        executed=execution_ok,
        error=execution_error,
    )
    try:
        append_live_audit_event(audit_event, runtime_data_dir=runtime_data_dir)
    except Exception:
        pass

    # Build and write execution report
    report = build_live_execution_report(
        frame_id=frame_id,
        manifest_id=str(action.get("manifest_id") or ""),
        profile=profile_name,
        action_id=action_id,
        tool=tool,
        business_ref=business_ref,
        idempotency_key=idempotency_key,
        approval_record={"approved_by": approved_by, "approved_at": str(action.get("approved_at") or ""), "approval_reason": str(action.get("approval_reason") or "")},
        guardrail_result={"guardrail": "sheet_write_rows_guardrail", "ok": execution_ok, "checks": []},
        execution_result=execution_result if execution_ok else None,
        blocked=not execution_ok,
        error_code=execution_error if not execution_ok else "",
        preflight=preflight,
    )
    report_paths: dict[str, Any] = {}
    try:
        report_paths = write_live_execution_report(report, runtime_data_dir=runtime_data_dir)
    except Exception:
        pass

    return {
        "ok": execution_ok,
        "blocked": False,
        "executed": execution_ok,
        "error_code": execution_error if not execution_ok else "",
        "preflight": preflight,
        "execution_result": execution_result,
        "ledger_entry": final_entry,
        "audit_event": audit_event,
        "report_paths": report_paths,
        "rollback_plan": rollback_plan,
    }


# ---------------------------------------------------------------------------
# Core: verify_live_side_effect_result
# ---------------------------------------------------------------------------

def verify_live_side_effect_result(
    *,
    execution_result: dict[str, Any],
    pending_action: dict[str, Any],
) -> dict[str, Any]:
    """
    Post-execution verification for sheet/write_rows.

    Checks that the execution result is consistent with the action plan.
    Does NOT make any external API call.
    """
    action = normalize_extended_pending_action(pending_action)
    tool = str(action.get("tool") or "").strip()
    target_ref = str(action.get("target_ref") or "").strip()
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, message: str = "") -> None:
        checks.append({"name": name, "ok": passed, "message": message})

    # 1. Execution must have ok=True
    exec_ok = bool(execution_result.get("ok", False))
    check("execution_ok", exec_ok, "" if exec_ok else "execution_result.ok is False.")

    # 2. Tool matches
    result_tool = str(execution_result.get("tool") or "").strip()
    tool_match = (not result_tool) or (result_tool == tool)
    check("tool_matches", tool_match, "" if tool_match else f"tool mismatch: action={tool}, result={result_tool}.")

    # 3. Target ref matches (if present in result)
    result_target = str(execution_result.get("target_ref") or execution_result.get("spreadsheet_id") or "").strip()
    target_match = (not result_target) or (result_target == target_ref)
    check("target_ref_matches", target_match,
          "" if target_match else f"target_ref mismatch: action={target_ref}, result={result_target}.")

    # 4. No side effects outside sheet writes
    is_side_effect_only = str(execution_result.get("type") or "").lower() in (
        "sheet_write", "sheet_write_rows", "dry_run_simulation", ""
    )
    check("no_unexpected_side_effects", is_side_effect_only,
          "" if is_side_effect_only else f"unexpected execution type: {execution_result.get('type')}.")

    # 5. Rows written is non-negative integer (if present)
    rows_written = execution_result.get("rows_written")
    if rows_written is not None:
        rows_ok = isinstance(rows_written, int) and rows_written >= 0
        check("rows_written_non_negative", rows_ok,
              "" if rows_ok else f"rows_written must be >= 0 (got: {rows_written}).")

    failed = [c for c in checks if not c["ok"]]
    ok = len(failed) == 0

    return {
        "ok": ok,
        "checks": checks,
        "failed_checks": failed,
        "tool": tool,
        "verified_at": _utc_now(),
    }


# ---------------------------------------------------------------------------
# Core: build_live_execution_audit_event
# ---------------------------------------------------------------------------

def build_live_execution_audit_event(
    *,
    frame_id: str,
    action_id: str,
    tool: str,
    idempotency_key: str,
    approved_by: str,
    worker_identity: str,
    executed: bool,
    error: str = "",
) -> dict[str, Any]:
    event_type = "LIVE_SIDE_EFFECT_EXECUTED" if executed else "LIVE_SIDE_EFFECT_FAILED"
    return {
        "event_type": event_type,
        "recorded_at": _utc_now(),
        "frame_id": frame_id,
        "action_id": action_id,
        "tool": tool,
        "idempotency_key": idempotency_key,
        "approved_by": approved_by,
        "worker_identity": worker_identity,
        "executed": executed,
        "error": error,
        "spec": "155",
    }


# ---------------------------------------------------------------------------
# Core: write_live_execution_report (wrapper)
# ---------------------------------------------------------------------------

def write_live_execution_report(
    report: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    return _write_base_report(report, runtime_data_dir=runtime_data_dir)


# ---------------------------------------------------------------------------
# Core: render_live_execution_markdown
# ---------------------------------------------------------------------------

def render_live_execution_markdown(result: dict[str, Any]) -> str:
    executed = result.get("executed", False)
    blocked = result.get("blocked", not executed)
    status = "EXECUTED" if executed else ("BLOCKED" if blocked else "FAILED")

    preflight = result.get("preflight") or {}
    exec_result = result.get("execution_result") or {}
    rollback = result.get("rollback_plan") or {}
    ledger = result.get("ledger_entry") or {}

    lines = [
        f"# Live Side-Effect Execution — {status}",
        "",
        f"**Tool:** {preflight.get('tool', '') or ledger.get('tool', '')}",
        f"**Frame ID:** {preflight.get('frame_id', '') or ledger.get('frame_id', '')}",
        f"**Action ID:** {preflight.get('action_id', '') or ledger.get('action_id', '')}",
        f"**Profile:** {preflight.get('profile', '') or ledger.get('profile', '')}",
        f"**Idempotency Key:** {preflight.get('idempotency_key', '') or ledger.get('idempotency_key', '')}",
        "",
        "## Preflight Checks",
        "",
    ]
    for c in preflight.get("checks") or []:
        mark = "pass" if c.get("ok") else "FAIL"
        lines.append(f"- [{mark}] {c.get('name', '')}: {c.get('message', '')}")

    lines += ["", "## Execution Result", ""]
    if blocked:
        ec = result.get("error_code") or preflight.get("error_code") or "BLOCKED"
        lines.append(f"**Blocked** — error code: `{ec}`")
    else:
        lines.append(f"- ok: {exec_result.get('ok', False)}")
        lines.append(f"- type: {exec_result.get('type', '')}")
        rows = exec_result.get("rows_written")
        if rows is not None:
            lines.append(f"- rows_written: {rows}")

    if rollback:
        lines += ["", "## Rollback Plan (Display Only)", ""]
        for key, val in rollback.items():
            lines.append(f"- {key}: {val}")

    lines += ["", "---", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal: sheet/write_rows execution stub
# ---------------------------------------------------------------------------

def _call_sheet_write_rows(action: dict[str, Any]) -> tuple[dict[str, Any], str, bool]:
    """
    Attempt to call sheet_write_live_execute from sheet_write_tool.

    Falls back to a structured error if the module or credentials are unavailable.
    """
    try:
        from .sheet_write_tool import sheet_write_live_execute
        result = sheet_write_live_execute(action)
        ok = bool(result.get("ok", False))
        error = str(result.get("error") or "") if not ok else ""
        return result, error, ok
    except ImportError:
        return {}, "sheet_write_tool not available", False
    except Exception as exc:
        return {}, str(exc), False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
