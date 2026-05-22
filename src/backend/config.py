from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKEND_AUTH_CONFIG_PATH = ROOT / "config" / "examples" / "taskframe.backend.example.json"

ROLE_ORDER = {"viewer": 1, "operator": 2, "admin": 3}
DEFAULT_TOKEN_ENV_BY_ROLE = {
    "admin": "TASKFRAME_BACKEND_ADMIN_TOKEN",
    "operator": "TASKFRAME_BACKEND_OPERATOR_TOKEN",
    "viewer": "TASKFRAME_BACKEND_VIEWER_TOKEN",
}


@dataclass(frozen=True)
class BackendAuthTokenConfig:
    name: str
    token_env: str
    role: str
    token_value: str = field(repr=False, compare=False, default="")


@dataclass
class BackendAuthConfig:
    enabled: bool = True
    allow_dev_bypass: bool = False
    tokens: list[BackendAuthTokenConfig] = field(default_factory=list)
    valid: bool = True
    error: str = ""
    source_path: str = ""

    @property
    def dev_bypass_active(self) -> bool:
        return bool(self.valid and not self.enabled and self.allow_dev_bypass)

    @property
    def configured_roles(self) -> list[str]:
        roles = {token.role for token in self.tokens if token.role in ROLE_ORDER}
        return sorted(roles, key=lambda item: ROLE_ORDER[item], reverse=True)


def load_backend_auth_config(config_path: str | Path | None = None) -> BackendAuthConfig:
    path = _resolve_backend_auth_config_path(config_path)
    if path is None:
        payload = _default_backend_auth_payload()
        return _build_backend_auth_config(payload, DEFAULT_BACKEND_AUTH_CONFIG_PATH, source_path="env", allow_env_overrides=True)
    raw = _load_json(path)
    if raw is None:
        return BackendAuthConfig(
            enabled=True,
            allow_dev_bypass=False,
            tokens=[],
            valid=False,
            error=f"Backend auth config file not found or invalid: {path}",
            source_path=str(path),
        )
    payload = raw.get("backend_auth", raw) if isinstance(raw, dict) else {}
    if not isinstance(payload, dict):
        return BackendAuthConfig(
            enabled=True,
            allow_dev_bypass=False,
            tokens=[],
            valid=False,
            error="Backend auth config must be a JSON object.",
            source_path=str(path),
        )
    return _build_backend_auth_config(payload, path, source_path=str(path), allow_env_overrides=False)


def _build_backend_auth_config(
    payload: dict[str, Any],
    path: Path,
    *,
    source_path: str,
    allow_env_overrides: bool,
) -> BackendAuthConfig:
    enabled_value = payload.get("enabled", True)
    allow_dev_bypass_value = payload.get("allow_dev_bypass", False)
    if allow_env_overrides:
        enabled_value = _env_override("TASKFRAME_BACKEND_AUTH_ENABLED", enabled_value)
        allow_dev_bypass_value = _env_override("TASKFRAME_BACKEND_ALLOW_DEV_BYPASS", allow_dev_bypass_value)
    enabled = _coerce_bool(enabled_value, True)
    allow_dev_bypass = _coerce_bool(allow_dev_bypass_value, False)
    if not enabled and not allow_dev_bypass:
        return BackendAuthConfig(
            enabled=enabled,
            allow_dev_bypass=allow_dev_bypass,
            tokens=[],
            valid=False,
            error="Backend auth cannot be disabled unless dev bypass is explicitly enabled.",
            source_path=source_path,
        )

    raw_tokens = payload.get("tokens", [])
    if not isinstance(raw_tokens, list):
        return BackendAuthConfig(
            enabled=enabled,
            allow_dev_bypass=allow_dev_bypass,
            tokens=[],
            valid=False,
            error="Backend auth tokens must be a list.",
            source_path=source_path,
        )

    tokens: list[BackendAuthTokenConfig] = []
    seen_envs: set[str] = set()
    seen_roles: set[str] = set()
    for item in raw_tokens:
        if not isinstance(item, dict):
            return _invalid_backend_auth(enabled, allow_dev_bypass, "Each backend auth token must be an object.", source_path)
        name = str(item.get("name", "")).strip()
        token_env = str(item.get("token_env", "")).strip()
        role = str(item.get("role", "")).strip().lower()
        if not name:
            return _invalid_backend_auth(enabled, allow_dev_bypass, "Backend auth token entries require a name.", source_path)
        if role not in ROLE_ORDER:
            return _invalid_backend_auth(enabled, allow_dev_bypass, f"Unknown backend auth role: {role!r}", source_path)
        if not token_env:
            return _invalid_backend_auth(enabled, allow_dev_bypass, f"Backend auth token {name!r} requires token_env.", source_path)
        if token_env in seen_envs:
            return _invalid_backend_auth(enabled, allow_dev_bypass, f"Duplicate backend auth token_env: {token_env}", source_path)
        if role in seen_roles:
            return _invalid_backend_auth(enabled, allow_dev_bypass, f"Duplicate backend auth role: {role}", source_path)
        token_value = ""
        if enabled:
            token_value = os.getenv(token_env, "")
            if not token_value.strip():
                return _invalid_backend_auth(enabled, allow_dev_bypass, f"Backend auth token env var is empty: {token_env}", source_path)
        seen_envs.add(token_env)
        seen_roles.add(role)
        tokens.append(
            BackendAuthTokenConfig(
                name=name,
                token_env=token_env,
                role=role,
                token_value=token_value,
            )
        )

    if not tokens and enabled:
        return BackendAuthConfig(
            enabled=enabled,
            allow_dev_bypass=allow_dev_bypass,
            tokens=[],
            valid=False,
            error="Backend auth requires at least one token entry.",
            source_path=source_path,
        )

    return BackendAuthConfig(
        enabled=enabled,
        allow_dev_bypass=allow_dev_bypass,
        tokens=tokens,
        valid=True,
        error="",
        source_path=source_path,
    )


def _invalid_backend_auth(enabled: bool, allow_dev_bypass: bool, error: str, source_path: str) -> BackendAuthConfig:
    return BackendAuthConfig(
        enabled=enabled,
        allow_dev_bypass=allow_dev_bypass,
        tokens=[],
        valid=False,
        error=error,
        source_path=source_path,
    )


def _default_backend_auth_payload() -> dict[str, Any]:
    return {
        "enabled": True,
        "allow_dev_bypass": False,
        "tokens": [
            {"name": "local-admin", "token_env": DEFAULT_TOKEN_ENV_BY_ROLE["admin"], "role": "admin"},
            {"name": "operator", "token_env": DEFAULT_TOKEN_ENV_BY_ROLE["operator"], "role": "operator"},
            {"name": "viewer", "token_env": DEFAULT_TOKEN_ENV_BY_ROLE["viewer"], "role": "viewer"},
        ],
    }


def _resolve_backend_auth_config_path(config_path: str | Path | None) -> Path | None:
    if config_path:
        return Path(config_path).expanduser()
    env_path = os.getenv("TASKFRAME_BACKEND_AUTH_CONFIG_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    env_path = os.getenv("TASKFRAME_BACKEND_CONFIG_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _env_override(name: str, value: Any) -> Any:
    env_value = os.getenv(name, "").strip()
    if env_value:
        return env_value
    return value
