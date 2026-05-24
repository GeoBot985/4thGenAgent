from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from runtime.event_router import EventRouter
from runtime.manifest_loader import load_manifest_catalog
from runtime.operational_monitoring import load_run_health_index
from runtime.persistence import ensure_dir, write_json_atomic
from runtime.runtime_environment import check_runtime_profile, load_runtime_profile
from runtime.tool_registry import TOOL_REGISTRY
from runtime.worker.worker_contract import DEFAULT_WORKER_CONFIG
from runtime.worker.worker_engine import build_worker_status, run_worker_once
from runtime.worker_identity import build_worker_identity, generate_runtime_instance_id, validate_worker_identity
from src.toolpack_loader import build_external_tool_registry, discover_toolpacks
from src.config_profiles import load_config_profile


ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR_NAME = "service"
SERVICE_PREFLIGHT_JSON = "service_preflight_latest.json"
SERVICE_PREFLIGHT_MD = "service_preflight_latest.md"
SERVICE_STATUS_JSON = "service_status_latest.json"
SERVICE_CYCLE_JSON = "service_cycle_latest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_service_preflight(
    *,
    profile_name: str = "service",
    runtime_data_dir: str | Path = "runtime_data",
    config_dir: str | Path | None = None,
    manifest_dir: str | Path = "manifests",
    routes_path: str | Path = "config/event_routes.json",
    toolpack_config_path: str | Path = "config/examples/taskframe.service.toolpacks.example.json",
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    service_dir = _service_dir(runtime_root)
    profile = load_runtime_profile(profile_name=profile_name)
    config = load_config_profile(profile_name=profile_name, config_dir=config_dir, runtime_data_dir=runtime_root)
    raw_identity = config.raw.get("worker_identity") or {}
    identity_error = ""
    raw_worker_id_present = bool(str(raw_identity.get("worker_id", "")).strip()) if isinstance(raw_identity, dict) else False
    try:
        identity = _build_service_identity(raw_identity, profile=profile)
    except Exception as exc:
        identity = _coerce_service_identity(raw_identity, profile=profile)
        identity_error = str(exc)

    checks: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    warnings: list[str] = []

    def add_check(check_id: str, ok: bool, message: str = "", *, data: dict[str, Any] | None = None) -> None:
        checks.append(
            {
                "id": check_id,
                "status": "PASS" if ok else "FAIL",
                "message": message,
                "data": dict(data or {}),
            }
        )
        if not ok:
            blockers.append({"id": check_id, "message": message, "data": dict(data or {})})

    add_check("profile_exists", bool(profile.get("profile")), "Runtime profile resolved.")
    add_check("service_profile_required", profile.get("profile") == "service", "Service commands require the service runtime profile.")
    add_check("profile_not_live", profile.get("profile") != "live", "Live profile must stay reserved.")
    add_check("dry_run_default", bool(profile.get("dry_run_default", False)), "Service profile must default to dry-run.")
    add_check("live_reads_disabled", not bool(profile.get("allow_live_reads", True)), "Service profile must not allow live reads.")
    add_check("live_side_effects_disabled", not bool(profile.get("allow_live_side_effects", True)), "Service profile must not allow live side effects.")
    add_check("tool_governance_required", bool(profile.get("require_tool_governance", False)), "Tool governance is required.")
    add_check("evidence_required", bool(profile.get("evidence_required", False)), "Evidence is required.")
    add_check("worker_identity_required", bool(profile.get("worker_identity_required", False)), "Worker identity metadata is required.")
    add_check("reserved_for_deployment", bool(profile.get("reserved_for_deployment", False)), "Service profile is reserved for deployment use.")
    add_check("config_worker_identity_present", raw_worker_id_present, "Worker identity is present.", data=identity)
    add_check("config_worker_identity_valid", raw_worker_id_present and not identity_error and validate_worker_identity(identity)["ok"], "Worker identity contract is valid.", data=identity)
    add_check("runtime_data_writable", _assert_runtime_data_writable(service_dir), f"Writable: {service_dir}")

    try:
        manifest_catalog = load_manifest_catalog(manifest_dir)
        add_check("manifest_catalog_loads", True, "Manifest catalog loaded.", data={"manifest_count": len(manifest_catalog)})
    except Exception as exc:
        add_check("manifest_catalog_loads", False, f"Manifest catalog failed to load: {exc}")

    try:
        tool_registry = dict(TOOL_REGISTRY)
        add_check("tool_registry_loads", bool(tool_registry), "Tool registry loaded.", data={"tool_count": len(tool_registry)})
    except Exception as exc:
        add_check("tool_registry_loads", False, f"Tool registry failed to load: {exc}")
        tool_registry = {}

    try:
        routes = EventRouter(routes_path=routes_path, manifest_dir=manifest_dir).load_routes()
        add_check("event_routes_load", True, "Event routes loaded.", data={"route_count": len(routes)})
    except Exception as exc:
        add_check("event_routes_load", False, f"Event routes failed to load: {exc}")

    if bool(config.optional_rpa_enabled) or bool(config.rpa_enabled):
        add_check("optional_rpa_blocked", False, "Optional RPA must remain disabled in service mode.", data={"rpa_enabled": config.rpa_enabled, "optional_rpa_enabled": config.optional_rpa_enabled})
    else:
        add_check("optional_rpa_blocked", True, "Optional RPA is disabled.")

    repo_root_credentials = _repo_root_credentials(config)
    add_check("repo_root_credentials_blocked", not repo_root_credentials, "Repository-root credentials are not allowed.", data={"paths": repo_root_credentials})

    try:
        external_registry = build_external_tool_registry(config_path=toolpack_config_path)
        add_check("external_tool_registry_loads", True, "External tool registry loaded.", data={"tool_count": len(external_registry)})
    except Exception as exc:
        add_check("external_tool_registry_loads", False, f"External tool registry failed to load: {exc}")
        external_registry = {}

    discovery = discover_toolpacks(config_path=toolpack_config_path, include_disabled=True)
    enabled_toolpacks = []
    enabled_unregistered: list[str] = []
    enabled_invalid: list[str] = []
    for item in discovery.get("toolpacks", []):
        if not isinstance(item, dict) or not item.get("enabled"):
            continue
        toolpack_id = str(item.get("toolpack_id", "") or "")
        if toolpack_id:
            enabled_toolpacks.append(toolpack_id)
        if not item.get("valid", False):
            enabled_invalid.append(toolpack_id or str(item.get("path", "")))
        if not item.get("registered", False):
            enabled_unregistered.append(toolpack_id or str(item.get("path", "")))
    add_check("no_unknown_external_toolpacks", not enabled_invalid and not enabled_unregistered, "Enabled external toolpacks must be valid and registered.", data={"enabled_toolpacks": enabled_toolpacks, "invalid": enabled_invalid, "unregistered": enabled_unregistered})

    check_runtime = check_runtime_profile(profile)
    add_check("runtime_profile_policy_ok", bool(check_runtime.get("ok", False)), "Runtime profile policy check passed.", data=check_runtime)

    result = {
        "ok": not blockers,
        "profile": str(profile.get("profile", "")),
        "worker_identity": identity,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "runtime_data_dir": str(runtime_root),
        "service_dir": str(service_dir),
        "config_dir": str(config_dir) if config_dir else "",
        "manifest_dir": str(manifest_dir),
        "routes_path": str(routes_path),
        "toolpack_config_path": str(toolpack_config_path),
        "enabled_toolpacks": enabled_toolpacks,
        "config_profile": _config_profile_summary(config, identity),
        "runtime_profile": profile,
        "runtime_profile_policy": check_runtime,
    }
    return result


