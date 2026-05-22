from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from fastapi import Request

from .config import BackendAuthConfig, ROLE_ORDER, load_backend_auth_config


@dataclass(frozen=True)
class BackendAuthContext:
    ok: bool
    role: str = ""
    token_name: str = ""
    authenticated: bool = False
    dev_bypass: bool = False
    error_code: str = ""
    error: str = ""


class BackendAuthError(Exception):
    def __init__(self, status_code: int, error_code: str, error: str):
        super().__init__(error)
        self.status_code = status_code
        self.error_code = error_code
        self.error = error


def install_backend_auth_middleware(app) -> None:
    @app.middleware("http")
    async def _backend_auth_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.backend_auth_context = resolve_backend_auth_context(request)
        return await call_next(request)


def resolve_backend_auth_context(request: Request) -> BackendAuthContext:
    config = _get_backend_auth_config(request)
    if not config.valid:
        return BackendAuthContext(ok=False, error_code="AUTH_INVALID", error="Authentication token is invalid.")
    if config.dev_bypass_active:
        return BackendAuthContext(ok=True, role="admin", authenticated=False, dev_bypass=True)

    token = _extract_token(request)
    if token is None:
        return BackendAuthContext(ok=False, error_code="AUTH_REQUIRED", error="Authentication token is required.")
    if not token.strip():
        return BackendAuthContext(ok=False, error_code="AUTH_INVALID", error="Authentication token is invalid.")

    for token_spec in config.tokens:
        if token == token_spec.token_value:
            return BackendAuthContext(
                ok=True,
                role=token_spec.role,
                token_name=token_spec.name,
                authenticated=True,
                dev_bypass=False,
            )

    return BackendAuthContext(ok=False, error_code="AUTH_INVALID", error="Authentication token is invalid.")


def require_backend_role(required_role: str) -> Callable[[Request], Coroutine[Any, Any, BackendAuthContext]]:
    required_role = str(required_role).strip().lower()
    if required_role not in ROLE_ORDER:
        raise ValueError(f"Unknown backend role: {required_role}")

    async def _dependency(request: Request) -> BackendAuthContext:
        context = getattr(request.state, "backend_auth_context", None)
        if not isinstance(context, BackendAuthContext):
            context = resolve_backend_auth_context(request)
            request.state.backend_auth_context = context
        if not context.ok:
            raise BackendAuthError(401, context.error_code or "AUTH_INVALID", context.error or "Authentication token is invalid.")
        if context.dev_bypass:
            return context
        if ROLE_ORDER.get(context.role, 0) < ROLE_ORDER[required_role]:
            raise BackendAuthError(
                403,
                "AUTH_FORBIDDEN",
                "The authenticated role is not allowed to perform this operation.",
            )
        return context

    return _dependency


def backend_auth_status(request: Request) -> dict[str, Any]:
    config = _get_backend_auth_config(request)
    return {
        "enabled": bool(config.enabled),
        "dev_bypass": bool(config.dev_bypass_active),
        "configured_roles": config.configured_roles,
    }


def backend_auth_error_response(error_code: str, error: str) -> dict[str, Any]:
    return {"ok": False, "error_code": error_code, "error": error}


def _extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header:
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() == "bearer":
            return token
        return ""
    fallback = request.headers.get("x-taskframe-token", "")
    if fallback:
        return fallback
    return None


def _get_backend_auth_config(request: Request) -> BackendAuthConfig:
    config = getattr(request.app.state, "backend_auth_config", None)
    if isinstance(config, BackendAuthConfig):
        return config
    config = load_backend_auth_config()
    request.app.state.backend_auth_config = config
    return config
