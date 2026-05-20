from __future__ import annotations

import json
import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], capture_output=True, text=True, check=False)


def test_profile_show_returns_structured_json() -> None:
    proc = _run("profile", "show", "--json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["profile"] == "demo"
    assert payload["fixture_mode"] is True
    assert "source" in payload
    assert "allowed_toolpacks" in payload
    assert "blocked_tool_classes" in payload
    assert "safe_for_demo" in payload
    assert "safe_for_pilot" in payload
    assert "safe_for_release" in payload


def test_profile_list_returns_profiles() -> None:
    proc = _run("profile", "list", "--json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    profiles = {item["profile"] for item in payload["profiles"]}
    assert profiles == {"demo", "dev", "test", "release", "pilot", "live"}


def test_profile_check_returns_valid_structured_output() -> None:
    proc = _run("profile", "check", "--json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["profile"] == "demo"
    assert "blockers" in payload
    assert isinstance(payload["blockers"], list)
