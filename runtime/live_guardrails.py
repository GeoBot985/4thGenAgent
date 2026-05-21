from __future__ import annotations

import json
from typing import Any



def run_live_guardrail(
    guardrail_name: str,
    pending_action: dict[str, Any],
    tool_spec: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    if guardrail_name == "sheet_create":
        return guardrail_sheet_create(pending_action, tool_spec)
    if guardrail_name == "sheet_write":
        return guardrail_sheet_write(pending_action, tool_spec)
    if guardrail_name == "sheet_write_rows_guardrail":
        return guardrail_sheet_write_rows(pending_action, tool_spec, **kwargs)
    if guardrail_name == "gmail_send":
        return guardrail_gmail_send(pending_action, tool_spec, **kwargs)
    return guardrail_blocked(pending_action, tool_spec)


def guardrail_sheet_create(pending_action: dict[str, Any], tool_spec: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    args = dict(pending_action.get("args", {}))
    title = str(args.get("title", "")).strip()
    ok = True

    def add_check(name: str, passed: bool, message: str = "") -> None:
        checks.append({"name": name, "ok": passed, "message": message})

    passed = bool(title)
    ok = ok and passed
    add_check("title_present", passed, "" if passed else "Title is required.")

    passed = len(title) <= 120
    ok = ok and passed
    add_check("title_length", passed, "" if passed else "Title is too long.")

    passed = not any(sep in title for sep in ("/", "\\", ":"))
    ok = ok and passed
    add_check("title_path_safe", passed, "" if passed else "Title contains a path separator.")

    passed = not title.startswith("test-delete")
    ok = ok and passed
    add_check("title_name_safe", passed, "" if passed else "Title starts with blocked prefix.")

    result = {"ok": ok, "guardrail": "sheet_create", "checks": checks}
    if not ok:
        result["error"] = "Sheet create guardrail failed."
    return result


def guardrail_sheet_write(pending_action: dict[str, Any], tool_spec: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    args = dict(pending_action.get("args", {}))
    ok = True

    def add_check(name: str, passed: bool, message: str = "") -> None:
        checks.append({"name": name, "ok": passed, "message": message})

    spreadsheet_id = str(args.get("spreadsheet_id", "")).strip()
    range_name = str(args.get("range_name", "")).strip()
    values_json = args.get("values_json", args.get("rows", ""))
    mode = str(args.get("mode", "append")).strip() or "append"

    passed = bool(spreadsheet_id)
    ok = ok and passed
    add_check("spreadsheet_id_present", passed, "" if passed else "Spreadsheet id is required.")

    passed = bool(range_name)
    ok = ok and passed
    add_check("range_name_present", passed, "" if passed else "Range name is required.")

    values: Any = None
    try:
        values = json.loads(values_json) if isinstance(values_json, str) else values_json
        passed = isinstance(values, list) and all(isinstance(row, list) for row in values)
    except Exception:
        passed = False
    ok = ok and passed
    add_check("values_json_valid_2d_list", passed, "" if passed else "values_json must be a 2D list.")

    passed = mode in {"append", "update"}
    ok = ok and passed
    add_check("mode_valid", passed, "" if passed else "mode must be append or update.")

    rows = len(values) if isinstance(values, list) else 0
    cols = max((len(row) for row in values if isinstance(row, list)), default=0) if isinstance(values, list) and values else 0
    cells = sum(len(row) for row in values if isinstance(row, list)) if isinstance(values, list) else 0

    passed = rows <= 100
    ok = ok and passed
    add_check("row_limit", passed, "" if passed else "Too many rows.")

    passed = cols <= 50
    ok = ok and passed
    add_check("column_limit", passed, "" if passed else "Too many columns.")

    passed = cells <= 1000
    ok = ok and passed
    add_check("cell_limit", passed, "" if passed else "Too many cells.")

    formula_cells = 0
    if isinstance(values, list):
        for row in values:
            if not isinstance(row, list):
                continue
            for cell in row:
                if isinstance(cell, str) and cell.startswith("="):
                    formula_cells += 1

    add_check("formula_cells_detected", True, str(formula_cells))

    result = {"ok": ok, "guardrail": "sheet_write", "checks": checks, "formula_cells_detected": formula_cells}
    if not ok:
        result["error"] = "Sheet write guardrail failed."
    return result


def guardrail_gmail_send(
    pending_action: dict[str, Any],
    tool_spec: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .gmail_send_tool import normalize_gmail_send_config

    checks: list[dict[str, Any]] = []
    ok = True

    def add_check(name: str, passed: bool, message: str = "") -> None:
        nonlocal ok
        checks.append({"name": name, "ok": passed, "message": message})
        if not passed:
            ok = False

    status = str(pending_action.get("status") or "").upper()
    passed = status == "APPROVED"
    add_check("action_approved", passed, "" if passed else f"Action status is not APPROVED: {status}")

    tool = str(pending_action.get("tool") or "")
    passed = tool == "gmail/send"
    add_check("tool_is_gmail_send", passed, "" if passed else f"Tool is not gmail/send: {tool}")

    tool_allow = bool(tool_spec.get("allow_live_side_effect", False))
    add_check(
        "tool_allows_live_side_effect",
        tool_allow,
        "" if tool_allow else "Tool does not allow live side effects.",
    )

    payload = dict(pending_action.get("payload") or {})
    to_list = list(payload.get("to") or [])
    subject = str(payload.get("subject") or "").strip()
    body = str(payload.get("body") or "").strip()

    add_check("recipients_not_empty", bool(to_list), "" if to_list else "Recipient list (to) must not be empty.")
    add_check("subject_not_empty", bool(subject), "" if subject else "Subject must not be empty.")
    add_check("body_not_empty", bool(body), "" if body else "Body must not be empty.")

    business_ref = str(pending_action.get("business_ref") or "").strip()
    add_check("business_ref_exists", bool(business_ref), "" if business_ref else "Business ref is required.")

    idempotency_key = str(pending_action.get("idempotency_key") or "").strip()
    add_check(
        "idempotency_key_present",
        bool(idempotency_key),
        "" if idempotency_key else "Idempotency key is required.",
    )

    cfg = normalize_gmail_send_config(config)
    blocked_domains = [d.lower() for d in (cfg.get("blocked_recipient_domains") or [])]
    allowed_domains = [d.lower() for d in (cfg.get("allowed_recipient_domains") or [])]
    all_recipients = to_list + list(payload.get("cc") or []) + list(payload.get("bcc") or [])

    if blocked_domains:
        bad = [
            a for a in all_recipients
            if "@" in a and a.split("@")[-1].lower() in set(blocked_domains)
        ]
        add_check(
            "no_blocked_domains",
            not bad,
            "" if not bad else f"Blocked domain in recipients: {bad[0].split('@')[-1]}",
        )

    if allowed_domains:
        bad = [
            a for a in all_recipients
            if "@" in a and a.split("@")[-1].lower() not in set(allowed_domains)
        ]
        add_check(
            "recipient_domain_allowlist",
            not bad,
            "" if not bad else f"Domain not in allowlist: {bad[0].split('@')[-1]}",
        )

    max_recipients = int(cfg.get("max_recipients") or 5)
    passed = len(all_recipients) <= max_recipients
    add_check(
        "max_recipients",
        passed,
        "" if passed else f"Too many recipients ({len(all_recipients)} > {max_recipients}).",
    )

    attachments = list(payload.get("attachments") or [])
    allow_attachments = bool(cfg.get("allow_attachments"))
    passed = not attachments or allow_attachments
    add_check(
        "attachments_allowed",
        passed,
        "" if passed else "Attachments are not enabled in config.",
    )

    result: dict[str, Any] = {"ok": ok, "guardrail": "gmail_send", "checks": checks}
    if not ok:
        result["error"] = "Gmail send guardrail failed."
    return result


def guardrail_sheet_write_rows(
    pending_action: dict[str, Any],
    tool_spec: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .sheet_write_tool import normalize_sheet_write_config

    checks: list[dict[str, Any]] = []
    ok = True

    def add_check(name: str, passed: bool, message: str = "") -> None:
        nonlocal ok
        checks.append({"name": name, "ok": passed, "message": message})
        if not passed:
            ok = False

    status = str(pending_action.get("status") or "").upper()
    passed = status == "APPROVED"
    add_check("action_approved", passed, "" if passed else f"Action status is not APPROVED: {status}")

    tool = str(pending_action.get("tool") or "")
    passed = tool == "sheet/write_rows"
    add_check("tool_is_sheet_write_rows", passed, "" if passed else f"Tool is not sheet/write_rows: {tool}")

    tool_allow = bool(tool_spec.get("allow_live_side_effect", False))
    add_check(
        "tool_allows_live_side_effect",
        tool_allow,
        "" if tool_allow else "Tool does not allow live side effects.",
    )

    cfg = normalize_sheet_write_config(config)

    sheet_write_enabled = bool(cfg.get("enabled", False))
    add_check(
        "sheet_write_config_enabled",
        sheet_write_enabled,
        "" if sheet_write_enabled else "Google Sheets write is not enabled in config.",
    )

    payload = dict(pending_action.get("payload") or {})
    spreadsheet_id = str(payload.get("spreadsheet_id") or "").strip()
    range_name = str(payload.get("range_name") or "").strip()
    rows = list(payload.get("rows") or [])
    write_mode = str(payload.get("write_mode") or "append").strip()
    expected_headers = list(payload.get("expected_headers") or [])

    add_check(
        "spreadsheet_id_present",
        bool(spreadsheet_id),
        "" if spreadsheet_id else "Spreadsheet ID must not be empty.",
    )

    allowed_spreadsheets = [s for s in (cfg.get("allowed_spreadsheets") or []) if s]
    if allowed_spreadsheets:
        passed = spreadsheet_id in set(allowed_spreadsheets)
        add_check(
            "spreadsheet_id_allowlisted",
            passed,
            "" if passed else f"Spreadsheet ID '{spreadsheet_id}' is not in the allowlist.",
        )

    allowed_ranges = [r for r in (cfg.get("allowed_ranges") or []) if r]
    if allowed_ranges:
        range_tab = range_name.split("!")[0].strip() if "!" in range_name else range_name
        passed = range_name in set(allowed_ranges) or range_tab in set(allowed_ranges)
        add_check(
            "range_allowlisted",
            passed,
            "" if passed else f"Range '{range_name}' is not in the allowed ranges.",
        )

    blocked_ranges = [r for r in (cfg.get("blocked_ranges") or []) if r]
    if blocked_ranges:
        range_tab = range_name.split("!")[0].strip() if "!" in range_name else range_name
        is_blocked = range_name in set(blocked_ranges) or range_tab in set(blocked_ranges)
        add_check(
            "range_not_blocked",
            not is_blocked,
            "" if not is_blocked else f"Range '{range_name}' is in the blocked ranges list.",
        )

    supported_modes: list[str] = []
    if cfg.get("allow_append_mode"):
        supported_modes.append("append")
    if cfg.get("allow_update_mode"):
        supported_modes.append("update")
    passed = write_mode in supported_modes
    add_check(
        "write_mode_supported",
        passed,
        "" if passed else f"Write mode '{write_mode}' is not supported. Supported: {supported_modes}.",
    )

    add_check(
        "rows_not_empty",
        bool(rows),
        "" if rows else "rows must not be empty.",
    )

    max_rows = int(cfg.get("max_rows_per_action") or 50)
    passed = len(rows) <= max_rows
    add_check(
        "row_count_within_limit",
        passed,
        "" if passed else f"Row count ({len(rows)}) exceeds max_rows_per_action ({max_rows}).",
    )

    if expected_headers and rows:
        first_row = rows[0] if rows else []
        passed = len(first_row) == len(expected_headers)
        add_check(
            "column_count_matches_headers",
            passed,
            "" if passed else (
                f"Column count ({len(first_row)}) does not match "
                f"expected headers ({len(expected_headers)})."
            ),
        )

    business_ref = str(pending_action.get("business_ref") or "").strip()
    add_check(
        "business_ref_exists",
        bool(business_ref),
        "" if business_ref else "Business ref is required.",
    )

    idempotency_key = str(pending_action.get("idempotency_key") or "").strip()
    add_check(
        "idempotency_key_present",
        bool(idempotency_key),
        "" if idempotency_key else "Idempotency key is required.",
    )

    result: dict[str, Any] = {"ok": ok, "guardrail": "sheet_write_rows_guardrail", "checks": checks}
    if not ok:
        result["error"] = "Sheet write rows guardrail failed."
    return result


def guardrail_blocked(pending_action: dict[str, Any], tool_spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "guardrail": str(tool_spec.get("live_guardrail", "blocked")),
        "checks": [
            {
                "name": "blocked",
                "ok": False,
                "message": "Live execution is blocked for this tool.",
            }
        ],
        "error": "Live execution is blocked for this tool.",
    }
