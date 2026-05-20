from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.manifest_loader import load_manifest
from runtime.persistence import PersistenceManager, write_json_atomic
from runtime.runtime_store import ensure_runtime_store_layout
from runtime.taskframe import create_taskframe


def write_recovery_manifest(
    manifest_dir: Path,
    *,
    manifest_id: str = "recovery.retryable",
    step_id: str = "check_mail",
    command: str = "[t:g/check -> unread_mail] max_results=5",
    retry: dict[str, Any] | None = None,
) -> Path:
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{manifest_id}.manifest.json"
    manifest = {
        "manifest_id": manifest_id,
        "name": "Recovery Test Manifest",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {
                "id": step_id,
                "command": command,
                **({"retry": retry} if retry is not None else {}),
            }
        ],
        "validations": [],
        "completion": {"success_outputs": [], "acceptable_empty_outputs": []},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def seed_recovery_runtime(runtime_root: Path, manifest_path: Path):
    ensure_runtime_store_layout(runtime_root)
    manifest = load_manifest(manifest_path)
    frame = create_taskframe(manifest)
    PersistenceManager(runtime_root).save_snapshot(frame)
    return frame


def write_tool_health_snapshot(runtime_root: Path, *, status: str = "ready") -> None:
    write_json_atomic(
        runtime_root / "tool_health" / "latest_tool_health.json",
        {
            "schema_version": 1,
            "generated_at": "2026-05-20T10:00:00Z",
            "include_optional": True,
            "live_rpa": False,
            "results": [
                {
                    "tool_id": "google_workspace_readonly",
                    "ok": True,
                    "status": status,
                    "severity": "info" if status == "ready" else "warning",
                    "message": "Tool health snapshot.",
                    "can_auto_resolve": False,
                    "recommended_action": "",
                    "checked_at": "2026-05-20T10:00:00Z",
                    "details": {},
                }
            ],
            "by_tool": {},
            "summary": {"tool_count": 1, "ready_count": 1 if status == "ready" else 0, "failed_count": 0},
        },
    )
