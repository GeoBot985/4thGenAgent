from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


DEMO_TOOLPACK = Path("tool_packs/demo_echo/toolpack.json")


def _write_config(tmp_path: Path, *, enabled: list[str] | None = None, disabled: list[str] | None = None, allow_optional: bool = False) -> Path:
    payload = {
        "enabled_toolpacks": enabled or [],
        "disabled_toolpacks": disabled or [],
        "allow_optional_toolpacks": allow_optional,
    }
    path = tmp_path / "enabled_toolpacks.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_toolpack(tmp_path: Path, descriptor: dict, filename: str = "toolpack.json") -> Path:
    path = tmp_path / filename
    path.write_text(json.dumps(descriptor, indent=2), encoding="utf-8")
    return path


def test_built_in_registry_still_loads() -> None:
    from runtime.tool_registry import build_tool_registry

    registry = build_tool_registry(include_external=False)
    assert "g/check" in registry
    assert "sheet/write" in registry


def test_external_demo_echo_tool_appears_when_enabled(tmp_path: Path) -> None:
    from runtime.tool_registry import build_tool_registry

    config_path = _write_config(tmp_path, enabled=[str(DEMO_TOOLPACK)], allow_optional=True)
    registry = build_tool_registry(include_external=True, config_path=config_path)
    assert "echo/echo" in registry
    assert registry["echo/echo"]["source"] == "external_toolpack"


def test_external_tool_cannot_override_built_in_tool(tmp_path: Path) -> None:
    from runtime.errors import ToolRegistryError
    from runtime.tool_registry import build_tool_registry

    descriptor = json.loads(DEMO_TOOLPACK.read_text(encoding="utf-8"))
    descriptor["toolpack_id"] = "collision_pack"
    descriptor["tools"][0]["tool"] = "g/check"
    descriptor["tools"][0]["namespace"] = "g"
    descriptor["tools"][0]["action"] = "check"
    descriptor["tools"][0]["module"] = "tool_packs.demo_echo.tools"
    descriptor["tools"][0]["function"] = "echo"
    pack_path = _write_toolpack(tmp_path, descriptor)
    config_path = _write_config(tmp_path, enabled=[str(pack_path)], allow_optional=True)

    with pytest.raises(ToolRegistryError):
        build_tool_registry(include_external=True, config_path=config_path)


def test_disabled_pack_does_not_register(tmp_path: Path) -> None:
    from runtime.tool_registry import build_tool_registry

    config_path = _write_config(tmp_path, disabled=[str(DEMO_TOOLPACK)], allow_optional=True)
    registry = build_tool_registry(include_external=True, config_path=config_path)
    assert "echo/echo" not in registry


def test_optional_pack_does_not_register_when_not_enabled(tmp_path: Path) -> None:
    from src.toolpack_loader import build_external_tool_registry

    config_path = _write_config(tmp_path, enabled=[str(DEMO_TOOLPACK)], allow_optional=False)
    registry = build_external_tool_registry(config_path=config_path)
    assert registry == {}


def test_registry_import_does_not_import_optional_rpa_dependencies() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, runtime.tool_registry; print('playwright' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "False"
