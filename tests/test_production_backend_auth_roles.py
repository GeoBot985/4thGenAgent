from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.config import load_backend_auth_config
from src.production_backend import create_app
from tests.backend_auth_support import auth_headers


def _write_config(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "taskframe.backend.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_dev_bypass_is_disabled_by_default(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app)

    response = client.get("/api/runs")

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_dev_bypass_works_only_when_explicitly_enabled(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_config(
        tmp_path,
        {
            "backend_auth": {
                "enabled": False,
                "allow_dev_bypass": True,
                "tokens": [
                    {"name": "local-admin", "token_env": "TASKFRAME_BACKEND_ADMIN_TOKEN", "role": "admin"},
                    {"name": "operator", "token_env": "TASKFRAME_BACKEND_OPERATOR_TOKEN", "role": "operator"},
                    {"name": "viewer", "token_env": "TASKFRAME_BACKEND_VIEWER_TOKEN", "role": "viewer"},
                ],
            }
        },
    )
    app = create_app(runtime_data_dir=str(tmp_path), backend_auth_config_path=str(config_path))
    client = TestClient(app)

    response = client.get("/api/runs")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    health = client.get("/api/health").json()
    assert health["auth"]["dev_bypass"] is True


def test_dev_bypass_can_be_enabled_via_environment_variables(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TASKFRAME_BACKEND_AUTH_ENABLED", "false")
    monkeypatch.setenv("TASKFRAME_BACKEND_ALLOW_DEV_BYPASS", "true")
    monkeypatch.setenv("TASKFRAME_BACKEND_ADMIN_TOKEN", "")
    monkeypatch.setenv("TASKFRAME_BACKEND_OPERATOR_TOKEN", "")
    monkeypatch.setenv("TASKFRAME_BACKEND_VIEWER_TOKEN", "")

    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app)

    response = client.get("/api/runs")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    health = client.get("/api/health").json()
    assert health["auth"]["dev_bypass"] is True


def test_health_reports_auth_status_without_token_values(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app, headers=auth_headers("viewer"))

    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["backend"] == "ready"
    assert data["auth"]["enabled"] is True
    assert data["auth"]["dev_bypass"] is False
    assert data["auth"]["configured_roles"] == ["admin", "operator", "viewer"]
    text = response.text
    for token in ("test-admin-token", "test-operator-token", "test-viewer-token"):
        assert token not in text


def test_unknown_role_in_config_fails_safe(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        {
            "backend_auth": {
                "enabled": True,
                "allow_dev_bypass": False,
                "tokens": [
                    {"name": "bad-role", "token_env": "TASKFRAME_BACKEND_ADMIN_TOKEN", "role": "auditor"},
                ],
            }
        },
    )
    app = create_app(runtime_data_dir=str(tmp_path), backend_auth_config_path=str(config_path))
    client = TestClient(app, headers=auth_headers("admin"))

    response = client.get("/api/runs")

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_INVALID"


def test_empty_token_in_config_fails_safe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TASKFRAME_BACKEND_ADMIN_TOKEN", "")
    config_path = _write_config(
        tmp_path,
        {
            "backend_auth": {
                "enabled": True,
                "allow_dev_bypass": False,
                "tokens": [
                    {"name": "local-admin", "token_env": "TASKFRAME_BACKEND_ADMIN_TOKEN", "role": "admin"},
                ],
            }
        },
    )
    app = create_app(runtime_data_dir=str(tmp_path), backend_auth_config_path=str(config_path))
    client = TestClient(app, headers=auth_headers("admin"))

    response = client.get("/api/runs")

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_INVALID"


def test_backend_auth_config_loader_reports_roles(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        {
            "backend_auth": {
                "enabled": True,
                "allow_dev_bypass": False,
                "tokens": [
                    {"name": "local-admin", "token_env": "TASKFRAME_BACKEND_ADMIN_TOKEN", "role": "admin"},
                    {"name": "operator", "token_env": "TASKFRAME_BACKEND_OPERATOR_TOKEN", "role": "operator"},
                    {"name": "viewer", "token_env": "TASKFRAME_BACKEND_VIEWER_TOKEN", "role": "viewer"},
                ],
            }
        },
    )
    config = load_backend_auth_config(config_path)
    assert config.valid is True
    assert config.configured_roles == ["admin", "operator", "viewer"]
