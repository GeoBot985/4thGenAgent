from __future__ import annotations

import runtime.runtime_environment as runtime_env
from runtime.runtime_environment import check_runtime_profile, list_runtime_profiles, load_runtime_profile


def test_service_profile_loads_with_safe_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runtime_env, "RUNTIME_PROFILE_PATH", tmp_path / "runtime_profile.json", raising=False)

    profile = load_runtime_profile(profile_name="service")

    assert profile["profile"] == "service"
    assert profile["environment"] == "service"
    assert profile["fixture_mode"] is False
    assert profile["dry_run_default"] is True
    assert profile["allow_live_reads"] is False
    assert profile["allow_live_side_effects"] is False
    assert profile["require_tool_governance"] is True
    assert profile["evidence_required"] is True
    assert profile["requires_credentials"] is False
    assert profile["allowed_toolpacks"] == []
    assert profile["blocked_tool_classes"] == ["rpa", "write", "send", "delete", "mutation", "side_effect"]
    assert profile["worker_identity_required"] is True
    assert profile["reserved_for_deployment"] is True
    assert check_runtime_profile(profile)["ok"] is True


def test_runtime_profile_listing_includes_service(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runtime_env, "RUNTIME_PROFILE_PATH", tmp_path / "runtime_profile.json", raising=False)

    profiles = list_runtime_profiles()
    names = {item["profile"] for item in profiles}

    assert "service" in names
    service_profile = next(item for item in profiles if item["profile"] == "service")
    assert service_profile["worker_identity_required"] is True
    assert service_profile["reserved_for_deployment"] is True
