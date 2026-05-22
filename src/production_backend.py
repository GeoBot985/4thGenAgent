"""Spec 141 — Production Backend Run Operations API v1.

FastAPI application exposing controlled read/operate endpoints for TaskFrame runs.

Safety contract:
- frame_id and action_id are validated as identifiers (no path traversal).
- No arbitrary file read endpoints.
- No direct tool execution from API requests.
- Approval/rejection flows through existing runtime approval functions only.
- Live side effects remain controlled by existing live execution guardrails.
- Dry-run is the default for all write operations.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


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

def create_app(runtime_data_dir: str = "runtime_data") -> FastAPI:
    """Create and return the production backend FastAPI application."""
    app = FastAPI(
        title="TaskFrame Production Backend",
        description="Spec 141 — controlled read/operate API for TaskFrame runs",
        version="1.0.0",
    )

    # Attach runtime_data_dir to app state so routes can read it
    app.state.runtime_data_dir = runtime_data_dir

    from src.backend.routes.events import router as events_router
    app.include_router(events_router, prefix="/api/events")

    # ── GET /api/runs ─────────────────────────────────────────────────────

    @app.get("/api/runs")
    async def list_runs(request: Request, limit: int = 50) -> dict[str, Any]:
        """List recent run ledger records."""
        rd = request.app.state.runtime_data_dir
        try:
            from runtime.run_ledger import read_ledger_records
            records = read_ledger_records(runtime_data_dir=rd)
        except Exception as exc:
            return {"ok": False, "runs": [], "count": 0, "error": str(exc)}
        # Most recent first; apply limit
        rows = list(reversed(records))[:max(1, limit)]
        return {"ok": True, "runs": rows, "count": len(rows), "error": ""}

    # ── GET /api/runs/{frame_id} ──────────────────────────────────────────

    @app.get("/api/runs/{frame_id}")
    async def get_run(frame_id: str, request: Request) -> dict[str, Any]:
        """Return normalized TaskFrame summary and core metadata for one run."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        try:
            from runtime.persistence import load_taskframe_dict, taskframe_exists
            if not taskframe_exists(frame_id, rd):
                return JSONResponse(
                    status_code=404,
                    content={"ok": False, "frame_id": frame_id, "error": f"Run not found: {frame_id}"},
                )
            frame = load_taskframe_dict(frame_id, rd)
        except Exception as exc:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "frame_id": frame_id, "error": str(exc)},
            )

        pending = [
            {k: v for k, v in a.items() if k not in ("args",)}
            for a in (frame.get("pending_actions") or [])
        ]
        outputs_preview = {
            k: v for i, (k, v) in enumerate((frame.get("outputs") or {}).items())
            if i < 10
        }
        artifact_dir = str(Path(rd) / "runs" / frame_id)

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

    @app.get("/api/runs/{frame_id}/evidence")
    async def get_evidence(frame_id: str, request: Request) -> dict[str, Any]:
        """Return the evidence bundle for one run (generated from persisted artifacts)."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        try:
            from runtime.evidence_bundle import build_evidence_bundle
            bundle = build_evidence_bundle(frame_id, rd)
        except Exception as exc:
            return JSONResponse(
                status_code=404 if "not found" in str(exc).lower() else 500,
                content={"ok": False, "frame_id": frame_id, "error": str(exc)},
            )
        return {"ok": True, "frame_id": frame_id, "evidence": bundle, "error": ""}

    # ── GET /api/runs/{frame_id}/approval-pack ────────────────────────────

    @app.get("/api/runs/{frame_id}/approval-pack")
    async def get_approval_pack(frame_id: str, request: Request) -> dict[str, Any]:
        """Return the approval pack view for one run."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        try:
            from runtime.persistence import load_taskframe_dict, taskframe_exists
            if not taskframe_exists(frame_id, rd):
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
            return JSONResponse(
                status_code=500,
                content={"ok": False, "frame_id": frame_id, "error": str(exc)},
            )
        return {
            "ok": True,
            "frame_id": frame_id,
            "approval_pack": approval_pack,
            "pending_action_count": pending_count,
            "error": "",
        }

    # ── GET /api/runs/{frame_id}/failure-summary ──────────────────────────

    @app.get("/api/runs/{frame_id}/failure-summary")
    async def get_failure_summary(frame_id: str, request: Request) -> dict[str, Any]:
        """Return the failure summary for one run."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        try:
            from runtime.persistence import load_taskframe_dict, taskframe_exists
            if not taskframe_exists(frame_id, rd):
                return JSONResponse(
                    status_code=404,
                    content={"ok": False, "frame_id": frame_id, "error": f"Run not found: {frame_id}"},
                )
            frame = load_taskframe_dict(frame_id, rd)
            from runtime.failure_summary import build_failure_summary
            failure_summary = build_failure_summary(frame)
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"ok": False, "frame_id": frame_id, "error": str(exc)},
            )
        return {
            "ok": True,
            "frame_id": frame_id,
            "failure_summary": failure_summary,
            "error": "",
        }

    # ── POST /api/runs/{frame_id}/report ──────────────────────────────────

    @app.post("/api/runs/{frame_id}/report")
    async def generate_report(frame_id: str, body: ReportRequest, request: Request) -> dict[str, Any]:
        """Generate or rebuild the operator run report."""
        _validate_id(frame_id, "frame_id")
        rd = request.app.state.runtime_data_dir
        try:
            from runtime.run_report import generate_run_report
            result = generate_run_report(rd, frame_id, rebuild=body.rebuild)
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"ok": False, "frame_id": frame_id, "error": str(exc)},
            )
        if not result.get("ok"):
            return JSONResponse(
                status_code=404 if "not found" in str(result.get("error", "")).lower() else 500,
                content={
                    "ok": False,
                    "frame_id": frame_id,
                    "markdown_path": "",
                    "html_path": "",
                    "evidence_bundle_path": "",
                    "error": str(result.get("error", "")),
                },
            )
        return {
            "ok": True,
            "frame_id": frame_id,
            "markdown_path": str(result.get("markdown_path", "")),
            "html_path": str(result.get("html_path", "")),
            "evidence_bundle_path": str(result.get("evidence_bundle_path", "")),
            "error": "",
        }

    # ── POST /api/runs/{frame_id}/pending-actions/{action_id}/approve ─────

    @app.post("/api/runs/{frame_id}/pending-actions/{action_id}/approve")
    async def approve_pending_action(frame_id: str, action_id: str, request: Request) -> dict[str, Any]:
        """Approve a pending action using the existing runtime approval function."""
        _validate_id(frame_id, "frame_id")
        _validate_id(action_id, "action_id")
        return await _handle_approval(frame_id, action_id, "approve", request)

    # ── POST /api/runs/{frame_id}/pending-actions/{action_id}/reject ──────

    @app.post("/api/runs/{frame_id}/pending-actions/{action_id}/reject")
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

            # Validate action_id exists
            try:
                get_pending_action(frame, action_id)
            except Exception:
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

            # Execute through existing approval functions only
            if operation == "approve":
                frame = approve_action(frame, action_id, approved_by="api", reason="Approved via production API")
            else:
                frame = reject_action(frame, action_id, rejected_by="api", reason="Rejected via production API")

            persist_frame_update(frame, rd)

            pending = list_pending_actions(frame)
            executed = list(frame.executed_actions or [])

        except Exception as exc:
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

        return {
            "ok": True,
            "frame_id": frame_id,
            "action_id": action_id,
            "operation": operation,
            "state": frame.state,
            "pending_actions": [dict(a) for a in pending],
            "executed_actions": [dict(a) for a in executed],
            "error": "",
        }

    return app


# ---------------------------------------------------------------------------
# Default app instance (importable as a module-level object)
# ---------------------------------------------------------------------------

app = create_app()
