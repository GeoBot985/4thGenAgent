from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .invoiceops_contracts import (
    validate_exception_shape,
    validate_goods_receipt_shape,
    validate_invoice_shape,
    validate_ledger_row_shape,
    validate_purchase_order_shape,
    validate_supplier_shape,
)
from .tool_result_contract import build_tool_evidence

_RESULT_TYPE = "invoiceops_sheet_rows"
_DEFAULT_FIXTURE_BASE = Path("tests/fixtures/invoiceops/sheets")

# ---------------------------------------------------------------------------
# Sheet registry
# ---------------------------------------------------------------------------

_SHEET_CFG: dict[str, dict] = {
    "supplier_master": {
        "sheet_name": "SupplierMaster",
        "tool": "invoiceops/read_supplier_master",
        "fixture_file": "supplier_master.json",
        "range_name": "SupplierMaster!A:Z",
        "validator": validate_supplier_shape,
        "primary_key": "supplier_id",
    },
    "po_register": {
        "sheet_name": "PORegister",
        "tool": "invoiceops/read_po_register",
        "fixture_file": "po_register.json",
        "range_name": "PORegister!A:Z",
        "validator": validate_purchase_order_shape,
        "primary_key": "po_number",
    },
    "receipt_register": {
        "sheet_name": "GoodsReceipts",
        "tool": "invoiceops/read_receipt_register",
        "fixture_file": "goods_receipts.json",
        "range_name": "GoodsReceipts!A:Z",
        "validator": validate_goods_receipt_shape,
        "primary_key": "receipt_id",
    },
    "invoice_register": {
        "sheet_name": "InvoiceRegister",
        "tool": "invoiceops/read_invoice_register",
        "fixture_file": "invoice_register.json",
        "range_name": "InvoiceRegister!A:Z",
        "validator": validate_invoice_shape,
        "primary_key": "invoice_number",
    },
    "ledger": {
        "sheet_name": "Ledger",
        "tool": "invoiceops/read_ledger",
        "fixture_file": "ledger.json",
        "range_name": "Ledger!A:Z",
        "validator": validate_ledger_row_shape,
        "primary_key": "ledger_entry_id",
    },
    "exception_register": {
        "sheet_name": "ExceptionRegister",
        "tool": "invoiceops/read_exception_register",
        "fixture_file": "exception_register.json",
        "range_name": "ExceptionRegister!A:Z",
        "validator": validate_exception_shape,
        "primary_key": "exception_id",
    },
}


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

def invoiceops_read_supplier_master(
    spreadsheet_id: str = "",
    fixture_mode: bool = True,
    _fixture_dir: str = "",
) -> dict:
    return _read_sheet("supplier_master", spreadsheet_id=spreadsheet_id, fixture_mode=fixture_mode, fixture_dir=_fixture_dir)


def invoiceops_read_po_register(
    spreadsheet_id: str = "",
    fixture_mode: bool = True,
    _fixture_dir: str = "",
) -> dict:
    return _read_sheet("po_register", spreadsheet_id=spreadsheet_id, fixture_mode=fixture_mode, fixture_dir=_fixture_dir)


def invoiceops_read_receipt_register(
    spreadsheet_id: str = "",
    fixture_mode: bool = True,
    _fixture_dir: str = "",
) -> dict:
    return _read_sheet("receipt_register", spreadsheet_id=spreadsheet_id, fixture_mode=fixture_mode, fixture_dir=_fixture_dir)


def invoiceops_read_invoice_register(
    spreadsheet_id: str = "",
    fixture_mode: bool = True,
    _fixture_dir: str = "",
) -> dict:
    return _read_sheet("invoice_register", spreadsheet_id=spreadsheet_id, fixture_mode=fixture_mode, fixture_dir=_fixture_dir)


def invoiceops_read_ledger(
    spreadsheet_id: str = "",
    fixture_mode: bool = True,
    _fixture_dir: str = "",
) -> dict:
    return _read_sheet("ledger", spreadsheet_id=spreadsheet_id, fixture_mode=fixture_mode, fixture_dir=_fixture_dir)


def invoiceops_read_exception_register(
    spreadsheet_id: str = "",
    fixture_mode: bool = True,
    _fixture_dir: str = "",
) -> dict:
    return _read_sheet("exception_register", spreadsheet_id=spreadsheet_id, fixture_mode=fixture_mode, fixture_dir=_fixture_dir)


# ---------------------------------------------------------------------------
# Core read dispatcher
# ---------------------------------------------------------------------------

