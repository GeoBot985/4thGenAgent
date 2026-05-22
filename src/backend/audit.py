"""Spec 145 — Backend audit trail helper.

Writes structured JSONL audit records for all production backend API activity.
Never stores bearer tokens, X-TaskFrame-Token, credentials, or raw request bodies.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request

_AUDIT_SUBDIR = "backend_audit"
_AUDIT_FILENAME = "backend_audit.jsonl"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")


# ---------------------------------------------------------------------------
# Request ID
# ---------------------------------------------------------------------------

def create_request_id(request: Request) -> str:
    """Return sanitized incoming X-Request-ID or generate a new one."""
    incoming = (request.headers.get("x-request-id") or "").strip()
    if incoming and _REQUEST_ID_RE.match(incoming):
        return incoming
    return f"req_{uuid.uuid4().hex}"


def install_audit_request_id_middleware(app) -> None:
    """Attach request_id to request.state and return it in X-Request-ID header."""
    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = create_request_id(request)
        response = await call_next(request)
        try:
            response.headers["X-Request-ID"] = request.state.request_id
        except Exception:
            pass
        return response


# ---------------------------------------------------------------------------
# Record construction
# ---------------------------------------------------------------------------

def build_backend_audit_record(
    *,
    request: Request,
    request_id: str,
    operation: str,
    result: str,
    status_code: int,
    target: dict[str, str] | None = None,
    security_auth_result: str = "allowed",
    forbidden_reason: str = "",
    summary: str = "",
    error: str = "",
) -> dict[str, Any]:
    auth_ctx = getattr(request.state, "backend_auth_context", None)
    actor: dict[str, Any] = {"token_name": "", "role": "", "authenticated": False}
    if auth_ctx is not None:
        actor = {
            "token_name": getattr(auth_ctx, "token_name", "") or "",
            "role": getattr(auth_ctx, "role", "") or "",
            "authenticated": bool(getattr(auth_ctx, "authenticated", False)),
        }
    return {
        "audit_id": f"aud_{uuid.uuid4().hex}",
        "timestamp": _utc_now(),
        "request_id": request_id,
        "actor": actor,
        "http": {
            "method": request.method,
            "path": str(request.url.path),
            "status_code": status_code,
        },
        "operation": operation,
        "result": result,
        "target": target or {"frame_id": "", "event_id": "", "action_id": "", "manifest_id": ""},
        "security": {
            "auth_required": True,
            "auth_result": security_auth_result,
            "forbidden_reason": forbidden_reason,
        },
        "summary": summary,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def append_backend_audit_record(record: dict[str, Any], runtime_data_dir: str) -> None:
    audit_dir = Path(runtime_data_dir) / _AUDIT_SUBDIR
    audit_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with (audit_dir / _AUDIT_FILENAME).open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_backend_audit_records(runtime_data_dir: str, limit: int = 100) -> list[dict[str, Any]]:
    audit_path = get_audit_ledger_path(runtime_data_dir)
    if not audit_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped:
                try:
                    records.append(json.loads(stripped))
                except Exception:
                    pass
    except Exception:
        return []
    return list(reversed(records))[:max(1, limit)]


def filter_backend_audit_records(
    records: list[dict[str, Any]],
    *,
    operation: str | None = None,
    result: str | None = None,
    role: str | None = None,
    frame_id: str | None = None,
    event_id: str | None = None,
    request_id: str | None = None,
) -> list[dict[str, Any]]:
    out = []
    for r in records:
        if operation and r.get("operation") != operation:
            continue
        if result and r.get("result") != result:
            continue
        if role and r.get("actor", {}).get("role") != role:
            continue
        if frame_id and r.get("target", {}).get("frame_id") != frame_id:
            continue
        if event_id and r.get("target", {}).get("event_id") != event_id:
            continue
        if request_id and r.get("request_id") != request_id:
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Payload redaction
# ---------------------------------------------------------------------------

def redact_request_summary(body: bytes | None, content_type: str = "") -> dict[str, Any]:
    """Summarise a request payload without storing its values."""
    if not body:
        return {"payload_keys": [], "payload_size": 0}
    size = len(body)
    keys: list[str] = []
    if "json" in content_type.lower():
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                keys = list(parsed.keys())
        except Exception:
            pass
    return {"payload_keys": keys, "payload_size": size}


# ---------------------------------------------------------------------------
# Convenience writer (used by route handlers)
# ---------------------------------------------------------------------------

def write_route_audit(
    request: Request,
    operation: str,
    result: str,
    status_code: int,
    *,
    target: dict[str, str] | None = None,
    security_auth_result: str = "allowed",
    forbidden_reason: str = "",
    summary: str = "",
    error: str = "",
    raise_on_failure: bool = False,
) -> bool:
    """Write an audit record for a route handler. Returns True on success.

    Swallows write errors by default so read-only routes are never crashed by audit failures.
    Pass raise_on_failure=True for write routes that must surface audit problems.
    """
    rd = getattr(getattr(request, "app", None), "state", None)
    rd = getattr(rd, "runtime_data_dir", "runtime_data") if rd is not None else "runtime_data"
    request_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex}"
    record = build_backend_audit_record(
        request=request,
        request_id=request_id,
        operation=operation,
        result=result,
        status_code=status_code,
        target=target,
        security_auth_result=security_auth_result,
        forbidden_reason=forbidden_reason,
        summary=summary,
        error=error,
    )
    try:
        append_backend_audit_record(record, str(rd))
        return True
    except Exception:
        if raise_on_failure:
            raise
        return False


# ---------------------------------------------------------------------------
# Status / path helpers
# ---------------------------------------------------------------------------

def get_audit_ledger_path(runtime_data_dir: str) -> Path:
    return Path(runtime_data_dir) / _AUDIT_SUBDIR / _AUDIT_FILENAME


def get_audit_status(runtime_data_dir: str) -> dict[str, Any]:
    ledger_path = get_audit_ledger_path(runtime_data_dir)
    return {
        "enabled": True,
        "ledger_path": str(ledger_path),
        "record_count_available": ledger_path.is_file(),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
