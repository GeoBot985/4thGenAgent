from __future__ import annotations

from typing import Any

from src.toolpack_governance import check_pack_allowed, get_pack_policy

from .runtime_environment import ENVIRONMENTS, load_runtime_profile


def evaluate_tool_governance(
    tool_key: str,
    tool_spec: dict,
    *,
    environment: str,
    dry_run: bool,
    live_requested: bool = False,
    operation: str = "execute",
) -> dict[str, Any]:
    environment = str(environment or "demo").strip().lower()
    if environment not in ENVIRONMENTS:
        return _decision(
            False,
            "BLOCK",
            tool_key,
            tool_spec,
            environment,
            dry_run,
            live_requested,
            operation,
            reason=f"Unknown runtime environment: {environment!r}",
            policy={"ok": False, "allowed": False, "reason": f"Unknown environment: {environment!r}"},
            errors=[f"Unknown environment: {environment!r}"],
        )

    runtime_profile = load_runtime_profile()
    governance_enforced = bool(runtime_profile.get("governance_enforced", True))
    if not governance_enforced:
        return _decision(
            True,
            "ALLOW",
            tool_key,
            tool_spec,
            environment,
            dry_run,
            live_requested,
            operation,
            reason="Governance enforcement is disabled in runtime profile.",
            warnings=["Governance enforcement disabled."],
            policy={"governance_enforced": False},
        )

    toolpack_id = str(tool_spec.get("toolpack_id", "") or "").strip()
    source = str(tool_spec.get("source", "") or "builtin").strip() or "builtin"
    classification = str(
        tool_spec.get("toolpack_classification", "")
        or tool_spec.get("toolpack_core_or_optional", "")
        or tool_spec.get("classification", "")
        or ""
    ).strip()
    if not classification:
        classification = "core" if source in {"builtin", "legacy_fallback"} and not toolpack_id else "optional"
    policy = get_pack_policy(toolpack_id) if toolpack_id else {"toolpack_id": "", "classification": "core", "enabled_environments": [], "governance_recorded": False, "errors": []}
    pack_policy_result = check_pack_allowed(toolpack_id, environment) if toolpack_id else {"ok": True, "allowed": True, "classification": classification, "reason": "Built-in core tool."}
    pack_allowed = bool(pack_policy_result.get("allowed", False))

    if source in {"builtin", "legacy_fallback"} and not toolpack_id:
        pack_allowed = True
        pack_policy_result = {"ok": True, "allowed": True, "classification": "core", "reason": "Built-in core tool."}
        classification = "core"

    if toolpack_id and not policy.get("governance_recorded", False):
        if environment == "dev" and bool(runtime_profile.get("allow_unknown_toolpack_in_dev", False)):
            return _decision(
                True,
                "WARN",
                tool_key,
                tool_spec,
                environment,
                dry_run,
                live_requested,
                operation,
                reason="Unknown toolpack policy allowed in dev by runtime profile.",
                policy=policy,
                warnings=["Toolpack policy not recorded."],
            )
        return _decision(
            False,
            "BLOCK",
            tool_key,
            tool_spec,
            environment,
            dry_run,
            live_requested,
            operation,
            reason="No governance policy recorded for toolpack.",
            policy=policy,
            errors=["No governance policy recorded for toolpack."],
        )

    if toolpack_id and not pack_allowed:
        decision = "BLOCK"
        if environment == "dev" and classification == "unknown" and bool(runtime_profile.get("allow_unknown_toolpack_in_dev", False)):
            decision = "WARN"
        return _decision(
            decision != "BLOCK",
            decision,
            tool_key,
            tool_spec,
            environment,
            dry_run,
            live_requested,
            operation,
            reason=str(pack_policy_result.get("reason", "Toolpack is not allowed.")),
            policy=policy | {"pack_decision": pack_policy_result},
            errors=[] if decision != "BLOCK" else [str(pack_policy_result.get("reason", "Toolpack is not allowed."))],
            warnings=[] if decision == "BLOCK" else [str(pack_policy_result.get("reason", "Toolpack is not allowed."))],
        )

    if classification in {"high_risk", "experimental"} and environment in {"demo", "release"}:
        return _decision(
            False,
            "BLOCK",
            tool_key,
            tool_spec,
            environment,
            dry_run,
            live_requested,
            operation,
            reason=f"{classification.replace('_', ' ')} toolpack is not allowed in {environment}.",
            policy=policy,
            errors=[f"{classification.replace('_', ' ')} toolpack is not allowed in {environment}."],
        )
    if classification == "blocked":
        return _decision(
            False,
            "BLOCK",
            tool_key,
            tool_spec,
            environment,
            dry_run,
            live_requested,
            operation,
            reason="Toolpack is blocked.",
            policy=policy,
            errors=["Toolpack is blocked."],
        )
    if classification == "high_risk" and environment == "live" and not bool(runtime_profile.get("allow_high_risk_live_override", False)):
        return _decision(
            False,
            "BLOCK",
            tool_key,
            tool_spec,
            environment,
            dry_run,
            live_requested,
            operation,
            reason="High-risk toolpack is not allowed in live without an explicit override.",
            policy=policy,
            errors=["High-risk toolpack is not allowed in live without an explicit override."],
        )

    side_effect = bool(tool_spec.get("side_effect", False))
    requires_approval = bool(tool_spec.get("requires_approval", False))
    allow_live_side_effect = bool(tool_spec.get("allow_live_side_effect", False))

    if live_requested and side_effect and not allow_live_side_effect:
        return _decision(
            False,
            "BLOCK",
            tool_key,
            tool_spec,
            environment,
            dry_run,
            live_requested,
            operation,
            reason="Live side effects are not allowed by the tool contract.",
            policy=policy,
            errors=["Live side effects are not allowed by the tool contract."],
        )
    if live_requested and side_effect and requires_approval is False:
        return _decision(
            False,
            "BLOCK",
            tool_key,
            tool_spec,
            environment,
            dry_run,
            live_requested,
            operation,
            reason="Live side-effect tool must require approval.",
            policy=policy,
            errors=["Live side-effect tool must require approval."],
        )

    if operation in {"stage_pending_action", "execute_pending_action"} and side_effect and not requires_approval:
        return _decision(
            False,
            "BLOCK",
            tool_key,
            tool_spec,
            environment,
            dry_run,
            live_requested,
            operation,
            reason="Side-effect tool must require approval before staging.",
            policy=policy,
            errors=["Side-effect tool must require approval before staging."],
        )

    if operation == "execute" and live_requested and side_effect and not allow_live_side_effect:
        return _decision(
            False,
            "BLOCK",
            tool_key,
            tool_spec,
            environment,
            dry_run,
            live_requested,
            operation,
            reason="Live execution of side-effect tools is not allowed.",
            policy=policy,
            errors=["Live execution of side-effect tools is not allowed."],
        )

    return _decision(
        True,
        "ALLOW",
        tool_key,
        tool_spec,
        environment,
        dry_run,
        live_requested,
        operation,
        reason="Governance policy allows execution.",
        policy=policy,
    )


def _decision(
    ok: bool,
    decision: str,
    tool_key: str,
    tool_spec: dict,
    environment: str,
    dry_run: bool,
    live_requested: bool,
    operation: str,
    *,
    reason: str,
    policy: dict[str, Any],
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    classification = str(tool_spec.get("toolpack_core_or_optional", "") or tool_spec.get("classification", "") or "unknown")
    toolpack_id = str(tool_spec.get("toolpack_id", "") or "")
    return {
        "ok": ok,
        "decision": decision,
        "reason": reason,
        "tool": tool_key,
        "toolpack_id": toolpack_id,
        "classification": classification or "unknown",
        "environment": environment,
        "dry_run": bool(dry_run),
        "live_requested": bool(live_requested),
        "operation": operation,
        "policy": dict(policy or {}),
        "errors": list(errors or []),
        "warnings": list(warnings or []),
    }
