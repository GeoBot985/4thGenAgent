"""Spec 146 — Backend request hardening.

Provides:
- BackendHardeningConfig dataclass with safe defaults.
- load_hardening_config() — load from config file or env vars.
- is_valid_id() — validate path parameter identifiers.
- clamp_limit() — bound list query limits.
- get_hardening_status() — health status dict.
- install_body_size_middleware() — reject oversized POST/PUT/PATCH bodies.
- require_json_body — FastAPI dependency for JSON body validation.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from src.backend.errors import (
    invalid_json_error,
    invalid_request_body_error,
    too_large_error,
)

# ---------------------------------------------------------------------------
# ID validation
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,120}$")

_FORBIDDEN_SEQUENCES = ("..", "/", "\\", "\n", "\r", "\x00")


def is_valid_id(value: str, max_length: int = 120) -> bool:
    if not value or len(value) > max_length:
        return False
    if not _ID_RE.match(value):
        return False
    for seq in _FORBIDDEN_SEQUENCES:
        if seq in value:
            return False
    return True


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_DEFAULT_RATE_LIMITS: dict[str, dict[str, int]] = {
    "health": {"requests": 120, "window_seconds": 60},
    "runs_read": {"requests": 60, "window_seconds": 60},
    "events_read": {"requests": 60, "window_seconds": 60},
    "events_submit": {"requests": 20, "window_seconds": 60},
    "report_generate": {"requests": 10, "window_seconds": 60},
    "pending_action_write": {"requests": 20, "window_seconds": 60},
    "audit_read": {"requests": 30, "window_seconds": 60},
    "auth_failure": {"requests": 20, "window_seconds": 60},
}


@dataclass
class RateLimitConfig:
    requests: int
    window_seconds: int


@dataclass
class BackendHardeningConfig:
    enabled: bool = True
    max_body_bytes: int = 262144
    max_id_length: int = 120
    default_list_limit: int = 50
    max_list_limit: int = 500
    rate_limits: dict[str, RateLimitConfig] = field(default_factory=dict)


def _default_rate_limits() -> dict[str, RateLimitConfig]:
    return {k: RateLimitConfig(**v) for k, v in _DEFAULT_RATE_LIMITS.items()}


def load_hardening_config(config_path: str | Path | None = None) -> BackendHardeningConfig:
    """Load hardening config from a JSON file or fall back to env/defaults."""
    raw: dict[str, Any] = {}

    if config_path is not None:
        path = Path(config_path)
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    raw = data.get("backend_hardening", {})
            except Exception:
                pass

    enabled = _coerce_bool(
        raw.get("enabled", os.getenv("TASKFRAME_BACKEND_HARDENING_ENABLED", "true")),
        default=True,
    )
    max_body_bytes = int(
        raw.get("max_body_bytes", os.getenv("TASKFRAME_BACKEND_MAX_BODY_BYTES", 262144))
    )
    max_id_length = int(raw.get("max_id_length", 120))
    default_list_limit = int(raw.get("default_list_limit", 50))
    max_list_limit = int(raw.get("max_list_limit", 500))

    # Rate limits: merge defaults with any overrides from config
    rl_raw = raw.get("rate_limits", {})
    rate_limits = _default_rate_limits()
    if isinstance(rl_raw, dict):
        for group, spec in rl_raw.items():
            if isinstance(spec, dict) and "requests" in spec and "window_seconds" in spec:
                rate_limits[group] = RateLimitConfig(
                    requests=int(spec["requests"]),
                    window_seconds=int(spec["window_seconds"]),
                )

    return BackendHardeningConfig(
        enabled=enabled,
        max_body_bytes=max(0, max_body_bytes),
        max_id_length=max(1, max_id_length),
        default_list_limit=max(1, default_list_limit),
        max_list_limit=max(1, max_list_limit),
        rate_limits=rate_limits,
    )


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


# ---------------------------------------------------------------------------
# Query bounds
# ---------------------------------------------------------------------------

def clamp_limit(limit: int | None, config: BackendHardeningConfig) -> int:
    """Return a safe list limit within [1, max_list_limit]."""
    if limit is None or limit < 1:
        return config.default_list_limit
    return min(limit, config.max_list_limit)


# ---------------------------------------------------------------------------
# Health status
# ---------------------------------------------------------------------------

def get_hardening_status(config: BackendHardeningConfig) -> dict[str, Any]:
    return {
        "enabled": config.enabled,
        "max_body_bytes": config.max_body_bytes,
        "max_id_length": config.max_id_length,
        "default_list_limit": config.default_list_limit,
        "max_list_limit": config.max_list_limit,
        "rate_limits_enabled": config.enabled and bool(config.rate_limits),
    }


# ---------------------------------------------------------------------------
# Body size middleware
# ---------------------------------------------------------------------------

def install_body_size_middleware(app) -> None:
    """Middleware that rejects oversized request bodies. Reads config at request time."""
    from src.backend.audit import write_route_audit

    @app.middleware("http")
    async def _body_size_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        hardening = getattr(request.app.state, "backend_hardening_config", None)
        if (
            hardening is not None
            and hardening.enabled
            and hardening.max_body_bytes > 0
            and request.method in ("POST", "PUT", "PATCH")
        ):
            # Check Content-Length header first (avoids reading body)
            cl_header = request.headers.get("content-length", "")
            if cl_header:
                try:
                    if int(cl_header) > hardening.max_body_bytes:
                        write_route_audit(
                            request,
                            "request.blocked.too_large",
                            "blocked",
                            413,
                            error=f"Content-Length {cl_header} exceeds limit {hardening.max_body_bytes}.",
                        )
                        return JSONResponse(status_code=413, content=too_large_error())
                except ValueError:
                    pass
            # Read body to check actual size
            body = await request.body()
            if len(body) > hardening.max_body_bytes:
                write_route_audit(
                    request,
                    "request.blocked.too_large",
                    "blocked",
                    413,
                    error=f"Body {len(body)} bytes exceeds limit {hardening.max_body_bytes}.",
                )
                return JSONResponse(status_code=413, content=too_large_error())
        return await call_next(request)


# ---------------------------------------------------------------------------
# JSON body validation dependency
# ---------------------------------------------------------------------------

_MAX_JSON_DEPTH = 10


def _json_depth(obj: Any, depth: int = 0) -> int:
    if depth > _MAX_JSON_DEPTH:
        return depth
    if isinstance(obj, dict):
        return max((_json_depth(v, depth + 1) for v in obj.values()), default=depth)
    if isinstance(obj, list):
        return max((_json_depth(v, depth + 1) for v in obj), default=depth)
    return depth


async def require_json_body(request: Request) -> None:
    """FastAPI dependency: validates that POST body is present, valid JSON, and a dict."""
    if request.method not in ("POST", "PUT", "PATCH"):
        return
    ct = (request.headers.get("content-type") or "").lower()
    if "json" not in ct:
        return
    body = await request.body()
    if not body or not body.strip():
        from src.backend.audit import write_route_audit
        write_route_audit(request, "request.blocked.invalid_json", "blocked", 400, error="Empty body.")
        raise _HardeningHTTPException(400, "INVALID_JSON", "Request body is not valid JSON.")
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        from src.backend.audit import write_route_audit
        write_route_audit(request, "request.blocked.invalid_json", "blocked", 400, error="Invalid JSON.")
        raise _HardeningHTTPException(400, "INVALID_JSON", "Request body is not valid JSON.")
    if not isinstance(parsed, dict):
        from src.backend.audit import write_route_audit
        write_route_audit(request, "request.blocked.invalid_json", "blocked", 400, error="Body is not a JSON object.")
        raise _HardeningHTTPException(400, "INVALID_REQUEST_BODY", "Request body must be a JSON object.")
    if _json_depth(parsed) > _MAX_JSON_DEPTH:
        from src.backend.audit import write_route_audit
        write_route_audit(request, "request.blocked.invalid_json", "blocked", 400, error="JSON nesting too deep.")
        raise _HardeningHTTPException(400, "INVALID_REQUEST_BODY", "Request body must be a JSON object.")


# ---------------------------------------------------------------------------
# Internal exception (resolved to flat JSON by production_backend exception handler)
# ---------------------------------------------------------------------------

class _HardeningHTTPException(Exception):
    """Internal exception for hardening rejections that need flat JSON responses."""
    def __init__(self, status_code: int, error_code: str, error: str, *, headers: dict[str, str] | None = None):
        super().__init__(error)
        self.status_code = status_code
        self.error_code = error_code
        self.error = error
        self.headers = headers or {}
