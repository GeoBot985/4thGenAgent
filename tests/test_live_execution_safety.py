from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from runtime.approval import approve_action
from runtime.live_execution import manifest_allows_live_tool
from runtime.live_execution_safety import build_live_execution_preflight, confirmation_phrase, redact_pending_action_args
from runtime.manifest_loader import load_manifest
from runtime.runtime_engine import RuntimeEngine
from runtime.tool_registry import TOOL_REGISTRY


SMOKE_MANIFEST_DIR = Path("tests/fixtures/smoke_manifests")
SMOKE_ROUTES_PATH = SMOKE_MANIFEST_DIR / "event_routes.json"


def smoke_manifest_path(name: str) -> Path:
    return SMOKE_MANIFEST_DIR / name


def _staged_frame(runtime_dir: Path, event_type: str, payload: dict[str, object] | None = None, *, approve: bool = True):
    engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH)
    frame = engine.handle_event(__import__("runtime.events", fromlist=["create_event"]).create_event(event_type, "manual", payload=payload or {}), dry_run=True)
    if approve:
        approve_action(frame, frame.pending_actions[0]["action_id"], approved_by="tester", reason="approve")
    return runtime_dir, frame


def test_dry_run_default_returns_dry_run_only(tmp_path):
    _, frame = _staged_frame(tmp_path, "manual.live_sheet_create_allowed", {"title": "Demo"})
    manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
    pending_action = frame.pending_actions[0]
    tool_spec = deepcopy(TOOL_REGISTRY["sheet/create"])

    preflight = build_live_execution_preflight(
        frame=frame,
        manifest=manifest,
        pending_action=pending_action,
        tool_spec=tool_spec,
        runtime_live_mode=False,
    )

    assert preflight["status"] == "DRY_RUN_ONLY"
    assert preflight["ok"] is True


def test_unapproved_pending_action_blocks_live(tmp_path):
    _, frame = _staged_frame(tmp_path, "manual.live_sheet_create_allowed", {"title": "Demo"}, approve=False)
    manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
    pending_action = frame.pending_actions[0]
    tool_spec = deepcopy(TOOL_REGISTRY["sheet/create"])

    preflight = build_live_execution_preflight(
        frame=frame,
        manifest=manifest,
        pending_action=pending_action,
        tool_spec=tool_spec,
        runtime_live_mode=True,
    )

    assert preflight["status"] == "LIVE_BLOCKED"
    assert any(blocker["id"] == "pending_action_not_approved" for blocker in preflight["blockers"])


def test_approved_action_blocks_if_runtime_live_mode_disabled(tmp_path):
    _, frame = _staged_frame(tmp_path, "manual.live_sheet_create_allowed", {"title": "Demo"})
    manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
    pending_action = frame.pending_actions[0]
    tool_spec = deepcopy(TOOL_REGISTRY["sheet/create"])

    preflight = build_live_execution_preflight(
        frame=frame,
        manifest=manifest,
        pending_action=pending_action,
        tool_spec=tool_spec,
        runtime_live_mode=False,
    )

    assert preflight["status"] == "DRY_RUN_ONLY"


def test_approved_action_blocks_if_manifest_live_execution_disabled(tmp_path):
    _, frame = _staged_frame(tmp_path, "manual.live_side_effect_blocked_by_manifest", {"title": "Demo"})
    manifest = load_manifest(smoke_manifest_path("smoke_live_side_effect_blocked_by_manifest.manifest.json"))
    pending_action = frame.pending_actions[0]
    tool_spec = deepcopy(TOOL_REGISTRY["sheet/create"])

    preflight = build_live_execution_preflight(
        frame=frame,
        manifest=manifest,
        pending_action=pending_action,
        tool_spec=tool_spec,
        runtime_live_mode=True,
    )

    assert preflight["status"] == "LIVE_BLOCKED"
    assert any(blocker["id"] == "manifest_live_disabled" for blocker in preflight["blockers"])


def test_approved_action_blocks_if_tool_not_in_manifest_allowed_tools(tmp_path):
    _, frame = _staged_frame(tmp_path, "manual.live_sheet_write_allowed", {"spreadsheet_id": "sheet-123", "range_name": "Sheet1!A1:B2", "values_json": "[[\"a\", \"b\"]]", "mode": "append"})
    manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
    pending_action = frame.pending_actions[0]
    tool_spec = deepcopy(TOOL_REGISTRY["sheet/write"])

    preflight = build_live_execution_preflight(
        frame=frame,
        manifest=manifest,
        pending_action=pending_action,
        tool_spec=tool_spec,
        runtime_live_mode=True,
    )

    assert preflight["status"] == "LIVE_BLOCKED"
    assert any(blocker["id"] == "manifest_does_not_allow_tool" for blocker in preflight["blockers"])


def test_approved_action_blocks_if_tool_does_not_allow_live_side_effect(tmp_path):
    _, frame = _staged_frame(tmp_path, "manual.live_sheet_create_allowed", {"title": "Demo"})
    manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
    pending_action = frame.pending_actions[0]
    tool_spec = deepcopy(TOOL_REGISTRY["g/send"])

    preflight = build_live_execution_preflight(
        frame=frame,
        manifest=manifest,
        pending_action=pending_action,
        tool_spec=tool_spec,
        runtime_live_mode=True,
    )

    assert preflight["status"] == "LIVE_BLOCKED"
    assert any(blocker["id"] == "tool_not_side_effect" or blocker["id"] == "tool_not_live_allowed" for blocker in preflight["blockers"])


def test_approved_action_blocks_if_guardrail_fails(tmp_path):
    _, frame = _staged_frame(tmp_path, "manual.live_sheet_create_allowed", {"title": "test-delete-unsafe"})
    manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
    pending_action = frame.pending_actions[0]
    tool_spec = deepcopy(TOOL_REGISTRY["sheet/create"])

    preflight = build_live_execution_preflight(
        frame=frame,
        manifest=manifest,
        pending_action=pending_action,
        tool_spec=tool_spec,
        runtime_live_mode=True,
    )

    assert preflight["status"] == "LIVE_BLOCKED"
    assert any(blocker["id"] == "live_guardrail_failed" for blocker in preflight["blockers"])


def test_confirmation_phrase_is_deterministic():
    assert confirmation_phrase("frame_123", "action_456") == "EXECUTE LIVE frame_123 action_456"


def test_redaction_removes_secret_like_fields():
    payload = {
        "subject": "PO update",
        "token": "abc",
        "nested": {"password": "secret", "order_id": "ORD-1"},
        "authorization": "Bearer abc",
        "items": [{"api_key": "xyz", "sku": "SKU-1"}],
    }

    redacted = redact_pending_action_args(payload)

    assert redacted["subject"] == "PO update"
    assert redacted["nested"]["order_id"] == "ORD-1"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["items"][0]["api_key"] == "[REDACTED]"
