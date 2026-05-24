from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any

from .errors import RuntimeProfilePolicyError


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PROFILE_PATH = ROOT / "config" / "runtime_profile.json"
DEFAULT_RUNTIME_PROFILE = "demo"
LEGACY_PROFILE_ALIASES = {
    "default": "demo",
    "controlled_live_read": "pilot",
}
ENVIRONMENT_ALIASES = dict(LEGACY_PROFILE_ALIASES)
RUNTIME_PROFILE_NAMES = ("demo", "dev", "test", "release", "pilot", "service", "live")
ENVIRONMENTS = RUNTIME_PROFILE_NAMES
PROFILE_SOURCE_ENV_VARS = ("TASKFRAME_PROFILE", "TASKFRAME_ENV")
RESERVED_LIVE_OVERRIDE_ENV = "TASKFRAME_ENABLE_RESERVED_LIVE_PROFILE"


@dataclass
class RuntimeProfile:
    profile: str
    environment: str
    fixture_mode: bool
    dry_run_default: bool
    allow_live_reads: bool
    allow_live_side_effects: bool
    require_tool_governance: bool
    allowed_toolpacks: list[str] = field(default_factory=list)
    blocked_tool_classes: list[str] = field(default_factory=list)
    llm_provider: str = "fake"
    requires_credentials: bool = False
    evidence_required: bool = True
    source: str = "internal"
    profile_path: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    activation_blocked: bool = False
    activation_block_reason: str = ""
    reserved: bool = False
    allow_unknown_toolpacks: bool = False
    allow_reserved_live_profile: bool = False
    safe_for_demo: bool = False
    safe_for_pilot: bool = False
    safe_for_release: bool = False
    worker_identity_required: bool = False
    reserved_for_deployment: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["profile_path"] = str(self.profile_path) if self.profile_path else ""
        payload["allowed_toolpacks"] = list(self.allowed_toolpacks)
        payload["blocked_tool_classes"] = list(self.blocked_tool_classes)
        payload["raw"] = _json_safe(self.raw)
        payload["governance_enforced"] = self.require_tool_governance
        payload["allow_unknown_toolpack_in_dev"] = self.allow_unknown_toolpacks
        payload["allow_high_risk_live_override"] = False
        payload["reserved_live_profile"] = self.reserved
        payload["safe_for_demo"] = self.safe_for_demo
        payload["safe_for_pilot"] = self.safe_for_pilot
        payload["safe_for_release"] = self.safe_for_release
        payload["worker_identity_required"] = self.worker_identity_required
        payload["reserved_for_deployment"] = self.reserved_for_deployment
        payload["blocked"] = self.activation_blocked
        payload["blocked_reason"] = self.activation_block_reason
        payload["config_source"] = self.source
        return payload


_RUNTIME_PROFILE_MATRIX: dict[str, dict[str, Any]] = {
    "demo": {
        "fixture_mode": True,
        "dry_run_default": True,
        "allow_live_reads": False,
        "allow_live_side_effects": False,
        "require_tool_governance": True,
        "allowed_toolpacks": [],
        "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"],
        "llm_provider": "fake",
        "requires_credentials": False,
        "evidence_required": True,
        "allow_unknown_toolpacks": False,
        "safe_for_demo": True,
    },
    "dev": {
        "fixture_mode": True,
        "dry_run_default": True,
        "allow_live_reads": True,
        "allow_live_side_effects": False,
        "require_tool_governance": True,
        "allowed_toolpacks": [],
        "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"],
        "llm_provider": "ollama",
        "requires_credentials": False,
        "evidence_required": True,
        "allow_unknown_toolpacks": True,
        "safe_for_demo": True,
    },
    "test": {
        "fixture_mode": True,
        "dry_run_default": True,
        "allow_live_reads": False,
        "allow_live_side_effects": False,
        "require_tool_governance": True,
        "allowed_toolpacks": [],
        "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"],
        "llm_provider": "fake",
        "requires_credentials": False,
        "evidence_required": True,
        "allow_unknown_toolpacks": False,
        "safe_for_demo": True,
    },
    "release": {
        "fixture_mode": True,
        "dry_run_default": True,
        "allow_live_reads": False,
        "allow_live_side_effects": False,
        "require_tool_governance": True,
        "allowed_toolpacks": [],
        "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"],
        "llm_provider": "fake",
        "requires_credentials": False,
        "evidence_required": True,
        "allow_unknown_toolpacks": False,
        "safe_for_release": True,
    },
    "pilot": {
        "fixture_mode": False,
        "dry_run_default": True,
        "allow_live_reads": True,
        "allow_live_side_effects": False,
        "require_tool_governance": True,
        "allowed_toolpacks": ["google_workspace_readonly"],
        "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"],
        "llm_provider": "external",
        "requires_credentials": True,
        "evidence_required": True,
        "allow_unknown_toolpacks": False,
        "safe_for_pilot": True,
    },
    "service": {
        "fixture_mode": False,
        "dry_run_default": True,
        "allow_live_reads": False,
        "allow_live_side_effects": False,
        "require_tool_governance": True,
        "allowed_toolpacks": [],
        "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"],
        "llm_provider": "fake",
        "requires_credentials": False,
        "evidence_required": True,
        "allow_unknown_toolpacks": False,
        "worker_identity_required": True,
        "reserved_for_deployment": True,
    },
    "live": {
        "fixture_mode": False,
        "dry_run_default": True,
        "allow_live_reads": True,
        "allow_live_side_effects": False,
        "require_tool_governance": True,
        "allowed_toolpacks": [],
        "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"],
        "llm_provider": "external",
        "requires_credentials": True,
        "evidence_required": True,
        "allow_unknown_toolpacks": False,
        "reserved": True,
    },
}


