from __future__ import annotations

from typing import Any

from .errors import LiveExecutionBlocked, LiveExecutionNotAllowedForTool, LiveExecutionPolicyError
from .models import Manifest, TaskFrame


DEFAULT_LIVE_EXECUTION_POLICY = {
    "enabled": False,
    "allowed_tools": [],
    "allowed_actions": [],
    "max_live_actions": 1,
    "requires_approval": True,
    "requires_operator_confirmation": True,
}


def normalize_live_execution_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(DEFAULT_LIVE_EXECUTION_POLICY)
    if policy is None:
        return normalized
    if not isinstance(policy, dict):
        raise LiveExecutionPolicyError("live_execution policy must be an object.")
    for key in (
        "enabled",
        "allowed_tools",
        "allowed_actions",
        "max_live_actions",
        "requires_approval",
        "requires_operator_confirmation",
    ):
        if key in policy:
            normalized[key] = policy[key]
    return normalized


def validate_live_execution_policy(policy: dict[str, Any]) -> None:
    if not isinstance(policy, dict):
        raise LiveExecutionPolicyError("live_execution policy must be an object.")
    enabled = policy.get("enabled", False)
    allowed_tools = policy.get("allowed_tools", [])
    allowed_actions = policy.get("allowed_actions", [])
    requires_approval = policy.get("requires_approval", True)
    requires_operator_confirmation = policy.get("requires_operator_confirmation", True)
    max_live_actions = policy.get("max_live_actions", 1)

    if not isinstance(enabled, bool):
        raise LiveExecutionPolicyError("live_execution.enabled must be a boolean.")
    if not isinstance(allowed_tools, list):
        raise LiveExecutionPolicyError("live_execution.allowed_tools must be a list.")
    if any(not isinstance(tool, str) or not tool.strip() for tool in allowed_tools):
        raise LiveExecutionPolicyError("live_execution.allowed_tools must contain non-empty strings.")
    if not isinstance(allowed_actions, list):
        raise LiveExecutionPolicyError("live_execution.allowed_actions must be a list.")
    if any(not isinstance(a, str) or not a.strip() for a in allowed_actions):
        raise LiveExecutionPolicyError("live_execution.allowed_actions must contain non-empty strings.")
    if not isinstance(requires_approval, bool):
        raise LiveExecutionPolicyError("live_execution.requires_approval must be a boolean.")
    if requires_approval is False:
        raise LiveExecutionPolicyError("live_execution.requires_approval must remain true.")
    if not isinstance(requires_operator_confirmation, bool):
        raise LiveExecutionPolicyError("live_execution.requires_operator_confirmation must be a boolean.")
    if requires_operator_confirmation is False:
        raise LiveExecutionPolicyError("live_execution.requires_operator_confirmation must remain true.")
    if not isinstance(max_live_actions, int) or max_live_actions < 1:
        raise LiveExecutionPolicyError("live_execution.max_live_actions must be a positive integer.")


def manifest_allows_live_tool(manifest: Manifest | dict[str, Any], tool_key: str) -> bool:
    if isinstance(manifest, dict):
        live_policy = manifest.get("live_execution")
    else:
        live_policy = getattr(manifest, "live_execution", None)
    policy = normalize_live_execution_policy(live_policy)
    try:
        validate_live_execution_policy(policy)
    except LiveExecutionPolicyError:
        return False
    return bool(policy.get("enabled")) and tool_key in set(policy.get("allowed_tools", []))


def tool_allows_live_side_effect(tool_spec: dict[str, Any]) -> bool:
    return bool(tool_spec.get("side_effect")) and bool(tool_spec.get("allow_live_side_effect")) and bool(
        tool_spec.get("requires_approval", False)
    )


def assert_live_execution_allowed(
    frame: TaskFrame,
    manifest: Manifest,
    pending_action: dict[str, Any],
    tool_spec: dict[str, Any],
    runtime_live_mode: bool,
) -> None:
    if not runtime_live_mode:
        raise LiveExecutionBlocked("Runtime live mode must be enabled.")
    if frame.state not in {"WAITING_FOR_EXECUTE", "EXECUTING_PENDING"}:
        raise LiveExecutionBlocked(f"TaskFrame must be WAITING_FOR_EXECUTE: {frame.state}")
    if pending_action.get("status") == "EXECUTED":
        raise LiveExecutionBlocked("Pending action has already been executed.")
    if pending_action.get("status") != "APPROVED":
        raise LiveExecutionBlocked(f"Pending action must be APPROVED: {pending_action.get('status')}")
    tool_key = str(pending_action.get("tool", "")).strip()
    if not tool_key:
        raise LiveExecutionBlocked("Pending action tool is missing.")
    if not tool_spec.get("side_effect"):
        raise LiveExecutionNotAllowedForTool(f"Tool is not a side-effect tool: {tool_key}")
    if not tool_spec.get("requires_approval", False):
        raise LiveExecutionNotAllowedForTool(f"Tool does not require approval: {tool_key}")
    if not tool_spec.get("allow_live_side_effect", False):
        raise LiveExecutionNotAllowedForTool(f"Tool is not allowed for live side effects: {tool_key}")
    if not manifest.live_execution.get("enabled", False):
        raise LiveExecutionBlocked("Manifest does not enable live execution.")
    if tool_key not in set(manifest.live_execution.get("allowed_tools", [])):
        raise LiveExecutionBlocked(f"Manifest does not allow live execution for tool: {tool_key}")
    if pending_action.get("status") == "EXECUTED":
        raise LiveExecutionBlocked("Pending action has already been executed.")
