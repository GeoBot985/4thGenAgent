from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.production_backend import create_app
from tests.backend_auth_support import auth_headers


def _client(runtime_dir: Path) -> TestClient:
    app = create_app(runtime_data_dir=str(runtime_dir))
    return TestClient(app, headers=auth_headers("admin"))


def _valid_event() -> dict[str, object]:
    return {
        "source": "api",
        "event_type": "customer.message.received",
        "payload": {
            "customer_id": "CUST-1001",
            "message": "Where is my order ORD-10042?",
            "channel": "callcenter",
        },
    }


def test_valid_event_creates_taskframe(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/events", json=_valid_event())

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"] == "api"
    assert data["event_type"] == "customer.message.received"
    assert data["route_id"] == "api.customer_message_received"
    assert data["manifest_id"] == "customer.message_status_check"
    assert data["linked_frame_id"]
    assert data["frame_state"] == "WAITING_FOR_EXECUTE"
    assert data["pending_action_count"] >= 0
    assert data["executed_action_count"] == 0

    detail = client.get(f"/api/events/{data['event_id']}")
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["ok"] is True
    assert detail_data["event"]["event_id"] == data["event_id"]
    assert detail_data["event"]["route_id"] == data["route_id"]
    assert detail_data["event"]["manifest_id"] == data["manifest_id"]
    assert detail_data["linked_frame"]["frame_id"] == data["linked_frame_id"]
    assert detail_data["linked_frame"]["manifest_id"] == data["manifest_id"]
    assert detail_data["linked_frame"]["state"] == data["frame_state"]
    assert detail_data["linked_frame"]["executed_action_count"] == 0


def test_unknown_event_route_fails_safely(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/events",
        json={
            "source": "api",
            "event_type": "customer.message.unknown",
            "payload": {
                "customer_id": "CUST-1001",
                "message": "Where is my order ORD-10042?",
                "channel": "callcenter",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["error"]

    events = client.get("/api/events?limit=10")
    assert events.status_code == 200
    rows = events.json()["events"]
    assert rows[0]["source"] == "api"
    assert rows[0]["event_type"] == "customer.message.unknown"
    assert rows[0]["route_id"] in {"", None}

    detail = client.get(f"/api/events/{rows[0]['event_id']}")
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["ok"] is True
    assert detail_data["event"]["event_id"] == rows[0]["event_id"]
    assert detail_data["linked_frame"] == {}


def test_missing_required_payload_field_fails_validation(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/events",
        json={
            "source": "api",
            "event_type": "customer.message.received",
            "payload": {
                "customer_id": "CUST-1001",
                "message": "Where is my order ORD-10042?",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert "channel" in data["error"]


def test_dry_run_false_is_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)

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
            "dry_run": False,
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["ok"] is False
    assert "live execution" in data["detail"]["error"]


def test_api_cannot_submit_raw_tool_commands_or_manifest_ids(tmp_path: Path) -> None:
    client = _client(tmp_path)

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
            "tool": "shell.exec",
        },
    )
    assert response.status_code == 422

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
            "manifest_id": "smoke.gmail_check",
        },
    )
    assert response.status_code == 422


def test_event_list_returns_recent_events(tmp_path: Path) -> None:
    client = _client(tmp_path)
    first = client.post("/api/events", json=_valid_event()).json()
    second = client.post(
        "/api/events",
        json={
            "source": "api",
            "event_type": "customer.message.unknown",
            "payload": {
                "customer_id": "CUST-1001",
                "message": "Where is my order ORD-10042?",
                "channel": "callcenter",
            },
        },
    ).json()

    response = client.get("/api/events?limit=1&source=api")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["count"] == 1
    assert data["events"][0]["event_id"] == second["event_id"]
    assert data["events"][0]["source"] == "api"
    assert data["events"][0]["route_id"] in {"", None}

    response = client.get("/api/events?status=FRAME_CREATED")
    assert response.status_code == 200
    created_rows = response.json()["events"]
    assert created_rows[0]["event_id"] == first["event_id"]
    assert created_rows[0]["route_id"] == "api.customer_message_received"


def test_event_detail_returns_linked_frame_metadata(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post("/api/events", json=_valid_event()).json()

    response = client.get(f"/api/events/{created['event_id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["event"]["event_id"] == created["event_id"]
    assert data["linked_frame"]["frame_id"] == created["linked_frame_id"]
    assert data["linked_frame"]["manifest_id"] == "customer.message_status_check"
    assert data["linked_frame"]["error_count"] >= 0


def test_event_detail_handles_events_with_no_linked_frame(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/events",
        json={
            "source": "api",
            "event_type": "customer.message.unknown",
            "payload": {
                "customer_id": "CUST-1001",
                "message": "Where is my order ORD-10042?",
                "channel": "callcenter",
            },
        },
    ).json()

    response = client.get(f"/api/events/{created['event_id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["event"]["event_id"] == created["event_id"]
    assert data["linked_frame"] == {}


def test_malformed_event_id_is_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/events/invalid!@#$")

    assert response.status_code == 400
    data = response.json()
    assert data["ok"] is False
    assert data["error_code"] == "INVALID_ID"
