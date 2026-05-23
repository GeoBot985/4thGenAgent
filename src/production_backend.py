"""Spec 141–146 — Production Backend Run Operations API.

FastAPI application exposing controlled read/operate endpoints for TaskFrame runs.
Spec 145 adds a structured audit trail. Spec 146 adds request hardening and rate limits.

Safety contract:
- frame_id and action_id are validated as identifiers (no path traversal).
- No arbitrary file read endpoints.
- No direct tool execution from API requests.
- Approval/rejection flows through existing runtime approval functions only.
- Live side effects remain controlled by existing live execution guardrails.
- Dry-run is the default for all write operations.
- Bearer tokens and credentials are never stored in audit records.
- Oversized, malformed, or rate-exceeded requests are rejected and audited.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from src.backend.audit import install_audit_request_id_middleware, write_route_audit
from src.backend.auth import BackendAuthError, backend_auth_error_response, install_backend_auth_middleware, require_backend_role
from src.backend.config import load_backend_auth_config
from src.backend.errors import invalid_id_error, invalid_json_error, invalid_request_body_error, rate_limited_error
from src.backend.hardening import (
    BackendHardeningConfig,
    _HardeningHTTPException,
    clamp_limit,
    install_body_size_middleware,
    is_valid_id,
    load_hardening_config,
    require_json_body,
)
from src.backend.rate_limit import (
    BackendRateLimitError,
    FixedWindowRateLimiter,
    make_auth_failure_key,
    require_rate_limit,
)
from src.backend_security import (
    BackendSecurityConfig,
    install_cors_middleware,
    install_security_headers_middleware,
    load_security_config,
)
from src.backend_authz import install_authz_middleware
from runtime.taskframe import to_dict as taskframe_to_dict


class ReportRequest(BaseModel):
    rebuild: bool = False


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str | None = None
    decision: str | None = None
    expected_version: int | None = None


# ---------------------------------------------------------------------------
# ID validation (public — imported by routes/events.py)
# ---------------------------------------------------------------------------

def _validate_id(value: str, label: str) -> str:
    """Validate a path parameter ID. Returns value on success, raises on failure."""
    if not is_valid_id(value):
        raise _HardeningHTTPException(400, "INVALID_ID", f"Invalid {label}: contains unsafe characters or exceeds length limit.")
    return value


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    runtime_data_dir: str = "runtime_data",
    *,
    backend_auth_config_path: str | None = None,
    backend_hardening_config_path: str | None = None,
    backend_security_config_path: str | None = None,
) -> FastAPI:
    """Create and return the production backend FastAPI application."""
    app = FastAPI(
        title="TaskFrame Production Backend",
        description="Spec 141–146 — controlled read/operate API with audit trail and request hardening",
        version="1.0.0",
    )

    app.state.runtime_data_dir = runtime_data_dir
    app.state.backend_auth_config = load_backend_auth_config(backend_auth_config_path)
    app.state.backend_hardening_config = load_hardening_config(backend_hardening_config_path)
    app.state.backend_security_config = load_security_config(backend_security_config_path)
    app.state.rate_limiter = FixedWindowRateLimiter()

    # Middleware order (last registered = outermost = runs first on requests):
    #   1. authz middleware             (innermost: enforces token scopes after auth)
    #   2. auth middleware              (resolves auth context, always calls call_next)
    #   3. request_id middleware        (generates request_id for audit)
    #   4. body_size middleware         (rejects oversized requests early)
    #   5. cors middleware              (enforces CORS allowlist, handles OPTIONS)
    #   6. security_headers middleware  (outermost: adds headers to ALL responses,
    #                                   enforces token expiry before inner chain)
    install_authz_middleware(app)
    install_backend_auth_middleware(app)
    install_audit_request_id_middleware(app)
    install_body_size_middleware(app)
    install_cors_middleware(app)
    install_security_headers_middleware(app)

    # ── Exception handlers ────────────────────────────────────────────────

    _AUTH_ERROR_MAP = {
        "AUTH_REQUIRED": ("auth.missing_token", "missing"),
        "AUTH_INVALID": ("auth.invalid_token", "invalid"),
        "AUTH_FORBIDDEN": ("auth.forbidden", "forbidden"),
    }

    @app.exception_handler(BackendAuthError)
    async def _handle_backend_auth_error(request: Request, exc: BackendAuthError):  # type: ignore[no-untyped-def]
        operation, auth_result = _AUTH_ERROR_MAP.get(exc.error_code, ("auth.invalid_token", "invalid"))
        forbidden_reason = exc.error if exc.error_code == "AUTH_FORBIDDEN" else ""

        # Auth-failure rate limiting
        hardening: BackendHardeningConfig | None = getattr(request.app.state, "backend_hardening_config", None)
        rate_limiter: FixedWindowRateLimiter | None = getattr(request.app.state, "rate_limiter", None)
        if hardening and hardening.enabled and rate_limiter is not None:
            rl = hardening.rate_limits.get("auth_failure")
            if rl is not None:
                key = make_auth_failure_key(request)
                allowed, _remaining, retry_after = rate_limiter.check(key, rl.requests, rl.window_seconds)
                if not allowed:
                    write_route_audit(
                        request,
                        "request.blocked.rate_limited",
                        "blocked",
                        429,
                        error="Auth failure rate limit exceeded.",
                    )
                    resp = JSONResponse(status_code=429, content=rate_limited_error())
                    resp.headers["Retry-After"] = str(retry_after)
                    resp.headers["X-RateLimit-Limit"] = str(rl.requests)
                    resp.headers["X-RateLimit-Remaining"] = "0"
                    return resp

        write_route_audit(
            request,
            operation=operation,
            result="failure",
            status_code=exc.status_code,
            security_auth_result=auth_result,
            forbidden_reason=forbidden_reason,
            summary=exc.error,
            error=exc.error,
        )
        return JSONResponse(status_code=exc.status_code, content=backend_auth_error_response(exc.error_code, exc.error))

    @app.exception_handler(BackendRateLimitError)
    async def _handle_rate_limit(request: Request, exc: BackendRateLimitError):  # type: ignore[no-untyped-def]
        write_route_audit(
            request,
            "request.blocked.rate_limited",
            "blocked",
            429,
            summary="Request blocked by backend hardening policy.",
            error=str(exc),
        )
        resp = JSONResponse(status_code=429, content=rate_limited_error())
        if exc.retry_after:
            resp.headers["Retry-After"] = str(exc.retry_after)
        resp.headers["X-RateLimit-Limit"] = str(exc.limit)
        resp.headers["X-RateLimit-Remaining"] = "0"
        return resp

    @app.exception_handler(_HardeningHTTPException)
    async def _handle_hardening_error(request: Request, exc: _HardeningHTTPException):  # type: ignore[no-untyped-def]
        op_map = {
            "INVALID_ID": "request.blocked.invalid_id",
            "INVALID_JSON": "request.blocked.invalid_json",
            "INVALID_REQUEST_BODY": "request.blocked.invalid_json",
            "INVALID_QUERY": "request.blocked.invalid_query",
            "REQUEST_TOO_LARGE": "request.blocked.too_large",
        }
        operation = op_map.get(exc.error_code, "request.blocked.invalid_id")
        write_route_audit(request, operation, "blocked", exc.status_code, error=exc.error)
        resp = JSONResponse(status_code=exc.status_code, content={"ok": False, "error_code": exc.error_code, "error": exc.error})
        for k, v in exc.headers.items():
            resp.headers[k] = v
        return resp

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError):  # type: ignore[no-untyped-def]
        errors = exc.errors() if hasattr(exc, "errors") else []
        # Detect JSON parse failures from Pydantic/FastAPI
        for err in errors:
            err_type = err.get("type", "")
            if "json" in err_type.lower() or "json" in str(err.get("msg", "")).lower():
                write_route_audit(request, "request.blocked.invalid_json", "blocked", 400, error="Invalid JSON body.")
                return JSONResponse(status_code=400, content=invalid_json_error())
        # Schema/field errors → keep standard 422 behaviour so Pydantic rejections work
        from fastapi.exception_handlers import request_validation_exception_handler
        return await request_validation_exception_handler(request, exc)

    # ── Routers ──────────────────────────────────────────────────────────

    from src.backend.routes.audit import router as audit_router
    from src.backend.routes.events import router as events_router
    from src.backend.routes.health import router as health_router
    from src.backend.routes.security import router as security_router
    app.include_router(health_router, prefix="/api/health")
    app.include_router(events_router, prefix="/api/events")
    app.include_router(audit_router, prefix="/api/audit")
    app.include_router(security_router, prefix="/api/security/status")

    # ── GET /api/runs ─────────────────────────────────────────────────────

    @app.get("/api/runs", dependencies=[Depends(require_backend_role("viewer")), Depends(require_rate_limit("runs_read"))])
    async def list_runs(request: Request, limit: int = 50) -> dict[str, Any]:
        """List recent run ledger records."""
        hardening = getattr(request.app.state, "backend_hardening_config", None)
        safe_limit = clamp_limit(limit, hardening) if hardening else min(max(1, limit), 500)
        rd = request.app.state.runtime_data_dir
        try:
            from runtime.run_ledger import read_ledger_records
            records = read_ledger_records(runtime_data_dir=rd)
        except Exception as exc:
            write_route_audit(request, "runs.list", "error", 500, error=str(exc))
            return {"ok": False, "runs": [], "count": 0, "error": str(exc)}
        rows = list(reversed(records))[:safe_limit]
        write_route_audit(request, "runs.list", "success", 200, summary=f"Listed {len(rows)} runs.")
        return {"ok": True, "runs": rows, "count": len(rows), "error": ""}

    # ── GET /api/runs/{frame_id} ──────────────────────────────────────────

    @app.get("/api/runs/{frame_id}", dependencies=[Depends(require_backend_role("viewer")), Depends(require_rate_limit("runs_read"))])
    async def get_run(frame_id: str, request: Request) -> dict[str, Any]:
        """Return normalized TaskFrame summary and core metadata for one run."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        _target = {"frame_id": frame_id, "event_id": "", "action_id": "", "manifest_id": ""}
        try:
            from runtime.persistence import load_taskframe_dict, taskframe_exists
            if not taskframe_exists(frame_id, rd):
                write_route_audit(request, "runs.read", "failure", 404, target=_target, error=f"Run not found: {frame_id}")
                return JSONResponse(status_code=404, content={"ok": False, "frame_id": frame_id, "error": f"Run not found: {frame_id}"})
            frame = load_taskframe_dict(frame_id, rd)
        except _HardeningHTTPException:
            raise
        except Exception as exc:
            write_route_audit(request, "runs.read", "error", 404, target=_target, error=str(exc))
            return JSONResponse(status_code=404, content={"ok": False, "frame_id": frame_id, "error": str(exc)})

        _target["manifest_id"] = str(frame.get("manifest_id") or "")
        pending = [
            {k: v for k, v in a.items() if k not in ("args",)}
            for a in (frame.get("pending_actions") or [])
        ]
        outputs_preview = {
            k: v for i, (k, v) in enumerate((frame.get("outputs") or {}).items())
            if i < 10
        }
        artifact_dir = str(Path(rd) / "runs" / frame_id)

        write_route_audit(request, "runs.read", "success", 200, target=_target, summary=f"Read run {frame_id}.")
        return {
            "ok": True,
            "frame_id": frame_id,
            "manifest_id": frame.get("manifest_id", ""),
            "state": frame.get("state", ""),
            "summary": frame.get("summary", {}),
            "outputs_preview": outputs_preview,
            "pending_actions": pending,
            "errors": (frame.get("errors") or [])[:20],
            "validations": (frame.get("validations") or [])[:20],
            "artifact_paths": {"artifact_dir": artifact_dir},
            "error": "",
        }

    # ── GET /api/runs/{frame_id}/evidence ─────────────────────────────────

    @app.get("/api/runs/{frame_id}/evidence", dependencies=[Depends(require_backend_role("viewer")), Depends(require_rate_limit("runs_read"))])
    async def get_evidence(frame_id: str, request: Request) -> dict[str, Any]:
        """Return the evidence bundle for one run."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        _target = {"frame_id": frame_id, "event_id": "", "action_id": "", "manifest_id": ""}
        try:
            from runtime.evidence_bundle import build_evidence_bundle
            bundle = build_evidence_bundle(frame_id, rd)
        except _HardeningHTTPException:
            raise
        except Exception as exc:
            status = 404 if "not found" in str(exc).lower() else 500
            write_route_audit(request, "runs.evidence.read", "error", status, target=_target, error=str(exc))
            return JSONResponse(status_code=status, content={"ok": False, "frame_id": frame_id, "error": str(exc)})
        write_route_audit(request, "runs.evidence.read", "success", 200, target=_target, summary=f"Read evidence for {frame_id}.")
        return {"ok": True, "frame_id": frame_id, "evidence": bundle, "error": ""}

    # ── GET /api/runs/{frame_id}/approval-pack ────────────────────────────

    @app.get("/api/runs/{frame_id}/approval-pack", dependencies=[Depends(require_backend_role("viewer")), Depends(require_rate_limit("runs_read"))])
    async def get_approval_pack(frame_id: str, request: Request) -> dict[str, Any]:
        """Return the approval pack view for one run."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        _target = {"frame_id": frame_id, "event_id": "", "action_id": "", "manifest_id": ""}
        try:
            from runtime.persistence import load_taskframe_dict, taskframe_exists
            if not taskframe_exists(frame_id, rd):
                write_route_audit(request, "runs.approval_pack.read", "failure", 404, target=_target, error=f"Run not found: {frame_id}")
                return JSONResponse(status_code=404, content={"ok": False, "frame_id": frame_id, "error": f"Run not found: {frame_id}"})
            frame = load_taskframe_dict(frame_id, rd)
            from src.operator_approval_pack import build_approval_pack_view
            approval_pack = build_approval_pack_view(frame)
            pending_count = len([a for a in (frame.get("pending_actions") or []) if a.get("status") == "PENDING_APPROVAL"])
        except _HardeningHTTPException:
            raise
        except Exception as exc:
            write_route_audit(request, "runs.approval_pack.read", "error", 500, target=_target, error=str(exc))
            return JSONResponse(status_code=500, content={"ok": False, "frame_id": frame_id, "error": str(exc)})
        write_route_audit(request, "runs.approval_pack.read", "success", 200, target=_target, summary=f"Read approval pack for {frame_id}.")
        return {"ok": True, "frame_id": frame_id, "approval_pack": approval_pack, "pending_action_count": pending_count, "error": ""}

    # ── GET /api/runs/{frame_id}/failure-summary ──────────────────────────

    @app.get("/api/runs/{frame_id}/failure-summary", dependencies=[Depends(require_backend_role("viewer")), Depends(require_rate_limit("runs_read"))])
    async def get_failure_summary(frame_id: str, request: Request) -> dict[str, Any]:
        """Return the failure summary for one run."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        _target = {"frame_id": frame_id, "event_id": "", "action_id": "", "manifest_id": ""}
        try:
            from runtime.persistence import load_taskframe_dict, taskframe_exists
            if not taskframe_exists(frame_id, rd):
                write_route_audit(request, "runs.failure_summary.read", "failure", 404, target=_target, error=f"Run not found: {frame_id}")
                return JSONResponse(status_code=404, content={"ok": False, "frame_id": frame_id, "error": f"Run not found: {frame_id}"})
            frame = load_taskframe_dict(frame_id, rd)
            from runtime.failure_summary import build_failure_summary
            failure_summary = build_failure_summary(frame)
        except _HardeningHTTPException:
            raise
        except Exception as exc:
            write_route_audit(request, "runs.failure_summary.read", "error", 500, target=_target, error=str(exc))
            return JSONResponse(status_code=500, content={"ok": False, "frame_id": frame_id, "error": str(exc)})
        write_route_audit(request, "runs.failure_summary.read", "success", 200, target=_target, summary=f"Read failure summary for {frame_id}.")
        return {"ok": True, "frame_id": frame_id, "failure_summary": failure_summary, "error": ""}

    # ── POST /api/runs/{frame_id}/report ──────────────────────────────────

    @app.post(
        "/api/runs/{frame_id}/report",
        dependencies=[Depends(require_backend_role("operator")), Depends(require_rate_limit("report_generate"))],
    )
    async def generate_report(frame_id: str, body: ReportRequest, request: Request) -> dict[str, Any]:
        """Generate or rebuild the operator run report."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        _target = {"frame_id": frame_id, "event_id": "", "action_id": "", "manifest_id": ""}
        try:
            from runtime.run_report import generate_run_report
            result = generate_run_report(rd, frame_id, rebuild=body.rebuild)
        except _HardeningHTTPException:
            raise
        except Exception as exc:
            write_route_audit(request, "runs.report.generate", "error", 500, target=_target, error=str(exc))
            return JSONResponse(status_code=500, content={"ok": False, "frame_id": frame_id, "error": str(exc)})
        if not result.get("ok"):
            status = 404 if "not found" in str(result.get("error", "")).lower() else 500
            write_route_audit(request, "runs.report.generate", "failure", status, target=_target, error=str(result.get("error", "")))
            return JSONResponse(
                status_code=status,
                content={"ok": False, "frame_id": frame_id, "markdown_path": "", "html_path": "", "evidence_bundle_path": "", "error": str(result.get("error", ""))},
            )
        write_route_audit(request, "runs.report.generate", "success", 200, target=_target, summary=f"Generated report for {frame_id}.")
        return {
            "ok": True,
            "frame_id": frame_id,
            "markdown_path": str(result.get("markdown_path", "")),
            "html_path": str(result.get("html_path", "")),
            "evidence_bundle_path": str(result.get("evidence_bundle_path", "")),
            "error": "",
        }

    # ── POST /api/runs/{frame_id}/pending-actions/{action_id}/approve ─────

    @app.post(
        "/api/runs/{frame_id}/pending-actions/{action_id}/approve",
        dependencies=[Depends(require_backend_role("operator")), Depends(require_rate_limit("pending_action_write"))],
    )
    async def approve_pending_action(frame_id: str, action_id: str, request: Request, body: ApprovalDecisionRequest | None = None) -> dict[str, Any]:
        """Approve a pending action using the existing runtime approval function."""
        _validate_id(frame_id, "frame_id")
        _validate_id(action_id, "action_id")
        return await _handle_approval(frame_id, action_id, "approve", request, expected_version=getattr(body, "expected_version", None))

    # ── POST /api/runs/{frame_id}/pending-actions/{action_id}/reject ──────

    @app.post(
        "/api/runs/{frame_id}/pending-actions/{action_id}/reject",
        dependencies=[Depends(require_backend_role("operator")), Depends(require_rate_limit("pending_action_write"))],
    )
    async def reject_pending_action(frame_id: str, action_id: str, request: Request, body: ApprovalDecisionRequest | None = None) -> dict[str, Any]:
        """Reject a pending action using the existing runtime rejection function."""
        _validate_id(frame_id, "frame_id")
        _validate_id(action_id, "action_id")
        return await _handle_approval(frame_id, action_id, "reject", request, expected_version=getattr(body, "expected_version", None))

    @app.post(
        "/api/approvals/{action_id}/approve",
        dependencies=[Depends(require_backend_role("operator")), Depends(require_rate_limit("pending_action_write"))],
    )
    async def approve_pending_action_alias(action_id: str, request: Request, body: ApprovalDecisionRequest | None = None) -> dict[str, Any]:
        _validate_id(action_id, "action_id")
        return await _handle_approval(None, action_id, "approve", request, expected_version=getattr(body, "expected_version", None))

    @app.post(
        "/api/approvals/{action_id}/reject",
        dependencies=[Depends(require_backend_role("operator")), Depends(require_rate_limit("pending_action_write"))],
    )
    async def reject_pending_action_alias(action_id: str, request: Request, body: ApprovalDecisionRequest | None = None) -> dict[str, Any]:
        _validate_id(action_id, "action_id")
        return await _handle_approval(None, action_id, "reject", request, expected_version=getattr(body, "expected_version", None))

    async def _resolve_frame_id_for_action(action_id: str, runtime_data_dir: str) -> str | None:
        try:
            from runtime.persistence import load_taskframe_dict
        except Exception:
            return None

        runs_dir = Path(runtime_data_dir) / "runs"
        if not runs_dir.is_dir():
            return None

        for taskframe_path in sorted(runs_dir.rglob("taskframe.json")):
            if not taskframe_path.is_file():
                continue
            frame_dir = taskframe_path.parent.name
            try:
                payload = load_taskframe_dict(frame_dir, runtime_data_dir)
            except Exception:
                continue
            for pending_action in payload.get("pending_actions", []) if isinstance(payload, dict) else []:
                if isinstance(pending_action, dict) and str(pending_action.get("action_id", "")) == action_id:
                    return frame_dir
        return None

    async def _handle_approval(
        frame_id: str | None,
        action_id: str,
        operation: str,
        request: Request,
        *,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        rd = request.app.state.runtime_data_dir
        audit_op = "pending_action.approve" if operation == "approve" else "pending_action.reject"
        _target = {"frame_id": str(frame_id or ""), "event_id": "", "action_id": action_id, "manifest_id": ""}
        try:
            from runtime.persistence import get_taskframe_path, load_taskframe_dict
            from runtime.approval import approve_action, reject_action
            from runtime.pending_actions import list_pending_actions, get_pending_action
            from runtime.runtime_locking import RuntimeLockTimeoutError, mutate_runtime_json
            from runtime.taskframe_reload import taskframe_from_dict

            resolved_frame_id = frame_id or await _resolve_frame_id_for_action(action_id, rd)
            if not resolved_frame_id:
                write_route_audit(request, audit_op, "failure", 404, target=_target, error=f"Pending action not found: {action_id}")
                return JSONResponse(status_code=404, content={"ok": False, "frame_id": "", "action_id": action_id, "operation": operation, "error": f"Pending action not found: {action_id}"})

            frame_id = resolved_frame_id
            _target["frame_id"] = frame_id
            path = get_taskframe_path(frame_id, rd)
            if not path.is_file():
                write_route_audit(request, audit_op, "failure", 404, target=_target, error=f"Run not found: {frame_id}")
                return JSONResponse(status_code=404, content={"ok": False, "frame_id": frame_id, "action_id": action_id, "operation": operation, "error": f"Run not found: {frame_id}"})

            def _mutate(payload: dict[str, Any]) -> dict[str, Any]:
                frame = taskframe_from_dict(payload)
                try:
                    get_pending_action(frame, action_id)
                except Exception:
                    return {
                        "ok": False,
                        "error": "APPROVAL_ALREADY_FINALIZED",
                        "message": f"Pending action not found: {action_id}",
                        "status_code": 404,
                        "current_status": "",
                        "current_version": int(payload.get("runtime_version", 1) or 1),
                        "action_id": action_id,
                    }

                pending_action = next((item for item in frame.pending_actions if str(item.get("action_id", "")) == action_id), None)
                if not isinstance(pending_action, dict):
                    return {
                        "ok": False,
                        "error": "APPROVAL_ALREADY_FINALIZED",
                        "message": f"Pending action not found: {action_id}",
                        "status_code": 404,
                        "current_status": "",
                        "current_version": int(payload.get("runtime_version", 1) or 1),
                        "action_id": action_id,
                    }
                current_status = str(pending_action.get("status", "")).upper()
                if current_status != "PENDING_APPROVAL":
                    return {
                        "ok": False,
                        "error": "APPROVAL_ALREADY_FINALIZED",
                        "message": "Pending action already finalized.",
                        "status_code": 409,
                        "current_status": current_status,
                        "current_version": int(payload.get("runtime_version", 1) or 1),
                        "action_id": action_id,
                    }

                if operation == "approve":
                    mutated = approve_action(frame, action_id, approved_by="api", reason="Approved via production API")
                else:
                    mutated = reject_action(frame, action_id, rejected_by="api", reason="Rejected via production API")
                return taskframe_to_dict(mutated)

            result = mutate_runtime_json(
                path,
                _mutate,
                expected_version=expected_version,
                resource_key=f"taskframe/{frame_id}",
                runtime_data_dir=rd,
                owner="backend-api",
                request_id=str(getattr(request.state, "request_id", "") or ""),
            )
            if not result.get("ok"):
                status_code = int(result.get("status_code", 409 if result.get("error") in {"VERSION_CONFLICT", "APPROVAL_ALREADY_FINALIZED"} else 500))
                if result.get("error") == "VERSION_CONFLICT":
                    current_payload = load_taskframe_dict(frame_id, rd)
                    current_frame = taskframe_from_dict(current_payload)
                    current_action = next((item for item in current_frame.pending_actions if str(item.get("action_id", "")) == action_id), None)
                    write_route_audit(request, audit_op, "failure", status_code, target=_target, error="Approval action changed since it was loaded.")
                    return JSONResponse(
                        status_code=status_code,
                        content={
                            "ok": False,
                            "error": "VERSION_CONFLICT",
                            "message": "Approval action changed since it was loaded.",
                            "action_id": action_id,
                            "expected_version": expected_version,
                            "actual_version": result.get("actual_version"),
                            "current_version": result.get("actual_version"),
                            "current_status": str((current_action or {}).get("status", "")),
                        },
                    )
                if result.get("error") == "APPROVAL_ALREADY_FINALIZED":
                    write_route_audit(request, audit_op, "failure", status_code, target=_target, error="Pending action already finalized.")
                    return JSONResponse(
                        status_code=status_code,
                        content={
                            "ok": False,
                            "error": "APPROVAL_ALREADY_FINALIZED",
                            "message": "Pending action already finalized.",
                            "action_id": action_id,
                            "expected_version": expected_version,
                            "actual_version": result.get("current_version"),
                            "current_version": result.get("current_version"),
                            "current_status": result.get("current_status", ""),
                        },
                    )
                write_route_audit(request, audit_op, "error", status_code, target=_target, error=str(result.get("message") or result.get("error") or "Approval update failed."))
                return JSONResponse(status_code=status_code, content={"ok": False, "frame_id": frame_id, "action_id": action_id, "operation": operation, "error": str(result.get("message") or result.get("error") or "Approval update failed.")})

            frame = taskframe_from_dict(result["data"]) if isinstance(result.get("data"), dict) else taskframe_from_dict(load_taskframe_dict(frame_id, rd))
            pending = list_pending_actions(frame)
            executed = list(frame.executed_actions or [])

        except (_HardeningHTTPException, BackendRateLimitError):
            raise
        except RuntimeLockTimeoutError as exc:
            write_route_audit(request, audit_op, "failure", 409, target=_target, error=str(exc))
            return JSONResponse(status_code=409, content={"ok": False, "error": "LOCK_TIMEOUT", "message": str(exc), "action_id": action_id, "frame_id": frame_id})
        except Exception as exc:
            write_route_audit(request, audit_op, "error", 500, target=_target, error=str(exc))
            return JSONResponse(status_code=500, content={"ok": False, "frame_id": frame_id, "action_id": action_id, "operation": operation, "error": str(exc)})

        summary_msg = "Pending action approved through production backend." if operation == "approve" else "Pending action rejected through production backend."
        audit_ok = write_route_audit(request, audit_op, "success", 200, target=_target, summary=summary_msg)

        resp: dict[str, Any] = {
            "ok": True,
            "frame_id": frame_id,
            "action_id": action_id,
            "operation": operation,
            "state": frame.state,
            "pending_actions": [dict(a) for a in pending],
            "executed_actions": [dict(a) for a in executed],
            "error": "",
        }
        if not audit_ok:
            resp["audit_warning"] = "Audit record could not be written."
        return resp

    return app


# ---------------------------------------------------------------------------
# Default app instance (importable as a module-level object)
# ---------------------------------------------------------------------------

app = create_app()
