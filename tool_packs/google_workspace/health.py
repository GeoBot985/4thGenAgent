from __future__ import annotations

from pathlib import Path
from typing import Any

from . import auth
from .schemas import GOOGLE_WORKSPACE_SERVICE_NAMES, GOOGLE_WORKSPACE_TOOLPACK_ID, GOOGLE_WORKSPACE_RISK_CLASS


def check_health(live: bool = False, service: str = "") -> dict[str, Any]:
    toolpack_path = Path(__file__).resolve().with_name("toolpack.json")
    dependency_state = auth.google_dependency_state()
    auth_files = auth.google_auth_files()
    files_ready = bool(auth_files.get("credentials_file_present")) or bool(auth_files.get("token_file_present"))

    if not dependency_state.get("ok"):
        status = "missing_dependency"
        severity = "error"
        ok = False
        message = "Google Workspace dependencies are missing."
    elif not files_ready:
        status = "needs_auth"
        severity = "warning"
        ok = False
        message = "Google Workspace credentials are not configured."
    elif not live:
        status = "ready"
        severity = "info"
        ok = True
        message = "Google Workspace read-only pack is ready for local use."
    else:
        probe_service = service.strip() if service.strip() in GOOGLE_WORKSPACE_SERVICE_NAMES else "gmail"
        live_checked = False
        try:
            if probe_service == "gmail":
                service_obj = auth.build_google_service("gmail", "v1")
                service_obj.users().getProfile(userId="me").execute()
            elif probe_service == "calendar":
                service_obj = auth.build_google_service("calendar", "v3")
                service_obj.calendarList().list(maxResults=1).execute()
            elif probe_service == "sheets":
                auth.build_google_service("sheets", "v4")
            status = "live_verified"
            severity = "info"
            ok = True
            message = f"Google Workspace live probe succeeded for {probe_service}."
            live_checked = True
        except Exception as exc:
            status = "failing"
            severity = "error"
            ok = False
            message = f"Google Workspace live probe failed: {exc}"[:500]
            live_checked = True

    return {
        "ok": ok,
        "toolpack_id": GOOGLE_WORKSPACE_TOOLPACK_ID,
        "status": status,
        "severity": severity,
        "message": message,
        "tool_count": 7,
        "live_checked": bool(live and (status == "live_verified" or status == "failing")),
        "health_supported": True,
        "details": {
            "toolpack_path": str(toolpack_path),
            "risk_class": GOOGLE_WORKSPACE_RISK_CLASS,
            "live": bool(live),
            "service": service,
            "dependencies": auth.redact_google_auth_state(dependency_state),
            "auth_files": auth.redact_google_auth_state(auth_files),
            "configured_services": list(GOOGLE_WORKSPACE_SERVICE_NAMES),
            "default_demo_included": False,
            "live_probe_available": files_ready and bool(dependency_state.get("ok")),
        },
        "errors": [] if ok else [message],
        "warnings": [] if ok else ([] if status == "failing" else [message]),
    }
