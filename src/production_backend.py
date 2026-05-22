"""Spec 141–145 — Production Backend Run Operations API.

FastAPI application exposing controlled read/operate endpoints for TaskFrame runs.
Spec 145 adds a structured audit trail for all API activity.

Safety contract:
- frame_id and action_id are validated as identifiers (no path traversal).
- No arbitrary file read endpoints.
- No direct tool execution from API requests.
- Approval/rejection flows through existing runtime approval functions only.
- Live side effects remain controlled by existing live execution guardrails.
- Dry-run is the default for all write operations.
- Bearer tokens and credentials are never stored in audit records.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.backend.audit import install_audit_request_id_middleware, write_route_audit
from src.backend.auth import BackendAuthError, backend_auth_error_response, install_backend_auth_middleware, require_backend_role
from src.backend.config import load_backend_auth_config


class ReportRequest(BaseModel):
    rebuild: bool = False


# ---------------------------------------------------------------------------
# ID validation
# ---------------------------------------------------------------------------

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")


def _validate_id(value: str, label: str) -> str:
    """Reject IDs that look like paths or contain unsafe characters."""
    if not value or not _SAFE_ID_RE.match(value):
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "error": f"Invalid {label}: must match [A-Za-z0-9_-]{{1,128}}"},
        )
    return value


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(runtime_data_dir: str = "runtime_data", *, backend_auth_config_path: str | None = None) -> FastAPI:
    """Create and return the production backend FastAPI application."""
    app = FastAPI(
        title="TaskFrame Production Backend",
        description="Spec 141–145 — controlled read/operate API for TaskFrame runs with audit trail",
        version="1.0.0",
    )

    app.state.runtime_data_dir = runtime_data_dir
    app.state.backend_auth_config = load_backend_auth_config(backend_auth_config_path)

    # Middleware order: install_backend_auth_middleware first (inner), then
    # install_audit_request_id_middleware (outer) so request_id is set first.
    install_backend_auth_middleware(app)
    install_audit_request_id_middleware(app)

    # Map BackendAuthError error_code to (operation, auth_result) for auditing.
    _AUTH_ERROR_MAP = {
        "AUTH_REQUIRED": ("auth.missing_token", "missing"),
        "AUTH_INVALID": ("auth.invalid_token", "invalid"),
        "AUTH_FORBIDDEN": ("auth.forbidden", "forbidden"),
    }

    @app.exception_handler(BackendAuthError)
    async def _handle_backend_auth_error(request: Request, exc: BackendAuthError):  # type: ignore[no-untyped-def]
        operation, auth_result = _AUTH_ERROR_MAP.get(exc.error_code, ("auth.invalid_token", "invalid"))
        forbidden_reason = exc.error if exc.error_code == "AUTH_FORBIDDEN" else ""
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

    from src.backend.routes.audit import router as audit_router
    from src.backend.routes.events import router as events_router
    from src.backend.routes.health import router as health_router
    app.include_router(health_router, prefix="/api/health")
    app.include_router(events_router, prefix="/api/events")
    app.include_router(audit_router, prefix="/api/audit")

    # ── GET /api/runs ─────────────────────────────────────────────────────

    @app.get("/api/runs", dependencies=[Depends(require_backend_role("viewer"))])
    async def list_runs(request: Request, limit: int = 50) -> dict[str, Any]:
        """List recent run ledger records."""
        rd = request.app.state.runtime_data_dir
        try:
            from runtime.run_ledger import read_ledger_records
            records = read_ledger_records(runtime_data_dir=rd)
        except Exception as exc:
            write_route_audit(request, "runs.list", "error", 500, error=str(exc))
            return {"ok": False, "runs": [], "count": 0, "error": str(exc)}
        rows = list(reversed(records))[:max(1, limit)]
        write_route_audit(request, "runs.list", "success", 200, summary=f"Listed {len(rows)} runs.")
        return {"ok": True, "runs": rows, "count": len(rows), "error": ""}

    # ── GET /api/runs/{frame_id} ──────────────────────────────────────────

    @app.get("/api/runs/{frame_id}", dependencies=[Depends(require_backend_role("viewer"))])
    async def get_run(frame_id: str, request: Request) -> dict[str, Any]:
        """Return normalized TaskFrame summary and core metadata for one run."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        _target = {"frame_id": frame_id, "event_id": "", "action_id": "", "manifest_id": ""}
        try:
            from runtime.persistence import load_taskframe_dict, taskframe_exists
            if not taskframe_exists(frame_id, rd):
                write_route_audit(
                    request, "runs.read", "failure", 404,
                    target=_target, error=f"Run not found: {frame_id}",
                )
                return JSONResponse(
                    status_code=404,
                    content={"ok": False, "frame_id": frame_id, "error": f"Run not found: {frame_id}"},
                )
            frame = load_taskframe_dict(frame_id, rd)
        except Exception as exc:
            write_route_audit(request, "runs.read", "error", 404, target=_target, error=str(exc))
            return JSONResponse(
                status_code=404,
                content={"ok": False, "frame_id": frame_id, "error": str(exc)},
            )

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

    @app.get("/api/runs/{frame_id}/evidence", dependencies=[Depends(require_backend_role("viewer"))])
    async def get_evidence(frame_id: str, request: Request) -> dict[str, Any]:
        """Return the evidence bundle for one run (generated from persisted artifacts)."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        _target = {"frame_id": frame_id, "event_id": "", "action_id": "", "manifest_id": ""}
        try:
            from runtime.evidence_bundle import build_evidence_bundle
            bundle = build_evidence_bundle(frame_id, rd)
        except Exception as exc:
            status = 404 if "not found" in str(exc).lower() else 500
            write_route_audit(request, "runs.evidence.read", "error", status, target=_target, error=str(exc))
            return JSONResponse(
                status_code=status,
                content={"ok": False, "frame_id": frame_id, "error": str(exc)},
            )
        write_route_audit(request, "runs.evidence.read", "success", 200, target=_target, summary=f"Read evidence for {frame_id}.")
        return {"ok": True, "frame_id": frame_id, "evidence": bundle, "error": ""}

    # ── GET /api/runs/{frame_id}/approval-pack ────────────────────────────

    @app.get("/api/runs/{frame_id}/approval-pack", dependencies=[Depends(require_backend_role("viewer"))])
    async def get_approval_pack(frame_id: str, request: Request) -> dict[str, Any]:
        """Return the approval pack view for one run."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        _target = {"frame_id": frame_id, "event_id": "", "action_id": "", "manifest_id": ""}
        try:
            from runtime.persistence import load_taskframe_dict, taskframe_exists
            if not taskframe_exists(frame_id, rd):
                write_route_audit(
                    request, "runs.approval_pack.read", "failure", 404,
                    target=_target, error=f"Run not found: {frame_id}",
                )
                return JSONResponse(
                    status_code=404,
                    content={"ok": False, "frame_id": frame_id, "error": f"Run not found: {frame_id}"},
                )
            frame = load_taskframe_dict(frame_id, rd)
            from src.operator_approval_pack import build_approval_pack_view
            approval_pack = build_approval_pack_view(frame)
            pending_count = len([
                a for a in (frame.get("pending_actions") or [])
                if a.get("status") == "PENDING_APPROVAL"
            ])
        except Exception as exc:
            write_route_audit(request, "runs.approval_pack.read", "error", 500, target=_target, error=str(exc))
            return JSONResponse(
                status_code=500,
                content={"ok": False, "frame_id": frame_id, "error": str(exc)},
            )
        write_route_audit(request, "runs.approval_pack.read", "success", 200, target=_target, summary=f"Read approval pack for {frame_id}.")
        return {
            "ok": True,
            "frame_id": frame_id,
            "approval_pack": approval_pack,
            "pending_action_count": pending_count,
            "error": "",
        }

    # ── GET /api/runs/{frame_id}/failure-summary ──────────────────────────

    @app.get("/api/runs/{frame_id}/failure-summary", dependencies=[Depends(require_backend_role("viewer"))])
    async def get_failure_summary(frame_id: str, request: Request) -> dict[str, Any]:
        """Return the failure summary for one run."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        _target = {"frame_id": frame_id, "event_id": "", "action_id": "", "manifest_id": ""}
        try:
            from runtime.persistence import load_taskframe_dict, taskframe_exists
            if not taskframe_exists(frame_id, rd):
                write_route_audit(
                    request, "runs.failure_summary.read", "failure", 404,
                    target=_target, error=f"Run not found: {frame_id}",
                )
                return JSONResponse(
                    status_code=404,
                    content={"ok": False, "frame_id": frame_id, "error": f"Run not found: {frame_id}"},
                )
            frame = load_taskframe_dict(frame_id, rd)
            from runtime.failure_summary import build_failure_summary
            failure_summary = build_failure_summary(frame)
        except Exception as exc:
            write_route_audit(request, "runs.failure_summary.read", "error", 500, target=_target, error=str(exc))
            return JSONResponse(
                status_code=500,
                content={"ok": False, "frame_id": frame_id, "error": str(exc)},
            )
        write_route_audit(request, "runs.failure_summary.read", "success", 200, target=_target, summary=f"Read failure summary for {frame_id}.")
        return {
            "ok": True,
            "frame_id": frame_id,
            "failure_summary": failure_summary,
            "error": "",
        }

    # ── POST /api/runs/{frame_id}/report ──────────────────────────────────

    @app.post("/api/runs/{frame_id}/report", dependencies=[Depends(require_backend_role("operator"))])
    async def generate_report(frame_id: str, body: ReportRequest, request: Request) -> dict[str, Any]:
        """Generate or rebuild the operator run report."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        _target = {"frame_id": frame_id, "event_id": "", "action_id": "", "manifest_id": ""}
        try:
            from runtime.run_report import generate_run_report
            result = generate_run_report(rd, frame_id, rebuild=body.rebuild)
        except Exception as exc:
            write_route_audit(request, "runs.report.generate", "error", 500, target=_target, error=str(exc))
            return JSONResponse(
                status_code=500,
                content={"ok": False, "frame_id": frame_id, "error": str(exc)},
            )
        if not result.get("ok"):
            status = 404 if "not found" in str(result.get("error", "")).lower() else 500
            write_route_audit(
                request, "runs.report.generate", "failure", status,
                target=_target, error=str(result.get("error", "")),
            )
            return JSONResponse(
                status_code=status,
                content={
                    "ok": False,
                    "frame_id": frame_id,
                    "markdown_path": "",
                    "html_path": "",
                    "evidence_bundle_path": "",
                    "error": str(result.get("error", "")),
                },
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

    @app.post("/api/runs/{frame_id}/pending-actions/{action_id}/approve", dependencies=[Depends(require_backend_role("operator"))])
    async def approve_pending_action(frame_id: str, action_id: str, request: Request) -> dict[str, Any]:
        """Approve a pending action using the existing runtime approval function."""
        _validate_id(frame_id, "frame_id")
        _validate_id(action_id, "action_id")
        return await _handle_approval(frame_id, action_id, "approve", request)

    # ── POST /api/runs/{frame_id}/pending-actions/{action_id}/reject ──────

    @app.post("/api/runs/{frame_id}/pending-actions/{action_id}/reject", dependencies=[Depends(require_backend_role("operator"))])
    async def reject_pending_action(frame_id: str, action_id: str, request: Request) -> dict[str, Any]:
        """Reject a pending action using the existing runtime rejection function."""
        _validate_id(frame_id, "frame_id")
        _validate_id(action_id, "action_id")
        return await _handle_approval(frame_id, action_id, "reject", request)

    async def _handle_approval(
        frame_id: str,
        action_id: str,
        operation: str,
        request: Request,
    ) -> dict[str, Any]:
        rd = request.app.state.runtime_data_dir
        audit_op = "pending_action.approve" if operation == "approve" else "pending_action.reject"
        _target = {"frame_id": frame_id, "event_id": "", "action_id": action_id, "manifest_id": ""}
        try:
            from runtime.taskframe_reload import load_taskframe
            from runtime.errors import TaskFrameReloadError
            from runtime.persistence import persist_frame_update
            from runtime.approval import approve_action, reject_action
            from runtime.errors import PendingActionError
            from runtime.pending_actions import list_pending_actions, get_pending_action

            try:
                frame = load_taskframe(frame_id, runtime_data_dir=rd)
            except (TaskFrameReloadError, Exception):
                write_route_audit(
                    request, audit_op, "failure", 404,
                    target=_target, error=f"Run not found: {frame_id}",
                )
                return JSONResponse(
                    status_code=404,
                    content={
                        "ok": False,
                        "frame_id": frame_id,
                        "action_id": action_id,
                        "operation": operation,
                        "error": f"Run not found: {frame_id}",
                    },
                )

            try:
                get_pending_action(frame, action_id)
            except Exception:
                write_route_audit(
                    request, audit_op, "failure", 404,
                    target=_target, error=f"Pending action not found: {action_id}",
                )
                return JSONResponse(
                    status_code=404,
                    content={
                        "ok": False,
                        "frame_id": frame_id,
                        "action_id": action_id,
                        "operation": operation,
                        "error": f"Pending action not found: {action_id}",
                    },
                )

            if operation == "approve":
                frame = approve_action(frame, action_id, approved_by="api", reason="Approved via production API")
            else:
                frame = reject_action(frame, action_id, rejected_by="api", reason="Rejected via production API")

            persist_frame_update(frame, rd)

            pending = list_pending_actions(frame)
            executed = list(frame.executed_actions or [])

        except Exception as exc:
            write_route_audit(
                request, audit_op, "error", 500,
                target=_target, error=str(exc),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "frame_id": frame_id,
                    "action_id": action_id,
                    "operation": operation,
                    "error": str(exc),
                },
            )

        summary_msg = (
            f"Pending action approved through production backend."
            if operation == "approve"
            else "Pending action rejected through production backend."
        )
        audit_ok = write_route_audit(
            request, audit_op, "success", 200,
            target=_target,
            summary=summary_msg,
        )

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
