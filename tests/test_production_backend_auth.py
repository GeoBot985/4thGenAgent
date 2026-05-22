from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.production_backend import create_app
from tests.backend_auth_support import auth_headers


def _client(runtime_dir: Path, *, role: str = "admin", config_path: Path | None = None) -> TestClient:
    app = create_app(runtime_data_dir=str(runtime_dir), backend_auth_config_path=str(config_path) if config_path else None)
    return TestClient(app, headers=auth_headers(role))


def _seed_pending_action(runtime_root: Path) -> tuple[str, str]:
    from runtime.manifest_loader import load_manifest
    from runtime.persistence import PersistenceManager
    from runtime.run_ledger import append_ledger_record
    from runtime.taskframe import create_taskframe

    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.state = "PENDING_APPROVAL"
    action_id = "action-001"
    frame.pending_actions.append(
        {
            "action_id": action_id,
            "tool": "write_sheet",
            "output_alias": "report",
            "args": {"sheet_id": "abc123"},
            "status": "PENDING_APPROVAL",
            "requested_at": "2026-01-01T00:00:00Z",
        }
    )
    PersistenceManager(runtime_root).save_snapshot(frame)
    append_ledger_record(frame, runtime_data_dir=runtime_root)
    return frame.frame_id, action_id


def test_protected_route_rejects_missing_token(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app)

    response = client.get("/api/runs")

    assert response.status_code == 401
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "AUTH_REQUIRED"


def test_protected_route_rejects_invalid_token(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app, headers={"Authorization": "Bearer wrong-token"})

    response = client.get("/api/runs")

    assert response.status_code == 401
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "AUTH_INVALID"


def test_viewer_can_read_run_list(tmp_path: Path) -> None:
    client = _client(tmp_path, role="viewer")

    response = client.get("/api/runs")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_viewer_cannot_approve_pending_actions(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    runtime_root.mkdir(parents=True, exist_ok=True)
    frame_id, action_id = _seed_pending_action(runtime_root)
    client = _client(runtime_root, role="viewer")

    response = client.post(f"/api/runs/{frame_id}/pending-actions/{action_id}/approve")

    assert response.status_code == 403
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "AUTH_FORBIDDEN"


def test_viewer_cannot_submit_events(tmp_path: Path) -> None:
    client = _client(tmp_path, role="viewer")

    response = client.post(
        "/api/events",
        json={
            "source": "api",
            "event_type": "customer.message.received",
            "payload": {
                "customer_id": "CUST-1001",
                "message": "Where is my order ORD-10042?",
                "channel": "callcenter",
            },
        },
    )

    assert response.status_code == 403
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "AUTH_FORBIDDEN"


def test_operator_can_submit_events(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")

    response = client.post(
        "/api/events",
        json={
            "source": "api",
            "event_type": "customer.message.received",
            "payload": {
                "customer_id": "CUST-1001",
                "message": "Where is my order ORD-10042?",
                "channel": "callcenter",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_operator_can_approve_and_reject_pending_actions(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    runtime_root.mkdir(parents=True, exist_ok=True)
    frame_id_approve, action_id_approve = _seed_pending_action(runtime_root)
    frame_id_reject, action_id_reject = _seed_pending_action(runtime_root)
    client = _client(runtime_root, role="operator")

    approve = client.post(f"/api/runs/{frame_id_approve}/pending-actions/{action_id_approve}/approve")
    reject = client.post(f"/api/runs/{frame_id_reject}/pending-actions/{action_id_reject}/reject")

    assert approve.status_code == 200
    assert approve.json()["ok"] is True
    assert reject.status_code == 200
    assert reject.json()["ok"] is True


def test_admin_can_access_all_backend_routes(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    runtime_root.mkdir(parents=True, exist_ok=True)
    frame_id, action_id = _seed_pending_action(runtime_root)
    client = _client(runtime_root, role="admin")

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/runs").status_code == 200
    assert client.get(f"/api/runs/{frame_id}").status_code == 200
    assert client.get(f"/api/runs/{frame_id}/evidence").status_code == 200
    assert client.get(f"/api/runs/{frame_id}/approval-pack").status_code == 200
    assert client.get(f"/api/runs/{frame_id}/failure-summary").status_code == 200
    assert client.get("/api/events").status_code == 200
    assert client.post(
        "/api/events",
        json={
            "source": "api",
            "event_type": "customer.message.received",
            "payload": {
                "customer_id": "CUST-1001",
                "message": "Where is my order ORD-10042?",
                "channel": "callcenter",
            },
        },
    ).status_code == 200
    assert client.post(f"/api/runs/{frame_id}/report", json={"rebuild": False}).status_code == 200
    assert client.post(f"/api/runs/{frame_id}/pending-actions/{action_id}/approve").status_code == 200
    frame_id_2, action_id_2 = _seed_pending_action(runtime_root)
    assert client.post(f"/api/runs/{frame_id_2}/pending-actions/{action_id_2}/reject").status_code == 200


def test_tokens_are_not_returned_in_responses(tmp_path: Path) -> None:
    client = _client(tmp_path, role="viewer")
    response = client.get("/api/health")
    text = response.text
    for token in ("test-admin-token", "test-operator-token", "test-viewer-token"):
        assert token not in text