def resolve_runtime_profile_name(cli_profile: str | None = None, *, profile_path: str | Path | None = None) -> str:
    profile_path = RUNTIME_PROFILE_PATH if profile_path is None else Path(profile_path)
    candidates = [
        cli_profile or "",
        *(os.getenv(name, "").strip() for name in PROFILE_SOURCE_ENV_VARS),
        _profile_name_from_file(profile_path),
        DEFAULT_RUNTIME_PROFILE,
    ]
    for candidate in candidates:
        normalized = _normalize_profile_name(candidate)
        if normalized:
            return normalized
    return DEFAULT_RUNTIME_PROFILE


def load_runtime_profile(
    path: str | Path | None = None,
    profile_name: str | None = None,
) -> dict[str, Any]:
    profile_path = Path(path) if path is not None else RUNTIME_PROFILE_PATH
    resolved_profile = resolve_runtime_profile_name(profile_name, profile_path=profile_path)
    raw = _load_json(profile_path)
    source = _resolve_profile_source(profile_name, profile_path, raw)
    profile = _build_runtime_profile(resolved_profile, raw=raw, source=source, profile_path=profile_path)
    return profile.to_dict()


def describe_runtime_profile(profile: RuntimeProfile | dict[str, Any]) -> dict[str, Any]:
    payload = _coerce_runtime_profile(profile).to_dict()
    payload["safe_for_demo"] = bool(payload.get("safe_for_demo", False))
    payload["safe_for_pilot"] = bool(payload.get("safe_for_pilot", False))
    payload["safe_for_release"] = bool(payload.get("safe_for_release", False))
    payload["is_safe_for_demo"] = payload["safe_for_demo"]
    payload["is_safe_for_pilot"] = payload["safe_for_pilot"]
    payload["is_safe_for_release"] = payload["safe_for_release"]
    payload["safe_for_live"] = bool(payload.get("profile") == "live" and not payload.get("allow_live_side_effects", False))
    return payload


def list_runtime_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for profile_name in RUNTIME_PROFILE_NAMES:
        profile = _build_runtime_profile(profile_name, raw={}, source="internal", profile_path=None)
        profiles.append(
            {
                "profile": profile.profile,
                "environment": profile.environment,
                "fixture_mode": profile.fixture_mode,
                "dry_run_default": profile.dry_run_default,
                "allow_live_reads": profile.allow_live_reads,
                "allow_live_side_effects": profile.allow_live_side_effects,
                "require_tool_governance": profile.require_tool_governance,
                "allowed_toolpacks": list(profile.allowed_toolpacks),
                "blocked_tool_classes": list(profile.blocked_tool_classes),
                "llm_provider": profile.llm_provider,
                "requires_credentials": profile.requires_credentials,
                "evidence_required": profile.evidence_required,
                "reserved": profile.reserved,
                "safe_for_demo": profile.safe_for_demo,
                "safe_for_pilot": profile.safe_for_pilot,
                "safe_for_release": profile.safe_for_release,
                "worker_identity_required": profile.worker_identity_required,
                "reserved_for_deployment": profile.reserved_for_deployment,
            }
        )
    return profiles


