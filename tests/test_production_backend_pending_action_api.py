"""Spec 141 — Tests for pending-action approve/reject routes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.production_backend import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def runtime_root(tmp_path):
    from runtime.runtime_store import ensure_runtime_store_layout
    root = tmp_path / "runtime_data"
    ensure_runtime_store_layout(root)
    return root


def _make_pending_action(action_id: str) -> dict:
    return {
        "action_id": action_id,
        "tool": "write_sheet",
        "output_alias": "report",
        "args": {"sheet_id": "abc123"},
        "status": "PENDING_APPROVAL",
        "requested_at": "2026-01-01T00:00:00Z",
    }


@pytest.fixture()
def frame_with_pending(runtime_root):
    """TaskFrame with one PENDING_APPROVAL action, persisted to runtime store."""
    from runtime.manifest_loader import load_manifest
    from runtime.persistence import PersistenceManager
    from runtime.taskframe import create_taskframe
    from runtime.run_ledger import append_ledger_record

    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.state = "PENDING_APPROVAL"
    action_id = "action-001"
    frame.pending_actions.append(_make_pending_action(action_id))

    PersistenceManager(runtime_root).save_snapshot(frame)
    append_ledger_record(frame, runtime_data_dir=runtime_root)
    return frame, action_id, runtime_root


@pytest.fixture()
def client_with_pending(frame_with_pending):
    frame, action_id, runtime_root = frame_with_pending
    app = create_app(runtime_data_dir=str(runtime_root))
    return TestClient(app), frame, action_id, runtime_root


# ---------------------------------------------------------------------------
# POST /api/runs/{frame_id}/pending-actions/{action_id}/approve
# ---------------------------------------------------------------------------

class TestApproveAction:
    def test_approve_returns_ok(self, client_with_pending):
        c, frame, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_approve_returns_required_fields(self, client_with_pending):
        c, frame, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/approve")
        data = resp.json()
        assert "frame_id" in data
        assert "action_id" in data
        assert "operation" in data
        assert "state" in data
        assert "pending_actions" in data
        assert "executed_actions" in data
        assert "error" in data

    def test_approve_operation_field(self, client_with_pending):
        c, frame, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/approve")
        data = resp.json()
        assert data["operation"] == "approve"
        assert data["action_id"] == action_id

    def test_approve_unknown_frame_returns_404(self, client_with_pending):
        c, _, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/no-such-frame/pending-actions/{action_id}/approve")
        assert resp.status_code == 404
        data = resp.json()
        assert data["ok"] is False

    def test_approve_unknown_action_returns_404(self, client_with_pending):
        c, frame, _, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/no-such-action/approve")
        assert resp.status_code == 404
        data = resp.json()
        assert data["ok"] is False

    def test_approve_invalid_frame_id_returns_400(self, client_with_pending):
        c, _, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/../etc/passwd/pending-actions/{action_id}/approve")
        assert resp.status_code in (400, 404, 422)

    def test_approve_invalid_action_id_returns_400(self, client_with_pending):
        c, frame, _, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/bad%2Fid/approve")
        assert resp.status_code in (400, 404, 422)

    def test_approve_persists_state_change(self, client_with_pending):
        c, frame, action_id, runtime_root = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/approve")
        assert resp.status_code == 200
        # Reload from disk to verify persistence
        from runtime.persistence import load_taskframe_dict
        reloaded = load_taskframe_dict(frame.frame_id, str(runtime_root))
        actions = reloaded.get("pending_actions") or []
        matching = [a for a in actions if a.get("action_id") == action_id]
        assert len(matching) == 1
        assert matching[0]["status"] == "APPROVED"

    def test_approve_no_live_side_effects(self, client_with_pending):
        c, frame, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/approve")
        data = resp.json()
        assert "tool_executed" not in data
        assert "live_side_effect" not in data

    def test_approve_long_id_blocked(self, client_with_pending):
        c, frame, _, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{'x' * 200}/approve")
        assert resp.status_code in (400, 404, 422)


# ---------------------------------------------------------------------------
# POST /api/runs/{frame_id}/pending-actions/{action_id}/reject
# ---------------------------------------------------------------------------

class TestRejectAction:
    def test_reject_returns_ok(self, client_with_pending):
        c, frame, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/reject")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_reject_returns_required_fields(self, client_with_pending):
        c, frame, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/reject")
        data = resp.json()
        assert "frame_id" in data
        assert "action_id" in data
        assert "operation" in data
        assert "state" in data
        assert "pending_actions" in data
        assert "executed_actions" in data

    def test_reject_operation_field(self, client_with_pending):
        c, frame, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/reject")
        data = resp.json()
        assert data["operation"] == "reject"
        assert data["action_id"] == action_id

    def test_reject_unknown_frame_returns_404(self, client_with_pending):
        c, _, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/no-such-frame/pending-actions/{action_id}/reject")
        assert resp.status_code == 404
        data = resp.json()
        assert data["ok"] is False

    def test_reject_unknown_action_returns_404(self, client_with_pending):
        c, frame, _, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/no-such-action/reject")
        assert resp.status_code == 404
        data = resp.json()
        assert data["ok"] is False

    def test_reject_persists_state_change(self, client_with_pending):
        c, frame, action_id, runtime_root = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/reject")
        assert resp.status_code == 200
        from runtime.persistence import load_taskframe_dict
        reloaded = load_taskframe_dict(frame.frame_id, str(runtime_root))
        actions = reloaded.get("pending_actions") or []
        matching = [a for a in actions if a.get("action_id") == action_id]
        assert len(matching) == 1
        assert matching[0]["status"] == "REJECTED"

    def test_reject_invalid_frame_id_returns_400(self, client_with_pending):
        c, _, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/a%2Fb/pending-actions/{action_id}/reject")
        assert resp.status_code in (400, 404, 422)

    def test_reject_no_live_side_effects(self, client_with_pending):
        c, frame, action_id, _ = client_with_pending
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/reject")
        data = resp.json()
        assert "tool_executed" not in data
        assert "live_side_effect" not in data


# ---------------------------------------------------------------------------
# Approve then reject (idempotency / double-operation)
# ---------------------------------------------------------------------------

class TestDoubleOperation:
    def test_cannot_approve_already_approved(self, client_with_pending):
        c, frame, action_id, _ = client_with_pending
        c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/approve")
        # Second approve should fail (action no longer PENDING_APPROVAL)
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/approve")
        assert resp.status_code in (400, 404, 500)
        data = resp.json()
        assert data["ok"] is False

    def test_cannot_reject_already_approved(self, client_with_pending):
        c, frame, action_id, _ = client_with_pending
        c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/approve")
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/{action_id}/reject")
        assert resp.status_code in (400, 404, 500)
        data = resp.json()
        assert data["ok"] is False


# ---------------------------------------------------------------------------
# Multiple pending actions
# ---------------------------------------------------------------------------

class TestMultiplePendingActions:
    def test_approve_one_leaves_others_pending(self, runtime_root):
        from runtime.manifest_loader import load_manifest
        from runtime.persistence import PersistenceManager
        from runtime.taskframe import create_taskframe
        from runtime.run_ledger import append_ledger_record

        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "PENDING_APPROVAL"
        frame.pending_actions.append(_make_pending_action("action-A"))
        frame.pending_actions.append(_make_pending_action("action-B"))

        PersistenceManager(runtime_root).save_snapshot(frame)
        append_ledger_record(frame, runtime_data_dir=runtime_root)

        app = create_app(runtime_data_dir=str(runtime_root))
        c = TestClient(app)
        resp = c.post(f"/api/runs/{frame.frame_id}/pending-actions/action-A/approve")
        assert resp.status_code == 200

        from runtime.persistence import load_taskframe_dict
        reloaded = load_taskframe_dict(frame.frame_id, str(runtime_root))
        actions = {a["action_id"]: a["status"] for a in (reloaded.get("pending_actions") or [])}
        assert actions["action-A"] == "APPROVED"
        assert actions["action-B"] == "PENDING_APPROVAL"
