from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from runtime.approval import approve_action
from runtime.events import create_event
from runtime.persistence import persist_frame_update
from runtime.runtime_engine import RuntimeEngine


SMOKE_MANIFEST_DIR = Path("tests/fixtures/smoke_manifests")
SMOKE_ROUTES_PATH = SMOKE_MANIFEST_DIR / "event_routes.json"


def _stage_frame(runtime_dir: Path, event_type: str, payload: dict[str, object], *, approve: bool = True) -> tuple[str, str]:
    engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH)
    frame = engine.handle_event(create_event(event_type, "manual", payload=payload), dry_run=True)
    if approve:
        approve_action(frame, frame.pending_actions[0]["action_id"], approved_by="tester", reason="approve")
    persist_frame_update(frame, runtime_dir)
    return frame.frame_id, frame.pending_actions[0]["action_id"]


def _run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], capture_output=True, text=True, check=False, env=merged_env)


def test_safety_status_exits_zero(tmp_path):
    proc = _run_cli("safety-status", "--runtime-data-dir", str(tmp_path))
    assert proc.returncode == 0
    assert "Dry-run only" in proc.stdout


def test_pending_actions_exits_zero_even_with_no_actions(tmp_path):
    proc = _run_cli("pending-actions", "--runtime-data-dir", str(tmp_path))
    assert proc.returncode == 0
    assert "No pending actions" in proc.stdout


def test_live_preflight_returns_blockers_for_normal_demo_actions(tmp_path):
    frame_id, action_id = _stage_frame(tmp_path, "manual.live_side_effect_blocked_by_manifest", {"title": "Demo"})
    proc = _run_cli(
        "live-preflight",
        "--frame-id",
        frame_id,
        "--action-id",
        action_id,
        "--manifest-dir",
        str(SMOKE_MANIFEST_DIR),
        "--runtime-data-dir",
        str(tmp_path),
        env={"TASKFRAME_ENABLE_LIVE_EXECUTION": "1"},
    )
    assert proc.returncode != 0
    assert "LIVE_BLOCKED" in proc.stdout
    assert "manifest_live_disabled" in proc.stdout or "pending_action_not_approved" in proc.stdout


def test_execute_approved_dry_run_works_for_existing_approved_flow(tmp_path):
    frame_id, action_id = _stage_frame(tmp_path, "manual.live_sheet_create_allowed", {"title": "Dry run OK"})
    proc = _run_cli(
        "execute-approved",
        "--frame-id",
        frame_id,
        "--action-id",
        action_id,
        "--manifest-dir",
        str(SMOKE_MANIFEST_DIR),
        "--runtime-data-dir",
        str(tmp_path),
        "--dry-run",
    )
    assert proc.returncode == 0
    assert "Mode: dry-run" in proc.stdout


def test_execute_approved_live_fails_without_env_var(tmp_path):
    frame_id, action_id = _stage_frame(tmp_path, "manual.live_sheet_create_allowed", {"title": "Live blocked"})
    proc = _run_cli(
        "execute-approved",
        "--frame-id",
        frame_id,
        "--action-id",
        action_id,
        "--manifest-dir",
        str(SMOKE_MANIFEST_DIR),
        "--runtime-data-dir",
        str(tmp_path),
        "--live",
        "--i-understand-live-side-effects",
        "--confirm",
        f"EXECUTE LIVE {frame_id} {action_id}",
    )
    assert proc.returncode != 0
    assert "TASKFRAME_ENABLE_LIVE_EXECUTION is not enabled" in proc.stdout or "LIVE EXECUTION BLOCKED" in proc.stdout


def test_execute_approved_live_fails_without_typed_confirmation(tmp_path):
    frame_id, action_id = _stage_frame(tmp_path, "manual.live_sheet_create_allowed", {"title": "Live blocked"})
    proc = _run_cli(
        "execute-approved",
        "--frame-id",
        frame_id,
        "--action-id",
        action_id,
        "--manifest-dir",
        str(SMOKE_MANIFEST_DIR),
        "--runtime-data-dir",
        str(tmp_path),
        "--live",
        "--i-understand-live-side-effects",
        env={"TASKFRAME_ENABLE_LIVE_EXECUTION": "1"},
    )
    assert proc.returncode != 0
    assert "Typed confirmation phrase does not match" in proc.stdout or "LIVE EXECUTION BLOCKED" in proc.stdout


def test_execute_approved_live_fails_with_wrong_confirmation_phrase(tmp_path):
    frame_id, action_id = _stage_frame(tmp_path, "manual.live_sheet_create_allowed", {"title": "Live blocked"})
    proc = _run_cli(
        "execute-approved",
        "--frame-id",
        frame_id,
        "--action-id",
        action_id,
        "--manifest-dir",
        str(SMOKE_MANIFEST_DIR),
        "--runtime-data-dir",
        str(tmp_path),
        "--live",
        "--i-understand-live-side-effects",
        "--confirm",
        "WRONG PHRASE",
        env={"TASKFRAME_ENABLE_LIVE_EXECUTION": "1"},
    )
    assert proc.returncode != 0
    assert "Typed confirmation phrase does not match" in proc.stdout


def test_execute_approved_live_fails_if_tool_or_manifest_policy_blocks_it(tmp_path):
    frame_id, action_id = _stage_frame(tmp_path, "manual.live_side_effect_blocked_by_manifest", {"title": "Blocked"})
    proc = _run_cli(
        "execute-approved",
        "--frame-id",
        frame_id,
        "--action-id",
        action_id,
        "--manifest-dir",
        str(SMOKE_MANIFEST_DIR),
        "--runtime-data-dir",
        str(tmp_path),
        "--live",
        "--i-understand-live-side-effects",
        "--confirm",
        f"EXECUTE LIVE {frame_id} {action_id}",
        env={"TASKFRAME_ENABLE_LIVE_EXECUTION": "1"},
    )
    assert proc.returncode != 0
    assert "LIVE EXECUTION BLOCKED" in proc.stdout
    assert "manifest_live_disabled" in proc.stdout or "tool_not_live_allowed" in proc.stdout
