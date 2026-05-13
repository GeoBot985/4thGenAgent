from __future__ import annotations

import json
from typing import Any



def run_live_guardrail(
    guardrail_name: str,
    pending_action: dict[str, Any],
    tool_spec: dict[str, Any],
) -> dict[str, Any]:
    if guardrail_name == "sheet_create":
        return guardrail_sheet_create(pending_action, tool_spec)
    if guardrail_name == "sheet_write":
        return guardrail_sheet_write(pending_action, tool_spec)
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
