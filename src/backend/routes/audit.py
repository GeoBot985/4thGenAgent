"""Spec 145–146 — Admin-only audit query endpoints with rate limiting and ID validation.

GET /api/audit          — list audit records (admin only)
GET /api/audit/{id}     — read single audit record (admin only)

All reads are themselves audited.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from src.backend.audit import (
    filter_backend_audit_records,
    read_backend_audit_records,
    write_route_audit,
)
from src.backend.auth import require_backend_role
from src.backend.errors import invalid_id_error
from src.backend.hardening import clamp_limit, is_valid_id
from src.backend.rate_limit import require_rate_limit

router = APIRouter()


@router.get("", dependencies=[Depends(require_backend_role("admin")), Depends(require_rate_limit("audit_read"))])
async def list_audit_records(
    request: Request,
    limit: int = 100,
    operation: str | None = None,
    result: str | None = None,
    role: str | None = None,
    frame_id: str | None = None,
    event_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    rd = request.app.state.runtime_data_dir
    hardening = getattr(request.app.state, "backend_hardening_config", None)
    safe_limit = clamp_limit(limit, hardening) if hardening else min(max(1, limit), 500)

    # Validate string filters that correspond to IDs
    for param_name, param_val in (("frame_id", frame_id), ("event_id", event_id), ("request_id", request_id)):
        if param_val and not is_valid_id(param_val):
            write_route_audit(request, "request.blocked.invalid_query", "blocked", 400, error=f"Invalid {param_name} filter.")
            return JSONResponse(status_code=400, content=invalid_id_error())

    try:
        records = read_backend_audit_records(rd, limit=100_000)
        records = filter_backend_audit_records(
            records,
            operation=operation or None,
            result=result or None,
            role=role or None,
            frame_id=frame_id or None,
            event_id=event_id or None,
            request_id=request_id or None,
        )
        records = records[:safe_limit]
    except Exception as exc:
        write_route_audit(request, "audit.list", "error", 500, error=str(exc))
        return {"ok": False, "records": [], "count": 0, "error": str(exc)}

    write_route_audit(
        request,
        "audit.list",
        "success",
        200,
        summary=f"Admin listed {len(records)} audit records.",
    )
    return {"ok": True, "records": records, "count": len(records), "error": ""}


@router.get("/{audit_id}", dependencies=[Depends(require_backend_role("admin")), Depends(require_rate_limit("audit_read"))])
async def get_audit_record(audit_id: str, request: Request) -> dict[str, Any]:
    if not is_valid_id(audit_id):
        write_route_audit(request, "request.blocked.invalid_id", "blocked", 400, error=f"Invalid audit_id: {audit_id!r}")
        return JSONResponse(status_code=400, content=invalid_id_error())

    rd = request.app.state.runtime_data_dir
    try:
        all_records = read_backend_audit_records(rd, limit=100_000)
        matching = [r for r in all_records if r.get("audit_id") == audit_id]
    except Exception as exc:
        write_route_audit(request, "audit.read", "error", 500, error=str(exc))
        return {"ok": False, "record": {}, "error": str(exc)}

    if not matching:
        write_route_audit(
            request, "audit.read", "failure", 404,
            error=f"Audit record not found: {audit_id}",
        )
        return {"ok": False, "record": {}, "error": f"Audit record not found: {audit_id}"}

    write_route_audit(
        request, "audit.read", "success", 200,
        summary=f"Admin read audit record {audit_id}.",
    )
    return {"ok": True, "record": matching[0], "error": ""}
