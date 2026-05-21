from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

LIVE_SIDE_EFFECTS_DISABLED = "LIVE_SIDE_EFFECTS_DISABLED"
LIVE_PROFILE_NOT_ALLOWED = "LIVE_PROFILE_NOT_ALLOWED"
LIVE_TOOL_NOT_ALLOWED = "LIVE_TOOL_NOT_ALLOWED"
LIVE_MANIFEST_NOT_ALLOWED = "LIVE_MANIFEST_NOT_ALLOWED"
PENDING_ACTION_NOT_APPROVED = "PENDING_ACTION_NOT_APPROVED"
IDEMPOTENCY_KEY_REQUIRED = "IDEMPOTENCY_KEY_REQUIRED"
DUPLICATE_SIDE_EFFECT_BLOCKED = "DUPLICATE_SIDE_EFFECT_BLOCKED"
LIVE_GUARDRAIL_FAILED = "LIVE_GUARDRAIL_FAILED"
TYPED_CONFIRMATION_REQUIRED = "TYPED_CONFIRMATION_REQUIRED"
LIVE_EVIDENCE_WRITE_FAILED = "LIVE_EVIDENCE_WRITE_FAILED"

ALL_ERROR_CODES = (
    LIVE_SIDE_EFFECTS_DISABLED,
    LIVE_PROFILE_NOT_ALLOWED,
    LIVE_TOOL_NOT_ALLOWED,
    LIVE_MANIFEST_NOT_ALLOWED,
    PENDING_ACTION_NOT_APPROVED,
    IDEMPOTENCY_KEY_REQUIRED,
    DUPLICATE_SIDE_EFFECT_BLOCKED,
    LIVE_GUARDRAIL_FAILED,
    TYPED_CONFIRMATION_REQUIRED,
    LIVE_EVIDENCE_WRITE_FAILED,
)

# ---------------------------------------------------------------------------
# Policy defaults
# ---------------------------------------------------------------------------

LIVE_SIDE_EFFECT_EXECUTION_POLICY: dict[str, Any] = {
    "live_side_effect_execution": {
        "enabled": False,
        "allowed_profiles": ["live"],
        "require_operator_approval": True,
        "require_typed_confirmation": True,
        "require_idempotency_key": True,
        "require_guardrail": True,
        "require_manifest_allowlist": True,
        "require_tool_allowlist": True,
        "default_dry_run": True,
    }
}

# Profiles that will never allow live side effects regardless of configuration
_PROFILES_BLOCKED_FROM_LIVE_SIDE_EFFECTS = frozenset({"demo", "dev", "test", "release", "pilot"})


# ---------------------------------------------------------------------------
# Policy normalisation / access
# ---------------------------------------------------------------------------