def _read_sheet(
    register_key: str,
    *,
    spreadsheet_id: str,
    fixture_mode: bool,
    fixture_dir: str = "",
) -> dict:
    cfg = _SHEET_CFG[register_key]
    tool = cfg["tool"]
    sheet_name = cfg["sheet_name"]
    primary_key = cfg["primary_key"]
    validator: Callable[[dict], dict] = cfg["validator"]
    warnings: list[str] = []

    if fixture_mode:
        base = Path(fixture_dir) if fixture_dir else _DEFAULT_FIXTURE_BASE
        load_result = _load_fixture(base / cfg["fixture_file"])
    else:
        if not str(spreadsheet_id).strip():
            return _error_result(tool, sheet_name, "SPREADSHEET_ID_REQUIRED", fixture_mode)
        load_result = _load_live(spreadsheet_id, cfg["range_name"], warnings)

    if load_result is None:
        return _error_result(tool, sheet_name, "SHEET_FIXTURE_NOT_FOUND", fixture_mode)

    ok, records, load_warnings = load_result
    warnings.extend(load_warnings)

    if not ok:
        return _error_result(tool, sheet_name, "SHEET_READ_FAILED", fixture_mode)

    if not records:
        return _error_result(tool, sheet_name, "SHEET_RECORDS_EMPTY", fixture_mode)

    # Duplicate key detection
    seen: dict[str, int] = {}
    for i, rec in enumerate(records):
        key = str(rec.get(primary_key, ""))
        if key and key in seen:
            warnings.append(f"Duplicate {primary_key}={key!r} found at rows {seen[key]} and {i}.")
        elif key:
            seen[key] = i

    # Per-record validation — failures become warnings, not errors
    for i, rec in enumerate(records):
        v = validator(rec)
        for err in v.get("errors", []):
            warnings.append(f"records[{i}] validation error: {err}")
        for w in v.get("warnings", []):
            warnings.append(f"records[{i}] validation warning: {w}")

    rows = _records_to_rows(records)

    evidence = build_tool_evidence(
        tool=tool,
        mode="dry_run",
        source="builtin",
        operation="read",
        input_refs=[f"sheet={sheet_name}"],
        output_ref=_RESULT_TYPE,
        extra={"fixture_mode": fixture_mode},
    )

    return {
        "ok": True,
        "type": _RESULT_TYPE,
        "data": {
            "sheet_name": sheet_name,
            "rows": rows,
            "records": records,
            "record_count": len(records),
            "validation_warnings": warnings,
        },
        "evidence": evidence,
        "error": "",
        "metadata": {"fixture_mode": fixture_mode},
    }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_fixture(path: Path) -> tuple[bool, list[dict], list[str]] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [], [f"Failed to parse fixture: {exc}"]
    if not isinstance(data, list):
        return False, [], ["Fixture must be a JSON array."]
    records = [dict(r) for r in data if isinstance(r, dict)]
    extra = len(data) - len(records)
    load_warnings: list[str] = []
    if extra:
        load_warnings.append(f"{extra} non-dict row(s) skipped in fixture.")
    return True, records, load_warnings


def _load_live(
    spreadsheet_id: str,
    range_name: str,
    warnings: list[str],
) -> tuple[bool, list[dict], list[str]] | None:
    try:
        from .google_sheet_tools import sheet_read_range
    except Exception as exc:
        return False, [], [f"sheet_read_range unavailable: {exc}"]

    result = sheet_read_range(spreadsheet_id, range_name)
    if not result.get("ok"):
        return False, [], [result.get("error", "SHEET_READ_FAILED")]

    raw_rows: list[list[str]] = result.get("rows", [])
    if not raw_rows:
        return True, [], []

    header = [str(h).strip() for h in raw_rows[0]]
    if not any(header):
        return False, [], ["SHEET_HEADERS_MISSING"]

    records: list[dict] = []
    unknown: set[str] = set()
    for row in raw_rows[1:]:
        rec: dict[str, Any] = {}
        for i, col in enumerate(header):
            rec[col] = row[i] if i < len(row) else ""
        records.append(rec)

    load_warnings: list[str] = []
    if unknown:
        load_warnings.append(f"Unknown columns in sheet: {sorted(unknown)}")

    return True, records, load_warnings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _records_to_rows(records: list[dict]) -> list[list[Any]]:
    if not records:
        return []
    headers = list(records[0].keys())
    result: list[list[Any]] = [headers]
    for rec in records:
        result.append([rec.get(h, "") for h in headers])
    return result


def _error_result(tool: str, sheet_name: str, error_code: str, fixture_mode: bool = True) -> dict:
    return {
        "ok": False,
        "type": _RESULT_TYPE,
        "data": {},
        "evidence": {},
        "error": error_code,
        "metadata": {"sheet_name": sheet_name, "fixture_mode": fixture_mode},
    }
