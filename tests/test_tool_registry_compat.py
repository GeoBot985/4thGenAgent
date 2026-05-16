from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_compatibility_check_passes_for_migrated_tools() -> None:
    from runtime.tool_registry import BUILTIN_LEGACY_TOOL_REGISTRY
    from src.tool_registry_compat import build_compatibility_registry, compare_legacy_and_toolpack_registry

    migrated_registry = build_compatibility_registry()
    result = compare_legacy_and_toolpack_registry(BUILTIN_LEGACY_TOOL_REGISTRY, migrated_registry)
    assert result["ok"] is True
    assert result["missing_tools"] == []
    assert result["changed_tools"] == []
    assert set(result["new_tools"]) == {"business/get_order_context", "memory/set", "q/extract_order_ref", "report/generate"}


def test_migrated_tool_cannot_become_less_safe_than_legacy_equivalent() -> None:
    from src.tool_registry_compat import compare_legacy_and_toolpack_registry

    legacy_registry = {
        "x/y": {
            "namespace": "x",
            "action": "y",
            "side_effect": False,
            "requires_approval": False,
            "allow_live_side_effect": False,
            "required_args": ["a"],
            "output_type": "x_result",
        }
    }
    migrated_registry = {
        "x/y": {
            "namespace": "x",
            "action": "y",
            "side_effect": True,
            "requires_approval": False,
            "allow_live_side_effect": False,
            "required_args": ["a"],
            "output_type": "x_result",
        }
    }
    result = compare_legacy_and_toolpack_registry(legacy_registry, migrated_registry)
    assert result["ok"] is False
    assert "x/y" in result["changed_tools"]


def test_missing_migrated_tool_is_reported_clearly() -> None:
    from src.tool_registry_compat import build_compatibility_registry, compare_legacy_and_toolpack_registry
    from runtime.tool_registry import BUILTIN_LEGACY_TOOL_REGISTRY

    migrated_registry = build_compatibility_registry()
    migrated_registry.pop("report/generate")
    result = compare_legacy_and_toolpack_registry(BUILTIN_LEGACY_TOOL_REGISTRY, migrated_registry)
    assert result["ok"] is False
    assert "report/generate" in result["missing_tools"]


def test_external_pack_cannot_override_migrated_built_in_tool(tmp_path: Path) -> None:
    from runtime.errors import ToolRegistryError
    from runtime.tool_registry import build_tool_registry

    descriptor = json.loads(Path("tool_packs/core_business/toolpack.json").read_text(encoding="utf-8"))
    descriptor["toolpack_id"] = "collision_pack"
    descriptor["core_or_optional"] = "optional"
    descriptor["tools"][0]["module"] = "tool_packs.core_business.tools"
    descriptor["tools"][0]["function"] = "business_get_order_context"
    pack_path = tmp_path / "toolpack.json"
    pack_path.write_text(json.dumps(descriptor, indent=2), encoding="utf-8")
    config_path = tmp_path / "enabled_toolpacks.json"
    config_path.write_text(
        json.dumps({"enabled_toolpacks": [str(pack_path)], "disabled_toolpacks": [], "allow_optional_toolpacks": True}, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ToolRegistryError):
        build_tool_registry(config_path=config_path)


def test_registry_still_exposes_expected_legacy_tool_keys() -> None:
    from runtime.tool_registry import TOOL_REGISTRY

    for tool_key in ["customer/prepare_message_action", "supplier/send_message", "sheet/write_rows", "file/write_json"]:
        assert tool_key in TOOL_REGISTRY


def test_registry_import_does_not_require_playwright() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", "import sys, runtime.tool_registry; print('playwright' in sys.modules)"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "False"
