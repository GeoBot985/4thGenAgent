from __future__ import annotations

import json
import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", "tools", *args], capture_output=True, text=True, check=False)


def test_taskframe_tools_inventory_exits_0() -> None:
    result = _run("inventory")
    assert result.returncode == 0
    assert "Tool inventory:" in result.stdout
    assert "Migrated tool-pack tools:" in result.stdout


def test_taskframe_tools_inventory_json_returns_valid_json() -> None:
    result = _run("inventory", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert "summary" in payload


def test_taskframe_tools_compat_check_exits_0() -> None:
    result = _run("compat-check")
    assert result.returncode == 0
    assert "Tool Registry Compatibility: PASS" in result.stdout
    assert "Migrated tool-pack tools:" in result.stdout


def test_taskframe_tools_compat_check_json_returns_valid_json() -> None:
    result = _run("compat-check", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert "new_tools" in payload

