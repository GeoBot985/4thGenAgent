from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .live_side_effect_contract import (
    mark_pending_action_dry_run_executed,
    mark_pending_action_live_capable,
    mark_pending_action_live_executed,
    run_live_side_effect_preflight,
)


SHEET_WRITE_TOOL_KEY = "sheet/write_rows"

SHEET_WRITE_DEFAULT_CONFIG: dict[str, Any] = {
    "sheet_write": {
        "enabled": False,
        "allowed_spreadsheets": [],
        "allowed_ranges": [],
        "blocked_ranges": [],
        "max_rows_per_action": 50,
        "allow_update_mode": False,
        "allow_append_mode": True,
    }
}

SHEET_WRITE_AUDIT_EVENT_EXECUTED = "LIVE_SHEET_ROWS_WRITTEN"
SHEET_WRITE_AUDIT_EVENT_BLOCKED = "LIVE_SHEET_WRITE_BLOCKED"


def normalize_sheet_write_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(SHEET_WRITE_DEFAULT_CONFIG["sheet_write"])
    if config is None:
        return base
    section = config.get("sheet_write")
    if not isinstance(section, dict):
        return base
    merged = dict(base)
    for key in base:
        if key in section:
            merged[key] = section[key]
    return merged


def build_sheet_write_pending_action(
    *,
    action_id: str,
    business_ref: str,
    idempotency_key: str,
    spreadsheet_id: str,
    range_name: str,
    rows: list[list[Any]],
    write_mode: str = "append",
    expected_headers: list[str] | None = None,
    source_ref: str = "",
    approved_by: str = "",
    approved_at: str = "",
    status: str = "PENDING_APPROVAL",
) -> dict[str, Any]:
    action: dict[str, Any] = {
        "action_id": action_id,
        "tool": SHEET_WRITE_TOOL_KEY,
        "operation": "side_effect",
        "status": status,
        "business_ref": business_ref,
        "idempotency_key": idempotency_key,
        "live_capable": True,
        "live_executed": False,
        "live_executed_at": "",
        "dry_run_executed": False,
        "guardrail_result": None,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "payload": {
            "spreadsheet_id": spreadsheet_id,
            "range_name": range_name,
            "rows": [list(row) for row in rows],
            "write_mode": write_mode,
            "expected_headers": list(expected_headers or []),
            "source_ref": source_ref,
        },
    }
    mark_pending_action_live_capable(action)
    return action


def validate_sheet_write_payload(
    payload: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = normalize_sheet_write_config(config)
    errors: list[str] = []

    spreadsheet_id = str(payload.get("spreadsheet_id") or "").strip()
    range_name = str(payload.get("range_name") or "").strip()
    rows = list(payload.get("rows") or [])
    write_mode = str(payload.get("write_mode") or "append").strip()
    expected_headers = list(payload.get("expected_headers") or [])

    if not spreadsheet_id:
        errors.append("spreadsheet_id: must not be empty.")
    if not range_name:
        errors.append("range_name: must not be empty.")
    if not rows:
        errors.append("rows: must not be empty.")

    max_rows = int(cfg.get("max_rows_per_action") or 50)
    if len(rows) > max_rows:
        errors.append(f"rows: row count ({len(rows)}) exceeds maximum ({max_rows}).")

    supported_modes: list[str] = []
    if cfg.get("allow_append_mode"):
        supported_modes.append("append")
    if cfg.get("allow_update_mode"):
        supported_modes.append("update")
    if write_mode not in supported_modes:
        errors.append(
            f"write_mode: '{write_mode}' is not supported. Supported: {supported_modes}."
        )

    if expected_headers and rows:
        first_data_row = rows[0] if rows else []
        if len(first_data_row) != len(expected_headers):
            errors.append(
                f"rows: column count ({len(first_data_row)}) does not match "
                f"expected headers ({len(expected_headers)})."
            )

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "spreadsheet_id": spreadsheet_id,
        "range_name": range_name,
        "write_mode": write_mode,
        "row_count": len(rows),
        "rows": rows,
        "expected_headers": expected_headers,
    }


def sheet_write_dry_run(
    pending_action: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(pending_action.get("payload") or {})
    validation = validate_sheet_write_payload(payload, config=config)
    mark_pending_action_dry_run_executed(pending_action)
    if not validation["ok"]:
        return {
            "ok": False,
            "type": "sheet_write_result",
            "error": "; ".join(validation["errors"]),
            "data": {
                "dry_run": True,
                "written": False,
                "spreadsheet_id": validation["spreadsheet_id"],
                "range_name": validation["range_name"],
                "write_mode": validation["write_mode"],
                "row_count": validation["row_count"],
                "updated_range": "",
            },
        }
    return {
        "ok": True,
        "type": "sheet_write_result",
        "data": {
            "dry_run": True,
            "written": False,
            "spreadsheet_id": validation["spreadsheet_id"],
            "range_name": validation["range_name"],
            "write_mode": validation["write_mode"],
            "row_count": validation["row_count"],
            "updated_range": "",
        },
        "evidence": {},
        "error": "",
    }


def _sheets_api_write(
    *,
    spreadsheet_id: str,
    range_name: str,
    rows: list[list[Any]],
    write_mode: str = "append",
) -> dict[str, Any]:
    try:
        from .google_sheet_tools import sheet_write_rows
    except ImportError as exc:
        return {"ok": False, "error": f"Google Sheets API unavailable: {exc}", "updated_range": ""}

    result = sheet_write_rows(
        spreadsheet_id=spreadsheet_id,
        range_name=range_name,
        rows=rows,
        mode=write_mode,
        dry_run=False,
    )
    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error", "Google Sheets write failed."),
            "updated_range": "",
            "row_count": len(rows),
        }
    return {
        "ok": True,
        "updated_range": str(result.get("range_name") or range_name),
        "row_count": int(result.get("row_count") or len(rows)),
    }


