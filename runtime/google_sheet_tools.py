from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import sys

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

try:
    from tools.read_sheet_entries import read_sheet_entries
except Exception:  # pragma: no cover - test environments without google client deps
    read_sheet_entries = None  # type: ignore[assignment]

try:
    from tools.write_sheet_entries import write_sheet_entries
except Exception:  # pragma: no cover - test environments without google client deps
    write_sheet_entries = None  # type: ignore[assignment]


def load_accounting_sheet_config(config_path: str = "config/accounting_google_sheet.json") -> dict[str, Any]:
    path = Path(config_path)
    if not path.is_file():
        return {"spreadsheet_id": "", "tabs": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"spreadsheet_id": "", "tabs": {}}


def sheet_read_range(spreadsheet_id: str, range_name: str) -> dict[str, Any]:
    if not str(spreadsheet_id).strip():
        return {"ok": False, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "rows": [], "row_count": 0, "error": "SPREADSHEET_ID_REQUIRED"}
    if read_sheet_entries is None:
        raise RuntimeError("Google Sheet reader is unavailable.")
    rows = read_sheet_entries(spreadsheet_id=spreadsheet_id, range_name=range_name)
    return {"ok": True, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "rows": rows, "row_count": len(rows), "error": ""}


def sheet_prepare_write_rows(spreadsheet_id: str, range_name: str, rows: list[list[Any]], mode: str = "append") -> dict[str, Any]:
    return {"ok": True, "action_type": "sheet_write_rows", "tool": "sheet/write_rows", "spreadsheet_id": spreadsheet_id, "range_name": range_name, "mode": mode, "rows": rows, "row_count": len(rows)}


def sheet_write_rows(spreadsheet_id: str, range_name: str, rows: list[list[Any]], mode: str = "append", dry_run: bool = True) -> dict[str, Any]:
    if dry_run:
        return {"ok": True, "dry_run": True, "written": False, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "mode": mode, "row_count": len(rows), "message": "Google Sheet write dry-run completed."}
    if not str(spreadsheet_id).strip():
        return {"ok": False, "dry_run": False, "written": False, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "mode": mode, "row_count": len(rows), "error": "SPREADSHEET_ID_REQUIRED"}
    if write_sheet_entries is None:
        raise RuntimeError("Google Sheet writer is unavailable.")
    try:
        result = write_sheet_entries(spreadsheet_id=spreadsheet_id, range_name=range_name, values=rows, mode=mode)
    except Exception as exc:
        return {
            "ok": False,
            "dry_run": False,
            "written": False,
            "spreadsheet_id": spreadsheet_id,
            "range_name": range_name,
            "mode": mode,
            "row_count": len(rows),
            "error": f"LIVE_SHEET_WRITE_FAILED: {exc}",
        }
    updated_range = result.get("updates", {}).get("updatedRange") or result.get("updatedRange") or range_name
    updated_rows = result.get("updates", {}).get("updatedRows") or result.get("updatedRows") or len(rows)
    return {
        "ok": True,
        "dry_run": False,
        "written": True,
        "spreadsheet_id": spreadsheet_id,
        "range_name": updated_range,
        "mode": mode,
        "row_count": updated_rows,
        "message": "Google Sheet write completed.",
        "google_response": result,
    }
