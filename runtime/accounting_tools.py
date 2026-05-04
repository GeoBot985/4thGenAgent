from __future__ import annotations

from typing import Any


def _normalize_rows(sheet_rows: list[list[object]], amount_fields: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    if not sheet_rows:
        return [], []
    headers = [str(h).strip().lower().replace(" ", "_") for h in sheet_rows[0]]
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, row in enumerate(sheet_rows[1:], start=2):
        if not any(str(cell).strip() for cell in row):
            continue
        record: dict[str, Any] = {"source_row": index}
        for i, header in enumerate(headers):
            value = row[i] if i < len(row) else ""
            if header in amount_fields and str(value).strip() != "":
                try:
                    record[header] = float(value)
                except Exception:
                    record[header] = 0.0
                    errors.append(f"row_{index}:{header}")
            else:
                record[header] = value if value is not None else ""
        records.append(record)
    return records, errors


def accounting_load_payments(sheet_rows: list[list[object]]) -> dict:
    records, errors = _normalize_rows(sheet_rows, {"amount"})
    return {"ok": True, "payments": records, "count": len(records), "errors": errors}


def accounting_load_orders(sheet_rows: list[list[object]]) -> dict:
    records, errors = _normalize_rows(sheet_rows, {"order_total"})
    return {"ok": True, "orders": records, "count": len(records), "errors": errors}


def accounting_load_invoices(sheet_rows: list[list[object]]) -> dict:
    records, errors = _normalize_rows(sheet_rows, {"invoice_total"})
    return {"ok": True, "invoices": records, "count": len(records), "errors": errors}


def accounting_load_ledger(sheet_rows: list[list[object]]) -> dict:
    records, errors = _normalize_rows(sheet_rows, {"amount"})
    return {"ok": True, "ledger_entries": records, "count": len(records), "errors": errors}


def accounting_build_recon_sheet_rows(reconciliation_result: dict, exception_summary: dict, frame_id: str = "") -> dict:
    recon_run_id = str(reconciliation_result.get("recon_run_id", "RECON-UNKNOWN"))
    summary = reconciliation_result.get("summary", {})
    recon_run_rows = [[recon_run_id, "", summary.get("matched_count", 0), summary.get("matched_count", 0), summary.get("exception_count", 0), summary.get("duplicate_count", 0), summary.get("amount_mismatch_count", 0), summary.get("already_posted_count", 0), summary.get("status", ""), frame_id]]
    recon_exception_rows = []
    for exc in reconciliation_result.get("exceptions", []) or []:
        recon_exception_rows.append([
            recon_run_id,
            exc.get("exception_id", ""),
            exc.get("exception_type", ""),
            exc.get("payment_ref", ""),
            exc.get("payment_id", ""),
            exc.get("order_ref", ""),
            exc.get("invoice_id", ""),
            exc.get("expected_amount", ""),
            exc.get("actual_amount", ""),
            exc.get("currency", ""),
            exc.get("severity", ""),
            exc.get("message", ""),
            frame_id,
        ])
    return {"ok": True, "recon_run_rows": recon_run_rows, "recon_exception_rows": recon_exception_rows, "recon_run_id": recon_run_id}
