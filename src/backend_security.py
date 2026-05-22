"""Spec 148 — Backend security headers, CORS enforcement, and token hardening.

Provides:
- BackendSecurityConfig — parsed from JSON or secure defaults.
- load_security_config() — load config file or fall back to secure defaults.
- hash_token() / verify_token() / redact_token() — token helpers.
- parse_token_metadata() — extract and validate a token_record dict.
- install_security_headers_middleware() — add security headers to all responses;
  also enforces token expiry when token_records are configured.
- install_cors_middleware() — enforce CORS allowlist, handle OPTIONS preflight.
- get_security_status() — return status dict for /api/security/status endpoint.

Security constraints (unchanged from Spec 145):
- Token values are NEVER logged.
- Only redacted previews (first 4 + ... + last 4) appear in audit records.
- Wildcard CORS (*) is blocked outside dev/test environments.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CORSConfig:
    enabled: bool = True
    allowed_origins: list[str] = field(default_factory=lambda: [
        "http://127.0.0.1:7860",
        "http://localhost:7860",
    ])
    allow_credentials: bool = False
    allowed_methods: list[str] = field(default_factory=lambda: ["GET", "POST", "OPTIONS"])
    allowed_headers: list[str] = field(default_factory=lambda: [
        "Authorization",
        "Content-Type",
        "X-TaskFrame-Request-ID",
    ])


@dataclass
class SecurityHeadersConfig:
    enabled: bool = True
    content_security_policy: str = "default-src 'self'; frame-ancestors 'none'; object-src 'none'"
    x_content_type_options: str = "nosniff"
    x_frame_options: str = "DENY"
    referrer_policy: str = "no-referrer"
    permissions_policy: str = "camera=(), microphone=(), geolocation=()"
    cache_control: str = "no-store"


@dataclass
class AuthSecurityConfig:
    token_required: bool = True
    token_hashes: list[str] = field(default_factory=list)
    allow_plaintext_dev_token: bool = True
    token_expiry_required: bool = False


@dataclass
class BackendSecurityConfig:
    enabled: bool = True
    cors: CORSConfig = field(default_factory=CORSConfig)
    security_headers: SecurityHeadersConfig = field(default_factory=SecurityHeadersConfig)
    auth: AuthSecurityConfig = field(default_factory=AuthSecurityConfig)
    token_records: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_security_config(config_path: str | Path | None = None) -> BackendSecurityConfig:
    """Load security config from a JSON file or return secure defaults.

    If the config file exists but is invalid, fails closed (returns a
    deny-all config with hardening enabled).
    """
    raw: dict[str, Any] = {}

    if config_path is not None:
        path = Path(config_path)
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    return _fail_closed_config()
                raw = data.get("backend_security", data)
            except Exception:
                return _fail_closed_config()

    try:
        return _parse_security_config(raw)
    except Exception:
        return _fail_closed_config()


def _fail_closed_config() -> BackendSecurityConfig:
    cfg = BackendSecurityConfig()
    cfg.cors.allowed_origins = []  # Block all cross-origin
    return cfg


def _parse_security_config(raw: dict[str, Any]) -> BackendSecurityConfig:
    enabled = _coerce_bool(raw.get("enabled", True), default=True)

    cors_raw = raw.get("cors", {}) if isinstance(raw.get("cors"), dict) else {}
    cors = CORSConfig(
        enabled=_coerce_bool(cors_raw.get("enabled", True), default=True),
        allowed_origins=list(cors_raw.get("allowed_origins", ["http://127.0.0.1:7860", "http://localhost:7860"])),
        allow_credentials=_coerce_bool(cors_raw.get("allow_credentials", False), default=False),
        allowed_methods=list(cors_raw.get("allowed_methods", ["GET", "POST", "OPTIONS"])),
        allowed_headers=list(cors_raw.get("allowed_headers", ["Authorization", "Content-Type", "X-TaskFrame-Request-ID"])),
    )

    sh_raw = raw.get("security_headers", {}) if isinstance(raw.get("security_headers"), dict) else {}
    headers = SecurityHeadersConfig(
        enabled=_coerce_bool(sh_raw.get("enabled", True), default=True),
        content_security_policy=str(sh_raw.get("content_security_policy", SecurityHeadersConfig.content_security_policy)),
        x_content_type_options=str(sh_raw.get("x_content_type_options", "nosniff")),
        x_frame_options=str(sh_raw.get("x_frame_options", "DENY")),
        referrer_policy=str(sh_raw.get("referrer_policy", "no-referrer")),
        permissions_policy=str(sh_raw.get("permissions_policy", "camera=(), microphone=(), geolocation=()")),
        cache_control=str(sh_raw.get("cache_control", "no-store")),
    )

    auth_raw = raw.get("auth", {}) if isinstance(raw.get("auth"), dict) else {}
    auth = AuthSecurityConfig(
        token_required=_coerce_bool(auth_raw.get("token_required", True), default=True),
        token_hashes=list(auth_raw.get("token_hashes", [])),
        allow_plaintext_dev_token=_coerce_bool(auth_raw.get("allow_plaintext_dev_token", True), default=True),
        token_expiry_required=_coerce_bool(auth_raw.get("token_expiry_required", False), default=False),
    )

    token_records = list(raw.get("token_records", []))

    return BackendSecurityConfig(
        enabled=enabled,
        cors=cors,
        security_headers=headers,
        auth=auth,
        token_records=token_records,
    )


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def hash_token(token: str) -> str:
    """Return SHA-256 hash of the token as 'sha256:<hex>'."""
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def verify_token(token: str, allowed_hashes: list[str]) -> bool:
    """Return True if hash_token(token) appears in allowed_hashes."""
    if not token or not allowed_hashes:
        return False
    token_hash = hash_token(token)
    return token_hash in allowed_hashes


def redact_token(token: str) -> str:
    """Return a redacted preview: first 4 chars + ... + last 4 chars."""
    if not token:
        return "***"
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def parse_token_metadata(token_record: dict[str, Any]) -> dict[str, Any]:
    """Extract and validate a token_record dict.

    Returns a dict with canonical fields including is_expired.
    """
    token_hash = str(token_record.get("token_hash", "") or "")
    label = str(token_record.get("label", "") or "")
    created_at = str(token_record.get("created_at", "") or "")
    expires_at_raw = str(token_record.get("expires_at", "") or "")
    scopes = list(token_record.get("scopes", []))

    is_expired = False
    if expires_at_raw:
        expires_dt = _parse_ts(expires_at_raw)
        if expires_dt is not None:
            is_expired = expires_dt <= datetime.now(timezone.utc)

    return {
        "token_hash": token_hash,
        "label": label,
        "created_at": created_at,
        "expires_at": expires_at_raw,
        "scopes": scopes,
        "is_expired": is_expired,
    }


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

def install_security_headers_middleware(app) -> None:
    """Outermost middleware: adds security headers to ALL responses.

    Also enforces token expiry when token_records are configured in
    app.state.backend_security_config.
    """
    from src.backend.audit import write_route_audit

    @app.middleware("http")
    async def _security_headers_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        config: BackendSecurityConfig | None = getattr(request.app.state, "backend_security_config", None)

        # Token expiry check — runs BEFORE delegating to inner middleware
        if config and config.enabled and config.token_records:
            early = _check_token_expiry(request, config)
            if early is not None:
                write_route_audit(
                    request,
                    "security.token_expired",
                    "blocked",
                    401,
                    error="Token has expired.",
                )
                if config.security_headers.enabled:
                    _apply_security_headers(early, config.security_headers)
                return early

        response = await call_next(request)

        if config and config.enabled and config.security_headers.enabled:
            _apply_security_headers(response, config.security_headers)

        return response


def _check_token_expiry(request: Request, config: BackendSecurityConfig) -> JSONResponse | None:
    """Return a 401 response if the bearer token matches an expired token_record, else None."""
    bearer = (request.headers.get("authorization") or "").strip()
    if not bearer.lower().startswith("bearer "):
        return None
    token = bearer[7:].strip()
    if not token:
        return None

    for record in config.token_records:
        meta = parse_token_metadata(record)
        if verify_token(token, [meta["token_hash"]]):
            if meta["is_expired"]:
                return JSONResponse(
                    status_code=401,
                    content={
                        "ok": False,
                        "error_code": "AUTH_TOKEN_EXPIRED",
                        "error": "Token has expired.",
                        "token_preview": redact_token(token),
                    },
                )
            return None  # Token matched and is valid

    return None  # Token not found in records — fall through to existing auth


def _apply_security_headers(response, cfg: SecurityHeadersConfig) -> None:
    try:
        h = response.headers
        h["X-Content-Type-Options"] = cfg.x_content_type_options
        h["X-Frame-Options"] = cfg.x_frame_options
        h["Referrer-Policy"] = cfg.referrer_policy
        h["Permissions-Policy"] = cfg.permissions_policy
        h["Cache-Control"] = cfg.cache_control
        h["Content-Security-Policy"] = cfg.content_security_policy
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

_DEV_ENVS = frozenset({"dev", "test"})


def install_cors_middleware(app) -> None:
    """CORS enforcement middleware.

    - No Origin header → passthrough (same-origin or server-to-server).
    - Allowlisted Origin → add CORS headers.
    - Non-allowlisted Origin → 403 CORS_ORIGIN_BLOCKED + audit.
    - OPTIONS preflight → 200 (or 403) immediately.
    - Wildcard * → blocked unless TASKFRAME_ENV is 'dev' or 'test'.
    """
    from src.backend.audit import write_route_audit

    @app.middleware("http")
    async def _cors_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        config: BackendSecurityConfig | None = getattr(request.app.state, "backend_security_config", None)

        origin = (request.headers.get("origin") or "").strip()

        if not config or not config.enabled or not config.cors.enabled or not origin:
            return await call_next(request)

        effective_origins = _effective_allowed_origins(config.cors.allowed_origins)

        if "*" not in effective_origins and origin not in effective_origins:
            write_route_audit(
                request,
                "security.cors_blocked",
                "blocked",
                403,
                summary=f"CORS origin blocked: {origin}",
                error=f"Origin '{origin}' is not in the CORS allowlist.",
            )
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error_code": "CORS_ORIGIN_BLOCKED",
                    "error": f"Origin is not in the CORS allowlist.",
                },
            )

        # Preflight OPTIONS — return immediately without hitting auth
        if request.method == "OPTIONS":
            response = JSONResponse(status_code=200, content={})
            _apply_cors_headers(response, origin, config.cors)
            return response

        response = await call_next(request)
        _apply_cors_headers(response, origin, config.cors)
        return response


def _effective_allowed_origins(origins: list[str]) -> list[str]:
    """Return the effective allowed origins, stripping wildcard outside dev/test."""
    env = os.getenv("TASKFRAME_ENV", "demo").lower().strip()
    if env in _DEV_ENVS:
        return origins
    # Strip wildcard outside dev/test
    return [o for o in origins if o != "*"]


def _apply_cors_headers(response, origin: str, cors: CORSConfig) -> None:
    try:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        if cors.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = ", ".join(cors.allowed_methods)
        response.headers["Access-Control-Allow-Headers"] = ", ".join(cors.allowed_headers)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Security status
# ---------------------------------------------------------------------------

def get_security_status(config: BackendSecurityConfig, runtime_data_dir: str = "runtime_data") -> dict[str, Any]:
    """Return a status dict safe for the /api/security/status endpoint.

    Never includes token hashes or plaintext values.
    """
    warnings: list[str] = []
    errors: list[str] = []

    if not config.enabled:
        warnings.append("Backend security hardening is disabled.")

    if not config.security_headers.enabled:
        warnings.append("Security headers are disabled.")

    if not config.cors.enabled:
        warnings.append("CORS enforcement is disabled.")

    if not config.auth.token_required:
        warnings.append("Token authentication is not required (auth.token_required=false).")

    if config.auth.allow_plaintext_dev_token:
        env = os.getenv("TASKFRAME_ENV", "demo").lower()
        if env not in _DEV_ENVS:
            warnings.append("Plaintext dev tokens are allowed in a non-dev environment.")

    # Check for wildcard CORS outside dev
    env = os.getenv("TASKFRAME_ENV", "demo").lower()
    if "*" in config.cors.allowed_origins and env not in _DEV_ENVS:
        errors.append("Wildcard CORS origin (*) is configured outside a dev/test environment.")

    # Expired tokens
    expired_count = sum(
        1 for r in config.token_records
        if parse_token_metadata(r).get("is_expired", False)
    )
    if expired_count > 0:
        warnings.append(f"{expired_count} expired token record(s) found.")

    # Authz posture — imported lazily to avoid circular imports
    authz_info: dict[str, Any] = {
        "authz_enabled": False,
        "known_scope_count": 0,
        "mapped_route_count": 0,
        "unmapped_route_count": 0,
        "tokens_with_unknown_scopes": 0,
    }
    try:
        from src.backend_authz import get_authz_status
        authz_info = get_authz_status(config.token_records)
    except Exception:
        pass

    return {
        "ok": len(errors) == 0,
        "security_headers_enabled": config.security_headers.enabled,
        "cors_enabled": config.cors.enabled,
        "allowed_origin_count": len(_effective_allowed_origins(config.cors.allowed_origins)),
        "auth_required": config.auth.token_required,
        "token_hash_count": len(config.auth.token_hashes),
        "token_record_count": len(config.token_records),
        "plaintext_dev_token_allowed": config.auth.allow_plaintext_dev_token,
        "expired_token_count": expired_count,
        "warnings": warnings,
        "errors": errors,
        **authz_info,
    }