def sheet_write_live_execute(
    pending_action: dict[str, Any],
    tool_spec: dict[str, Any],
    *,
    manifest_live_execution: dict[str, Any] | None = None,
    profile_name: str = "demo",
    profile_data: dict[str, Any] | None = None,
    executed_actions: list[dict[str, Any]] | None = None,
    confirmation: str | None = None,
    config: dict[str, Any] | None = None,
    _sheets_api_write_fn: Any = None,
) -> dict[str, Any]:
    preflight = run_live_side_effect_preflight(
        pending_action=pending_action,
        tool_spec=tool_spec,
        manifest_live_execution=manifest_live_execution,
        profile_name=profile_name,
        profile_data=profile_data,
        executed_actions=executed_actions,
        dry_run=False,
        confirmation=confirmation,
    )

    payload = dict(pending_action.get("payload") or {})
    spreadsheet_id = str(payload.get("spreadsheet_id") or "")
    range_name = str(payload.get("range_name") or "")
    write_mode = str(payload.get("write_mode") or "append")
    rows = list(payload.get("rows") or [])

    if not preflight["ok"]:
        return {
            "ok": False,
            "type": "sheet_write_result",
            "blocked": True,
            "error_code": preflight.get("error_code"),
            "preflight": preflight,
            "data": {
                "dry_run": False,
                "written": False,
                "spreadsheet_id": spreadsheet_id,
                "range_name": range_name,
                "write_mode": write_mode,
                "row_count": len(rows),
                "updated_range": "",
            },
        }

    from .live_guardrails import guardrail_sheet_write_rows

    guardrail_result = guardrail_sheet_write_rows(pending_action, tool_spec, config=config)
    if not guardrail_result["ok"]:
        return {
            "ok": False,
            "type": "sheet_write_result",
            "blocked": True,
            "error_code": "LIVE_GUARDRAIL_FAILED",
            "guardrail_result": guardrail_result,
            "data": {
                "dry_run": False,
                "written": False,
                "spreadsheet_id": spreadsheet_id,
                "range_name": range_name,
                "write_mode": write_mode,
                "row_count": len(rows),
                "updated_range": "",
            },
        }

    validation = validate_sheet_write_payload(payload, config=config)
    if not validation["ok"]:
        return {
            "ok": False,
            "type": "sheet_write_result",
            "blocked": True,
            "error": "; ".join(validation["errors"]),
            "data": {
                "dry_run": False,
                "written": False,
                "spreadsheet_id": spreadsheet_id,
                "range_name": range_name,
                "write_mode": write_mode,
                "row_count": len(rows),
                "updated_range": "",
            },
        }

    write_fn = _sheets_api_write_fn or _sheets_api_write
    write_result = write_fn(
        spreadsheet_id=spreadsheet_id,
        range_name=range_name,
        rows=rows,
        write_mode=write_mode,
    )

    if not write_result.get("ok"):
        return {
            "ok": False,
            "type": "sheet_write_result",
            "blocked": False,
            "error": write_result.get("error", "Google Sheets write API error."),
            "data": {
                "dry_run": False,
                "written": False,
                "spreadsheet_id": spreadsheet_id,
                "range_name": range_name,
                "write_mode": write_mode,
                "row_count": len(rows),
                "updated_range": "",
            },
        }

    updated_range = str(write_result.get("updated_range") or range_name)
    row_count = int(write_result.get("row_count") or len(rows))
    mark_pending_action_live_executed(pending_action, guardrail_result)
    pending_action["updated_range"] = updated_range

    return {
        "ok": True,
        "type": "sheet_write_result",
        "blocked": False,
        "guardrail_result": guardrail_result,
        "data": {
            "dry_run": False,
            "written": True,
            "spreadsheet_id": spreadsheet_id,
            "range_name": range_name,
            "write_mode": write_mode,
            "row_count": row_count,
            "updated_range": updated_range,
        },
        "evidence": {},
        "error": "",
    }


