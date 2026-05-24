from __future__ import annotations

import pytest
from runtime.live_read_proof import build_live_read_status


def test_status_returns_dict():
    result = build_live_read_status()
    assert isinstance(result, dict)


def test_status_ok_true():
    result = build_live_read_status()
    assert result.get("ok") is True


def test_status_profile_field():
    result = build_live_read_status(profile="controlled_live_read")
    assert result.get("profile") == "controlled_live_read"


def test_status_profile_config_present():
    result = build_live_read_status()
    cfg = result.get("profile_config", {})
    assert isinstance(cfg, dict)
    assert cfg.get("allow_live_reads") is True
    assert cfg.get("allow_live_side_effects") is False


def test_status_live_side_effects_not_allowed():
    result = build_live_read_status()
    assert result.get("live_side_effects_allowed") is False


def test_status_rpa_not_allowed():
    result = build_live_read_status()
    assert result.get("rpa_allowed") is False


def test_status_credential_status_field():
    result = build_live_read_status()
    assert "credential_status" in result
    assert result["credential_status"] in ("needs_auth", "token_missing", "token_expired", "ready")


def test_status_allowed_read_tools():
    result = build_live_read_status()
    tools = result.get("allowed_read_tools", [])
    assert isinstance(tools, list)
    assert "gmail/search" in tools


def test_status_blocked_side_effect_tools():
    result = build_live_read_status()
    tools = result.get("blocked_side_effect_tools", [])
    assert isinstance(tools, list)
    assert "gmail/send" in tools


def test_status_no_credentials_safe():
    result = build_live_read_status()
    assert result.get("ok") is True
    assert result.get("credential_status") in ("needs_auth", "token_missing", "ready", "token_expired")


def test_status_latest_proof_path_field():
    result = build_live_read_status()
    assert "latest_proof_path" in result
    assert "latest_proof_available" in result
