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
