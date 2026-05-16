"""Tests for taskframe tools governance CLI commands."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    import os
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
        env=env,
    )


@pytest.fixture(autouse=True)
def restore_governance():
    """Restore governance file after each test that might mutate it."""
    gov_path = ROOT / "config" / "toolpack_governance.json"
    original = gov_path.read_text(encoding="utf-8") if gov_path.is_file() else None
    yield
    if original is not None:
        gov_path.write_text(original, encoding="utf-8")
    elif gov_path.is_file():
        gov_path.unlink()


def test_policy_all_json_returns_list():
    result = _run("tools", "policy", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) > 0


def test_policy_single_pack_json():
    result = _run("tools", "policy", "core_business", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["toolpack_id"] == "core_business"
    assert data["classification"] == "core"


def test_policy_unknown_pack_returns_unknown():
    result = _run("tools", "policy", "nonexistent_pack_xyz", "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["classification"] == "unknown"
    assert data["governance_recorded"] is False


def test_enable_then_policy_reflects_change():
    _run("tools", "enable", "new_test_pack", "--classification", "optional", "--env", "dev", "--reason", "test")
    result = _run("tools", "policy", "new_test_pack", "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["classification"] == "optional"
    assert "dev" in data["enabled_environments"]


def test_enable_invalid_classification_fails():
    result = _run("tools", "enable", "some_pack", "--classification", "invalid_cls", "--env", "dev", "--json")
    assert result.returncode != 0


def test_disable_removes_pack_from_env():
    _run("tools", "enable", "dis_test_pack", "--classification", "optional", "--env", "dev,test")
    _run("tools", "disable", "dis_test_pack", "--env", "test")
    result = _run("tools", "policy", "dis_test_pack", "--json")
    data = json.loads(result.stdout)
    assert "test" not in data.get("enabled_environments", [])
    assert "dev" in data.get("enabled_environments", [])


def test_governance_report_json_ok():
    result = _run("tools", "governance-report", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert "by_classification" in data
    assert "by_environment" in data
    assert data["violations"] == []


def test_governance_report_text_output():
    result = _run("tools", "governance-report")
    assert result.returncode == 0
    assert "By Classification" in result.stdout
    assert "By Environment" in result.stdout


def test_policy_text_output_tabular():
    result = _run("tools", "policy")
    assert result.returncode == 0
    assert "core_business" in result.stdout
    assert "core" in result.stdout
