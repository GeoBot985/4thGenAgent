"""Tests for src/toolpack_governance.py — core enable/disable/policy functions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.toolpack_governance as gov


@pytest.fixture(autouse=True)
def isolated_governance(tmp_path, monkeypatch):
    """Redirect GOVERNANCE_PATH to a temp file so tests don't mutate config/."""
    tmp_gov = tmp_path / "toolpack_governance.json"
    monkeypatch.setattr(gov, "GOVERNANCE_PATH", tmp_gov)
    yield tmp_gov


def test_load_governance_missing_returns_empty():
    data = gov.load_governance()
    assert data["schema_version"] == 1
    assert data["entries"] == []


def test_enable_pack_creates_entry():
    result = gov.enable_pack("my_pack", classification="optional", environments=["dev", "test"], reason="Testing")
    assert result["ok"] is True
    assert result["toolpack_id"] == "my_pack"
    assert result["classification"] == "optional"
    assert "dev" in result["environments"]


def test_enable_pack_persists_to_file(isolated_governance):
    gov.enable_pack("persist_pack", classification="core", environments=["demo", "dev"])
    data = json.loads(isolated_governance.read_text(encoding="utf-8"))
    assert any(e["toolpack_id"] == "persist_pack" for e in data["entries"])


def test_enable_pack_updates_existing():
    gov.enable_pack("upd_pack", classification="optional", environments=["dev"])
    gov.enable_pack("upd_pack", classification="optional", environments=["dev", "test"], reason="Updated")
    policy = gov.get_pack_policy("upd_pack")
    assert "test" in policy["enabled_environments"]


def test_enable_pack_invalid_classification_fails():
    result = gov.enable_pack("bad_pack", classification="invalid", environments=["dev"])
    assert result["ok"] is False
    assert any("classification" in e for e in result["errors"])


def test_enable_pack_invalid_environment_fails():
    result = gov.enable_pack("bad_pack", classification="optional", environments=["prod"])
    assert result["ok"] is False
    assert any("Invalid environments" in e for e in result["errors"])


def test_enable_blocked_with_environments_fails():
    result = gov.enable_pack("bad_pack", classification="blocked", environments=["dev"])
    assert result["ok"] is False
    assert any("Blocked" in e for e in result["errors"])


def test_disable_pack_removes_environments():
    gov.enable_pack("dis_pack", classification="optional", environments=["dev", "test"])
    gov.disable_pack("dis_pack", environments=["test"])
    policy = gov.get_pack_policy("dis_pack")
    assert "test" not in policy["enabled_environments"]
    assert "dev" in policy["enabled_environments"]


def test_disable_pack_all_sets_blocked():
    gov.enable_pack("block_pack", classification="optional", environments=["dev"])
    gov.disable_pack("block_pack")
    policy = gov.get_pack_policy("block_pack")
    assert policy["classification"] == "blocked"
    assert policy["enabled_environments"] == []


def test_disable_unknown_pack_creates_blocked_entry():
    gov.disable_pack("never_seen", reason="Preemptive block")
    policy = gov.get_pack_policy("never_seen")
    assert policy["governance_recorded"] is True
    assert policy["classification"] == "blocked"


def test_get_pack_policy_missing_returns_unknown():
    policy = gov.get_pack_policy("does_not_exist")
    assert policy["governance_recorded"] is False
    assert policy["classification"] == "unknown"
    assert policy["errors"]


def test_check_pack_allowed_in_enabled_env():
    gov.enable_pack("allowed_pack", classification="optional", environments=["dev"])
    result = gov.check_pack_allowed("allowed_pack", "dev")
    assert result["allowed"] is True


def test_check_pack_not_allowed_in_disabled_env():
    gov.enable_pack("partial_pack", classification="optional", environments=["dev"])
    result = gov.check_pack_allowed("partial_pack", "test")
    assert result["allowed"] is False


def test_check_pack_blocked_not_allowed():
    gov.enable_pack("blk", classification="blocked", environments=[])
    result = gov.check_pack_allowed("blk", "dev")
    assert result["allowed"] is False


def test_check_pack_unknown_env_fails():
    result = gov.check_pack_allowed("any_pack", "prod")
    assert result["ok"] is False
    assert "Unknown environment" in result["reason"]


def test_get_all_policies_returns_list():
    gov.enable_pack("p1", classification="core", environments=["demo"])
    gov.enable_pack("p2", classification="optional", environments=["dev"])
    policies = gov.get_all_policies()
    ids = [p["toolpack_id"] for p in policies]
    assert "p1" in ids
    assert "p2" in ids
