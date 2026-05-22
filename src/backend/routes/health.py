from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from src.backend.audit import get_audit_status, write_route_audit
from src.backend.auth import backend_auth_status, require_backend_role

router = APIRouter()


@router.get("", dependencies=[Depends(require_backend_role("viewer"))])
async def get_health(request: Request) -> dict[str, Any]:
    from runtime.runtime_environment import load_runtime_profile

    runtime_profile = load_runtime_profile()
    runtime_live_mode = bool(runtime_profile.get("profile") == "live" and not runtime_profile.get("activation_blocked", False))
    auth_status = backend_auth_status(request)
    rd = request.app.state.runtime_data_dir

    error = ""
    if not request.app.state.backend_auth_config.valid:
        error = "Backend auth config is invalid."
        backend = "auth_invalid"
        ok = False
    else:
        backend = "ready"
        ok = True

    audit_status = get_audit_status(rd)

    write_route_audit(request, "health.read", "success", 200, summary="Health check.")

    return {
        "ok": ok,
        "backend": backend,
        "auth": auth_status,
        "audit": audit_status,
        "runtime_live_mode": runtime_live_mode,
        "error": error,
    }
