"""Spec 149 — Backend Auth Scopes + Route Permission Enforcement.

Provides:
- KNOWN_SCOPES — canonical scope set.
- ROUTE_SCOPE_REQUIREMENTS — method+path → required scopes map.
- normalize_scope() / validate_token_scopes() — scope validation helpers.
- get_required_scopes() — route lookup (None = unmapped → fail closed).
- assert_token_has_scopes() — per-token scope check.
- build_authz_decision() — full decision record (ALLOW / DENY).
- get_authz_status() — safe status dict for /api/security/status.
- install_authz_middleware() — ASGI middleware enforcing scopes after auth.

Security constraints:
- Token values and hashes are NEVER logged or returned.
- Only token_label (from the token_record) appears in audit records.
- Scope enforcement is active only when token_records are configured.
- Tokens without a matching token_record pass through unchanged (backwards compat).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Canonical scopes
# ---------------------------------------------------------------------------

KNOWN_SCOPES: frozenset[str] = frozenset({
    "read",
    "events:intake",
    "runs:read",
    "reports:read",
    "approvals:read",
    "approvals:write",
    "readiness:read",
    "security:read",
    "admin:status",
})

# ---------------------------------------------------------------------------
# Route permission map
# ---------------------------------------------------------------------------

ROUTE_SCOPE_REQUIREMENTS: dict[str, list[str]] = {
    "GET /api/health":                                                          [],
    "GET /api/security/status":                                                 ["security:read"],
    "POST /api/events":                                                         ["events:intake"],
    "GET /api/events":                                                          ["runs:read"],
    "GET /api/events/{event_id}":                                               ["runs:read"],
    "GET /api/audit":                                                           ["admin:status"],
    "GET /api/audit/{audit_id}":                                                ["admin:status"],
    "GET /api/runs":                                                            ["runs:read"],
    "GET /api/runs/{frame_id}":                                                 ["runs:read"],
    "GET /api/runs/{frame_id}/evidence":                                        ["reports:read"],
    "GET /api/runs/{frame_id}/approval-pack":                                   ["approvals:read"],
    "GET /api/runs/{frame_id}/failure-summary":                                 ["runs:read"],
    "POST /api/runs/{frame_id}/report":                                         ["reports:read"],
    "POST /api/runs/{frame_id}/pending-actions/{action_id}/approve":            ["approvals:write"],
    "POST /api/runs/{frame_id}/pending-actions/{action_id}/reject":             ["approvals:write"],
}

# ---------------------------------------------------------------------------
# Route pattern compilation
# ---------------------------------------------------------------------------

def _path_pattern_to_regex(path: str) -> str:
    """Convert a path like '/api/runs/{frame_id}/evidence' to a regex string."""
    parts = re.split(r"(\{[^}]+\})", path)
    regex_parts: list[str] = []
    for part in parts:
        if part.startswith("{") and part.endswith("}"):
            regex_parts.append("[^/]+")
        else:
            regex_parts.append(re.escape(part))
    return "".join(regex_parts)


def _compile_route_patterns() -> list[tuple[re.Pattern[str], list[str]]]:
    compiled: list[tuple[re.Pattern[str], list[str]]] = []
    for key, scopes in ROUTE_SCOPE_REQUIREMENTS.items():
        method, _, path = key.partition(" ")
        path_regex = _path_pattern_to_regex(path)
        full_pattern = re.compile(f"^{method.upper()} {path_regex}$")
        compiled.append((full_pattern, list(scopes)))
    return compiled


_COMPILED_PATTERNS: list[tuple[re.Pattern[str], list[str]]] = _compile_route_patterns()


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------

def normalize_scope(scope: str) -> str:
    """Normalize a scope string to lowercase, stripped."""
    return str(scope).strip().lower()


def validate_token_scopes(scopes: list[str]) -> dict[str, Any]:
    """Validate a list of scopes against the canonical known set.

    Returns dict with ok, errors, unknown_scopes.
    """
    if not isinstance(scopes, list):
        return {"ok": False, "errors": ["scopes must be a list"], "unknown_scopes": []}
    unknown = [s for s in scopes if normalize_scope(s) not in KNOWN_SCOPES]
    if unknown:
        return {
            "ok": False,
            "errors": [f"Unknown scope(s): {unknown}"],
            "unknown_scopes": unknown,
        }
    return {"ok": True, "errors": [], "unknown_scopes": []}


# ---------------------------------------------------------------------------
# Route lookup
# ---------------------------------------------------------------------------

def get_required_scopes(method: str, path: str) -> list[str] | None:
    """Return required scopes for the given method+path, or None if unmapped.

    None signals that the route is not in the permission map; callers must
    fail closed when scope enforcement is active.
    """
    key = f"{method.upper()} {path.rstrip('/')}"
    # Try exact match first (fast path)
    if key in ROUTE_SCOPE_REQUIREMENTS:
        return list(ROUTE_SCOPE_REQUIREMENTS[key])
    # Try without trailing slash (normalize)
    for pattern, scopes in _COMPILED_PATTERNS:
        if pattern.match(key):
            return list(scopes)
    return None


# ---------------------------------------------------------------------------
# Token scope assertion
# ---------------------------------------------------------------------------

def assert_token_has_scopes(
    token_record: dict[str, Any],
    required_scopes: list[str],
) -> dict[str, Any]:
    """Check that token_record has all required_scopes.

    Returns dict with ok, missing_scopes, errors.
    """
    token_scopes = {normalize_scope(s) for s in token_record.get("scopes", [])}
    missing = [s for s in required_scopes if normalize_scope(s) not in token_scopes]
    if missing:
        return {
            "ok": False,
            "missing_scopes": missing,
            "errors": [f"Missing required scope: {missing[0]}"],
        }
    return {"ok": True, "missing_scopes": [], "errors": []}


# ---------------------------------------------------------------------------
# Full authz decision
# ---------------------------------------------------------------------------

def build_authz_decision(
    token_record: dict[str, Any],
    method: str,
    path: str,
) -> dict[str, Any]:
    """Build a deterministic authz decision dict for one request.

    Returns ALLOW or DENY with full context. Never includes token values.
    """
    method_upper = method.upper()
    token_label = str(token_record.get("label", "") or "")
    token_scopes = [normalize_scope(s) for s in token_record.get("scopes", [])]
    required_scopes = get_required_scopes(method_upper, path)

    if required_scopes is None:
        return {
            "ok": False,
            "decision": "DENY",
            "reason": "Route is not in the permission map.",
            "token_label": token_label,
            "method": method_upper,
            "path": path,
            "required_scopes": [],
            "token_scopes": token_scopes,
            "missing_scopes": [],
            "errors": ["AUTHZ_ROUTE_UNMAPPED"],
        }

    check = assert_token_has_scopes(token_record, required_scopes)
    missing = check.get("missing_scopes", [])

    if missing:
        return {
            "ok": False,
            "decision": "DENY",
            "reason": f"Missing required scope: {missing[0]}",
            "token_label": token_label,
            "method": method_upper,
            "path": path,
            "required_scopes": required_scopes,
            "token_scopes": token_scopes,
            "missing_scopes": missing,
            "errors": [],
        }

    return {
        "ok": True,
        "decision": "ALLOW",
        "token_label": token_label,
        "method": method_upper,
        "path": path,
        "required_scopes": required_scopes,
        "token_scopes": token_scopes,
        "missing_scopes": [],
        "errors": [],
    }


# ---------------------------------------------------------------------------
# Authz status (safe for /api/security/status)
# ---------------------------------------------------------------------------

def get_authz_status(token_records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return authz posture summary. Never includes token hashes or values."""
    unknown_scope_token_count = 0
    if token_records:
        for record in token_records:
            scopes = list(record.get("scopes", []) or [])
            result = validate_token_scopes(scopes)
            if not result["ok"]:
                unknown_scope_token_count += 1

    return {
        "authz_enabled": True,
        "known_scope_count": len(KNOWN_SCOPES),
        "mapped_route_count": len(ROUTE_SCOPE_REQUIREMENTS),
        "unmapped_route_count": 0,
        "tokens_with_unknown_scopes": unknown_scope_token_count,
    }


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------

