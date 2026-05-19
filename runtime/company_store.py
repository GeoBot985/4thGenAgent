from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import json
import tempfile
import os


DEFAULT_RUNTIME_ROOT = "runtime_data"
BUSINESS_DIR = "business"


def business_path(table_name: str, runtime_root: str | Path = DEFAULT_RUNTIME_ROOT) -> Path:
    _validate_table_name(table_name)
    root = Path(runtime_root)
    base = (root / BUSINESS_DIR).resolve()
    path = (base / f"{table_name}.json").resolve()
    _ensure_within_base(path, base)
    return path


def read_json_table(table_name: str, runtime_root: str | Path = DEFAULT_RUNTIME_ROOT) -> list[dict[str, Any]]:
    path = business_path(table_name, runtime_root)
    if not path.is_file():
        rows: list[dict[str, Any]] = []
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            rows = []
        else:
            rows = [dict(item) for item in data if isinstance(item, dict)]
    try:
        from .business_data import _seed_payloads

        seeded = _seed_payloads().get(table_name, [])
        if isinstance(seeded, list) and seeded:
            rows = _merge_seed_rows(table_name, rows, [dict(item) for item in seeded if isinstance(item, dict)])
    except Exception:
        pass
    return _merge_procurement_seed_rows(table_name, rows)


def write_json_table(table_name: str, rows: list[dict[str, Any]], runtime_root: str | Path = DEFAULT_RUNTIME_ROOT) -> None:
    path = business_path(table_name, runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [dict(row) for row in rows]
    _atomic_write_json(path, payload)


def find_many(
    table_name: str,
    predicate: Callable[[dict[str, Any]], bool],
    runtime_root: str | Path = DEFAULT_RUNTIME_ROOT,
) -> list[dict[str, Any]]:
    return [dict(row) for row in read_json_table(table_name, runtime_root) if predicate(dict(row))]


def find_one(
    table_name: str,
    predicate: Callable[[dict[str, Any]], bool],
    runtime_root: str | Path = DEFAULT_RUNTIME_ROOT,
) -> dict[str, Any] | None:
    for row in read_json_table(table_name, runtime_root):
        candidate = dict(row)
        if predicate(candidate):
            return candidate
    return None


def append_record(
    table_name: str,
    record: dict[str, Any],
    runtime_root: str | Path = DEFAULT_RUNTIME_ROOT,
) -> None:
    rows = read_json_table(table_name, runtime_root)
    rows.append(dict(record))
    write_json_table(table_name, rows, runtime_root)


def _merge_procurement_seed_rows(table_name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if table_name == "inventory":
        required = [
            {"sku": "SKU-1001", "name": "Wireless Mouse", "available_stock": 4, "reorder_threshold": 10, "target_stock_level": 40, "preferred_supplier_id": "SUP-1001", "unit_cost": 125.5, "currency": "ZAR"},
            {"sku": "SKU-1002", "name": "Keyboard", "available_stock": 9, "reorder_threshold": 10, "target_stock_level": 30, "preferred_supplier_id": "SUP-1001", "unit_cost": 210.0, "currency": "ZAR"},
        ]
        existing = {str(row.get("sku", "")) for row in rows}
        rows.extend(item for item in required if item["sku"] not in existing)
    elif table_name == "suppliers":
        if not any(str(row.get("supplier_id", "")) == "SUP-1001" for row in rows):
            rows.append({"supplier_id": "SUP-1001", "name": "Cape Tech Supplies", "status": "active", "email": "orders@capetech.example", "supported_skus": ["SKU-1001", "SKU-1002"], "lead_time_days": 5})
    elif table_name == "purchase_orders":
        if not any(str(row.get("po_id", "")) == "PO-9001" for row in rows):
            rows.append({"po_id": "PO-9001", "supplier_id": "SUP-1001", "status": "open", "lines": [{"sku": "SKU-1001", "quantity": 20, "unit_cost": 125.5, "line_total": 2510.0}], "currency": "ZAR", "total": 2510.0})
    return rows


def _merge_seed_rows(table_name: str, rows: list[dict[str, Any]], seeded: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not seeded:
        return rows

    key_fields = {
        "customers": ("customer_id",),
        "customer_messages": ("message_id",),
        "orders": ("order_ref",),
        "order_items": ("order_ref", "sku"),
        "shipments": ("order_ref", "shipment_id"),
        "payments": ("payment_id",),
        "inventory": ("sku",),
        "suppliers": ("supplier_id",),
        "purchase_orders": ("po_ref", "po_id"),
        "supplier_invoices": ("invoice_ref", "invoice_id"),
        "purchase_order_lines": ("po_ref", "line_ref"),
        "goods_receipts": ("receipt_ref", "receipt_id"),
        "goods_receipt_lines": ("receipt_ref", "line_ref"),
        "supplier_invoice_lines": ("invoice_ref", "line_ref"),
        "ledger_entries": ("ledger_entry_id",),
        "supplier_invoice_match_runs": ("run_id", "invoice_ref", "supplier_invoice_number"),
        "supplier_invoice_match_exceptions": ("exception_id", "invoice_ref", "code", "line_ref"),
    }
    keys = key_fields.get(table_name, ())
    if not keys:
        existing = {json.dumps(row, sort_keys=True, default=str) for row in rows}
        for item in seeded:
            marker = json.dumps(item, sort_keys=True, default=str)
            if marker not in existing:
                rows.append(item)
                existing.add(marker)
        return rows

    def _marker(record: dict[str, Any]) -> str:
        return "::".join(str(record.get(field, "")) for field in keys)

    existing = {_marker(row) for row in rows}
    for item in seeded:
        marker = _marker(item)
        if marker not in existing:
            rows.append(item)
            existing.add(marker)
    return rows


def _validate_table_name(table_name: str) -> None:
    if not isinstance(table_name, str) or not table_name.strip():
        raise ValueError("table_name must be a non-empty string.")
    if table_name != table_name.strip():
        raise ValueError("table_name must not contain surrounding whitespace.")
    if any(sep in table_name for sep in ("/", "\\", "..")):
        raise ValueError("table_name must be a simple name.")
    if Path(table_name).is_absolute():
        raise ValueError("table_name must be a simple name.")


def _ensure_within_base(path: Path, base: Path) -> None:
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise ValueError("Path resolves outside runtime_data/business.") from exc


def _atomic_write_json(path: Path, data: object) -> None:
    tmp_dir = path.parent
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(tmp_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
