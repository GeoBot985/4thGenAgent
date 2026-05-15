from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .live_execution import manifest_allows_live_tool, tool_allows_live_side_effect
from .live_guardrails import guardrail_blocked, run_live_guardrail


_SENSITIVE_KEY_PARTS = ("token", "password", "secret", "authorization", "api_key", "credential", "cookie")


def confirmation_phrase(frame_id: str, action_id: str) -> str:
    return f"EXECUTE LIVE {frame_id} {action_id}"


def redact_pending_action_args(args: dict[str, Any]) -> dict[str, Any]:
    return _redact_value(args)


def build_live_execution_preflight(
    *,
    frame: Any,
    manifest: Any,
    pending_action: dict[str, Any],
    tool_spec: dict[str, Any],
    runtime_live_mode: bool,
    tool_health: dict | None = None,
) -> dict:
    frame_data = _as_mapping(frame)
    manifest_data = _as_mapping(manifest)
    action_data = dict(pending_action or {})
    spec = dict(tool_spec or {})

    frame_id = str(frame_data.get("frame_id") or "")
    manifest_id = str(manifest_data.get("manifest_id") or "")
    action_id = str(action_data.get("action_id") or "")
    tool = str(action_data.get("tool") or _tool_key(spec) or "")
    pending_action_status = str(action_data.get("status") or "")
    side_effect = bool(spec.get("side_effect"))
    requires_approval = bool(spec.get("requires_approval", False))
    allow_live_side_effect = bool(spec.get("allow_live_side_effect", False))
    manifest_live_enabled = bool(_live_execution_spec(manifest_data).get("enabled", False))
    manifest_allows_tool = bool(manifest_allows_live_tool(manifest, tool) if tool else False)
    guardrail_name = str(spec.get("live_guardrail", "blocked") or "blocked")
    guardrail_result = run_live_guardrail(guardrail_name, action_data, spec) if spec else guardrail_blocked(action_data, spec)
    tool_health_result = _resolve_tool_health(tool_health, tool)

    blockers: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not runtime_live_mode:
        warnings.append("Runtime live mode is disabled; dry-run remains the default path.")
    else:
        if frame_data.get("state") not in {"WAITING_FOR_EXECUTE", "EXECUTING_PENDING"}:
            blockers.append(
                {
                    "id": "frame_state_not_ready",
                    "message": f"TaskFrame must be WAITING_FOR_EXECUTE or EXECUTING_PENDING: {frame_data.get('state', '')}",
                    "source": "runtime",
                }
            )
        if pending_action_status != "APPROVED":
            blockers.append(
                {
                    "id": "pending_action_not_approved",
                    "message": f"Pending action must be APPROVED: {pending_action_status or 'UNKNOWN'}",
                    "source": "approval",
                }
            )
        if not tool:
            blockers.append(
                {
                    "id": "pending_action_tool_missing",
                    "message": "Pending action tool is missing.",
                    "source": "runtime",
                }
            )
        if not side_effect:
            blockers.append(
                {
                    "id": "tool_not_side_effect",
                    "message": "Tool is not a side-effect tool.",
                    "source": "tool_registry",
                }
            )
        if not requires_approval:
            blockers.append(
                {
                    "id": "tool_requires_approval_missing",
                    "message": "Tool does not require approval.",
                    "source": "tool_registry",
                }
            )
        if not allow_live_side_effect:
            blockers.append(
                {
                    "id": "tool_not_live_allowed",
                    "message": "Tool does not allow live side effects.",
                    "source": "tool_registry",
                }
            )
        if not manifest_live_enabled:
            blockers.append(
                {
                    "id": "manifest_live_disabled",
                    "message": "Manifest does not enable live execution.",
                    "source": "manifest",
                }
            )
        if tool and not manifest_allows_tool:
            blockers.append(
                {
                    "id": "manifest_does_not_allow_tool",
                    "message": f"Manifest does not allow live execution for tool: {tool}",
                    "source": "manifest",
                }
            )
        if not guardrail_result.get("ok", False):
            blockers.append(
                {
                    "id": "live_guardrail_failed",
                    "message": str(guardrail_result.get("error") or "Live guardrail check failed."),
                    "source": "guardrail",
                }
            )
        if tool_health_result and not bool(tool_health_result.get("ok", True)):
            blockers.append(
                {
                    "id": "tool_health_failing",
                    "message": str(tool_health_result.get("message") or "Relevant tool health is failing."),
                    "source": "tool_health",
                }
            )

    status = "DRY_RUN_ONLY"
    severity = "info"
    if runtime_live_mode:
        if blockers:
            status = "LIVE_BLOCKED"
            severity = "critical" if any(blocker["id"] in {"manifest_live_disabled", "tool_not_live_allowed", "live_guardrail_failed", "tool_health_failing"} for blocker in blockers) else "warning"
        else:
            status = "LIVE_READY_REQUIRES_CONFIRMATION"
            severity = "warning"

    ok = status != "LIVE_BLOCKED"
    tool_health_payload = tool_health_result if tool_health_result is not None else {}

    return {
        "ok": ok,
        "status": status,
        "severity": severity,
        "frame_id": frame_id,
        "manifest_id": manifest_id,
        "action_id": action_id,
        "tool": tool,
        "side_effect": side_effect,
        "requires_approval": requires_approval,
        "allow_live_side_effect": allow_live_side_effect,
        "runtime_live_mode": runtime_live_mode,
        "manifest_live_enabled": manifest_live_enabled,
        "manifest_allows_tool": manifest_allows_tool,
        "pending_action_status": pending_action_status,
        "guardrail": {
            "name": guardrail_name,
            "ok": bool(guardrail_result.get("ok", False)),
            "checks": list(guardrail_result.get("checks", []) or []),
        },
        "tool_health": tool_health_payload,
        "blockers": blockers,
        "warnings": warnings,
        "confirmation_phrase": confirmation_phrase(frame_id, action_id),
        "safe_default_command": f"taskframe execute-approved --frame-id {frame_id} --action-id {action_id} --dry-run",
        "target_summary": _target_summary(action_data),
        "redacted_args": redact_pending_action_args(dict(action_data.get("args", {}) or {})),
    }


