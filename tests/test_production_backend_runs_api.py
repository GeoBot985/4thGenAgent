"""Spec 141 — Tests for GET /api/runs and run detail/evidence/report routes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.production_backend import create_app
from tests.backend_auth_support import auth_headers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def runtime_root(tmp_path):
    from runtime.runtime_store import ensure_runtime_store_layout
    root = tmp_path / "runtime_data"
    ensure_runtime_store_layout(root)
    return root


@pytest.fixture()
def seeded_runtime(runtime_root):
    """Create a couple of completed frames in the runtime store."""
    from runtime.manifest_loader import load_manifest
    from runtime.persistence import PersistenceManager
    from runtime.taskframe import create_taskframe
    from runtime.run_ledger import append_ledger_record

    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frames = {}

    completed = create_taskframe(manifest)
    completed.state = "COMPLETED"
    PersistenceManager(runtime_root).save_snapshot(completed)
    append_ledger_record(completed, runtime_data_dir=runtime_root)
    frames["completed"] = completed

    failed = create_taskframe(manifest)
    failed.state = "FAILED_EXECUTION"
    failed.errors.append({
        "type": "tool",
        "message": "Fixture data unavailable",
        "data": {},
        "timestamp": failed.updated_at,
    })
    PersistenceManager(runtime_root).save_snapshot(failed)
    append_ledger_record(failed, runtime_data_dir=runtime_root)
    frames["failed"] = failed

    return frames, runtime_root


@pytest.fixture()
def client(seeded_runtime):
    _, runtime_root = seeded_runtime
    app = create_app(runtime_data_dir=str(runtime_root))
    return TestClient(app, headers=auth_headers("admin")), seeded_runtime


# ---------------------------------------------------------------------------
# GET /api/runs
# ---------------------------------------------------------------------------

class TestListRuns:
    def test_returns_ok(self, client):
        c, _ = client
        resp = c.get("/api/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_returns_runs_list(self, client):
        c, (frames, _) = client
        resp = c.get("/api/runs")
        data = resp.json()
        assert isinstance(data["runs"], list)
        assert data["count"] == len(data["runs"])

    def test_runs_contain_required_fields(self, client):
        c, (frames, _) = client
        resp = c.get("/api/runs")
        data = resp.json()
        for run in data["runs"]:
            assert "frame_id" in run
            assert "manifest_id" in run
            assert "state" in run

    def test_runs_are_seeded_frames(self, client):
        c, (frames, _) = client
        resp = c.get("/api/runs")
        data = resp.json()
        frame_ids = {r["frame_id"] for r in data["runs"]}
        assert frames["completed"].frame_id in frame_ids
        assert frames["failed"].frame_id in frame_ids

    def test_limit_parameter(self, seeded_runtime):
        _, runtime_root = seeded_runtime
        app = create_app(runtime_data_dir=str(runtime_root))
        c = TestClient(app, headers=auth_headers("admin"))
        resp = c.get("/api/runs?limit=1")
        data = resp.json()
        assert data["count"] == 1

    def test_empty_runtime_returns_empty_list(self, runtime_root):
        app = create_app(runtime_data_dir=str(runtime_root))
        c = TestClient(app, headers=auth_headers("admin"))
        resp = c.get("/api/runs")
        data = resp.json()
        assert data["ok"] is True
        assert data["runs"] == []
        assert data["count"] == 0


# ---------------------------------------------------------------------------
# GET /api/runs/{frame_id}
# ---------------------------------------------------------------------------

class TestGetRun:
    def test_returns_ok_for_existing_frame(self, client):
        c, (frames, _) = client
        fid = frames["completed"].frame_id
        resp = c.get(f"/api/runs/{fid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["frame_id"] == fid

    def test_returns_required_fields(self, client):
        c, (frames, _) = client
        fid = frames["completed"].frame_id
        resp = c.get(f"/api/runs/{fid}")
        data = resp.json()
        assert "manifest_id" in data
        assert "state" in data
        assert "summary" in data
        assert "outputs_preview" in data
        assert "pending_actions" in data
        assert "errors" in data
        assert "validations" in data
        assert "artifact_paths" in data
        assert "error" in data

    def test_unknown_frame_returns_404(self, client):
        c, _ = client
        resp = c.get("/api/runs/unknown-frame-999")
        assert resp.status_code == 404
        data = resp.json()
        assert data["ok"] is False

    def test_invalid_frame_id_returns_400(self, client):
        c, _ = client
        resp = c.get("/api/runs/../etc/passwd")
        assert resp.status_code in (400, 404, 422)

    def test_path_traversal_blocked_dots(self, client):
        c, _ = client
        resp = c.get("/api/runs/..%2Fetc%2Fpasswd")
        assert resp.status_code in (400, 404, 422)

    def test_path_traversal_blocked_slash(self, client):
        c, _ = client
        resp = c.get("/api/runs/a%2Fb")
        assert resp.status_code in (400, 404, 422)

    def test_does_not_return_raw_filesystem_path_contents(self, client):
        c, (frames, _) = client
        fid = frames["completed"].frame_id
        resp = c.get(f"/api/runs/{fid}")
        data = resp.json()
        # artifact_paths should contain string paths, not file contents
        for v in (data.get("artifact_paths") or {}).values():
            assert isinstance(v, str)
            assert "{" not in v and "[" not in v

    def test_state_matches_seeded_frame(self, client):
        c, (frames, _) = client
        fid = frames["completed"].frame_id
        resp = c.get(f"/api/runs/{fid}")
        data = resp.json()
        assert data["state"] == "COMPLETED"

    def test_failed_frame_has_errors(self, client):
        c, (frames, _) = client
        fid = frames["failed"].frame_id
        resp = c.get(f"/api/runs/{fid}")
        data = resp.json()
        assert len(data["errors"]) >= 1


# ---------------------------------------------------------------------------
# GET /api/runs/{frame_id}/evidence
# ---------------------------------------------------------------------------

class TestGetEvidence:
    def test_returns_ok_for_existing_frame(self, client):
        c, (frames, _) = client
        fid = frames["completed"].frame_id
        resp = c.get(f"/api/runs/{fid}/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["frame_id"] == fid
        assert "evidence" in data

    def test_evidence_uses_persisted_artifacts(self, client):
        c, (frames, _) = client
        fid = frames["completed"].frame_id
        resp = c.get(f"/api/runs/{fid}/evidence")
        data = resp.json()
        bundle = data["evidence"]
        assert bundle.get("frame_id") == fid

    def test_unknown_frame_returns_error(self, client):
        c, _ = client
        resp = c.get("/api/runs/no-such-frame/evidence")
        assert resp.status_code in (404, 500)
        data = resp.json()
        assert data["ok"] is False


# ---------------------------------------------------------------------------
# GET /api/runs/{frame_id}/approval-pack
# ---------------------------------------------------------------------------

class TestGetApprovalPack:
    def test_returns_ok_for_existing_frame(self, client):
        c, (frames, _) = client
        fid = frames["completed"].frame_id
        resp = c.get(f"/api/runs/{fid}/approval-pack")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["frame_id"] == fid
        assert "approval_pack" in data
        assert "pending_action_count" in data

    def test_unknown_frame_returns_404(self, client):
        c, _ = client
        resp = c.get("/api/runs/no-such-frame/approval-pack")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/runs/{frame_id}/failure-summary
# ---------------------------------------------------------------------------

class TestGetFailureSummary:
    def test_works_for_completed_frame(self, client):
        c, (frames, _) = client
        fid = frames["completed"].frame_id
        resp = c.get(f"/api/runs/{fid}/failure-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "failure_summary" in data

    def test_works_for_failed_frame(self, client):
        c, (frames, _) = client
        fid = frames["failed"].frame_id
        resp = c.get(f"/api/runs/{fid}/failure-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "failure_summary" in data

    def test_unknown_frame_returns_404(self, client):
        c, _ = client
        resp = c.get("/api/runs/no-such-frame/failure-summary")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/runs/{frame_id}/report
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_generates_report_for_existing_frame(self, client):
        c, (frames, _) = client
        fid = frames["completed"].frame_id
        resp = c.post(f"/api/runs/{fid}/report", json={"rebuild": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["frame_id"] == fid
        assert "markdown_path" in data
        assert "html_path" in data
        assert "evidence_bundle_path" in data

    def test_report_paths_are_strings(self, client):
        c, (frames, _) = client
        fid = frames["completed"].frame_id
        resp = c.post(f"/api/runs/{fid}/report", json={"rebuild": False})
        data = resp.json()
        assert isinstance(data["markdown_path"], str)
        assert isinstance(data["html_path"], str)

    def test_unknown_frame_returns_error(self, client):
        c, _ = client
        resp = c.post("/api/runs/no-such-frame/report", json={"rebuild": False})
        assert resp.status_code in (404, 500)
        data = resp.json()
        assert data["ok"] is False

    def test_no_live_side_effects_in_report(self, client):
        c, (frames, _) = client
        fid = frames["completed"].frame_id
        resp = c.post(f"/api/runs/{fid}/report", json={"rebuild": True})
        data = resp.json()
        # Report generation must not produce live side effects
        assert data.get("ok") is True
        # No tool execution indicators in the response
        assert "tool_executed" not in data
        assert "live_side_effect" not in data


# ---------------------------------------------------------------------------
# Safety: no arbitrary tool execution from API
# ---------------------------------------------------------------------------

class TestAPISafetyRules:
    def test_no_tool_execution_endpoint(self, client):
        c, _ = client
        # Should 404 — no tool execution endpoint exists
        resp = c.post("/api/tools/execute", json={"tool": "any_tool", "args": {}})
        assert resp.status_code == 404

    def test_no_arbitrary_file_read_endpoint(self, client):
        c, _ = client
        resp = c.get("/api/files/runtime_data/runs/")
        assert resp.status_code == 404

    def test_invalid_id_blocked(self, client):
        c, _ = client
        resp = c.get("/api/runs/" + "x" * 200)
        assert resp.status_code in (400, 404, 422)