def build_sheet_write_report(
    *,
    frame_id: str,
    action_id: str,
    manifest_id: str = "",
    profile: str = "",
    spreadsheet_id: str,
    range_name: str,
    write_mode: str,
    row_count: int,
    updated_range: str = "",
    written: bool = False,
    blocked: bool = False,
    error_code: str = "",
    guardrail_result: dict[str, Any] | None = None,
    idempotency_key: str = "",
    business_ref: str = "",
    approved_by: str = "",
    expected_headers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "report_type": "sheet_write_attempt",
        "generated_at": _utc_now(),
        "frame_id": frame_id,
        "action_id": action_id,
        "manifest_id": manifest_id,
        "profile": profile,
        "tool": SHEET_WRITE_TOOL_KEY,
        "spreadsheet_id": spreadsheet_id,
        "range_name": range_name,
        "write_mode": write_mode,
        "row_count": row_count,
        "updated_range": updated_range,
        "expected_headers": list(expected_headers or []),
        "written": written,
        "blocked": blocked,
        "error_code": error_code,
        "guardrail_result": guardrail_result or {},
        "idempotency_key": idempotency_key,
        "business_ref": business_ref,
        "approval_record": {"approved_by": approved_by},
    }


def write_sheet_write_report(
    report: dict[str, Any],
    *,
    runtime_data_dir: str = "runtime_data",
) -> dict[str, Any]:
    from pathlib import Path
    import json

    reports_dir = Path(runtime_data_dir) / "live_execution"
    reports_dir.mkdir(parents=True, exist_ok=True)

    frame_id = _safe_slug(str(report.get("frame_id") or "frame"))
    action_id = _safe_slug(str(report.get("action_id") or "action"))
    ts = _timestamp_slug()
    stem = f"sheet_write_{frame_id}_{action_id}_{ts}"

    json_path = reports_dir / f"{stem}.json"
    md_path = reports_dir / f"{stem}.md"

    try:
        json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        md_path.write_text(_build_sheet_write_report_md(report), encoding="utf-8")
    except OSError as exc:
        return {
            "ok": False,
            "error_code": "LIVE_EVIDENCE_WRITE_FAILED",
            "message": str(exc),
            "json_path": "",
            "md_path": "",
        }

    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def _build_sheet_write_report_md(report: dict[str, Any]) -> str:
    blocked = report.get("blocked", True)
    written = report.get("written", False)
    if written:
        status_line = "WRITTEN"
    elif blocked:
        status_line = "BLOCKED"
    else:
        status_line = "DRY-RUN"

    lines = [
        f"# Google Sheets Write Report — {status_line}",
        "",
        f"**Generated:** {report.get('generated_at', '')}",
        f"**Frame ID:** {report.get('frame_id', '')}",
        f"**Action ID:** {report.get('action_id', '')}",
        f"**Manifest ID:** {report.get('manifest_id', '')}",
        f"**Profile:** {report.get('profile', '')}",
        f"**Tool:** {report.get('tool', '')}",
        f"**Business Ref:** {report.get('business_ref', '')}",
        f"**Idempotency Key:** {report.get('idempotency_key', '')}",
        "",
        "## Target",
        "",
        f"- Spreadsheet ID: `{report.get('spreadsheet_id', '')}`",
        f"- Range: `{report.get('range_name', '')}`",
        f"- Write Mode: {report.get('write_mode', '')}",
        "",
        "## Write Result",
        "",
        f"- Row Count: {report.get('row_count', 0)}",
        f"- Updated Range: `{report.get('updated_range', '') or 'n/a'}`",
        f"- Written: {written}",
        f"- Blocked: {blocked}",
    ]
    if report.get("error_code"):
        lines.append(f"- Error Code: {report.get('error_code', '')}")
    headers = report.get("expected_headers") or []
    if headers:
        lines += ["", f"- Expected Headers: {headers}"]
    lines += [
        "",
        "_(Row payloads are not included in this report. See evidence references for full data.)_",
        "",
        "## Approval",
        "",
    ]
    approval = report.get("approval_record") or {}
    lines.append(f"- Approved by: {approval.get('approved_by', '')}")
    guardrail = report.get("guardrail_result") or {}
    if guardrail:
        lines += ["", "## Guardrail", ""]
        lines.append(f"- Guardrail: {guardrail.get('guardrail', '')}")
        lines.append(f"- OK: {guardrail.get('ok', False)}")
        for check in guardrail.get("checks") or []:
            status = "pass" if check.get("ok") else "FAIL"
            lines.append(f"  - [{status}] {check.get('name', '')}: {check.get('message', '')}")
    return "\n".join(lines) + "\n"


def build_sheet_write_audit_event(
    *,
    event_type: str,
    frame_id: str,
    action_id: str,
    idempotency_key: str,
    business_ref: str,
    spreadsheet_id: str,
    range_name: str,
    updated_range: str = "",
    row_count: int = 0,
    approved_by: str = "",
    reason: str = "",
    error_code: str = "",
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "frame_id": frame_id,
        "action_id": action_id,
        "tool": SHEET_WRITE_TOOL_KEY,
        "idempotency_key": idempotency_key,
        "business_ref": business_ref,
        "spreadsheet_id": spreadsheet_id,
        "range_name": range_name,
        "updated_range": updated_range,
        "row_count": row_count,
        "approved_by": approved_by,
        "reason": reason,
        "error_code": error_code,
        "executed_at": _utc_now(),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_slug(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)