def _resolve_tool_health(tool_health: dict | None, tool_key: str) -> dict | None:
    if not isinstance(tool_health, dict) or not tool_key:
        return tool_health if isinstance(tool_health, dict) else None
    if "tool_id" in tool_health and str(tool_health.get("tool_id")) == tool_key:
        return dict(tool_health)
    by_tool = tool_health.get("by_tool")
    if isinstance(by_tool, dict) and tool_key in by_tool and isinstance(by_tool[tool_key], dict):
        return dict(by_tool[tool_key])
    results = tool_health.get("results")
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and str(item.get("tool_id", "")) == tool_key:
                return dict(item)
    return None


def _tool_key(spec: dict[str, Any]) -> str:
    namespace = str(spec.get("namespace") or "").strip()
    action = str(spec.get("action") or "").strip()
    if namespace and action:
        return f"{namespace}/{action}"
    return ""


def _target_summary(action_data: dict[str, Any]) -> str:
    args = dict(action_data.get("args", {}) or {})
    pieces: list[str] = []
    for key in ("subject", "po_id", "order_id", "sku", "spreadsheet_title", "title", "recipient", "to", "chat", "order", "customer_id"):
        value = str(args.get(key, "")).strip()
        if value:
            pieces.append(f"{key}={value}")
    return ", ".join(pieces) if pieces else str(action_data.get("tool", "") or "")


def _redact_value(value: Any, key_name: str = "") -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _SENSITIVE_KEY_PARTS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_value(item, key_text)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item, key_name) for item in value]
    return value


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return dict(asdict(value))
    return dict(getattr(value, "__dict__", {}) or {})


def _live_execution_spec(manifest_data: dict[str, Any]) -> dict[str, Any]:
    live = manifest_data.get("live_execution")
    return dict(live) if isinstance(live, dict) else {}
