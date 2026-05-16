from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.errors import ToolPackValidationError
from src.toolpack_loader import load_toolpack_descriptor, validate_toolpack_descriptor


ROOT = Path(__file__).resolve().parents[1]
CORE_TOOLPACK_PATHS: tuple[Path, ...] = (
    ROOT / "tool_packs" / "core_business" / "toolpack.json",
    ROOT / "tool_packs" / "core_memory" / "toolpack.json",
    ROOT / "tool_packs" / "core_llm_micro" / "toolpack.json",
    ROOT / "tool_packs" / "core_reports" / "toolpack.json",
)
EXPECTED_MIGRATED_TOOL_KEYS: tuple[str, ...] = (
    "business/get_order_context",
    "memory/set",
    "q/extract_order_ref",
    "report/generate",
)


def build_compatibility_registry() -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for path in CORE_TOOLPACK_PATHS:
        descriptor = load_toolpack_descriptor(path)
        validation = validate_toolpack_descriptor(descriptor, base_path=path.parent, validate_health=False)
        if not validation.get("ok", False):
            raise ToolPackValidationError(
                f"Core tool pack failed validation: {validation.get('toolpack_id', path.stem)} | "
                f"errors={validation.get('errors', [])}"
            )
        descriptor_data = validation.get("descriptor", {})
        toolpack_id = str(descriptor_data.get("toolpack_id", path.stem))
        for tool in descriptor_data.get("tools", []):
            tool_key = str(tool.get("tool", "")).strip()
            if not tool_key:
                continue
            if tool_key in registry:
                raise ToolPackValidationError(f"Duplicate migrated tool key: {tool_key}")
            registry[tool_key] = _decorate_tool_spec(tool, descriptor_data, path)
    return registry


def compare_legacy_and_toolpack_registry(
    legacy_registry: dict[str, dict[str, Any]],
    migrated_registry: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    missing_tools: list[str] = []
    new_tools: list[str] = []
    changed_tools: list[str] = []
    compatible_tools: list[str] = []
    warnings: list[str] = []

    for tool_key in EXPECTED_MIGRATED_TOOL_KEYS:
        if tool_key not in migrated_registry:
            missing_tools.append(tool_key)

    for tool_key, migrated_spec in migrated_registry.items():
        legacy_spec = legacy_registry.get(tool_key)
        if legacy_spec is None:
            new_tools.append(tool_key)
            compatible_tools.append(tool_key)
            warnings.append(f"Additive migrated tool: {tool_key}")
            continue
        if _tool_is_compatible(legacy_spec, migrated_spec):
            compatible_tools.append(tool_key)
        else:
            changed_tools.append(tool_key)

    ok = not changed_tools and not missing_tools
    return {
        "ok": ok,
        "missing_tools": missing_tools,
        "new_tools": new_tools,
        "changed_tools": changed_tools,
        "compatible_tools": compatible_tools,
        "warnings": warnings,
    }


def assert_registry_compatibility(
    legacy_registry: dict[str, dict[str, Any]],
    migrated_registry: dict[str, dict[str, Any]],
) -> None:
    result = compare_legacy_and_toolpack_registry(legacy_registry, migrated_registry)
    if not result["ok"]:
        raise ToolPackValidationError(
            "Tool registry compatibility failed: "
            f"missing={result['missing_tools']} changed={result['changed_tools']}"
        )


def build_builtin_toolpack_capabilities() -> list[dict[str, Any]]:
    capabilities: list[dict[str, Any]] = []
    for path in CORE_TOOLPACK_PATHS:
        descriptor = load_toolpack_descriptor(path)
        validation = validate_toolpack_descriptor(descriptor, base_path=path.parent, validate_health=False)
        descriptor_data = validation.get("descriptor", {})
        pack_id = str(descriptor_data.get("toolpack_id", path.stem))
        capabilities.append(
            {
                "tool_id": f"toolpack:{pack_id}",
                "name": str(descriptor_data.get("name", pack_id)),
                "display_name": str(descriptor_data.get("name", pack_id)),
                "category": "toolpack",
                "description": str(descriptor_data.get("description", "")),
                "core_or_optional": str(descriptor_data.get("core_or_optional", "core")),
                "side_effect_level": _toolpack_side_effect_level(descriptor_data),
                "auth_required": False,
                "auth_type": None,
                "setup_available": False,
                "setup_action": None,
                "rpa_live_probe_required": False,
                "excluded_from_default_release": False,
                "limitations": list(validation.get("warnings", [])),
                "source": "migrated_toolpack",
                "path": _display_path(path),
                "toolpack_id": pack_id,
                "enabled": True,
                "registered": True,
                "valid": bool(validation.get("ok", False)),
                "tool_count": int(validation.get("tool_count", 0) or 0),
            }
        )
    return capabilities


def _tool_is_compatible(legacy_spec: dict[str, Any], migrated_spec: dict[str, Any]) -> bool:
    if str(legacy_spec.get("namespace", "")) != str(migrated_spec.get("namespace", "")):
        return False
    if str(legacy_spec.get("action", "")) != str(migrated_spec.get("action", "")):
        return False
    if bool(migrated_spec.get("side_effect", False)) and not bool(legacy_spec.get("side_effect", False)):
        return False
    if bool(legacy_spec.get("requires_approval", False)) and not bool(migrated_spec.get("requires_approval", False)):
        return False
    if bool(legacy_spec.get("allow_live_side_effect", False)) and not bool(migrated_spec.get("allow_live_side_effect", False)):
        return False
    legacy_required = set(legacy_spec.get("required_args", []))
    migrated_required = set(migrated_spec.get("required_args", []))
    if not legacy_required.issubset(migrated_required):
        return False
    if not str(migrated_spec.get("output_type", "")).strip():
        return False
    return True


def _decorate_tool_spec(tool: dict[str, Any], descriptor_data: dict[str, Any], path: Path) -> dict[str, Any]:
    spec = dict(tool)
    spec["source"] = "migrated_toolpack"
    spec["toolpack_id"] = str(descriptor_data.get("toolpack_id", path.stem))
    spec["toolpack_name"] = str(descriptor_data.get("name", path.stem))
    spec["toolpack_version"] = str(descriptor_data.get("version", ""))
    spec["toolpack_path"] = _display_path(path)
    spec["toolpack_core_or_optional"] = str(descriptor_data.get("core_or_optional", "core"))
    spec["toolpack_registered"] = True
    return spec


def _toolpack_side_effect_level(descriptor_data: dict[str, Any]) -> str:
    tools = descriptor_data.get("tools", [])
    if any(bool(tool.get("side_effect", False)) for tool in tools if isinstance(tool, dict)):
        if any(bool(tool.get("allow_live_side_effect", False)) for tool in tools if isinstance(tool, dict)):
            return "high_risk"
        return "stateful"
    return "read_only"


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return path.as_posix()
