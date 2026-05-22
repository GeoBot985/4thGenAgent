"""Spec 145 — Audit redaction tests.

Proves that audit records never store:
- Bearer tokens
- X-TaskFrame-Token values
- Raw credentials
- Full request bodies

Also tests the redact_request_summary helper.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.audit import read_backend_audit_records, redact_request_summary
from src.production_backend import create_app
from tests.backend_auth_support import TOKENS, auth_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _records(runtime_dir: Path) -> list[dict]:
    return read_backend_audit_records(str(runtime_dir), limit=10_000)


def _all_record_text(records: list[dict]) -> str:
    """Serialise all audit records to a single searchable string."""
    return json.dumps(records, ensure_ascii=False)


def _make_client(runtime_dir: Path, *, role: str = "admin") -> TestClient:
    app = create_app(runtime_data_dir=str(runtime_dir))
    return TestClient(app, headers=auth_headers(role))


# ---------------------------------------------------------------------------
# Bearer token is never stored
# ---------------------------------------------------------------------------

def test_bearer_token_not_stored_in_audit_records(tmp_path: Path) -> None:
    for role in ("admin", "operator", "viewer"):
        app = create_app(runtime_data_dir=str(tmp_path))
        client = TestClient(app, headers=auth_headers(role))
        client.get("/api/runs")

    records = _records(tmp_path)
    text = _all_record_text(records)
    for role, token in TOKENS.items():
        assert token not in text, (
            f"Token for role '{role}' found in audit records — redaction failure"
        )


def test_bearer_token_not_stored_on_auth_failure(tmp_path: Path) -> None:
    secret_token = "super-secret-bearer-value-xyz"
    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app, headers={"Authorization": f"Bearer {secret_token}"})
    client.get("/api/runs")

    records = _records(tmp_path)
    text = _all_record_text(records)
    assert secret_token not in text, "Secret bearer token appeared in audit records"


# ---------------------------------------------------------------------------
# X-TaskFrame-Token is never stored
# ---------------------------------------------------------------------------

def test_x_taskframe_token_not_stored(tmp_path: Path) -> None:
    secret_token = "taskframe-fallback-token-secret"
    app = create_app(runtime_data_dir=str(tmp_path))
    # Use X-TaskFrame-Token header (fallback auth path)
    client = TestClient(app, headers={"X-TaskFrame-Token": secret_token})
    client.get("/api/runs")

    records = _records(tmp_path)
    text = _all_record_text(records)
    assert secret_token not in text, "X-TaskFrame-Token appeared in audit records"


# ---------------------------------------------------------------------------
# Full request bodies are not stored
# ---------------------------------------------------------------------------

def test_request_body_values_not_stored(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app, headers=auth_headers("operator"))
    sensitive_value = "SENSITIVE_CUSTOMER_DATA_DO_NOT_LOG"
    client.post(
        "/api/events",
        json={
            "source": "api",
            "event_type": "customer.message.received",
            "payload": {
                "customer_id": sensitive_value,
                "message": "Where is my order ORD-10042?",
                "channel": "callcenter",
            },
        },
    )

    records = _records(tmp_path)
    text = _all_record_text(records)
    assert sensitive_value not in text, "Payload value appeared verbatim in audit records"


# ---------------------------------------------------------------------------
# Actor dict does not expose token values
# ---------------------------------------------------------------------------

def test_actor_dict_contains_token_name_not_value(tmp_path: Path) -> None:
    client = _make_client(tmp_path, role="admin")
    client.get("/api/runs")

    records = [r for r in _records(tmp_path) if r.get("operation") == "runs.list"]
    assert records
    actor = records[0]["actor"]
    # token_name is the configured name (e.g. "local-admin"), not the raw token value
    for role, token in TOKENS.items():
        assert token != actor.get("token_name"), (
            "actor.token_name contains the raw token value — should be the config name"
        )
    # It should contain the role
    assert actor["role"] == "admin"
    # authenticated should be True for a valid token
    assert actor["authenticated"] is True


# ---------------------------------------------------------------------------
# redact_request_summary unit tests
# ---------------------------------------------------------------------------

def test_redact_request_summary_json_body() -> None:
    body = json.dumps({"customer_id": "CUST-1", "message": "hello", "channel": "web"}).encode()
    result = redact_request_summary(body, "application/json")
    assert result["payload_size"] == len(body)
    assert set(result["payload_keys"]) == {"customer_id", "message", "channel"}


def test_redact_request_summary_empty_body() -> None:
    result = redact_request_summary(None)
    assert result == {"payload_keys": [], "payload_size": 0}


def test_redact_request_summary_non_json_body() -> None:
    body = b"not json data"
    result = redact_request_summary(body, "text/plain")
    assert result["payload_size"] == len(body)
    assert result["payload_keys"] == []


def test_redact_request_summary_malformed_json() -> None:
    body = b"{not valid json"
    result = redact_request_summary(body, "application/json")
    assert result["payload_size"] == len(body)
    assert result["payload_keys"] == []


# ---------------------------------------------------------------------------
# Audit record fields are safe (no raw auth headers stored)
# ---------------------------------------------------------------------------

def test_audit_record_actor_has_no_token_field(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    client.get("/api/runs")

    records = [r for r in _records(tmp_path) if r.get("operation") == "runs.list"]
    assert records
    actor = records[0]["actor"]
    # The actor dict must not contain a raw "token" key
    assert "token" not in actor, "actor dict should not have a 'token' key"
    assert "token_value" not in actor


def test_audit_records_have_no_authorization_header_field(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    client.get("/api/runs")

    records = _records(tmp_path)
    text = _all_record_text(records)
    # The raw Authorization header value should not appear
    token = TOKENS["admin"]
    # The token string should not appear anywhere in the serialised records
    assert token not in text
