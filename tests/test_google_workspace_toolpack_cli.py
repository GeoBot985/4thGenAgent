from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


TOOLPACK = Path("tool_packs/google_workspace/toolpack.json")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], capture_output=True, text=True, check=False)


def test_taskframe_tools_discover_exits_0() -> None:
    result = _run("tools", "discover")
    assert result.returncode == 0
    assert "google_workspace" in result.stdout.lower()


def test_taskframe_tools_discover_json_returns_valid_json() -> None:
    result = _run("tools", "discover", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert any(item["toolpack_id"] == "google_workspace" for item in payload["toolpacks"])


def test_taskframe_tools_list_reports_google_workspace() -> None:
    result = _run("tools", "list")
    assert result.returncode == 0
    assert "Google Workspace" in result.stdout or "google_workspace" in result.stdout.lower()


def test_taskframe_tools_list_json_returns_valid_json() -> None:
    result = _run("tools", "list", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "tools" in payload
    assert "toolpacks" in payload
    assert any(pack["toolpack_id"] == "google_workspace" for pack in payload["toolpacks"])


def test_taskframe_tools_inspect_toolpack_json_returns_metadata() -> None:
    result = _run("tools", "inspect", "toolpack:google_workspace", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["toolpack_id"] == "google_workspace"
    assert payload["name"] == "Google Workspace Read-Only Tool Pack"
    assert payload["health"]["toolpack_id"] == "google_workspace"


def test_taskframe_tools_inspect_tool_contract_json_returns_contract() -> None:
    result = _run("tools", "inspect", "gmail/list_unread", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["tool"] == "gmail/list_unread"
    assert payload["module"] == "tool_packs.google_workspace.tools"
    assert payload["function"] == "gmail_list_unread"
    assert payload["allow_live"] is True


def test_taskframe_tools_validate_google_workspace_pack_exits_0() -> None:
    result = _run("tools", "validate", str(TOOLPACK))
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_taskframe_tools_health_google_workspace_exits_0() -> None:
    result = _run("tools", "health", "google_workspace")
    assert result.returncode == 0
    assert "google_workspace" in result.stdout.lower()


def test_taskframe_tools_lifecycle_google_workspace_dev_json() -> None:
    result = _run("tools", "lifecycle", str(TOOLPACK), "--env", "dev", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["toolpack_id"] == "google_workspace"
    assert payload["environment"] == "dev"
    assert payload["status"] in {"READY", "READY_WITH_WARNINGS", "GOVERNANCE_REQUIRED", "UNTESTED", "DISABLED"}


def test_taskframe_tools_lifecycle_google_workspace_release_not_live_ready_by_default() -> None:
    result = _run("tools", "lifecycle", str(TOOLPACK), "--env", "release", "--json")
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["toolpack_id"] == "google_workspace"
    assert payload["environment"] == "release"
    assert payload["status"] in {"BLOCKED", "GOVERNANCE_REQUIRED", "DISABLED", "READY_WITH_WARNINGS"}
    assert payload["status"] != "READY"
