from __future__ import annotations

from pathlib import Path
from typing import Any

from .business_data import seed_business_dataset, validate_business_dataset
from .memory_store import MemoryStore
from .tool_capabilities import ToolHealthResult
from .tool_capability_registry import get_tool_capability


def get_tool_setup_instructions(tool_id: str) -> dict[str, Any]:
    capability = get_tool_capability(tool_id)
    instructions = {
        "tool_id": capability.tool_id,
        "display_name": capability.display_name,
        "summary": capability.description,
        "operator_action_required": not capability.setup_available or capability.auth_required or capability.rpa_live_probe_required,
        "steps": [],
    }

    if tool_id in {"business_context", "business_database"}:
        instructions["steps"] = [
            "Ensure runtime_data/business exists in the clone.",
            "Run the demo business dataset seed or validation if local fixtures are missing.",
        ]
    elif tool_id == "memory_store":
        instructions["steps"] = [
            "Create the local runtime_data/memory_store.json file if it does not exist.",
        ]
    elif tool_id == "report_generator":
        instructions["steps"] = [
            "Ensure runtime_data/tool_health and runtime_data/outputs directories exist.",
        ]
    elif tool_id == "gmail":
        instructions["steps"] = [
            "Add Google OAuth credentials and token files under ~/.taskframe/google/.",
            "Authorize read-only Gmail access manually.",
        ]
    elif tool_id == "google_sheets":
        instructions["steps"] = [
            "Add Google OAuth credentials and token files under ~/.taskframe/google/.",
            "Select a spreadsheet ID in ~/.taskframe/accounting_google_sheet.json.",
        ]
    elif tool_id == "google_calendar":
        instructions["steps"] = [
            "Add Google OAuth credentials and token files under ~/.taskframe/google/.",
            "Authorize Calendar access manually.",
        ]
    elif tool_id == "llm_ollama":
        instructions["steps"] = [
            "Start a local Ollama server, or switch the clean-clone demo to the fake provider.",
        ]
    elif tool_id == "rpa_google_messages":
        instructions["steps"] = [
            "Install Playwright locally.",
            "Pair Google Messages manually in the browser profile.",
            "Keep this tool outside the default RC path.",
        ]
    return instructions


def run_safe_setup_action(tool_id: str) -> ToolHealthResult:
    from .taskframe import utc_now

    capability = get_tool_capability(tool_id)
    checked_at = utc_now()

    if tool_id in {"business_context", "business_database"}:
        seed_business_dataset("runtime_data", overwrite=False)
        validation = validate_business_dataset("runtime_data")
        ok = bool(validation.get("ok", False))
        return ToolHealthResult(
            tool_id=tool_id,
            ok=ok,
            status="ready" if ok else "failing",
            severity="info" if ok else "error",
            message="Demo business dataset seeded and validated." if ok else "Demo business dataset validation failed.",
            can_auto_resolve=True,
            recommended_action=None if ok else "Review runtime_data/business fixtures.",
            checked_at=checked_at,
            details={"validation": validation, "capability": capability.to_dict()},
        )

    if tool_id == "memory_store":
        store = MemoryStore()
        store.load()
        return ToolHealthResult(
            tool_id=tool_id,
            ok=True,
            status="ready",
            severity="info",
            message="Local memory store is available.",
            can_auto_resolve=True,
            recommended_action=None,
            checked_at=checked_at,
            details={"path": str(store.path), "capability": capability.to_dict()},
        )

    if tool_id == "report_generator":
        reports_dir = Path("runtime_data") / "tool_health" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return ToolHealthResult(
            tool_id=tool_id,
            ok=True,
            status="ready",
            severity="info",
            message="Local report output directories are available.",
            can_auto_resolve=True,
            recommended_action=None,
            checked_at=checked_at,
            details={"reports_dir": str(reports_dir), "capability": capability.to_dict()},
        )

    instructions = get_tool_setup_instructions(tool_id)
    status = "needs_auth" if capability.auth_required else "live_probe_required" if capability.rpa_live_probe_required else "not_run"
    severity = "warning" if status in {"needs_auth", "live_probe_required"} else "info"
    return ToolHealthResult(
        tool_id=tool_id,
        ok=False,
        status=status,
        severity=severity,
        message=f"{capability.display_name} requires operator setup.",
        can_auto_resolve=False,
        recommended_action=instructions["steps"][0] if instructions.get("steps") else capability.setup_action,
        checked_at=checked_at,
        details={"instructions": instructions, "capability": capability.to_dict()},
    )
