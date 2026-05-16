from __future__ import annotations


def test_health_missing_dependencies(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, health

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": False, "missing": ["googleapiclient.discovery"]})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": False, "token_file_present": False, "configured_services": [], "profile": "default", "config_dir": "."})
    result = health.check_health(live=False)
    assert result["status"] == "missing_dependency"
    assert result["ok"] is False


def test_health_needs_auth_when_files_missing(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, health

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": False, "token_file_present": False, "configured_services": [], "profile": "default", "config_dir": "."})
    result = health.check_health(live=False)
    assert result["status"] == "needs_auth"
    assert result["ok"] is False


def test_health_ready_without_live_probe(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, health

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": True, "token_file_present": True, "configured_services": ["gmail", "calendar", "sheets"], "profile": "default", "config_dir": "."})
    result = health.check_health(live=False)
    assert result["status"] == "ready"
    assert result["ok"] is True
    assert result["live_checked"] is False


def test_health_live_probe_only_runs_when_requested(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, health

    calls = {"count": 0}

    def fake_build(*args, **kwargs):
        calls["count"] += 1
        class _Service:
            def users(self):
                class _Users:
                    def getProfile(self, **kwargs):
                        class _Req:
                            def execute(self):
                                return {"emailAddress": "user@example.com"}
                        return _Req()
                return _Users()
        return _Service()

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": True, "token_file_present": True, "configured_services": ["gmail"], "profile": "default", "config_dir": "."})
    monkeypatch.setattr(auth, "build_google_service", fake_build)

    result = health.check_health(live=True, service="gmail")
    assert result["status"] == "live_verified"
    assert result["ok"] is True
    assert result["live_checked"] is True
    assert calls["count"] == 1


def test_health_result_does_not_expose_secret_contents(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, health

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": True, "token_file_present": True, "credentials_path": "C:/secret/credentials.json", "token_path": "C:/secret/token.json", "configured_services": ["gmail"], "profile": "default", "config_dir": "."})
    result = health.check_health(live=False)
    text = str(result)
    assert "token.json" not in text
    assert "credentials.json" not in text
    assert result["details"]["auth_files"]["credentials_path"] == "***REDACTED***"
    assert result["details"]["auth_files"]["token_path"] == "***REDACTED***"
