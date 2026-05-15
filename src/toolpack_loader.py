from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from runtime.errors import ToolPackHealthError, ToolPackLoadError, ToolPackValidationError


ROOT = Path(__file__).resolve().parents[1]
TOOLPACKS_DIR = ROOT / "tool_packs"
DEFAULT_CONFIG_PATH = ROOT / "config" / "enabled_toolpacks.json"
DEFAULT_CONFIG = {
    "enabled_toolpacks": [],
    "disabled_toolpacks": [],
    "allow_optional_toolpacks": False,
}


def load_toolpack_descriptor(path: str | Path) -> dict[str, Any]:
    toolpack_path = _resolve_path(path, ROOT)
    if not toolpack_path.is_file():
        raise ToolPackLoadError(f"Tool pack descriptor not found: {toolpack_path}")
    try:
        payload = json.loads(toolpack_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolPackLoadError(f"Invalid JSON in tool pack descriptor: {toolpack_path}") from exc
    except OSError as exc:
        raise ToolPackLoadError(f"Unable to read tool pack descriptor: {toolpack_path}") from exc
    if not isinstance(payload, dict):
        raise ToolPackValidationError("Tool pack descriptor root must be a JSON object.")
    payload.setdefault("_path", str(toolpack_path))
    return payload


def validate_toolpack_descriptor(descriptor: dict[str, Any], *, base_path: str | Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    base_dir = _resolve_path(base_path or ROOT, ROOT)
    toolpack_id = str(descriptor.get("toolpack_id", "")).strip()
    name = str(descriptor.get("name", "")).strip()
    version = str(descriptor.get("version", "")).strip()
    runtime_contract_version = descriptor.get("runtime_contract_version")
    core_or_optional = str(descriptor.get("core_or_optional", "")).strip()
    tools = descriptor.get("tools", [])
    health = descriptor.get("health", {})
    health_supported = bool(descriptor.get("health_supported", True))
    path = str(descriptor.get("_path", "")).strip()

    if not toolpack_id:
        errors.append("Missing toolpack_id.")
    if not name:
        errors.append("Missing name.")
    if not version:
        errors.append("Missing version.")
    if runtime_contract_version is None:
        errors.append("Missing runtime_contract_version.")
    else:
        try:
            if int(runtime_contract_version) != 1:
                errors.append("Unsupported runtime_contract_version.")
        except Exception:
            errors.append("runtime_contract_version must be an integer.")
    if core_or_optional not in {"core", "optional"}:
        errors.append("core_or_optional must be core or optional.")
    if not isinstance(tools, list) or not tools:
        errors.append("tools must be a non-empty list.")
    if not isinstance(health, dict):
        if health_supported:
            errors.append("health must be an object or health_supported must be false.")
        health = {}
    if not health_supported and health:
        warnings.append("health_supported is false; health metadata will be ignored.")
    if not health_supported and not health:
        warnings.append("Health checks are disabled for this tool pack.")
    if not path:
        warnings.append("Descriptor path is missing.")

    seen_keys: set[str] = set()
    resolved_tools: list[dict[str, Any]] = []
    for index, tool in enumerate(tools if isinstance(tools, list) else []):
        if not isinstance(tool, dict):
            errors.append(f"Tool entry {index} must be an object.")
            continue
        tool_key = str(tool.get("tool", "")).strip()
        namespace = str(tool.get("namespace", "")).strip()
        action = str(tool.get("action", "")).strip()
        module_name = str(tool.get("module", "")).strip()
        function_name = str(tool.get("function", "")).strip()
        output_type = str(tool.get("output_type", "")).strip()
        required_args = tool.get("required_args", [])
        optional_args = tool.get("optional_args", [])
        arg_types = tool.get("arg_types", {})
        side_effect = tool.get("side_effect", None)
        requires_approval = tool.get("requires_approval", None)
        allow_live = tool.get("allow_live", None)
        allow_live_side_effect = tool.get("allow_live_side_effect", None)
        live_guardrail = str(tool.get("live_guardrail", "")).strip()

        if not tool_key or "/" not in tool_key:
            errors.append(f"Tool entry {index} has malformed tool key.")
            continue
        if tool_key in seen_keys:
            errors.append(f"Duplicate tool key: {tool_key}")
        seen_keys.add(tool_key)
        if tool_key != f"{namespace}/{action}":
            errors.append(f"Tool key does not match namespace/action: {tool_key}")
        if not module_name:
            errors.append(f"Tool {tool_key} is missing module.")
        if not function_name:
            errors.append(f"Tool {tool_key} is missing function.")
        if not output_type:
            errors.append(f"Tool {tool_key} is missing output_type.")
        if side_effect is None:
            errors.append(f"Tool {tool_key} is missing side_effect.")
        if requires_approval is None:
            errors.append(f"Tool {tool_key} is missing requires_approval.")
        if allow_live is None:
            errors.append(f"Tool {tool_key} is missing allow_live.")
        if allow_live_side_effect is None:
            errors.append(f"Tool {tool_key} is missing allow_live_side_effect.")
        if not live_guardrail:
            errors.append(f"Tool {tool_key} is missing live_guardrail.")
        if not isinstance(required_args, list):
            errors.append(f"Tool {tool_key} required_args must be a list.")
        if not isinstance(optional_args, list):
            errors.append(f"Tool {tool_key} optional_args must be a list.")
        if not isinstance(arg_types, dict):
            errors.append(f"Tool {tool_key} arg_types must be an object.")
        if bool(side_effect) and not bool(requires_approval):
            errors.append(f"Tool {tool_key} is side-effecting and must require approval.")
        if bool(allow_live_side_effect):
            if not bool(allow_live):
                errors.append(f"Tool {tool_key} allowing live side effects must allow live execution.")
            if live_guardrail == "blocked":
                errors.append(f"Tool {tool_key} allowing live side effects must declare a live guardrail.")
        resolved_tools.append(
            {
                "tool": tool_key,
                "namespace": namespace,
                "action": action,
                "module": module_name,
                "function": function_name,
                "output_type": output_type,
                "required_args": list(required_args) if isinstance(required_args, list) else [],
                "optional_args": list(optional_args) if isinstance(optional_args, list) else [],
                "arg_types": dict(arg_types) if isinstance(arg_types, dict) else {},
                "side_effect": bool(side_effect),
                "requires_approval": bool(requires_approval),
                "allow_live": bool(allow_live),
                "allow_live_side_effect": bool(allow_live_side_effect),
                "live_guardrail": live_guardrail or "blocked",
            }
        )
        _validate_import_target(module_name, function_name, tool_key, base_dir, errors)

    if health_supported:
        health_module = str(health.get("module", "")).strip()
        health_function = str(health.get("function", "")).strip()
        if not health_module:
            errors.append("health.module is required when health_supported is true.")
        if not health_function:
            errors.append("health.function is required when health_supported is true.")
        if health_module and health_function:
            _validate_import_target(health_module, health_function, f"{toolpack_id}:health", base_dir, errors)

    return {
        "ok": not errors,
        "toolpack_id": toolpack_id,
        "tool_count": len(resolved_tools),
        "errors": errors,
        "warnings": warnings,
        "descriptor": {
            "toolpack_id": toolpack_id,
            "name": name,
            "version": version,
            "runtime_contract_version": runtime_contract_version,
            "core_or_optional": core_or_optional,
            "description": str(descriptor.get("description", "")).strip(),
            "module_prefix": str(descriptor.get("module_prefix", "")).strip(),
            "health": dict(health),
            "health_supported": health_supported,
            "tools": resolved_tools,
            "path": _display_path(path) if path else "",
        },
    }


def discover_toolpacks(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    include_disabled: bool = False,
) -> dict[str, Any]:
    config, config_file = _load_toolpack_config(config_path)
    enabled_paths = _normalize_pack_paths(config.get("enabled_toolpacks", []), config_file.parent)
    disabled_paths = _normalize_pack_paths(config.get("disabled_toolpacks", []), config_file.parent)
    allow_optional = bool(config.get("allow_optional_toolpacks", False))

    entries: list[dict[str, Any]] = []
    registered_tool_count = 0

    def add_entry(path: Path, enabled: bool) -> None:
        nonlocal registered_tool_count
        try:
            descriptor = load_toolpack_descriptor(path)
            validation = validate_toolpack_descriptor(descriptor, base_path=path.parent)
        except Exception as exc:
            descriptor = {}
            validation = {
                "ok": False,
                "toolpack_id": _guess_toolpack_id_from_path(path),
                "tool_count": 0,
                "errors": [str(exc)],
                "warnings": [],
                "descriptor": {},
            }
        descriptor_data = validation.get("descriptor", {}) if isinstance(validation, dict) else {}
        toolpack_id = str(validation.get("toolpack_id") or descriptor_data.get("toolpack_id") or _guess_toolpack_id_from_path(path))
        registered = bool(enabled and validation.get("ok") and _is_pack_allowed(descriptor_data, allow_optional))
        if registered:
            registered_tool_count += int(validation.get("tool_count", 0) or 0)
        entries.append(
            {
                "toolpack_id": toolpack_id,
                "path": _display_path(path),
                "enabled": enabled,
                "registered": registered,
                "valid": bool(validation.get("ok", False)),
                "tool_count": int(validation.get("tool_count", 0) or 0),
                "errors": list(validation.get("errors", [])),
                "warnings": list(validation.get("warnings", [])),
                "core_or_optional": str(descriptor_data.get("core_or_optional", "optional")),
                "allow_optional_toolpacks": allow_optional,
                "health_supported": bool(descriptor_data.get("health_supported", True)),
                "name": str(descriptor_data.get("name", toolpack_id)),
                "version": str(descriptor_data.get("version", "")),
            }
        )

    for path in enabled_paths:
        add_entry(path, True)
    if include_disabled:
        for path in disabled_paths:
            add_entry(path, False)

    enabled_count = sum(1 for item in entries if item["enabled"])
    disabled_count = sum(1 for item in entries if not item["enabled"])
    return {
        "ok": True,
        "enabled_count": enabled_count,
        "disabled_count": disabled_count,
        "registered_tool_count": registered_tool_count,
        "toolpacks": entries,
    }


def build_external_tool_registry(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, dict[str, Any]]:
    discovery = discover_toolpacks(config_path=config_path, include_disabled=False)
    registry: dict[str, dict[str, Any]] = {}
    for pack in discovery.get("toolpacks", []):
        if pack.get("enabled") and not pack.get("valid"):
            raise ToolPackValidationError(f"Enabled tool pack failed validation: {pack.get('toolpack_id', '')}")
        if not pack.get("enabled") or not pack.get("registered"):
            continue
        descriptor = load_toolpack_descriptor(pack["path"])
        validation = validate_toolpack_descriptor(descriptor, base_path=Path(pack["path"]).parent)
        descriptor_data = validation.get("descriptor", {})
        for tool in descriptor_data.get("tools", []):
            tool_key = str(tool.get("tool", "")).strip()
            spec = {
                "namespace": tool.get("namespace"),
                "action": tool.get("action"),
                "module": tool.get("module"),
                "function": tool.get("function"),
                "side_effect": tool.get("side_effect", False),
                "requires_approval": tool.get("requires_approval", False),
                "allow_live": tool.get("allow_live", False),
                "allow_live_side_effect": tool.get("allow_live_side_effect", False),
                "live_guardrail": tool.get("live_guardrail", "blocked"),
                "output_type": tool.get("output_type"),
                "required_args": list(tool.get("required_args", [])),
                "optional_args": list(tool.get("optional_args", [])),
                "arg_types": dict(tool.get("arg_types", {})),
                "dry_run_executes": bool(tool.get("dry_run_executes", False)),
                "source": "external_toolpack",
                "toolpack_id": descriptor_data.get("toolpack_id"),
                "toolpack_name": descriptor_data.get("name"),
                "toolpack_version": descriptor_data.get("version"),
                "toolpack_path": str(pack["path"]),
                "toolpack_core_or_optional": descriptor_data.get("core_or_optional", "optional"),
                "toolpack_registered": True,
            }
            if tool_key in registry:
                raise ToolPackValidationError(f"Duplicate external tool key: {tool_key}")
            registry[tool_key] = spec
    return registry


def build_external_tool_capabilities(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> list[dict[str, Any]]:
    discovery = discover_toolpacks(config_path=config_path, include_disabled=True)
    capabilities: list[dict[str, Any]] = []
    for pack in discovery.get("toolpacks", []):
        pack_id = str(pack.get("toolpack_id", "")).strip()
        if not pack_id:
            continue
        capabilities.append(
            {
                "tool_id": f"toolpack:{pack_id}",
                "name": str(pack.get("name", pack_id)),
                "display_name": str(pack.get("name", pack_id)),
                "category": "toolpack",
                "description": f"Tool pack: {pack.get('path', '')}",
                "core_or_optional": str(pack.get("core_or_optional", "optional")),
                "side_effect_level": _pack_side_effect_level(pack),
                "auth_required": False,
                "auth_type": None,
                "setup_available": False,
                "setup_action": None,
                "rpa_live_probe_required": False,
                "excluded_from_default_release": bool(not pack.get("registered", False) or pack.get("core_or_optional") == "optional"),
                "limitations": list(pack.get("warnings", [])),
                "source": "external_toolpack",
                "path": str(pack.get("path", "")),
                "toolpack_id": pack_id,
                "enabled": bool(pack.get("enabled", False)),
                "registered": bool(pack.get("registered", False)),
                "valid": bool(pack.get("valid", False)),
                "tool_count": int(pack.get("tool_count", 0) or 0),
            }
        )
    return capabilities


def check_toolpack_health(
    toolpack_id: str,
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    live: bool = False,
) -> dict[str, Any]:
    discovery = discover_toolpacks(config_path=config_path, include_disabled=True)
    entry = next((item for item in discovery.get("toolpacks", []) if str(item.get("toolpack_id", "")) == toolpack_id), None)
    if entry is None:
        return {
            "ok": False,
            "toolpack_id": toolpack_id,
            "status": "not_found",
            "severity": "warning",
            "message": "Tool pack not found.",
            "health_supported": False,
            "errors": ["Tool pack not found."],
            "warnings": [],
            "details": {},
        }

    if not entry.get("enabled"):
        return {
            "ok": False,
            "toolpack_id": toolpack_id,
            "status": "disabled",
            "severity": "info",
            "message": "Tool pack is disabled.",
            "health_supported": False,
            "errors": [],
            "warnings": ["Tool pack is disabled."],
            "details": dict(entry),
        }
    if not entry.get("valid"):
        return {
            "ok": False,
            "toolpack_id": toolpack_id,
            "status": "invalid",
            "severity": "error",
            "message": "Tool pack descriptor failed validation.",
            "health_supported": bool(entry.get("health_supported", False)),
            "errors": list(entry.get("errors", [])),
            "warnings": list(entry.get("warnings", [])),
            "details": dict(entry),
        }

    descriptor = load_toolpack_descriptor(entry["path"])
    validation = validate_toolpack_descriptor(descriptor, base_path=Path(entry["path"]).parent)
    descriptor_data = validation.get("descriptor", {})
    health = descriptor_data.get("health", {})
    health_supported = bool(descriptor_data.get("health_supported", True))
    if not health_supported:
        return {
            "ok": True,
            "toolpack_id": toolpack_id,
            "status": "not_run",
            "severity": "info",
            "message": "Tool pack health checks are not supported.",
            "health_supported": False,
            "errors": [],
            "warnings": list(validation.get("warnings", [])),
            "details": dict(entry),
        }
    try:
        module_name = str(health.get("module", "")).strip()
        function_name = str(health.get("function", "")).strip()
        module = importlib.import_module(module_name)
        func = getattr(module, function_name)
        result = func(live=live)
    except Exception as exc:
        raise ToolPackHealthError(f"Unable to run tool pack health check for {toolpack_id}: {exc}") from exc

    if isinstance(result, dict):
        payload = dict(result)
    else:
        payload = {
            "ok": bool(getattr(result, "ok", False)),
            "status": str(getattr(result, "status", "unknown")),
            "severity": str(getattr(result, "severity", "warning")),
            "message": str(getattr(result, "message", "")),
            "details": dict(getattr(result, "details", {}) or {}),
        }

    payload.setdefault("toolpack_id", toolpack_id)
    payload.setdefault("health_supported", True)
    payload.setdefault("warnings", [])
    payload.setdefault("errors", [])
    payload.setdefault("details", {})
    payload.setdefault("tool_count", int(validation.get("tool_count", 0) or 0))
    payload.setdefault("source", "external_toolpack")
    payload.setdefault("path", str(entry["path"]))
    payload.setdefault("enabled", True)
    payload.setdefault("registered", bool(entry.get("registered", False)))
    return payload


def _validate_import_target(module_name: str, function_name: str, tool_key: str, base_dir: Path, errors: list[str]) -> None:
    if not module_name or not function_name:
        return
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        errors.append(f"Tool {tool_key} module import failed: {exc}")
        return
    if not hasattr(module, function_name):
        errors.append(f"Tool {tool_key} function not found: {function_name}")


def _load_toolpack_config(config_path: str | Path) -> tuple[dict[str, Any], Path]:
    config_file = _resolve_path(config_path, ROOT)
    if not config_file.is_file():
        return dict(DEFAULT_CONFIG), config_file
    try:
        payload = json.loads(config_file.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_CONFIG), config_file
    if not isinstance(payload, dict):
        return dict(DEFAULT_CONFIG), config_file
    return {
        "enabled_toolpacks": list(payload.get("enabled_toolpacks", [])) if isinstance(payload.get("enabled_toolpacks", []), list) else [],
        "disabled_toolpacks": list(payload.get("disabled_toolpacks", [])) if isinstance(payload.get("disabled_toolpacks", []), list) else [],
        "allow_optional_toolpacks": bool(payload.get("allow_optional_toolpacks", False)),
    }, config_file


def _normalize_pack_paths(paths: list[Any], base_dir: Path) -> list[Path]:
    normalized: list[Path] = []
    for entry in paths:
        if not isinstance(entry, str) or not entry.strip():
            continue
        normalized.append(_resolve_path(entry, base_dir))
    return normalized


def _resolve_path(path: str | Path, base_dir: Path) -> Path:
    value = Path(path).expanduser()
    if value.is_absolute():
        return value
    candidate = base_dir / value
    if candidate.exists():
        return candidate
    return (ROOT / value).resolve()


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return candidate.as_posix()


def _guess_toolpack_id_from_path(path: Path) -> str:
    try:
        return path.parent.name
    except Exception:
        return str(path).rsplit("/", 2)[-2] if "/" in str(path) else str(path)


def _is_pack_allowed(descriptor_data: dict[str, Any], allow_optional: bool) -> bool:
    core_or_optional = str(descriptor_data.get("core_or_optional", "optional"))
    if core_or_optional == "core":
        return True
    return allow_optional


def _pack_side_effect_level(_pack: dict[str, Any]) -> str:
    return "none"
