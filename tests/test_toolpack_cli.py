from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


DEMO_TOOLPACK = Path("tool_packs/demo_echo/toolpack.json")


def _write_config(tmp_path: Path, *, enabled: list[str] | None = None, allow_optional: bool = True) -> Path:
    payload = {
        "enabled_toolpacks": enabled or [],
        "disabled_toolpacks": [],
        "allow_optional_toolpacks": allow_optional,
    }
    path = tmp_path / "enabled_toolpacks.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], capture_output=True, text=True, check=False)


def test_taskframe_tools_discover_exits_0(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, enabled=[str(DEMO_TOOLPACK)], allow_optional=True)
    result = _run("tools", "discover", "--config-path", str(config_path))
    assert result.returncode == 0
    assert "Tool pack discovery:" in result.stdout
    assert "Registered external tools:" in result.stdout


def test_taskframe_tools_discover_json_returns_valid_json(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, enabled=[str(DEMO_TOOLPACK)], allow_optional=True)
    result = _run("tools", "discover", "--config-path", str(config_path), "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["enabled_count"] == 1
    assert payload["registered_tool_count"] == 3


def test_taskframe_tools_list_includes_echo_tool(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, enabled=[str(DEMO_TOOLPACK)], allow_optional=True)
    result = _run("tools", "list", "--config-path", str(config_path))
    assert result.returncode == 0
    assert "echo/echo" in result.stdout


def test_taskframe_tools_inspect_shows_contract_fields(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, enabled=[str(DEMO_TOOLPACK)], allow_optional=True)
    result = _run("tools", "inspect", "echo/echo", "--config-path", str(config_path), "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["tool"] == "echo/echo"
    assert payload["module"] == "tool_packs.demo_echo.tools"
    assert payload["function"] == "echo"
    assert payload["source"] == "external_toolpack"


def test_taskframe_tools_validate_demo_echo_pack_exits_0() -> None:
    result = _run("tools", "validate", str(DEMO_TOOLPACK))
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_taskframe_tools_validate_invalid_descriptor_returns_failure(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad_toolpack.json"
    bad_path.write_text(
        json.dumps(
            {
                "toolpack_id": "bad",
                "name": "Bad Pack",
                "version": "1.0.0",
                "runtime_contract_version": 1,
                "core_or_optional": "optional",
                "module_prefix": "tool_packs.bad",
                "health": {"module": "tool_packs.demo_echo.health", "function": "check_health"},
                "tools": [
                    {
                        "tool": "badkey",
                        "namespace": "bad",
                        "action": "key",
                        "function": "echo",
                        "side_effect": False,
                        "requires_approval": False,
                        "allow_live": False,
                        "allow_live_side_effect": False,
                        "live_guardrail": "blocked",
                        "output_type": "bad_result",
                        "required_args": [],
                        "optional_args": [],
                        "arg_types": {},
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    result = _run("tools", "validate", str(bad_path))
    assert result.returncode != 0
    assert "FAIL" in result.stdout or "Errors:" in result.stdout


def test_taskframe_tools_health_demo_echo_exits_0(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, enabled=[str(DEMO_TOOLPACK)], allow_optional=True)
    result = _run("tools", "health", "demo_echo", "--config-path", str(config_path))
    assert result.returncode == 0
    assert "Status: ready" in result.stdout or "Status: ready" in result.stdout.lower()
