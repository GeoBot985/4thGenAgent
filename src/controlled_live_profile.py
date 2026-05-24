from __future__ import annotations

CONTROLLED_LIVE_READ_PROFILE = {
    "profile_id": "controlled_live_read",
    "label": "Controlled Live Read Profile",
    "environment": "live",
    "dry_run": False,
    "allow_live_reads": True,
    "allow_live_side_effects": False,
    "require_tool_governance": True,
    "allowed_toolpacks": ["google_workspace_readonly"],
    "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"],
}

ALLOWED_LIVE_READ_TOOLS = [
    "gmail/search", "gmail/read",
    "calendar/search", "calendar/read",
    "sheet/read", "sheet/get_values",
]

BLOCKED_LIVE_SIDE_EFFECT_TOOLS = [
    "gmail/send", "gmail/draft_send",
    "calendar/create", "calendar/update", "calendar/delete",
    "sheet/write", "sheet/write_rows", "sheet/update",
]


def is_live_read_allowed(tool_key: str, tool_spec: dict) -> tuple[bool, str]:
    """Returns (allowed, reason). Does NOT require real credentials."""
    if tool_spec.get("side_effect", False):
        return False, f"Tool {tool_key} has side_effect=True; blocked in controlled_live_read."
    if not tool_spec.get("allow_live", False):
        return False, f"Tool {tool_key} has allow_live=False; blocked in controlled_live_read."
    namespace = tool_key.split("/")[0] if "/" in tool_key else ""
    if namespace in CONTROLLED_LIVE_READ_PROFILE["blocked_tool_classes"]:
        return False, f"Tool namespace '{namespace}' is in blocked_tool_classes."
    if tool_key in BLOCKED_LIVE_SIDE_EFFECT_TOOLS:
        return False, f"Tool {tool_key} is explicitly blocked."
    return True, "ok"


def is_live_side_effect_blocked(tool_key: str) -> tuple[bool, str]:
    """Returns (blocked, reason)."""
    if tool_key in BLOCKED_LIVE_SIDE_EFFECT_TOOLS:
        return True, f"Tool {tool_key} is a blocked side-effect tool."
    return False, "not a known side-effect tool"


def build_live_side_effect_blocked_result() -> dict:
    return {
        "ok": False,
        "error_type": "LIVE_SIDE_EFFECT_BLOCKED",
        "message": "Live side effects are blocked in controlled_live_read profile.",
    }


# ---------------------------------------------------------------------------
# Spec 155 — Controlled Live Write Profile (Pilot)
# Only sheet/write_rows is executable. Gmail/Calendar/RPA remain blocked.
# ---------------------------------------------------------------------------

CONTROLLED_LIVE_WRITE_PROFILE = {
    "profile_id": "controlled_live_write",
    "label": "Controlled Live Write Profile (Pilot)",
    "environment": "pilot",
    "dry_run": False,
    "allow_live_reads": True,
    "allow_live_side_effects": True,
    "require_tool_governance": True,
    "require_operator_approval": True,
    "require_typed_confirmation": True,
    "require_idempotency_key": True,
    "require_worker_identity": True,
    "require_rollback_plan": True,
    "allowed_toolpacks": ["google_workspace_readonly", "google_sheets_write_pilot"],
    "blocked_tool_classes": ["rpa", "send", "delete", "mutation"],
    "executable_tools": ["sheet/write_rows"],
    "blocked_executable_tools": [
        "gmail/send",
        "gmail/draft_send",
        "calendar/create",
        "calendar/update",
        "calendar/delete",
        "rpa/run",
        "rpa/click",
        "rpa/type",
        "rpa/navigate",
    ],
}

V1_EXECUTABLE_TOOLS = list(CONTROLLED_LIVE_WRITE_PROFILE["executable_tools"])
V1_BLOCKED_EXECUTABLE_TOOLS = list(CONTROLLED_LIVE_WRITE_PROFILE["blocked_executable_tools"])


def is_live_write_tool_executable(tool_key: str) -> tuple[bool, str]:
    """Returns (executable, reason) for the controlled_live_write profile."""
    if tool_key in CONTROLLED_LIVE_WRITE_PROFILE["blocked_executable_tools"]:
        return False, f"Tool '{tool_key}' is blocked in controlled_live_write (v1)."
    if tool_key in CONTROLLED_LIVE_WRITE_PROFILE["executable_tools"]:
        return True, "ok"
    return False, f"Tool '{tool_key}' is not in the v1 executable list."


def is_live_write_tool_blocked(tool_key: str) -> tuple[bool, str]:
    """Returns (blocked, reason) for the controlled_live_write profile."""
    if tool_key in CONTROLLED_LIVE_WRITE_PROFILE["blocked_executable_tools"]:
        return True, f"Tool '{tool_key}' is blocked in controlled_live_write (v1)."
    return False, "not a known blocked tool"
