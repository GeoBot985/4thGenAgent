from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from runtime.manifest_loader import load_manifest_by_id
from runtime.pending_actions import list_pending_actions
from runtime.taskframe_reload import load_taskframe
from runtime.tool_health import LATEST_TOOL_HEALTH_JSON, load_latest_tool_health_snapshot
from runtime.tool_registry import get_tool_spec

from src.config_profiles import load_config_profile
from src.operator_data import build_operator_snapshot
from runtime.live_execution_safety import build_live_execution_preflight


def build_live_safety_status(runtime_data_dir: str | Path = "runtime_data") -> dict:
    runtime_root = Path(runtime_data_dir)
    snapshot = build_operator_snapshot(str(runtime_root))
    active_frame = snapshot.get("active_frame") if isinstance(snapshot, dict) else None
    active_frame_data = dict(active_frame) if isinstance(active_frame, dict) else {}
    frame_id = str(active_frame_data.get("frame_id", "")).strip()
    pending_raw = active_frame_data.get("pending_actions", [])
    pending_actions = list(pending_raw) if isinstance(pending_raw, list) else []
    approved_pending_action_count = sum(1 for item in pending_actions if isinstance(item, dict) and str(item.get("status", "")).upper() == "APPROVED")
    live_ready_action_count = 0
    blocked_action_count = 0
    runtime_live_mode = _runtime_live_mode_enabled()
    tool_health_snapshot = load_latest_tool_health_snapshot()

    if frame_id:
        try:
            frame = load_taskframe(frame_id, runtime_root)
            manifest = load_manifest_by_id(frame.manifest_id)
            for action in list_pending_actions(frame):
                tool_key = str(action.get("tool", "")).strip()
                tool_spec = _tool_spec_for(tool_key)
                preflight = build_live_execution_preflight(
                    frame=frame,
                    manifest=manifest,
                    pending_action=action,
                    tool_spec=tool_spec,
                    runtime_live_mode=runtime_live_mode,
                    tool_health=_resolve_tool_health(tool_health_snapshot, tool_key),
                )
                if preflight.get("status") == "LIVE_READY_REQUIRES_CONFIRMATION":
                    live_ready_action_count += 1
                elif preflight.get("status") == "LIVE_BLOCKED":
                    blocked_action_count += 1
        except Exception:
            blocked_action_count = max(blocked_action_count, len(pending_actions))
    else:
        blocked_action_count = len(pending_actions)

    profile = load_config_profile()
    summary = "Dry-run only. No live-ready pending actions."
    if live_ready_action_count:
        summary = f"Dry-run only. {live_ready_action_count} live-ready pending action(s) require confirmation."

    return {
        "live_execution_env_enabled": runtime_live_mode,
        "default_mode": "dry_run",
        "optional_rpa_enabled": bool(profile.optional_rpa_enabled),
        "pending_action_count": len(pending_actions),
        "approved_pending_action_count": approved_pending_action_count,
        "live_ready_action_count": live_ready_action_count,
        "blocked_action_count": blocked_action_count,
        "tool_health_snapshot_path": str(LATEST_TOOL_HEALTH_JSON),
        "summary": summary,
    }


def _runtime_live_mode_enabled() -> bool:
    value = os.environ.get("TASKFRAME_ENABLE_LIVE_EXECUTION", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _tool_spec_for(tool_key: str) -> dict[str, Any]:
    if not tool_key or "/" not in tool_key:
        return {}
    namespace, action = tool_key.split("/", 1)
    try:
        return get_tool_spec(namespace, action)
    except Exception:
        return {}


def _resolve_tool_health(snapshot: dict[str, Any], tool_key: str) -> dict | None:
    if not tool_key:
        return None
    if "by_tool" in snapshot and isinstance(snapshot.get("by_tool"), dict):
        by_tool = snapshot["by_tool"]
        if tool_key in by_tool and isinstance(by_tool[tool_key], dict):
            return dict(by_tool[tool_key])
    results = snapshot.get("results", [])
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and str(item.get("tool_id", "")) == tool_key:
                return dict(item)
    return None
