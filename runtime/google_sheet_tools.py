from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

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

_SHEET_FIXTURE_MODE: ContextVar[bool] = ContextVar("sheet_fixture_mode", default=False)
_SHEET_FIXTURE_RUNTIME_DIR: ContextVar[str] = ContextVar("sheet_fixture_runtime_dir", default="runtime_data")

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
    if _SHEET_FIXTURE_MODE.get():
        return read_range_fixture(spreadsheet_id, range_name, runtime_data_dir=_SHEET_FIXTURE_RUNTIME_DIR.get())
    if str(spreadsheet_id).strip() == DEMO_SPREADSHEET_ID:
        rows = DEMO_ACCOUNTING_SHEET_ROWS.get(range_name)
        if rows is None:
            return {"ok": False, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "rows": [], "row_count": 0, "error": f"UNKNOWN_DEMO_RANGE:{range_name}"}
        return {"ok": True, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "rows": rows, "row_count": len(rows), "error": ""}
    if read_sheet_entries is None:
        raise RuntimeError("Google Sheet reader is unavailable.")
    rows = read_sheet_entries(spreadsheet_id=spreadsheet_id, range_name=range_name)
    return {"ok": True, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "rows": rows, "row_count": len(rows), "error": ""}


@contextmanager
def use_sheet_fixture_mode(enabled: bool, runtime_data_dir: str = "runtime_data"):
    mode_token = _SHEET_FIXTURE_MODE.set(bool(enabled))
    root_token = _SHEET_FIXTURE_RUNTIME_DIR.set(str(runtime_data_dir))
    try:
        yield
    finally:
        _SHEET_FIXTURE_MODE.reset(mode_token)
        _SHEET_FIXTURE_RUNTIME_DIR.reset(root_token)


def read_range_fixture(spreadsheet_id: str, range_name: str, runtime_data_dir: str = "runtime_data") -> dict[str, Any]:
    fixture = _load_accounting_fixture_rows(range_name, runtime_data_dir)
    if fixture is None:
        return {
            "ok": False,
            "spreadsheet_id": spreadsheet_id,
            "range_name": range_name,
            "rows": [],
            "row_count": 0,
            "fixture_mode": True,
            "live_external_call": False,
            "source": "workbench_fixture",
            "error": "Fixture data not available for this tool/range.",
            "metadata": {
                "fixture_mode": True,
                "live_external_call": False,
                "source": "workbench_fixture",
            },
        }
    rows, fixture_source = fixture
    return {
        "ok": True,
        "spreadsheet_id": spreadsheet_id,
        "range_name": range_name,
        "rows": rows,
        "row_count": len(rows),
        "fixture_mode": True,
        "live_external_call": False,
        "source": "workbench_fixture",
        "fixture_source": fixture_source,
        "error": "",
        "metadata": {
            "fixture_mode": True,
            "live_external_call": False,
            "source": "workbench_fixture",
            "fixture_source": fixture_source,
        },
    }


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


def _load_accounting_fixture_rows(range_name: str, runtime_data_dir: str = "runtime_data") -> tuple[list[list[str]], str] | None:
    base = Path(runtime_data_dir) / "business"
    sheet_name = _sheet_name(range_name)
    if sheet_name == "Payments":
        rows = _rows_from_records(
            _load_json_records(base / "payments.json"),
            ["payment_id", "payment_ref", "order_ref", "customer_id", "amount", "currency", "payment_date", "status", "source"],
            lambda record: [
                _string(record.get("payment_id")),
                _string(record.get("payment_ref") or record.get("provider_ref")),
                _string(record.get("order_ref")),
                _string(record.get("customer_id")),
                _format_money(record.get("amount")),
                _string(record.get("currency")),
                _date_only(record.get("paid_at")),
                _string(record.get("status")),
                _string(record.get("source") or "bank"),
            ],
        )
        if rows:
            return rows, str(base / "payments.json")
        for key in DEMO_ACCOUNTING_SHEET_ROWS:
            if _sheet_name(key) == "Payments":
                return list(DEMO_ACCOUNTING_SHEET_ROWS[key]), "built_in_demo_fixture"
    if sheet_name == "Orders":
        rows = _rows_from_records(
            _load_json_records(base / "orders.json"),
            ["order_ref", "customer_id", "order_total", "currency", "order_status", "invoice_id"],
            lambda record: [
                _string(record.get("order_ref")),
                _string(record.get("customer_id")),
                _format_money(record.get("total_amount")),
                _string(record.get("currency")),
                _string(record.get("status")),
                _string(record.get("invoice_id") or _invoice_id_for_order(record.get("order_ref"))),
            ],
        )
        if rows:
            return rows, str(base / "orders.json")
        for key in DEMO_ACCOUNTING_SHEET_ROWS:
            if _sheet_name(key) == "Orders":
                return list(DEMO_ACCOUNTING_SHEET_ROWS[key]), "built_in_demo_fixture"
    if sheet_name in {"CustomerInvoices", "Invoices"}:
        for key in DEMO_ACCOUNTING_SHEET_ROWS:
            if _sheet_name(key) in {"CustomerInvoices", "Invoices"}:
                return list(DEMO_ACCOUNTING_SHEET_ROWS[key]), "built_in_demo_fixture"
    if sheet_name == "Ledger":
        for key in DEMO_ACCOUNTING_SHEET_ROWS:
            if _sheet_name(key) == "Ledger":
                return list(DEMO_ACCOUNTING_SHEET_ROWS[key]), "built_in_demo_fixture"
    if sheet_name == "ReconRuns":
        return _built_in_recon_runs_fixture()
    if sheet_name == "ReconExceptions":
        return _built_in_recon_exceptions_fixture()
    if range_name in DEMO_ACCOUNTING_SHEET_ROWS:
        return list(DEMO_ACCOUNTING_SHEET_ROWS[range_name]), "built_in_demo_fixture"
    return None


def _load_json_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _rows_from_records(records: list[dict[str, Any]], header: list[str], row_builder: Any) -> list[list[str]]:
    if not records:
        return []
    rows = [list(header)]
    for record in records:
        rows.append([_string(value) for value in row_builder(record)])
    return rows


def _format_money(value: Any) -> str:
    try:
        if value is None or value == "":
            return ""
        return f"{float(value):.2f}"
    except Exception:
        return _string(value)


def _date_only(value: Any) -> str:
    text = _string(value)
    if "T" in text:
        return text.split("T", 1)[0]
    return text


def _invoice_id_for_order(order_ref: Any) -> str:
    text = _string(order_ref)
    if text.startswith("ORD-"):
        suffix = text.split("-", 1)[1]
        return f"INV-{suffix}"
    return ""


def _sheet_name(range_name: str) -> str:
    text = _string(range_name).strip()
    if not text:
        return ""
    return text.split("!", 1)[0].strip()


def _built_in_recon_runs_fixture() -> tuple[list[list[str]], str]:
    rows = [
        ["run_id", "status", "processed_count", "exception_count", "generated_at"],
        ["RECON-1", "prepared", "8", "3", "2026-05-01T00:00:00Z"],
    ]
    return rows, "built_in_demo_fixture"


def _built_in_recon_exceptions_fixture() -> tuple[list[list[str]], str]:
    rows = [
        ["exception_id", "payment_id", "order_ref", "reason", "severity", "status"],
        ["EXC-1", "PAY-7003", "ORD-10044", "Amount mismatch", "high", "open"],
        ["EXC-2", "PAY-7004", "ORD-99998", "Order missing", "high", "open"],
    ]
    return rows, "built_in_demo_fixture"


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)
