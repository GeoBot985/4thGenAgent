from __future__ import annotations

from pathlib import Path


def test_dependency_state_does_not_raise() -> None:
    from tool_packs.google_workspace import auth

    state = auth.google_dependency_state()
    assert "ok" in state
    assert "missing" in state


def test_missing_dependencies_return_structured_state(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, tools

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": False, "missing": ["googleapiclient.discovery"]})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": False, "token_file_present": False, "configured_services": [], "profile": "default", "config_dir": str(Path.home() / ".taskframe")})
    result = tools.google_auth_status()
    assert result["ok"] is False
    assert result["type"] == "google_auth_status"
    assert result["data"]["dependencies_ok"] is False
    assert result["data"]["configured_services"] == []
    assert result["error"] == "MISSING_GOOGLE_DEPENDENCIES"


def test_missing_credentials_return_needs_auth(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, tools

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": False, "token_file_present": False, "configured_services": [], "profile": "default", "config_dir": str(Path.home() / ".taskframe")})
    result = tools.google_auth_status()
    assert result["ok"] is False
    assert result["error"] == "GOOGLE_AUTH_NOT_CONFIGURED"


def test_auth_state_redaction_removes_secret_like_fields() -> None:
    from tool_packs.google_workspace import auth

    state = {
        "token_path": "C:/tmp/google_token.json",
        "credentials_path": "C:/tmp/credentials.json",
        "authorization": "Bearer secret-value",
        "nested": {"api_key": "abc123", "subject": "Quarterly Update"},
    }
    redacted = auth.redact_google_auth_state(state)
    assert redacted["token_path"] == "***REDACTED***"
    assert redacted["credentials_path"] == "***REDACTED***"
    assert redacted["authorization"] == "***REDACTED***"
    assert redacted["nested"]["api_key"] == "***REDACTED***"
    assert redacted["nested"]["subject"] == "Quarterly Update"


def test_static_auth_check_does_not_build_google_client(monkeypatch) -> None:
    from tool_packs.google_workspace import auth

    called = {"count": 0}

    def fake_build(*args, **kwargs):
        called["count"] += 1
        raise AssertionError("build_google_service should not be called")

    monkeypatch.setattr(auth, "build_google_service", fake_build)
    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": False, "token_file_present": False, "configured_services": [], "profile": "default", "config_dir": str(Path.home() / ".taskframe")})

    from tool_packs.google_workspace import tools

    result = tools.google_auth_status()
    assert result["ok"] is False
    assert called["count"] == 0
