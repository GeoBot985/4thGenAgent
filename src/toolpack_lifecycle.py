from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.taskframe import utc_now
from src.toolpack_contract_runner import run_toolpack_contract_tests
from src.toolpack_governance import check_pack_allowed, get_pack_policy
from src.toolpack_loader import (
    build_external_tool_capabilities,
    discover_toolpacks,
    load_toolpack_descriptor,
    validate_toolpack_descriptor,
)

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE_DIRNAME = Path("toolpacks") / "lifecycle"
ENVIRONMENTS = ("demo", "dev", "test", "release", "pilot", "live")
LIFECYCLE_STATUSES = {
    "UNKNOWN",
    "DISCOVERED",
    "INVALID",
    "UNTESTED",
    "GOVERNANCE_REQUIRED",
    "DISABLED",
    "READY",
    "READY_WITH_WARNINGS",
    "BLOCKED",
}


def evaluate_toolpack_lifecycle(
    toolpack_path: str | Path,
    *,
    environment: str = "dev",
    config_path: str | Path = "config/enabled_toolpacks.json",
    runtime_data_dir: str | Path = "runtime_data",
    include_contract_tests: bool = True,
    include_health: bool = True,
    include_manifest_smoke: bool = True,
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    path = _resolve_path(toolpack_path)
    env = str(environment or "dev").strip().lower()
    result: dict[str, Any] = {
        "ok": False,
        "toolpack_id": "",
        "environment": env,
        "status": "UNKNOWN",
        "generated_at": utc_now(),
        "toolpack_path": _display_path(path),
        "config_path": _display_path(_resolve_path(config_path)),
        "runtime_data_dir": _display_path(runtime_root),
        "stages": {},
        "stage_details": {},
        "errors": [],
        "warnings": [],
        "recommended_next_action": "Ensure the tool pack descriptor exists and can be loaded.",
    }

    if env not in ENVIRONMENTS:
        result["status"] = "INVALID"
        result["errors"].append(f"Unknown environment: {environment!r}")
        result["stage_details"]["discovered"] = _stage("FAIL", f"Unknown environment: {environment!r}")
        result["stages"] = {"discovered": "FAIL"}
        return result

    discovered = _load_discovery_state(path, config_path)
    result["toolpack_id"] = discovered.get("toolpack_id", "")
    result["stage_details"]["discovered"] = discovered["stage_details"]["discovered"]
    result["stages"]["discovered"] = discovered["stages"]["discovered"]
    result["warnings"].extend(discovered.get("warnings", []))
    result["errors"].extend(discovered.get("errors", []))
    if discovered["status"] != "DISCOVERED":
        result["status"] = discovered["status"]
        result["recommended_next_action"] = discovered["recommended_next_action"]
        result["ok"] = False
        return result

    descriptor = discovered["descriptor"]
    validation = validate_toolpack_descriptor(descriptor, base_path=path.parent)
    result["stage_details"]["descriptor_valid"] = _validation_stage(validation)
    result["stages"]["descriptor_valid"] = "PASS" if bool(validation.get("ok", False)) else "INVALID"
    result["warnings"].extend(list(validation.get("warnings", [])))
    result["errors"].extend(list(validation.get("errors", [])))
    if not bool(validation.get("ok", False)):
        result["status"] = "INVALID"
        result["recommended_next_action"] = "Fix descriptor validation errors."
        return result

    descriptor_data = dict(validation.get("descriptor", {}) or {})
    toolpack_id = str(validation.get("toolpack_id") or descriptor_data.get("toolpack_id") or result["toolpack_id"]).strip()
    result["toolpack_id"] = toolpack_id
    tool_count = int(validation.get("tool_count", 0) or 0)

    if include_contract_tests:
        contract = run_toolpack_contract_tests(path, runtime_data_dir=runtime_root, include_manifest_smoke=include_manifest_smoke)
        contract_ok = bool(contract.get("ok", False))
        result["stage_details"]["contract_test"] = contract
        result["stages"]["contract_test"] = "PASS" if contract_ok else "INVALID"
        result["warnings"].extend(list(contract.get("warnings", [])))
        result["errors"].extend(list(contract.get("errors", [])))
        if not contract_ok:
            result["status"] = "INVALID"
            result["recommended_next_action"] = "Fix contract test failures."
            return result
    else:
        result["stage_details"]["contract_test"] = _stage("UNTESTED", "Contract tests were skipped.")
        result["stages"]["contract_test"] = "UNTESTED"

    health_result: dict[str, Any] = {"ok": True, "status": "skipped", "message": "Health checks were skipped."}
    if include_health:
        from src.toolpack_loader import check_toolpack_health

        health_result = check_toolpack_health(toolpack_id, config_path=config_path, live=False)
        health_status = str(health_result.get("status", "")).strip().lower()
        health_ok = bool(health_result.get("ok", False))
        health_warn_ok = _toolpack_health_may_warn(descriptor, health_result)
        result["stage_details"]["health_check"] = health_result
        if health_status == "disabled":
            result["stages"]["health_check"] = "DISABLED"
            result["status"] = "DISABLED"
            result["recommended_next_action"] = "Re-enable the pack in configuration before running lifecycle checks."
            result["ok"] = False
            result["warnings"].extend(list(health_result.get("warnings", [])))
            result["errors"].extend(list(health_result.get("errors", [])))
            return result
        if health_ok or health_warn_ok:
            result["stages"]["health_check"] = "PASS"
            if health_warn_ok and not health_ok:
                result["warnings"].append(
                    f"Health check returned {health_status}; treating as a warning for optional read-only external pack."
                )
        else:
            result["stages"]["health_check"] = "INVALID"
        result["warnings"].extend(list(health_result.get("warnings", [])))
        result["errors"].extend(list(health_result.get("errors", [])))
        if not health_ok and not health_warn_ok:
            result["status"] = "INVALID"
            result["recommended_next_action"] = "Resolve the health check failure."
            return result
    else:
        result["stage_details"]["health_check"] = _stage("UNTESTED", "Health checks were skipped.")
        result["stages"]["health_check"] = "UNTESTED"

    governance = _evaluate_governance(toolpack_id, env, descriptor_data, path, config_path)
    result["stage_details"]["governance_policy"] = governance["stage_detail"]
    result["stages"]["governance_policy"] = governance["stage_status"]
    result["warnings"].extend(governance.get("warnings", []))
    result["errors"].extend(governance.get("errors", []))
    if governance["stage_status"] in {"BLOCKED"}:
        result["status"] = "BLOCKED"
        result["recommended_next_action"] = governance["recommended_next_action"]
        result["ok"] = False
        return result
    if governance["stage_status"] == "GOVERNANCE_REQUIRED":
        result["status"] = "GOVERNANCE_REQUIRED"
        result["recommended_next_action"] = governance["recommended_next_action"]
        result["ok"] = False
    if governance["stage_status"] == "DISABLED":
        result["status"] = "DISABLED"
        result["recommended_next_action"] = governance["recommended_next_action"]
        result["ok"] = False
        return result

    enablement = _evaluate_enablement(toolpack_id, env, path, config_path)
    result["stage_details"]["enabled_for_environment"] = enablement["stage_detail"]
    result["stages"]["enabled_for_environment"] = enablement["stage_status"]
    result["warnings"].extend(enablement.get("warnings", []))
    result["errors"].extend(enablement.get("errors", []))
    if enablement["stage_status"] == "DISABLED":
        result["status"] = "DISABLED"
        result["recommended_next_action"] = enablement["recommended_next_action"]
        result["ok"] = False
        return result
    if enablement["stage_status"] == "GOVERNANCE_REQUIRED":
        result["status"] = "GOVERNANCE_REQUIRED"
        result["recommended_next_action"] = enablement["recommended_next_action"]
        result["ok"] = False

    registry = _evaluate_registry_integration(toolpack_id, descriptor_data, config_path)
    result["stage_details"]["registry_integration"] = registry["stage_detail"]
    result["stages"]["registry_integration"] = registry["stage_status"]
    result["warnings"].extend(registry.get("warnings", []))
    result["errors"].extend(registry.get("errors", []))
    if registry["stage_status"] == "FAIL":
        result["status"] = "INVALID"
        result["recommended_next_action"] = "Ensure the tool pack is present in the runtime registry."
        return result

    manifest_smoke = _evaluate_example_manifest_smoke(path, include_manifest_smoke=include_manifest_smoke)
    result["stage_details"]["example_manifest_smoke"] = manifest_smoke["stage_detail"]
    result["stages"]["example_manifest_smoke"] = manifest_smoke["stage_status"]
    result["warnings"].extend(manifest_smoke.get("warnings", []))
    result["errors"].extend(manifest_smoke.get("errors", []))
    if manifest_smoke["stage_status"] == "FAIL":
        result["status"] = "INVALID"
        result["recommended_next_action"] = manifest_smoke["recommended_next_action"]
        return result

    if result["status"] not in {"GOVERNANCE_REQUIRED", "DISABLED", "BLOCKED"}:
        if any(status == "UNTESTED" for status in result["stages"].values()):
            result["status"] = "UNTESTED"
            result["recommended_next_action"] = "Run the skipped lifecycle checks."
        elif result["warnings"]:
            result["status"] = "READY_WITH_WARNINGS"
            result["recommended_next_action"] = "Tool pack is usable; review warnings before widening use."
        else:
            result["status"] = "READY"
            result["recommended_next_action"] = f"Tool pack is ready for {env} use."

    if result["status"] in {"READY", "READY_WITH_WARNINGS"}:
        result["ok"] = True
    else:
        result["ok"] = False

    result["summary"] = {
        "tool_count": tool_count,
        "enabled": bool(enablement.get("enabled", False)),
        "registered": bool(registry.get("registered", False)),
    }
    result["completed_at"] = utc_now()
    return result


def render_lifecycle_markdown(result: dict[str, Any]) -> str:
    stages = result.get("stages", {}) if isinstance(result, dict) else {}
    stage_details = result.get("stage_details", {}) if isinstance(result, dict) else {}
    lines = [
        "# Tool Pack Lifecycle Report",
        "",
        f"**Tool pack:** {result.get('toolpack_id', '')}",
        f"**Environment:** {result.get('environment', '')}",
        f"**Status:** {result.get('status', 'UNKNOWN')}",
        f"**Generated at:** {result.get('generated_at', '')}",
        "",
        "## Stages",
        "",
        "| Stage | Status |",
        "|---|---|",
    ]
    for key in _stage_order():
        if key in stages:
            lines.append(f"| {key} | {stages.get(key, '')} |")
    lines.extend(["", "## Recommended Next Action", "", str(result.get("recommended_next_action", "")), ""])

    if result.get("warnings"):
        lines.extend(["## Warnings", ""])
        for warning in result.get("warnings", []):
            lines.append(f"- {warning}")
        lines.append("")

    if result.get("errors"):
        lines.extend(["## Errors", ""])
        for error in result.get("errors", []):
            lines.append(f"- {error}")
        lines.append("")

    lines.extend(["## Stage Details", ""])
    for key in _stage_order():
        detail = stage_details.get(key)
        if detail is None:
            continue
        lines.append(f"### {key}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(detail, indent=2, ensure_ascii=False, default=str))
        lines.append("```")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_lifecycle_report(
    result: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    lifecycle_dir = runtime_root / LIFECYCLE_DIRNAME
    lifecycle_dir.mkdir(parents=True, exist_ok=True)
    toolpack_id = str(result.get("toolpack_id", "")).strip() or "unknown"
    json_path = lifecycle_dir / f"{toolpack_id}_lifecycle.json"
    markdown_path = lifecycle_dir / f"{toolpack_id}_lifecycle.md"
    payload = dict(result)
    payload["json_path"] = _display_path(json_path)
    payload["markdown_path"] = _display_path(markdown_path)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_path.write_text(render_lifecycle_markdown(payload), encoding="utf-8")
    return {
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "toolpack_id": toolpack_id,
    }


def _load_discovery_state(toolpack_path: Path, config_path: str | Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not toolpack_path.is_file():
        return {
            "status": "UNKNOWN",
            "toolpack_id": toolpack_path.parent.name,
            "errors": [f"Tool pack descriptor not found: {toolpack_path}"],
            "warnings": [],
            "recommended_next_action": "Create or restore the tool pack descriptor.",
            "stages": {"discovered": "UNKNOWN"},
            "stage_details": {"discovered": _stage("UNKNOWN", f"Tool pack descriptor not found: {toolpack_path}")},
        }

    if toolpack_path.name != "toolpack.json":
        errors.append("Descriptor file must be named toolpack.json.")
        return {
            "status": "UNKNOWN",
            "toolpack_id": toolpack_path.parent.name,
            "errors": errors,
            "warnings": warnings,
            "recommended_next_action": "Rename the descriptor to toolpack.json.",
            "stages": {"discovered": "UNKNOWN"},
            "stage_details": {"discovered": _stage("UNKNOWN", "Descriptor file must be named toolpack.json.")},
        }

    try:
        descriptor = load_toolpack_descriptor(toolpack_path)
    except Exception as exc:
        errors.append(str(exc))
        return {
            "status": "UNKNOWN",
            "toolpack_id": toolpack_path.parent.name,
            "errors": errors,
            "warnings": warnings,
            "recommended_next_action": "Fix descriptor JSON or path resolution errors.",
            "stages": {"discovered": "UNKNOWN"},
            "stage_details": {"discovered": _stage("UNKNOWN", str(exc))},
        }

    discovery = discover_toolpacks(config_path=config_path, include_disabled=True)
    descriptor_id = str(descriptor.get("toolpack_id", "")).strip()
    entry = _find_discovery_entry(discovery, toolpack_path, descriptor_id)
    stage_status = "PASS"
    try:
        from src.toolpack_loader import get_builtin_toolpack_path
    except Exception:
        get_builtin_toolpack_path = lambda _toolpack_id: None  # type: ignore[assignment]
    builtin_path = get_builtin_toolpack_path(descriptor_id)
    if entry is None and not (builtin_path and _resolve_path(builtin_path) == _resolve_path(toolpack_path)):
        warnings.append("Tool pack is not present in the enabled/disabled config list.")
    stage_detail = {
        "status": "PASS",
        "message": "Descriptor found and parsed.",
        "path": _display_path(toolpack_path),
        "toolpack_id": descriptor_id or toolpack_path.parent.name,
        "config_entry": entry or {},
    }
    return {
        "status": "DISCOVERED",
        "toolpack_id": descriptor_id or toolpack_path.parent.name,
        "descriptor": descriptor,
        "errors": errors,
        "warnings": warnings,
        "recommended_next_action": "Validate the descriptor and run contract tests.",
        "stages": {"discovered": stage_status},
        "stage_details": {"discovered": stage_detail},
    }


def _evaluate_governance(
    toolpack_id: str,
    environment: str,
    descriptor_data: dict[str, Any],
    toolpack_path: Path,
    config_path: str | Path,
) -> dict[str, Any]:
    policy = get_pack_policy(toolpack_id)
    allow = check_pack_allowed(toolpack_id, environment)
    classification = str(policy.get("classification", descriptor_data.get("risk_class", descriptor_data.get("core_or_optional", "unknown"))))
    enabled_envs = list(policy.get("enabled_environments", []))
    governance_recorded = bool(policy.get("governance_recorded", False))
    warnings: list[str] = []
    errors: list[str] = []

    if not governance_recorded:
        status = "GOVERNANCE_REQUIRED" if environment not in {"demo", "release", "live"} else "BLOCKED"
        message = "No governance entry found."
        if status == "BLOCKED":
            errors.append(message)
        else:
            warnings.append(message)
        return {
            "stage_status": status,
            "stage_detail": {
                "status": status,
                "message": message,
                "classification": classification,
                "enabled_environments": enabled_envs,
                "governance_recorded": governance_recorded,
                "policy": policy,
                "allowance": allow,
                "path": _display_path(toolpack_path),
            },
            "warnings": warnings,
            "errors": errors,
            "recommended_next_action": "Record a governance policy for this tool pack.",
        }

    if classification in {"blocked", "high_risk", "experimental"} and environment in {"demo", "release", "live"}:
        message = f"Pack classification {classification!r} is not allowed in {environment}."
        errors.append(message)
        return {
            "stage_status": "BLOCKED",
            "stage_detail": {
                "status": "BLOCKED",
                "message": message,
                "classification": classification,
                "enabled_environments": enabled_envs,
                "governance_recorded": governance_recorded,
                "policy": policy,
                "allowance": allow,
                "path": _display_path(toolpack_path),
            },
            "warnings": warnings,
            "errors": errors,
            "recommended_next_action": "Remove the pack from restricted environments or lower its risk classification.",
        }

    if allow.get("allowed"):
        return {
            "stage_status": "PASS",
            "stage_detail": {
                "status": "PASS",
                "message": allow.get("reason", "Pack is allowed."),
                "classification": classification,
                "enabled_environments": enabled_envs,
                "governance_recorded": governance_recorded,
                "policy": policy,
                "allowance": allow,
                "path": _display_path(toolpack_path),
            },
            "warnings": warnings,
            "errors": errors,
            "recommended_next_action": "Proceed with enablement checks.",
        }

    status = "GOVERNANCE_REQUIRED" if environment not in {"demo", "release", "live"} else "BLOCKED"
    message = str(allow.get("reason", "Pack is not enabled for this environment."))
    if status == "BLOCKED":
        errors.append(message)
    else:
        warnings.append(message)
    return {
        "stage_status": status,
        "stage_detail": {
            "status": status,
            "message": message,
            "classification": classification,
            "enabled_environments": enabled_envs,
            "governance_recorded": governance_recorded,
            "policy": policy,
            "allowance": allow,
            "path": _display_path(toolpack_path),
        },
        "warnings": warnings,
        "errors": errors,
        "recommended_next_action": "Enable the pack for the requested environment or adjust governance.",
    }


def _evaluate_enablement(
    toolpack_id: str,
    environment: str,
    toolpack_path: Path,
    config_path: str | Path,
) -> dict[str, Any]:
    discovery = discover_toolpacks(config_path=config_path, include_disabled=True)
    entry = _find_discovery_entry(discovery, toolpack_path, toolpack_id)
    policy = get_pack_policy(toolpack_id)
    enabled_envs = list(policy.get("enabled_environments", []))
    warnings: list[str] = []
    errors: list[str] = []
    try:
        from src.toolpack_loader import get_builtin_toolpack_path
    except Exception:
        get_builtin_toolpack_path = lambda _toolpack_id: None  # type: ignore[assignment]
    builtin_path = get_builtin_toolpack_path(toolpack_id)
    if builtin_path and _resolve_path(builtin_path) == _resolve_path(toolpack_path):
        return {
            "stage_status": "PASS",
            "stage_detail": {
                "status": "PASS",
                "message": "Built-in pack is enabled by default.",
                "entry": entry or {},
                "path": _display_path(toolpack_path),
                "enabled_environments": enabled_envs or list(ENVIRONMENTS),
                "builtin": True,
            },
            "warnings": warnings,
            "errors": errors,
            "recommended_next_action": "Proceed with registry integration checks.",
            "enabled": True,
        }
    if entry is None:
        message = "Tool pack is not present in the enabled tool pack config."
        status = "DISABLED" if environment in {"demo", "release", "live"} else "GOVERNANCE_REQUIRED"
        return {
            "stage_status": status,
            "stage_detail": {
                "status": status,
                "message": message,
                "entry": entry or {},
                "path": _display_path(toolpack_path),
                "enabled_environments": enabled_envs,
            },
            "warnings": warnings if status != "DISABLED" else [],
            "errors": [message] if status == "DISABLED" else [],
            "recommended_next_action": "Add the pack to config/enabled_toolpacks.json.",
            "enabled": False,
        }
    if not bool(entry.get("enabled", False)):
        message = "Tool pack is explicitly disabled."
        return {
            "stage_status": "DISABLED",
            "stage_detail": {
                "status": "DISABLED",
                "message": message,
                "entry": entry,
                "path": _display_path(toolpack_path),
                "enabled_environments": enabled_envs,
            },
            "warnings": warnings,
            "errors": [message],
            "recommended_next_action": "Remove the pack from the disabled list or re-enable it.",
            "enabled": False,
        }
    if str(environment) not in enabled_envs:
        message = f"Tool pack is not enabled for {environment}."
        status = "DISABLED" if environment in {"demo", "release", "live"} else "GOVERNANCE_REQUIRED"
        return {
            "stage_status": status,
            "stage_detail": {
                "status": status,
                "message": message,
                "entry": entry,
                "path": _display_path(toolpack_path),
                "enabled_environments": enabled_envs,
            },
            "warnings": warnings if status != "DISABLED" else [message],
            "errors": [message] if status == "DISABLED" else [],
            "recommended_next_action": "Enable the pack for the requested environment.",
            "enabled": True,
        }
    return {
        "stage_status": "PASS",
        "stage_detail": {
            "status": "PASS",
            "message": f"Enabled for {environment}.",
            "entry": entry,
            "path": _display_path(toolpack_path),
            "enabled_environments": enabled_envs,
        },
        "warnings": warnings,
        "errors": errors,
        "recommended_next_action": "Proceed with registry integration checks.",
        "enabled": True,
    }


def _evaluate_registry_integration(
    toolpack_id: str,
    descriptor_data: dict[str, Any],
    config_path: str | Path,
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    discovery = discover_toolpacks(config_path=config_path, include_disabled=True)
    entry = next((dict(item) for item in discovery.get("toolpacks", []) if isinstance(item, dict) and str(item.get("toolpack_id", "")).strip() == toolpack_id), None)
    discovered_ids = {str(item.get("toolpack_id", "")).strip() for item in discovery.get("toolpacks", [])}
    try:
        from src.toolpack_loader import get_builtin_toolpack_path
    except Exception:
        get_builtin_toolpack_path = lambda _toolpack_id: None  # type: ignore[assignment]
    builtin_path = get_builtin_toolpack_path(toolpack_id)
    if toolpack_id not in discovered_ids and not builtin_path:
        warnings.append("Tool pack is not discovered in config inventory.")
    try:
        from runtime.tool_registry import build_tool_registry
        from runtime.tool_capability_registry import list_tool_capabilities

        registry = build_tool_registry(include_external=True, config_path=config_path)
        capabilities = build_external_tool_capabilities(config_path=config_path)
        all_capabilities = list_tool_capabilities()
    except Exception as exc:
        return {
            "stage_status": "FAIL",
            "stage_detail": {"status": "FAIL", "message": f"Registry build failed: {exc}", "toolpack_id": toolpack_id},
            "warnings": warnings,
            "errors": [str(exc)],
            "recommended_next_action": "Fix the external tool registry build.",
        }

    declared_tools = [dict(item) for item in descriptor_data.get("tools", []) if isinstance(item, dict)]
    missing_tools = [str(item.get("tool", "")) for item in declared_tools if str(item.get("tool", "")).strip() not in registry]
    capability = next((item for item in capabilities if str(item.get("toolpack_id", "")) == toolpack_id), None)
    capability_entry = next((item for item in all_capabilities if str(item.toolpack_id or "").strip() == toolpack_id), None)
    runtime_capability = capability_entry.to_dict() if hasattr(capability_entry, "to_dict") else {}
    effective_capability = capability or runtime_capability
    registered = bool(entry and entry.get("registered", False)) or bool(runtime_capability.get("registered", False))
    if registered:
        ok = not missing_tools and bool(effective_capability)
    else:
        ok = bool(effective_capability)
    stage_status = "PASS" if ok else "FAIL"
    detail = {
        "status": stage_status,
        "message": "Registry integration verified." if ok else "Registry integration failed.",
        "toolpack_id": toolpack_id,
        "declared_tools": [str(item.get("tool", "")) for item in declared_tools],
        "missing_tools": missing_tools,
        "capability": effective_capability,
        "runtime_capability": runtime_capability,
        "registered": registered,
        "registry_source_count": len({str(spec.get("source", "")) for spec in registry.values()}),
        "registered_tools": sorted(k for k, spec in registry.items() if str(spec.get("toolpack_id", "")) == toolpack_id),
    }
    if not ok:
        errors.append("One or more declared tools are missing from the registry.")
    return {
        "stage_status": stage_status,
        "stage_detail": detail,
        "warnings": warnings,
        "errors": errors,
        "recommended_next_action": "Register the tool pack tools before enabling it.",
        "registered": bool(capability and not missing_tools),
    }


def _toolpack_health_may_warn(descriptor: dict[str, Any], health_result: dict[str, Any]) -> bool:
    status = str(health_result.get("status", "")).strip().lower()
    return (
        status in {"needs_auth", "missing_dependency"}
        and str(descriptor.get("core_or_optional", "")).strip() == "optional"
        and str(descriptor.get("risk_class", "")).strip() == "read_only_external_api"
    )


def _evaluate_example_manifest_smoke(
    toolpack_path: Path,
    *,
    include_manifest_smoke: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    if not include_manifest_smoke:
        return {
            "stage_status": "UNTESTED",
            "stage_detail": {"status": "UNTESTED", "message": "Example manifest smoke was skipped."},
            "warnings": warnings,
            "errors": [],
            "recommended_next_action": "Run manifest smoke validation when ready.",
        }

    examples_dir = toolpack_path.parent / "examples"
    if not examples_dir.is_dir():
        return {
            "stage_status": "PASS",
            "stage_detail": {"status": "PASS", "message": "No example manifests found.", "examples_dir": _display_path(examples_dir)},
            "warnings": warnings,
            "errors": [],
            "recommended_next_action": "Add example manifests to document expected usage.",
        }

    manifests = sorted(examples_dir.glob("*.manifest.json"))[:3]
    if not manifests:
        return {
            "stage_status": "PASS",
            "stage_detail": {"status": "PASS", "message": "No example manifests found.", "examples_dir": _display_path(examples_dir)},
            "warnings": warnings,
            "errors": [],
            "recommended_next_action": "Add example manifests to document expected usage.",
        }

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for manifest_path in manifests:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("Manifest root must be a JSON object.")
            missing = [field for field in ("manifest_id", "steps") if field not in manifest]
            if missing:
                raise ValueError(f"Missing required fields: {missing}")
            results.append({"manifest": manifest_path.name, "status": "PASS"})
        except Exception as exc:
            errors.append(f"{manifest_path.name}: {exc}")
            results.append({"manifest": manifest_path.name, "status": "FAIL", "error": str(exc)})

    ok = not errors
    return {
        "stage_status": "PASS" if ok else "FAIL",
        "stage_detail": {
            "status": "PASS" if ok else "FAIL",
            "message": f"Validated {len(manifests)} example manifest(s).",
            "examples_dir": _display_path(examples_dir),
            "manifests": results,
        },
        "warnings": warnings,
        "errors": errors,
        "recommended_next_action": "Fix example manifests before marking the pack ready." if not ok else "Example manifest smoke passed.",
    }


def _find_discovery_entry(discovery: dict[str, Any], toolpack_path: Path, toolpack_id: str) -> dict[str, Any] | None:
    candidate_path = _display_path(toolpack_path)
    for item in discovery.get("toolpacks", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("toolpack_id", "")) == toolpack_id:
            return dict(item)
        if _display_path(item.get("path", "")) == candidate_path:
            return dict(item)
    return None


def _validation_stage(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "PASS" if bool(validation.get("ok", False)) else "INVALID",
        "message": "Descriptor validation passed." if bool(validation.get("ok", False)) else "Descriptor validation failed.",
        "validation": validation,
    }


def _stage(status: str, message: str, **extra: Any) -> dict[str, Any]:
    payload = {"status": status, "message": message}
    payload.update(extra)
    return payload


def _stage_order() -> list[str]:
    return [
        "discovered",
        "descriptor_valid",
        "contract_test",
        "health_check",
        "governance_policy",
        "enabled_for_environment",
        "registry_integration",
        "example_manifest_smoke",
    ]


def _resolve_path(path: str | Path) -> Path:
    value = Path(path).expanduser()
    if value.is_absolute():
        return value
    candidate = (ROOT / value).resolve()
    return candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return candidate.as_posix()
