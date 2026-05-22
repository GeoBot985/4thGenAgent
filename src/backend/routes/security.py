"""Spec 148 — /api/security/status endpoint."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from src.backend.auth import require_backend_role
from src.backend.rate_limit import require_rate_limit

router = APIRouter()


@router.get("", dependencies=[Depends(require_backend_role("viewer")), Depends(require_rate_limit("runs_read"))])
async def security_status(request: Request) -> dict[str, Any]:
    """Return backend security posture. Never exposes token hashes or plaintext secrets."""
    from src.backend.audit import write_route_audit
    from src.backend_security import BackendSecurityConfig, get_security_status

    config: BackendSecurityConfig | None = getattr(request.app.state, "backend_security_config", None)
    rd = getattr(getattr(request.app, "state", None), "runtime_data_dir", "runtime_data")

    if config is None:
        write_route_audit(request, "security.status", "error", 500, error="Security config not loaded.")
        return {"ok": False, "error": "Security config not available."}

    status = get_security_status(config, runtime_data_dir=str(rd))
    write_route_audit(request, "security.status", "success", 200, summary="Security status read.")
    return status