def write_service_preflight_report(result: dict[str, Any], *, runtime_data_dir: str | Path = "runtime_data") -> dict[str, str]:
    service_dir = _service_dir(runtime_data_dir)
    json_path = service_dir / SERVICE_PREFLIGHT_JSON
    md_path = service_dir / SERVICE_PREFLIGHT_MD
    write_json_atomic(json_path, result)
    md_path.write_text(_render_preflight_markdown(result), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def build_service_status(
    *,
    profile_name: str = "service",
    runtime_data_dir: str | Path = "runtime_data",
    config_dir: str | Path | None = None,
    manifest_dir: str | Path = "manifests",
    routes_path: str | Path = "config/event_routes.json",
    toolpack_config_path: str | Path = "config/examples/taskframe.service.toolpacks.example.json",
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    service_dir = _service_dir(runtime_root)
    profile = load_runtime_profile(profile_name=profile_name)
    config = load_config_profile(profile_name=profile_name, config_dir=config_dir, runtime_data_dir=runtime_root)
    raw_identity = config.raw.get("worker_identity") or {}
    try:
        identity = _build_service_identity(raw_identity, profile=profile)
    except Exception:
        identity = _coerce_service_identity(raw_identity, profile=profile)
    preflight_path = service_dir / SERVICE_PREFLIGHT_JSON
    cycle_path = service_dir / SERVICE_CYCLE_JSON

    worker_status = build_worker_status(runtime_root)
    try:
        monitoring_snapshot = _compact_monitoring_snapshot(load_run_health_index(runtime_root))
    except Exception:
        monitoring_snapshot = {}
    recovery_summary = _load_latest_recovery_summary(runtime_root)
    discovery = discover_toolpacks(config_path=toolpack_config_path, include_disabled=True)
    enabled_toolpacks = [
        str(item.get("toolpack_id", "") or "")
        for item in discovery.get("toolpacks", [])
        if isinstance(item, dict) and item.get("enabled") and item.get("registered", False) and item.get("valid", False)
    ]

    payload = {
        "ok": True,
        "profile": str(profile.get("profile", "")),
        "environment": str(profile.get("environment", "")),
        "runtime_data_dir": str(runtime_root),
        "service_dir": str(service_dir),
        "worker_identity": identity,
        "live_read_status": "blocked" if not bool(profile.get("allow_live_reads", False)) else "ready",
        "live_side_effect_status": "blocked" if not bool(profile.get("allow_live_side_effects", False)) else "ready",
        "allow_live_reads": bool(profile.get("allow_live_reads", False)),
        "allow_live_side_effects": bool(profile.get("allow_live_side_effects", False)),
        "enabled_toolpacks": enabled_toolpacks,
        "last_worker_cycle": worker_status.get("last_cycle") or worker_status.get("last_cycle_summary") or {},
        "worker_status": worker_status,
        "latest_monitoring_snapshot": monitoring_snapshot,
        "latest_recovery_summary": recovery_summary,
        "latest_preflight_report": _read_json_if_exists(preflight_path),
        "latest_service_cycle": _read_json_if_exists(cycle_path),
        "manifest_dir": str(manifest_dir),
        "routes_path": str(routes_path),
        "toolpack_config_path": str(toolpack_config_path),
    }
    return payload


def write_service_status_report(result: dict[str, Any], *, runtime_data_dir: str | Path = "runtime_data") -> dict[str, str]:
    service_dir = _service_dir(runtime_data_dir)
    json_path = service_dir / SERVICE_STATUS_JSON
    write_json_atomic(json_path, result)
    return {"json": str(json_path)}


def run_service_once(
    *,
    profile_name: str = "service",
    runtime_data_dir: str | Path = "runtime_data",
    config_dir: str | Path | None = None,
    manifest_dir: str | Path = "manifests",
    routes_path: str | Path = "config/event_routes.json",
    toolpack_config_path: str | Path = "config/examples/taskframe.service.toolpacks.example.json",
    queue_limit: int = 10,
    no_scheduler: bool = False,
    no_event_sources: bool = False,
) -> dict[str, Any]:
    preflight = build_service_preflight(
        profile_name=profile_name,
        runtime_data_dir=runtime_data_dir,
        config_dir=config_dir,
        manifest_dir=manifest_dir,
        routes_path=routes_path,
        toolpack_config_path=toolpack_config_path,
    )
    write_service_preflight_report(preflight, runtime_data_dir=runtime_data_dir)
    if not preflight.get("ok"):
        return {
            "ok": False,
            "profile": preflight.get("profile", profile_name),
            "worker_identity": preflight.get("worker_identity", {}),
            "preflight": preflight,
            "worker_cycle": {},
            "service_cycle_record_path": "",
            "blockers": list(preflight.get("blockers", [])),
            "warnings": list(preflight.get("warnings", [])),
        }

    worker_identity = dict(preflight.get("worker_identity") or {})
    worker_id = str(worker_identity.get("worker_id", "") or "service-worker")
    config = {
        **DEFAULT_WORKER_CONFIG,
        "worker_id": worker_id,
        "mode": "run_once",
        "runtime_data_dir": str(runtime_data_dir),
        "frame_metadata": {"worker_identity": worker_identity},
        "features": {
            "recover_stale_queue": True,
            "run_scheduler_tick": not no_scheduler,
            "poll_event_sources": not no_event_sources,
            "process_queue": True,
        },
        "limits": {
            **DEFAULT_WORKER_CONFIG.get("limits", {}),
            "max_queue_items_per_cycle": int(queue_limit),
        },
        "safety": {
            **DEFAULT_WORKER_CONFIG.get("safety", {}),
            "dry_run_only": True,
            "allow_live_side_effects": False,
        },
    }
    worker_cycle = run_worker_once(config, runtime_data_dir=runtime_data_dir)
    worker_cycle["worker_identity"] = worker_identity
    service_cycle = {
        "ok": bool(worker_cycle.get("ok", False)) and bool(preflight.get("ok", False)),
        "profile": preflight.get("profile", profile_name),
        "worker_identity": worker_identity,
        "preflight": preflight,
        "worker_cycle": worker_cycle,
        "runtime_data_dir": str(runtime_data_dir),
        "generated_at": _utc_now(),
    }
    cycle_path = _service_dir(runtime_data_dir) / SERVICE_CYCLE_JSON
    write_json_atomic(cycle_path, service_cycle)
    service_cycle["service_cycle_record_path"] = str(cycle_path)
    return service_cycle


def _build_service_identity(raw_identity: dict[str, Any], *, profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_identity, dict):
        raw_identity = {}
    environment = str(profile.get("environment", "service") or "service")
    try:
        return build_worker_identity(
            raw_identity,
            environment=environment,
            operator_id=raw_identity.get("operator_id"),
            approval_authority=raw_identity.get("approval_authority"),
            runtime_instance_id=raw_identity.get("runtime_instance_id"),
        )
    except Exception as exc:
        raise ValueError(f"Invalid worker identity: {exc}") from exc


def _coerce_service_identity(raw_identity: dict[str, Any], *, profile: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw_identity or {})
    data.setdefault("worker_id", "service-worker")
    data.setdefault("worker_role", "general")
    data.setdefault("environment", str(profile.get("environment", "service") or "service"))
    data.setdefault("operator_id", "system")
    data.setdefault("approval_authority", "system")
    data.setdefault("runtime_instance_id", generate_runtime_instance_id())
    try:
        return build_worker_identity(
            data,
            environment=str(profile.get("environment", "service") or "service"),
            operator_id=data.get("operator_id"),
            approval_authority=data.get("approval_authority"),
            runtime_instance_id=data.get("runtime_instance_id"),
        )
    except Exception:
        return data


def _repo_root_credentials(config: Any) -> list[str]:
    paths: list[str] = []
    for candidate in (
        getattr(config, "google_credentials_path", None),
        getattr(config, "google_token_path", None),
        getattr(config, "accounting_sheet_config_path", None),
        getattr(config, "rpa_browser_user_data_dir", None),
    ):
        if not candidate:
            continue
        path = Path(candidate)
        if _is_within_repo(path):
            paths.append(str(path))
    raw = getattr(config, "raw", {})
    if isinstance(raw, dict):
        for key, value in raw.items():
            if "credential" in str(key).lower() and isinstance(value, str) and value.strip():
                path = Path(value)
                if _is_within_repo(path):
                    paths.append(str(path))
    return sorted(set(paths))


def _is_within_repo(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
        return resolved.is_relative_to(ROOT)
    except Exception:
        return False


def _assert_runtime_data_writable(service_dir: Path) -> bool:
    try:
        ensure_dir(service_dir)
        probe = service_dir / ".writable_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _load_latest_recovery_summary(runtime_data_dir: str | Path) -> dict[str, Any]:
    recovery_dir = Path(runtime_data_dir) / "recovery"
    if not recovery_dir.is_dir():
        return {}
    candidates = sorted(recovery_dir.glob("recovery_assessment_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return {}
    return _read_json_if_exists(candidates[0])


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _compact_monitoring_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict) or not snapshot:
        return {}
    compact = {
        "ok": bool(snapshot.get("ok", False)),
        "generated_at": str(snapshot.get("generated_at", "")),
        "profile": str(snapshot.get("profile", "")),
        "summary": dict(snapshot.get("summary", {})) if isinstance(snapshot.get("summary", {}), dict) else {},
        "runtime_store_status": dict(snapshot.get("runtime_store_status", {})) if isinstance(snapshot.get("runtime_store_status", {}), dict) else {},
        "live_read_readiness": dict(snapshot.get("live_read_readiness", {})) if isinstance(snapshot.get("live_read_readiness", {}), dict) else {},
        "tool_health_status": dict(snapshot.get("tool_health_status", {})) if isinstance(snapshot.get("tool_health_status", {}), dict) else {},
        "latest_failed_runs": list(snapshot.get("latest_failed_runs", [])[:5]) if isinstance(snapshot.get("latest_failed_runs", []), list) else [],
        "latest_pending_runs": list(snapshot.get("latest_pending_runs", [])[:5]) if isinstance(snapshot.get("latest_pending_runs", []), list) else [],
        "latest_stuck_runs": list(snapshot.get("latest_stuck_runs", [])[:5]) if isinstance(snapshot.get("latest_stuck_runs", []), list) else [],
        "latest_blocked_runs": list(snapshot.get("latest_blocked_runs", [])[:5]) if isinstance(snapshot.get("latest_blocked_runs", []), list) else [],
    }
    return compact


def _config_profile_summary(config: Any, identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": getattr(config, "name", ""),
        "runtime_data_dir": str(getattr(config, "runtime_data_dir", "")),
        "llm_provider": getattr(config, "llm_provider", ""),
        "google_enabled": bool(getattr(config, "google_enabled", False)),
        "rpa_enabled": bool(getattr(config, "rpa_enabled", False)),
        "optional_rpa_enabled": bool(getattr(config, "optional_rpa_enabled", False)),
        "live_execution_enabled": bool(getattr(config, "live_execution_enabled", False)),
        "worker_identity": dict(identity),
    }


def _service_dir(runtime_data_dir: str | Path) -> Path:
    return Path(runtime_data_dir) / SERVICE_DIR_NAME


def _render_preflight_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Service Runtime Preflight",
        "",
        f"- Profile: `{result.get('profile', '')}`",
        f"- Ok: `{str(result.get('ok', False)).lower()}`",
        f"- Runtime data dir: `{result.get('runtime_data_dir', '')}`",
        "",
        "## Worker Identity",
        "",
    ]
    identity = result.get("worker_identity") or {}
    if isinstance(identity, dict):
        for key in ("worker_id", "worker_role", "environment", "operator_id", "approval_authority", "runtime_instance_id"):
            lines.append(f"- {key}: `{identity.get(key, '')}`")
    lines.extend(["", "## Checks", ""])
    for check in result.get("checks", []):
        if not isinstance(check, dict):
            continue
        lines.append(f"- [{check.get('status', '')}] {check.get('id', '')}: {check.get('message', '')}")
    if result.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        for blocker in result["blockers"]:
            if isinstance(blocker, dict):
                lines.append(f"- {blocker.get('id', '')}: {blocker.get('message', '')}")
    if result.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in result["warnings"]:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"
