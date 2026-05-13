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


DEMO_SPREADSHEET_ID = "demo-sheet-local"

DEMO_ACCOUNTING_SHEET_ROWS: dict[str, list[list[str]]] = {
    "Payments!A:I": [
        ["payment_id", "payment_ref", "order_ref", "customer_id", "amount", "currency", "payment_date", "status", "source"],
        ["PAY-1001", "EFT-9001", "ORD-10042", "CUST-1001", "1250.00", "ZAR", "2026-05-04", "received", "bank"],
        ["PAY-1002", "EFT-9002", "ORD-10043", "CUST-1002", "450.00", "ZAR", "2026-05-04", "received", "bank"],
        ["PAY-1003", "EFT-9003", "ORD-10044", "CUST-1003", "300.00", "ZAR", "2026-05-04", "received", "bank"],
        ["PAY-1004", "EFT-9005", "ORD-10045", "CUST-1004", "500.00", "ZAR", "2026-05-04", "received", "bank"],
        ["PAY-1005", "EFT-9005", "ORD-10046", "CUST-1005", "250.00", "ZAR", "2026-05-04", "received", "bank"],
    ],
    "Orders!A:F": [
        ["order_ref", "customer_id", "order_total", "currency", "order_status", "invoice_id"],
        ["ORD-10042", "CUST-1001", "1250.00", "ZAR", "invoiced", "INV-10042"],
        ["ORD-10043", "CUST-1002", "500.00", "ZAR", "invoiced", "INV-10043"],
        ["ORD-10044", "CUST-1003", "300.00", "ZAR", "invoiced", "INV-10044"],
        ["ORD-10045", "CUST-1004", "500.00", "ZAR", "invoiced", "INV-10045"],
        ["ORD-10046", "CUST-1005", "250.00", "ZAR", "invoiced", "INV-10046"],
    ],
    "CustomerInvoices!A:H": [
        ["invoice_id", "order_ref", "customer_id", "invoice_total", "currency", "invoice_status", "issued_date", "due_date"],
        ["INV-10042", "ORD-10042", "CUST-1001", "1250.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
        ["INV-10043", "ORD-10043", "CUST-1002", "500.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
        ["INV-10044", "ORD-10044", "CUST-1003", "300.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
        ["INV-10045", "ORD-10045", "CUST-1004", "500.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
        ["INV-10046", "ORD-10046", "CUST-1005", "250.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
    ],
    "Ledger!A:I": [
        ["ledger_entry_id", "source_type", "source_ref", "debit_account", "credit_account", "amount", "currency", "posted_date", "status"],
        ["LED-1001", "payment", "EFT-9001", "bank", "revenue", "1250.00", "ZAR", "2026-05-04", "posted"],
    ],
}


def load_accounting_sheet_config(config_path: str = "config/accounting_google_sheet.json") -> dict[str, Any]:
    path = Path(config_path)
    if not path.is_file():
        return {"spreadsheet_id": "", "tabs": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"spreadsheet_id": "", "tabs": {}}


def sheet_read_range(spreadsheet_id: str, range_name: str) -> dict[str, Any]:
    if not str(spreadsheet_id).strip():
        return {"ok": False, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "rows": [], "row_count": 0, "error": "SPREADSHEET_ID_REQUIRED"}
    if str(spreadsheet_id).strip() == DEMO_SPREADSHEET_ID:
        rows = DEMO_ACCOUNTING_SHEET_ROWS.get(range_name)
        if rows is None:
            return {"ok": False, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "rows": [], "row_count": 0, "error": f"UNKNOWN_DEMO_RANGE:{range_name}"}
        return {"ok": True, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "rows": rows, "row_count": len(rows), "error": ""}
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
