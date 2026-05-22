from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.production_backend import create_app


def _client(runtime_dir: Path) -> TestClient:
    app = create_app(runtime_data_dir=str(runtime_dir))
    return TestClient(app)


def test_event_idempotency_same_key_returns_existing_result(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = {
        "source": "api",
        "event_type": "customer.message.received",
        "payload": {
            "customer_id": "CUST-1001",
            "message": "Where is my order ORD-10042?",
            "channel": "callcenter",
        },
        "idempotency_key": "test_key_123",
    }

    resp1 = client.post("/api/events", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["ok"] is True
    assert data1["linked_frame_id"]

    resp2 = client.post("/api/events", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data2["ok"] is True
    assert data2["duplicate"] is True
    assert data2["event_id"] == data1["event_id"]
    assert data2["linked_frame_id"] == data1["linked_frame_id"]

    runs = [path for path in (tmp_path / "runs").iterdir() if path.is_dir()]
    assert len(runs) == 1

    events = client.get("/api/events?source=api&event_type=customer.message.received")
    assert events.status_code == 200
    rows = events.json()["events"]
    assert len(rows) == 2
    assert rows[0]["event_id"] == data2["event_id"]
    assert rows[0]["status"] == "DUPLICATE_EVENT"
    assert rows[1]["event_id"] == data1["event_id"]