def profile_safety_summary(profile: RuntimeProfile | dict[str, Any]) -> dict[str, Any]:
    resolved = _coerce_runtime_profile(profile)
    return {
        "profile": resolved.profile,
        "environment": resolved.environment,
        "safe_for_demo": bool(resolved.safe_for_demo),
        "safe_for_pilot": bool(resolved.safe_for_pilot),
        "safe_for_release": bool(resolved.safe_for_release),
        "reserved": bool(resolved.reserved),
        "activation_blocked": bool(resolved.activation_blocked),
        "activation_block_reason": resolved.activation_block_reason,
        "fixture_mode": bool(resolved.fixture_mode),
        "dry_run_default": bool(resolved.dry_run_default),
        "allow_live_reads": bool(resolved.allow_live_reads),
        "allow_live_side_effects": bool(resolved.allow_live_side_effects),
        "allow_unknown_toolpacks": bool(resolved.allow_unknown_toolpacks),
        "worker_identity_required": bool(resolved.worker_identity_required),
        "reserved_for_deployment": bool(resolved.reserved_for_deployment),
    }


def check_runtime_profile(profile: RuntimeProfile | dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = _coerce_runtime_profile(profile or load_runtime_profile())
    blockers = _runtime_profile_blockers(resolved)
    return {
        "ok": not blockers,
        "profile": resolved.profile,
        "environment": resolved.environment,
        "source": resolved.source,
        "profile_path": str(resolved.profile_path) if resolved.profile_path else "",
        "fixture_mode": bool(resolved.fixture_mode),
        "dry_run_default": bool(resolved.dry_run_default),
        "allow_live_reads": bool(resolved.allow_live_reads),
        "allow_live_side_effects": bool(resolved.allow_live_side_effects),
        "require_tool_governance": bool(resolved.require_tool_governance),
        "allowed_toolpacks": list(resolved.allowed_toolpacks),
        "blocked_tool_classes": list(resolved.blocked_tool_classes),
        "llm_provider": resolved.llm_provider,
        "requires_credentials": bool(resolved.requires_credentials),
        "evidence_required": bool(resolved.evidence_required),
        "reserved": bool(resolved.reserved),
        "worker_identity_required": bool(resolved.worker_identity_required),
        "reserved_for_deployment": bool(resolved.reserved_for_deployment),
        "activation_blocked": bool(resolved.activation_blocked),
        "activation_block_reason": resolved.activation_block_reason,
        "safe_for_demo": bool(resolved.safe_for_demo),
        "safe_for_pilot": bool(resolved.safe_for_pilot),
        "safe_for_release": bool(resolved.safe_for_release),
        "blockers": blockers,
    }


def assert_runtime_profile_allows_tool_execution(
    profile: RuntimeProfile | dict[str, Any] | None,
    tool_key: str,
    tool_spec: dict[str, Any],
    *,
    dry_run: bool,
    live_requested: bool,
    operation: str,
    data_source: str | None = None,
    evidence_required: bool = True,
    credentials_required: bool | None = None,
) -> dict[str, Any]:
    resolved = _coerce_runtime_profile(profile or load_runtime_profile())
    decision = _runtime_profile_execution_decision(
        resolved,
        tool_key,
        tool_spec,
        dry_run=dry_run,
        live_requested=live_requested,
        operation=operation,
        data_source=data_source,
        evidence_required=evidence_required,
        credentials_required=credentials_required,
    )
    if not decision["ok"]:
        raise RuntimeProfilePolicyError(decision["reason"])
    return decision


def resolve_runtime_environment(explicit: str = "", *, profile_path: str | Path | None = None) -> str:
    return resolve_runtime_profile_name(explicit, profile_path=profile_path)


def profile_file_path(profile: str, config_dir: str | Path | None = None) -> Path:
    config_root = resolve_config_dir(config_dir)
    return config_root / f"taskframe.{profile}.json"


def resolve_config_dir(cli_config_dir: str | Path | None = None) -> Path:
    if cli_config_dir:
        return Path(cli_config_dir).expanduser()
    env_dir = os.getenv("TASKFRAME_CONFIG_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser()
    return ROOT / "config"


def _resolve_profile_source(profile_name: str | None, profile_path: Path, raw: dict[str, Any]) -> str:
    if profile_name:
        return "cli"
    if any(os.getenv(name, "").strip() for name in PROFILE_SOURCE_ENV_VARS):
        return "env"
    if profile_path.is_file() and raw:
        return "config"
    return "default"


def _build_runtime_profile(profile_name: str, *, raw: dict[str, Any], source: str, profile_path: Path | None) -> RuntimeProfile:
    normalized = _normalize_profile_name(profile_name) or DEFAULT_RUNTIME_PROFILE
    preset = dict(_RUNTIME_PROFILE_MATRIX.get(normalized, _RUNTIME_PROFILE_MATRIX[DEFAULT_RUNTIME_PROFILE]))
    merged = _merge_profile_data(normalized, raw)

    fixture_mode = _coerce_bool(merged.get("fixture_mode"), preset["fixture_mode"])
    dry_run_default = _coerce_bool(merged.get("dry_run_default"), preset["dry_run_default"])
    allow_live_reads = _coerce_bool(merged.get("allow_live_reads"), preset["allow_live_reads"])
    allow_live_side_effects = _coerce_bool(merged.get("allow_live_side_effects"), preset["allow_live_side_effects"])
    require_tool_governance = _coerce_bool(merged.get("require_tool_governance"), preset["require_tool_governance"])
    allowed_toolpacks = _coerce_list(merged.get("allowed_toolpacks"), preset["allowed_toolpacks"])
    blocked_tool_classes = _coerce_list(merged.get("blocked_tool_classes"), preset["blocked_tool_classes"])
    llm_provider = _first_non_empty_mapping(merged, ("llm_provider", "provider")) or preset["llm_provider"]
    requires_credentials = _coerce_bool(merged.get("requires_credentials"), preset["requires_credentials"])
    evidence_required = _coerce_bool(merged.get("evidence_required"), preset["evidence_required"])
    allow_unknown_toolpacks = _coerce_bool(merged.get("allow_unknown_toolpacks"), preset.get("allow_unknown_toolpacks", False))
    allow_reserved_live_profile = _coerce_bool(merged.get("allow_reserved_live_profile"), False) or _env_bool(RESERVED_LIVE_OVERRIDE_ENV)
    reserved = _coerce_bool(merged.get("reserved"), preset.get("reserved", False))
    worker_identity_required = _coerce_bool(merged.get("worker_identity_required"), preset.get("worker_identity_required", False))
    reserved_for_deployment = _coerce_bool(merged.get("reserved_for_deployment"), preset.get("reserved_for_deployment", False))

    activation_blocked = False
    activation_block_reason = ""
    if normalized == "live" and not allow_reserved_live_profile:
        activation_blocked = True
        activation_block_reason = "The live runtime profile is reserved until a future override explicitly enables it."

    return RuntimeProfile(
        profile=normalized,
        environment=normalized,
        fixture_mode=fixture_mode,
        dry_run_default=dry_run_default,
        allow_live_reads=allow_live_reads,
        allow_live_side_effects=allow_live_side_effects,
        require_tool_governance=require_tool_governance,
        allowed_toolpacks=allowed_toolpacks,
        blocked_tool_classes=blocked_tool_classes,
        llm_provider=llm_provider,
        requires_credentials=requires_credentials,
        evidence_required=evidence_required,
        source=source,
        profile_path=profile_path,
        raw=dict(raw or {}),
        activation_blocked=activation_blocked,
        activation_block_reason=activation_block_reason,
        reserved=reserved,
        allow_unknown_toolpacks=allow_unknown_toolpacks,
        allow_reserved_live_profile=allow_reserved_live_profile,
        safe_for_demo=bool(preset.get("safe_for_demo", False) and normalized in {"demo", "dev", "test", "release"}),
        safe_for_pilot=bool(preset.get("safe_for_pilot", False) and normalized == "pilot"),
        safe_for_release=bool(preset.get("safe_for_release", False) and normalized == "release"),
        worker_identity_required=worker_identity_required,
        reserved_for_deployment=reserved_for_deployment,
    )


def _merge_profile_data(profile_name: str, raw: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    top_level_candidate = _coerce_str(raw.get("profile") or raw.get("environment"))
    try:
        normalized_top_level = _normalize_profile_name(top_level_candidate) if top_level_candidate else ""
    except ValueError:
        normalized_top_level = ""

    inherited_keys = {"llm", "google", "rpa", "accounting", "runtime_data_dir"}
    if not top_level_candidate or normalized_top_level == profile_name:
        merged.update(raw)
    else:
        for key in inherited_keys:
            if key in raw:
                merged[key] = raw[key]
        for key in ("profile", "environment"):
            if key in raw:
                merged[key] = raw[key]
        for key in ("governance_enforced", "allow_unknown_toolpack_in_dev", "allow_high_risk_live_override"):
            if key in raw:
                merged[key] = raw[key]

    for key in ("runtime_profile", profile_name):
        nested = raw.get(key)
        if isinstance(nested, dict):
            merged.update(nested)
    if profile_name == "pilot":
        nested = raw.get("controlled_live_read")
        if isinstance(nested, dict):
            merged.update(nested)
    llm = merged.get("llm")
    if isinstance(llm, dict):
        merged.setdefault("llm_provider", llm.get("provider", ""))
        merged.setdefault("llm", dict(llm))
    if "environment" not in merged and "profile" in merged:
        merged["environment"] = merged["profile"]
    return merged


def _runtime_profile_blockers(profile: RuntimeProfile) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if profile.activation_blocked:
        blockers.append(
            {
                "id": "profile_reserved",
                "message": profile.activation_block_reason,
                "source": "profile",
            }
        )
    if not profile.require_tool_governance:
        blockers.append(
            {
                "id": "tool_governance_disabled",
                "message": "Runtime profile must require tool governance.",
                "source": "profile",
            }
        )
    if not profile.evidence_required:
        blockers.append(
            {
                "id": "evidence_not_required",
                "message": "Runtime profile must require evidence.",
                "source": "profile",
            }
        )
    if profile.profile == "release" and profile.allow_live_side_effects:
        blockers.append(
            {
                "id": "release_live_side_effects_enabled",
                "message": "Release profile must not allow live side effects.",
                "source": "profile",
            }
        )
    if profile.profile == "pilot" and not profile.require_tool_governance:
        blockers.append(
            {
                "id": "pilot_tool_governance_disabled",
                "message": "Pilot profile must require tool governance.",
                "source": "profile",
            }
        )
    if profile.profile == "service":
        if profile.environment != "service":
            blockers.append(
                {
                    "id": "service_environment_mismatch",
                    "message": "Service profile must resolve to the service environment.",
                    "source": "profile",
                }
            )
        if profile.fixture_mode:
            blockers.append(
                {
                    "id": "service_fixture_mode_enabled",
                    "message": "Service profile must not run in fixture mode.",
                    "source": "profile",
                }
            )
        if not profile.dry_run_default:
            blockers.append(
                {
                    "id": "service_dry_run_default_disabled",
                    "message": "Service profile must default to dry-run.",
                    "source": "profile",
                }
            )
        if profile.allow_live_reads:
            blockers.append(
                {
                    "id": "service_live_reads_enabled",
                    "message": "Service profile must not allow live reads.",
                    "source": "profile",
                }
            )
        if profile.allow_live_side_effects:
            blockers.append(
                {
                    "id": "service_live_side_effects_enabled",
                    "message": "Service profile must not allow live side effects.",
                    "source": "profile",
                }
            )
        if not profile.worker_identity_required:
            blockers.append(
                {
                    "id": "service_worker_identity_disabled",
                    "message": "Service profile must require worker identity metadata.",
                    "source": "profile",
                }
            )
        if not profile.reserved_for_deployment:
            blockers.append(
                {
                    "id": "service_reserved_for_deployment_disabled",
                    "message": "Service profile must be reserved for deployment use.",
                    "source": "profile",
                }
            )
    return blockers


def _runtime_profile_execution_decision(
    profile: RuntimeProfile,
    tool_key: str,
    tool_spec: dict[str, Any],
    *,
    dry_run: bool,
    live_requested: bool,
    operation: str,
    data_source: str | None,
    evidence_required: bool,
    credentials_required: bool | None,
) -> dict[str, Any]:
    side_effect = bool(tool_spec.get("side_effect", False))
    allow_live = bool(tool_spec.get("allow_live", False))
    allow_live_side_effect = bool(tool_spec.get("allow_live_side_effect", False))
    toolpack_id = _coerce_str(tool_spec.get("toolpack_id", ""))
    source = _coerce_str(tool_spec.get("source", "builtin")) or "builtin"
    classification = _coerce_str(
        tool_spec.get("toolpack_classification", "")
        or tool_spec.get("toolpack_core_or_optional", "")
        or tool_spec.get("classification", "")
    ) or "unknown"
    tool_class = _coerce_str(tool_spec.get("tool_class", "")) or _coerce_str(tool_spec.get("namespace", ""))
    credential_flag = profile.requires_credentials if credentials_required is None else bool(credentials_required)
    blockers: list[dict[str, Any]] = []

    if profile.activation_blocked:
        blockers.append(
            {
                "id": "profile_reserved",
                "message": profile.activation_block_reason,
                "source": "profile",
            }
        )
    if not profile.require_tool_governance:
        blockers.append(
            {
                "id": "tool_governance_disabled",
                "message": "Runtime profile requires tool governance.",
                "source": "profile",
            }
        )
    if evidence_required and not profile.evidence_required:
        blockers.append(
            {
                "id": "evidence_required_missing",
                "message": "Runtime profile requires evidence for tool execution.",
                "source": "profile",
            }
        )
    if live_requested and data_source == "fixture" and not profile.fixture_mode:
        blockers.append(
            {
                "id": "fixture_mode_required",
                "message": "Live execution requested but the active profile is not fixture-mode safe.",
                "source": "profile",
            }
        )
    if live_requested and profile.profile in {"demo", "test"}:
        blockers.append(
            {
                "id": "live_reads_blocked",
                "message": f"Profile {profile.profile} blocks live reads.",
                "source": "profile",
            }
        )
    if live_requested and profile.profile == "release":
        blockers.append(
            {
                "id": "release_live_execution_blocked",
                "message": "Release profile blocks live execution.",
                "source": "profile",
            }
        )
    if live_requested and profile.profile == "live" and not profile.allow_reserved_live_profile:
        blockers.append(
            {
                "id": "live_profile_reserved",
                "message": "Live profile is reserved and cannot be activated without an explicit future override.",
                "source": "profile",
            }
        )
    if live_requested and side_effect and not profile.allow_live_side_effects:
        blockers.append(
            {
                "id": "live_side_effects_blocked",
                "message": f"Profile {profile.profile} blocks live side effects.",
                "source": "profile",
            }
        )
    if live_requested and not side_effect and not profile.allow_live_reads:
        blockers.append(
            {
                "id": "live_reads_not_enabled",
                "message": f"Profile {profile.profile} does not enable live reads.",
                "source": "profile",
            }
        )
    if live_requested and profile.allowed_toolpacks and toolpack_id and toolpack_id not in set(profile.allowed_toolpacks):
        blockers.append(
            {
                "id": "toolpack_not_allowlisted",
                "message": f"Tool pack {toolpack_id} is not allowlisted for profile {profile.profile}.",
                "source": "profile",
            }
        )
    if live_requested and source == "external_toolpack" and not toolpack_id:
        blockers.append(
            {
                "id": "toolpack_missing",
                "message": "External toolpack execution requires a toolpack_id.",
                "source": "profile",
            }
        )
    if tool_class in set(profile.blocked_tool_classes):
        blockers.append(
            {
                "id": "tool_class_blocked",
                "message": f"Tool class {tool_class!r} is blocked by profile {profile.profile}.",
                "source": "profile",
            }
        )
    if credential_flag and not profile.requires_credentials:
        blockers.append(
            {
                "id": "credentials_not_allowed",
                "message": "Credentials are not allowed for the active profile.",
                "source": "profile",
            }
        )
    if profile.requires_credentials and live_requested and source == "external_toolpack" and not profile.allowed_toolpacks:
        blockers.append(
            {
                "id": "credentials_required_allowlist_missing",
                "message": "Live execution requires allowlisted toolpacks and credentials in this profile.",
                "source": "profile",
            }
        )

    if live_requested and side_effect and not allow_live_side_effect:
        blockers.append(
            {
                "id": "tool_blocks_live_side_effect",
                "message": f"Tool {tool_key} does not allow live side effects.",
                "source": "tool",
            }
        )
    if live_requested and not side_effect and not allow_live:
        blockers.append(
            {
                "id": "tool_blocks_live_reads",
                "message": f"Tool {tool_key} does not allow live reads.",
                "source": "tool",
            }
        )
    if live_requested and profile.profile == "pilot" and source == "external_toolpack" and toolpack_id not in set(profile.allowed_toolpacks):
        blockers.append(
            {
                "id": "pilot_read_allowlist_required",
                "message": f"Pilot profile only allows live reads for allowlisted toolpacks. {toolpack_id or 'unknown toolpack'} is not allowed.",
                "source": "profile",
            }
        )
    if live_requested and profile.profile == "dev" and source == "external_toolpack" and toolpack_id and toolpack_id not in set(profile.allowed_toolpacks):
        blockers.append(
            {
                "id": "dev_toolpack_allowlist_required",
                "message": f"Dev profile requires an allowlist for live reads. {toolpack_id} is not allowlisted.",
                "source": "profile",
            }
        )

    ok = not blockers
    reason = "Runtime profile allows execution." if ok else blockers[0]["message"]
    return {
        "ok": ok,
        "reason": reason,
        "profile": profile.profile,
        "environment": profile.environment,
        "tool": tool_key,
        "toolpack_id": toolpack_id,
        "classification": classification,
        "tool_class": tool_class,
        "source": source,
        "dry_run": bool(dry_run),
        "live_requested": bool(live_requested),
        "operation": operation,
        "fixture_mode": bool(profile.fixture_mode),
        "data_source": data_source or ("fixture" if dry_run or profile.fixture_mode else "live"),
        "evidence_required": bool(evidence_required),
        "credentials_required": credential_flag,
        "blocked": blockers,
    }


def _coerce_runtime_profile(profile: RuntimeProfile | dict[str, Any]) -> RuntimeProfile:
    if isinstance(profile, RuntimeProfile):
        return profile
    if not isinstance(profile, dict):
        return _build_runtime_profile(DEFAULT_RUNTIME_PROFILE, raw={}, source="default", profile_path=RUNTIME_PROFILE_PATH)
    profile_name = _coerce_str(profile.get("profile", profile.get("environment", DEFAULT_RUNTIME_PROFILE)))
    return _build_runtime_profile(profile_name or DEFAULT_RUNTIME_PROFILE, raw=profile, source=str(profile.get("source", "internal")), profile_path=Path(str(profile.get("profile_path", ""))) if profile.get("profile_path") else None)


def _normalize_profile_name(value: str | None) -> str:
    text = _coerce_str(value).lower()
    if not text:
        return ""
    text = LEGACY_PROFILE_ALIASES.get(text, text)
    if text not in RUNTIME_PROFILE_NAMES:
        raise ValueError(f"Invalid runtime profile: {value!r}")
    return text


def _profile_name_from_file(profile_path: str | Path) -> str:
    path = Path(profile_path)
    if not path.is_file():
        return ""
    payload = _load_json(path)
    if not isinstance(payload, dict):
        return ""
    candidate = _coerce_str(payload.get("profile") or payload.get("environment"))
    if candidate:
        try:
            return _normalize_profile_name(candidate)
        except ValueError:
            return ""
    for key in ("runtime_profile", "controlled_live_read"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidate = _coerce_str(nested.get("profile") or nested.get("environment"))
            if candidate:
                try:
                    return _normalize_profile_name(candidate)
                except ValueError:
                    return ""
    return ""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _coerce_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = _coerce_str(value).lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on", "enabled"}


def _coerce_list(value: Any, default: list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return list(default)
    if isinstance(value, str):
        parts = [item.strip() for item in value.split(",")]
        return [item for item in parts if item]
    return list(default)


def _first_non_empty_mapping(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _coerce_str(data.get(key))
        if value:
            return value
    return ""


def _env_bool(name: str) -> bool:
    return _coerce_bool(os.getenv(name, ""), False)


def _resolve_profile_source(profile_name: str | None, profile_path: Path, raw: dict[str, Any]) -> str:
    if profile_name:
        return "cli"
    if any(os.getenv(name, "").strip() for name in PROFILE_SOURCE_ENV_VARS):
        return "env"
    if profile_path.is_file() and raw:
        return "config"
    return "default"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, Path):
        return str(value)
    return str(value)