def normalize_live_side_effect_policy(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(LIVE_SIDE_EFFECT_EXECUTION_POLICY["live_side_effect_execution"])
    if raw is None:
        return base
    policy_section = raw.get("live_side_effect_execution")
    if not isinstance(policy_section, dict):
        return base
    merged = dict(base)
    merged.update({k: v for k, v in policy_section.items() if k in base})
    return merged


def profile_allows_live_side_effects(profile_name: str, profile_data: dict[str, Any] | None = None) -> bool:
    if profile_name in _PROFILES_BLOCKED_FROM_LIVE_SIDE_EFFECTS:
        return False
    if profile_data is not None:
        return bool(profile_data.get("allow_live_side_effects", False))
    return profile_name == "live"


# ---------------------------------------------------------------------------
# Manifest live allowlist (extended Spec 132 schema)
# ---------------------------------------------------------------------------

DEFAULT_MANIFEST_LIVE_ALLOWLIST: dict[str, Any] = {
    "enabled": False,
    "allowed_tools": [],
    "allowed_actions": [],
    "max_live_actions": 1,
    "requires_operator_confirmation": True,
}


def normalize_manifest_live_allowlist(live_execution: dict[str, Any] | None) -> dict[str, Any]:
    base = dict(DEFAULT_MANIFEST_LIVE_ALLOWLIST)
    if not isinstance(live_execution, dict):
        return base
    merged = dict(base)
    for key in ("enabled", "allowed_tools", "allowed_actions", "max_live_actions", "requires_operator_confirmation"):
        if key in live_execution:
            merged[key] = live_execution[key]
    # Carry through legacy requires_approval field.
    if "requires_approval" in live_execution and "requires_operator_confirmation" not in live_execution:
        merged["requires_operator_confirmation"] = bool(live_execution["requires_approval"])
    return merged


def manifest_live_allowlist_allows_tool(live_execution: dict[str, Any] | None, tool_key: str) -> bool:
    policy = normalize_manifest_live_allowlist(live_execution)
    return bool(policy.get("enabled")) and tool_key in set(policy.get("allowed_tools") or [])


def manifest_live_allowlist_allows_action(live_execution: dict[str, Any] | None, action_id: str) -> bool:
    policy = normalize_manifest_live_allowlist(live_execution)
    allowed_actions = list(policy.get("allowed_actions") or [])
    if not allowed_actions:
        return True
    return action_id in set(allowed_actions)


def manifest_live_max_actions(live_execution: dict[str, Any] | None) -> int:
    policy = normalize_manifest_live_allowlist(live_execution)
    try:
        return int(policy.get("max_live_actions") or 1)
    except (TypeError, ValueError):
        return 1


# ---------------------------------------------------------------------------
# Pending action live fields
# ---------------------------------------------------------------------------

LIVE_CAPABLE_PENDING_ACTION_FIELDS: dict[str, Any] = {
    "operation": "side_effect",
    "approval_required": True,
    "approved_by": "",
    "approved_at": "",
    "idempotency_key": "",
    "business_ref": "",
    "live_capable": False,
    "live_executed": False,
    "live_executed_at": "",
    "dry_run_executed": False,
    "guardrail_result": None,
}


def normalize_live_capable_pending_action(action: dict[str, Any]) -> dict[str, Any]:
    result = dict(action)
    for key, default in LIVE_CAPABLE_PENDING_ACTION_FIELDS.items():
        result.setdefault(key, default)
    return result


def mark_pending_action_live_capable(action: dict[str, Any]) -> None:
    action["live_capable"] = True
    action.setdefault("operation", "side_effect")
    action.setdefault("approval_required", True)
    action.setdefault("live_executed", False)
    action.setdefault("live_executed_at", "")
    action.setdefault("dry_run_executed", False)
    action.setdefault("guardrail_result", None)


def mark_pending_action_live_executed(action: dict[str, Any], guardrail_result: dict[str, Any] | None = None) -> None:
    action["live_executed"] = True
    action["live_executed_at"] = _utc_now()
    if guardrail_result is not None:
        action["guardrail_result"] = guardrail_result


def mark_pending_action_dry_run_executed(action: dict[str, Any]) -> None:
    action["dry_run_executed"] = True


# ---------------------------------------------------------------------------
# Idempotency helpers
# ---------------------------------------------------------------------------

def check_idempotency_key_present(pending_action: dict[str, Any]) -> dict[str, Any]:
    key = str(pending_action.get("idempotency_key") or "").strip()
    if not key:
        return {
            "ok": False,
            "error_code": IDEMPOTENCY_KEY_REQUIRED,
            "message": "Idempotency key is required for live side-effect execution.",
        }
    return {"ok": True, "idempotency_key": key}


def check_idempotency_key_not_used(
    pending_action: dict[str, Any],
    executed_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    key = str(pending_action.get("idempotency_key") or "").strip()
    action_id = str(pending_action.get("action_id") or "")
    if not key:
        return {
            "ok": False,
            "error_code": IDEMPOTENCY_KEY_REQUIRED,
            "message": "Idempotency key is required.",
        }
    for executed in executed_actions:
        if (
            str(executed.get("idempotency_key") or "") == key
            and str(executed.get("action_id") or "") != action_id
            and str(executed.get("status") or "").upper() == "EXECUTED"
        ):
            return {
                "ok": False,
                "error_code": DUPLICATE_SIDE_EFFECT_BLOCKED,
                "message": f"Duplicate idempotency key blocked: {key}",
                "duplicate_action_id": str(executed.get("action_id") or ""),
            }
    if pending_action.get("live_executed") is True:
        return {
            "ok": False,
            "error_code": DUPLICATE_SIDE_EFFECT_BLOCKED,
            "message": f"Action has already been live-executed: {action_id}",
        }
    return {"ok": True, "idempotency_key": key}


# ---------------------------------------------------------------------------
# Typed confirmation
# ---------------------------------------------------------------------------

def live_execute_confirmation_phrase() -> str:
    return "LIVE-EXECUTE"


def check_typed_confirmation(confirmation: str) -> dict[str, Any]:
    phrase = live_execute_confirmation_phrase()
    if str(confirmation or "").strip() != phrase:
        return {
            "ok": False,
            "error_code": TYPED_CONFIRMATION_REQUIRED,
            "message": f"Typed confirmation required. Expected: {phrase!r}",
            "expected": phrase,
            "received": str(confirmation or ""),
        }
    return {"ok": True}


# ---------------------------------------------------------------------------
# Core preflight gate
# ---------------------------------------------------------------------------

def run_live_side_effect_preflight(
    *,
    pending_action: dict[str, Any],
    tool_spec: dict[str, Any],
    manifest_live_execution: dict[str, Any] | None,
    profile_name: str,
    profile_data: dict[str, Any] | None = None,
    executed_actions: list[dict[str, Any]] | None = None,
    dry_run: bool | None = None,
    confirmation: str | None = None,
) -> dict[str, Any]:
    """
    Run the full Spec 132 preflight gate for a live side-effect execution request.

    Returns a dict with:
      ok            - True only when all checks pass
      blocked       - True when execution must not proceed
      error_code    - first failing error code (or None)
      checks        - list of individual check results
    """
    checks: list[dict[str, Any]] = []
    error_code: str | None = None

    def add_check(name: str, passed: bool, code: str | None, message: str = "") -> None:
        nonlocal error_code
        checks.append({"name": name, "ok": passed, "error_code": code if not passed else None, "message": message})
        if not passed and error_code is None and code:
            error_code = code

    # 1. dry_run must be explicitly False for live execution
    dry_run_false = dry_run is False
    add_check(
        "dry_run_is_false",
        dry_run_false,
        LIVE_SIDE_EFFECTS_DISABLED,
        "" if dry_run_false else "dry_run must be explicitly False for live side-effect execution.",
    )

    # 2. Profile must allow live side effects
    profile_ok = profile_allows_live_side_effects(profile_name, profile_data)
    add_check(
        "profile_allows_live_side_effects",
        profile_ok,
        LIVE_PROFILE_NOT_ALLOWED,
        "" if profile_ok else f"Profile '{profile_name}' does not allow live side effects.",
    )

    # 3. Manifest allowlist must enable the tool
    manifest_policy = normalize_manifest_live_allowlist(manifest_live_execution)
    manifest_enabled = bool(manifest_policy.get("enabled"))
    tool_key = str(pending_action.get("tool") or "").strip()
    manifest_tool_ok = manifest_enabled and bool(tool_key) and tool_key in set(manifest_policy.get("allowed_tools") or [])
    add_check(
        "manifest_allows_tool",
        manifest_tool_ok,
        LIVE_MANIFEST_NOT_ALLOWED,
        "" if manifest_tool_ok else f"Manifest does not allow live execution for tool '{tool_key}'.",
    )

    # 4. Tool registry must allow live side effects
    tool_side_effect = bool(tool_spec.get("side_effect"))
    tool_requires_approval = bool(tool_spec.get("requires_approval", False))
    tool_allow_live = bool(tool_spec.get("allow_live_side_effect", False))
    tool_ok = tool_side_effect and tool_requires_approval and tool_allow_live
    add_check(
        "tool_allows_live_side_effect",
        tool_ok,
        LIVE_TOOL_NOT_ALLOWED,
        "" if tool_ok else (
            f"Tool '{tool_key}' does not allow live side effects "
            f"(side_effect={tool_side_effect}, requires_approval={tool_requires_approval}, "
            f"allow_live_side_effect={tool_allow_live})."
        ),
    )

    # 5. Pending action must be APPROVED
    action_status = str(pending_action.get("status") or "").upper()
    action_approved = action_status == "APPROVED"
    add_check(
        "pending_action_approved",
        action_approved,
        PENDING_ACTION_NOT_APPROVED,
        "" if action_approved else f"Pending action must be APPROVED (current: {action_status}).",
    )

    # 6. Approval record must exist (approved_by + approved_at)
    approved_by = str(pending_action.get("approved_by") or "").strip()
    approved_at = str(pending_action.get("approved_at") or "").strip()
    approval_record_ok = bool(approved_by) and bool(approved_at)
    add_check(
        "approval_record_exists",
        approval_record_ok,
        PENDING_ACTION_NOT_APPROVED,
        "" if approval_record_ok else "Approval record (approved_by/approved_at) is missing.",
    )

    # 7. Idempotency key must be present
    idempotency_check = check_idempotency_key_present(pending_action)
    add_check(
        "idempotency_key_present",
        idempotency_check["ok"],
        idempotency_check.get("error_code"),
        "" if idempotency_check["ok"] else idempotency_check.get("message", ""),
    )

    # 8. Idempotency key must not have been used already
    if idempotency_check["ok"]:
        dup_check = check_idempotency_key_not_used(pending_action, executed_actions or [])
        add_check(
            "idempotency_key_unused",
            dup_check["ok"],
            dup_check.get("error_code"),
            "" if dup_check["ok"] else dup_check.get("message", ""),
        )

    # 9. Guardrail must be specified and not "blocked"
    guardrail_name = str(tool_spec.get("live_guardrail") or "blocked")
    guardrail_ok = guardrail_name not in ("", "blocked")
    add_check(
        "guardrail_specified",
        guardrail_ok,
        LIVE_GUARDRAIL_FAILED,
        "" if guardrail_ok else f"Tool '{tool_key}' has no live guardrail (got: {guardrail_name!r}).",
    )

    # 10. Typed confirmation (when supplied)
    if confirmation is not None:
        confirm_check = check_typed_confirmation(confirmation)
        add_check(
            "typed_confirmation",
            confirm_check["ok"],
            confirm_check.get("error_code"),
            "" if confirm_check["ok"] else confirm_check.get("message", ""),
        )

    failed = [c for c in checks if not c["ok"]]
    ok = len(failed) == 0

    return {
        "ok": ok,
        "blocked": not ok,
        "error_code": error_code,
        "checks": checks,
        "failed_checks": failed,
        "tool": tool_key,
        "profile": profile_name,
        "idempotency_key": str(pending_action.get("idempotency_key") or ""),
        "action_id": str(pending_action.get("action_id") or ""),
    }


# ---------------------------------------------------------------------------
# Audit event builders
# ---------------------------------------------------------------------------

def build_live_executed_audit_event(
    *,
    frame_id: str,
    action_id: str,
    tool: str,
    idempotency_key: str,
    approved_by: str,
    guardrail_result: dict[str, Any],
    result_ref: str = "",
) -> dict[str, Any]:
    return {
        "event_type": "LIVE_SIDE_EFFECT_EXECUTED",
        "frame_id": frame_id,
        "action_id": action_id,
        "tool": tool,
        "idempotency_key": idempotency_key,
        "approved_by": approved_by,
        "executed_at": _utc_now(),
        "guardrail_result": guardrail_result,
        "result_ref": result_ref,
    }


def build_live_blocked_audit_event(
    *,
    frame_id: str,
    action_id: str,
    tool: str,
    reason: str,
    error_code: str,
) -> dict[str, Any]:
    return {
        "event_type": "LIVE_SIDE_EFFECT_BLOCKED",
        "frame_id": frame_id,
        "action_id": action_id,
        "tool": tool,
        "reason": reason,
        "error_code": error_code,
        "blocked_at": _utc_now(),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