def _write_authz_audit(
    *,
    runtime_data_dir: str,
    event_type: str,
    request_id: str,
    token_label: str,
    method: str,
    path: str,
    required_scopes: list[str],
    missing_scopes: list[str],
) -> None:
    """Write an authz audit record. Never includes token values or hashes."""
    from src.backend.audit import append_backend_audit_record

    record: dict[str, Any] = {
        "event_type": event_type,
        "request_id": request_id,
        "token_label": token_label,
        "method": method,
        "path": path,
        "required_scopes": required_scopes,
        "missing_scopes": missing_scopes,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    try:
        append_backend_audit_record(record, runtime_data_dir)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# ASGI middleware
# ---------------------------------------------------------------------------

def install_authz_middleware(app) -> None:
    """Innermost middleware: enforces token scopes after auth resolves context.

    Registration order: call this BEFORE install_backend_auth_middleware so
    that it becomes innermost and executes after auth sets the auth context.

    Enforcement is skipped when:
    - No token_records are configured on app.state.backend_security_config.
    - Auth context is missing or auth failed (passes to route for 401).
    - Dev bypass is active (no bearer token present).
    - The bearer token has no matching record in token_records (pass-through).
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.middleware("http")
    async def _authz_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        from src.backend_security import parse_token_metadata, verify_token

        config = getattr(request.app.state, "backend_security_config", None)

        # Skip: no token_records configured (backwards compatibility)
        if not config or not getattr(config, "token_records", None):
            return await call_next(request)

        # Skip: auth hasn't run or failed — let route handle 401
        auth_ctx = getattr(request.state, "backend_auth_context", None)
        if auth_ctx is None or not getattr(auth_ctx, "ok", False):
            return await call_next(request)

        # Skip: dev_bypass mode has no bearer token
        if getattr(auth_ctx, "dev_bypass", False):
            return await call_next(request)

        # Extract bearer token
        bearer = (request.headers.get("authorization") or "").strip()
        if not bearer.lower().startswith("bearer "):
            return await call_next(request)
        token = bearer[7:].strip()
        if not token:
            return await call_next(request)

        # Find matching token_record by hash
        matched_record: dict[str, Any] | None = None
        for record in config.token_records:
            meta = parse_token_metadata(record)
            if verify_token(token, [meta["token_hash"]]):
                matched_record = dict(record)
                break

        # Skip: token not in records → no scope enforcement
        if matched_record is None:
            return await call_next(request)

        # Build authz decision
        method = request.method.upper()
        path = str(request.url.path)
        decision = build_authz_decision(matched_record, method, path)

        rd = str(getattr(getattr(request.app, "state", None), "runtime_data_dir", "runtime_data"))
        request_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex}"
        token_label = decision.get("token_label", "")

        if not decision["ok"]:
            is_unmapped = "AUTHZ_ROUTE_UNMAPPED" in decision.get("errors", [])
            event_type = "AUTHZ_ROUTE_UNMAPPED" if is_unmapped else "AUTHZ_DENIED"
            _write_authz_audit(
                runtime_data_dir=rd,
                event_type=event_type,
                request_id=request_id,
                token_label=token_label,
                method=method,
                path=path,
                required_scopes=decision.get("required_scopes", []),
                missing_scopes=decision.get("missing_scopes", []),
            )
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": "FORBIDDEN",
                    "message": "Token does not have permission for this endpoint.",
                    "required_scopes": decision.get("required_scopes", []),
                    "missing_scopes": decision.get("missing_scopes", []),
                    "request_id": request_id,
                },
            )

        _write_authz_audit(
            runtime_data_dir=rd,
            event_type="AUTHZ_ALLOWED",
            request_id=request_id,
            token_label=token_label,
            method=method,
            path=path,
            required_scopes=decision.get("required_scopes", []),
            missing_scopes=[],
        )
        return await call_next(request)
