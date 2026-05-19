from __future__ import annotations

import re
from typing import Any

from .invoiceops_constants import (
    CHECK_STATUSES,
    EVIDENCE_SOURCE_TYPES,
    EXCEPTION_SEVERITIES,
    EXCEPTION_TYPES,
    LEDGER_STATUSES,
    MATCH_STATUSES,
    NUMERIC_TOLERANCE,
    PO_STATUSES,
    PREPARED_WRITE_OPERATIONS,
    PREPARED_WRITE_TARGETS,
    RECEIPT_STATUSES,
    ROLLBACK_TYPES,
    SUPPLIER_STATUSES,
    WRITE_LIKE_OPERATIONS,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_missing(data: dict, fields: list[str], errors: list[str]) -> None:
    missing = [f for f in fields if f not in data]
    if missing:
        errors.append(f"Missing required fields: {missing}.")


def _str(data: dict, field: str, errors: list[str]) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        errors.append(f"'{field}' must be a string, got {type(value).__name__}.")
        return ""
    if not value.strip():
        errors.append(f"'{field}' must not be empty.")
    return value


def _num(data: dict, field: str, errors: list[str]) -> float | None:
    value = data.get(field)
    if not _is_numeric(value):
        errors.append(f"'{field}' must be a number, got {type(value).__name__}.")
        return None
    return float(value)


def _lst(data: dict, field: str, errors: list[str]) -> list:
    value = data.get(field)
    if not isinstance(value, list):
        errors.append(f"'{field}' must be a list, got {type(value).__name__}.")
        return []
    return value


def _bol(data: dict, field: str, errors: list[str]) -> bool | None:
    value = data.get(field)
    if not isinstance(value, bool):
        errors.append(f"'{field}' must be a bool, got {type(value).__name__}.")
        return None
    return value


def _dct(data: dict, field: str, errors: list[str]) -> dict:
    value = data.get(field)
    if not isinstance(value, dict):
        errors.append(f"'{field}' must be a dict, got {type(value).__name__}.")
        return {}
    return value


def _enum(data: dict, field: str, valid: frozenset[str], errors: list[str]) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        errors.append(f"'{field}' must be a string, got {type(value).__name__}.")
        return ""
    if value not in valid:
        errors.append(f"'{field}' must be one of {sorted(valid)}, got {value!r}.")
    return value


def _date(data: dict, field: str, errors: list[str]) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        errors.append(f"'{field}' must be a string in YYYY-MM-DD format, got {type(value).__name__}.")
        return ""
    if not _DATE_RE.match(value):
        errors.append(f"'{field}' must be in YYYY-MM-DD format, got {value!r}.")
    return value


def _int_field(data: dict, field: str, errors: list[str], prefix: str = "") -> int | None:
    value = data.get(field)
    label = f"{prefix}.{field}" if prefix else field
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"'{label}' must be an int, got {type(value).__name__}.")
        return None
    return value


def _vresult(errors: list[str], warnings: list[str]) -> dict:
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def _guard_dict(data: Any) -> tuple[dict | None, dict | None]:
    if not isinstance(data, dict):
        return None, {"ok": False, "errors": ["Input must be a dict."], "warnings": []}
    return data, None


# ---------------------------------------------------------------------------
# Invoice line item
# ---------------------------------------------------------------------------

def _validate_invoice_line(item: dict, idx: int, errors: list[str], warnings: list[str]) -> None:
    px = f"line_items[{idx}]"
    _int_field(item, "line_no", errors, px)
    for f in ("description", "sku"):
        if not isinstance(item.get(f), str):
            errors.append(f"'{px}.{f}' must be a string, got {type(item.get(f)).__name__}.")
    qty = item.get("quantity")
    unit_price = item.get("unit_price")
    tax_amount = item.get("tax_amount")
    line_total = item.get("line_total")
    for fname, fval in (("quantity", qty), ("unit_price", unit_price), ("tax_amount", tax_amount), ("line_total", line_total)):
        if not _is_numeric(fval):
            errors.append(f"'{px}.{fname}' must be a number, got {type(fval).__name__}.")
    if all(_is_numeric(v) for v in (qty, unit_price, tax_amount, line_total)):
        excl = float(qty) * float(unit_price)
        incl = excl + float(tax_amount)
        actual = float(line_total)
        if abs(actual - excl) > NUMERIC_TOLERANCE and abs(actual - incl) > NUMERIC_TOLERANCE:
            warnings.append(
                f"{px}.line_total ({actual}) does not match "
                f"quantity*unit_price ({excl:.4f}) or quantity*unit_price+tax_amount ({incl:.4f})."
            )


# ---------------------------------------------------------------------------
# PO line item
# ---------------------------------------------------------------------------

def _validate_po_line(item: dict, idx: int, errors: list[str]) -> None:
    px = f"line_items[{idx}]"
    _int_field(item, "line_no", errors, px)
    for f in ("sku", "description"):
        if not isinstance(item.get(f), str):
            errors.append(f"'{px}.{f}' must be a string, got {type(item.get(f)).__name__}.")
    for f in ("ordered_quantity", "unit_price", "line_total"):
        if not _is_numeric(item.get(f)):
            errors.append(f"'{px}.{f}' must be a number, got {type(item.get(f)).__name__}.")


# ---------------------------------------------------------------------------
# Receipt line item
# ---------------------------------------------------------------------------

def _validate_receipt_line(item: dict, idx: int, errors: list[str]) -> None:
    px = f"line_items[{idx}]"
    _int_field(item, "line_no", errors, px)
    for f in ("sku", "description"):
        if not isinstance(item.get(f), str):
            errors.append(f"'{px}.{f}' must be a string, got {type(item.get(f)).__name__}.")
    if not _is_numeric(item.get("received_quantity")):
        errors.append(f"'{px}.received_quantity' must be a number, got {type(item.get('received_quantity')).__name__}.")


# ---------------------------------------------------------------------------
# Check item (used inside match_result)
# ---------------------------------------------------------------------------

def _validate_check_item(item: dict, idx: int, errors: list[str]) -> None:
    px = f"checks[{idx}]"
    if not isinstance(item, dict):
        errors.append(f"{px} must be a dict.")
        return
    if not isinstance(item.get("check_id"), str) or not item.get("check_id", "").strip():
        errors.append(f"'{px}.check_id' must be a non-empty string.")
    status = item.get("status")
    if status not in CHECK_STATUSES:
        errors.append(f"'{px}.status' must be one of {sorted(CHECK_STATUSES)}, got {status!r}.")
    for f in ("expected", "actual", "message"):
        if not isinstance(item.get(f), str):
            errors.append(f"'{px}.{f}' must be a string, got {type(item.get(f)).__name__}.")


# ---------------------------------------------------------------------------
# Rollback step (used inside rollback_plan)
# ---------------------------------------------------------------------------

def _validate_rollback_step(item: dict, idx: int, errors: list[str]) -> None:
    px = f"steps[{idx}]"
    if not isinstance(item, dict):
        errors.append(f"{px} must be a dict.")
        return
    _int_field(item, "step_no", errors, px)
    for f in ("action", "target"):
        if not isinstance(item.get(f), str):
            errors.append(f"'{px}.{f}' must be a string, got {type(item.get(f)).__name__}.")
    if not isinstance(item.get("data"), dict):
        errors.append(f"'{px}.data' must be a dict, got {type(item.get('data')).__name__}.")


# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------

def validate_invoice_shape(data: dict) -> dict:
    d, early = _guard_dict(data)
    if early:
        return early
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        "invoice_id", "supplier_id", "supplier_name", "invoice_number",
        "invoice_date", "po_number", "currency",
        "subtotal", "tax_total", "invoice_total", "line_items",
    ]
    _check_missing(d, required, errors)

    for f in ("invoice_id", "supplier_id", "supplier_name", "invoice_number", "po_number", "currency"):
        if f in d:
            _str(d, f, errors)
    if "invoice_date" in d:
        _date(d, "invoice_date", errors)

    subtotal = _num(d, "subtotal", errors) if "subtotal" in d else None
    tax_total = _num(d, "tax_total", errors) if "tax_total" in d else None
    invoice_total = _num(d, "invoice_total", errors) if "invoice_total" in d else None

    if subtotal is not None and tax_total is not None and invoice_total is not None:
        expected = subtotal + tax_total
        if abs(invoice_total - expected) > NUMERIC_TOLERANCE:
            warnings.append(
                f"invoice_total ({invoice_total}) does not equal subtotal + tax_total ({expected:.4f})."
            )

    if "line_items" in d:
        items = _lst(d, "line_items", errors)
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"line_items[{i}] must be a dict.")
            else:
                _validate_invoice_line(item, i, errors, warnings)

    return _vresult(errors, warnings)


def validate_purchase_order_shape(data: dict) -> dict:
    d, early = _guard_dict(data)
    if early:
        return early
    errors: list[str] = []
    warnings: list[str] = []

    required = ["po_number", "supplier_id", "supplier_name", "status", "currency", "po_total", "line_items"]
    _check_missing(d, required, errors)

    for f in ("po_number", "supplier_id", "supplier_name", "currency"):
        if f in d:
            _str(d, f, errors)
    if "status" in d:
        _enum(d, "status", PO_STATUSES, errors)
    if "po_total" in d:
        _num(d, "po_total", errors)
    if "line_items" in d:
        items = _lst(d, "line_items", errors)
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"line_items[{i}] must be a dict.")
            else:
                _validate_po_line(item, i, errors)

    return _vresult(errors, warnings)


def validate_goods_receipt_shape(data: dict) -> dict:
    d, early = _guard_dict(data)
    if early:
        return early
    errors: list[str] = []
    warnings: list[str] = []

    required = ["receipt_id", "po_number", "supplier_id", "receipt_date", "status", "line_items"]
    _check_missing(d, required, errors)

    for f in ("receipt_id", "po_number", "supplier_id"):
        if f in d:
            _str(d, f, errors)
    if "receipt_date" in d:
        _date(d, "receipt_date", errors)
    if "status" in d:
        _enum(d, "status", RECEIPT_STATUSES, errors)
    if "line_items" in d:
        items = _lst(d, "line_items", errors)
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"line_items[{i}] must be a dict.")
            else:
                _validate_receipt_line(item, i, errors)

    return _vresult(errors, warnings)


def validate_supplier_shape(data: dict) -> dict:
    d, early = _guard_dict(data)
    if early:
        return early
    errors: list[str] = []
    warnings: list[str] = []

    required = ["supplier_id", "supplier_name", "status", "vat_number", "payment_terms", "default_currency"]
    _check_missing(d, required, errors)

    for f in ("supplier_id", "supplier_name", "vat_number", "payment_terms", "default_currency"):
        if f in d:
            _str(d, f, errors)
    if "status" in d:
        _enum(d, "status", SUPPLIER_STATUSES, errors)

    return _vresult(errors, warnings)


def validate_match_result_shape(data: dict) -> dict:
    d, early = _guard_dict(data)
    if early:
        return early
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        "match_id", "invoice_id", "invoice_number", "supplier_id", "po_number",
        "match_status", "checks", "exceptions", "ledger_posting_allowed", "prepared_write_allowed",
    ]
    _check_missing(d, required, errors)

    for f in ("match_id", "invoice_id", "invoice_number", "supplier_id", "po_number"):
        if f in d:
            _str(d, f, errors)
    if "match_status" in d:
        _enum(d, "match_status", MATCH_STATUSES, errors)
    for f in ("ledger_posting_allowed", "prepared_write_allowed"):
        if f in d:
            _bol(d, f, errors)
    if "checks" in d:
        checks = _lst(d, "checks", errors)
        for i, item in enumerate(checks):
            _validate_check_item(item, i, errors)
    if "exceptions" in d:
        _lst(d, "exceptions", errors)

    return _vresult(errors, warnings)


def validate_exception_shape(data: dict) -> dict:
    d, early = _guard_dict(data)
    if early:
        return early
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        "exception_id", "exception_type", "severity",
        "invoice_id", "po_number", "message", "recommended_action", "blocking",
    ]
    _check_missing(d, required, errors)

    for f in ("exception_id", "invoice_id", "po_number", "message", "recommended_action"):
        if f in d:
            _str(d, f, errors)
    if "exception_type" in d:
        _enum(d, "exception_type", EXCEPTION_TYPES, errors)
    if "severity" in d:
        _enum(d, "severity", EXCEPTION_SEVERITIES, errors)
    if "blocking" in d:
        _bol(d, "blocking", errors)

    return _vresult(errors, warnings)


def validate_ledger_row_shape(data: dict) -> dict:
    d, early = _guard_dict(data)
    if early:
        return early
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        "ledger_entry_id", "source_type", "source_ref", "supplier_id",
        "invoice_number", "po_number", "debit_account", "credit_account",
        "amount", "currency", "status",
    ]
    _check_missing(d, required, errors)

    for f in ("ledger_entry_id", "source_ref", "supplier_id", "invoice_number",
              "po_number", "debit_account", "credit_account", "currency"):
        if f in d:
            _str(d, f, errors)
    if "source_type" in d:
        value = d.get("source_type")
        if not isinstance(value, str):
            errors.append(f"'source_type' must be a string, got {type(value).__name__}.")
        elif value != "supplier_invoice":
            errors.append(f"'source_type' must be 'supplier_invoice', got {value!r}.")
    if "amount" in d:
        _num(d, "amount", errors)
    if "status" in d:
        _enum(d, "status", LEDGER_STATUSES, errors)

    return _vresult(errors, warnings)


def validate_prepared_write_shape(data: dict) -> dict:
    d, early = _guard_dict(data)
    if early:
        return early
    errors: list[str] = []
    warnings: list[str] = []

    required = ["prepared_write_id", "target", "operation", "rows", "dry_run", "requires_approval", "rollback_plan"]
    _check_missing(d, required, errors)

    if "prepared_write_id" in d:
        _str(d, "prepared_write_id", errors)
    if "target" in d:
        _enum(d, "target", PREPARED_WRITE_TARGETS, errors)
    if "operation" in d:
        _enum(d, "operation", PREPARED_WRITE_OPERATIONS, errors)
    if "rows" in d:
        _lst(d, "rows", errors)

    dry_run = _bol(d, "dry_run", errors) if "dry_run" in d else None
    if dry_run is False:
        warnings.append("dry_run is False; live writes require explicit confirmation.")

    requires_approval = _bol(d, "requires_approval", errors) if "requires_approval" in d else None
    if requires_approval is False:
        errors.append("requires_approval must be True for all prepared writes.")

    if "rollback_plan" in d:
        rollback_plan = d.get("rollback_plan")
        if not isinstance(rollback_plan, dict):
            errors.append(f"'rollback_plan' must be a dict, got {type(rollback_plan).__name__}.")
        else:
            op = d.get("operation", "")
            if op in WRITE_LIKE_OPERATIONS and not rollback_plan:
                errors.append(f"'rollback_plan' must be non-empty for write-like operation '{op}'.")

    return _vresult(errors, warnings)


def validate_rollback_plan_shape(data: dict) -> dict:
    d, early = _guard_dict(data)
    if early:
        return early
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        "rollback_id", "rollback_type", "target",
        "source_prepared_write_id", "safe_to_auto_prepare", "steps", "reason",
    ]
    _check_missing(d, required, errors)

    for f in ("rollback_id", "target", "source_prepared_write_id", "reason"):
        if f in d:
            _str(d, f, errors)
    if "rollback_type" in d:
        _enum(d, "rollback_type", ROLLBACK_TYPES, errors)
    if "safe_to_auto_prepare" in d:
        _bol(d, "safe_to_auto_prepare", errors)
    if "steps" in d:
        steps = _lst(d, "steps", errors)
        for i, item in enumerate(steps):
            _validate_rollback_step(item, i, errors)

    return _vresult(errors, warnings)


def validate_report_shape(data: dict) -> dict:
    d, early = _guard_dict(data)
    if early:
        return early
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        "report_id", "invoice_id", "match_status", "summary",
        "checks", "exceptions", "prepared_writes", "rollback_plans", "evidence",
    ]
    _check_missing(d, required, errors)

    for f in ("report_id", "invoice_id", "summary"):
        if f in d:
            _str(d, f, errors)
    if "match_status" in d:
        _enum(d, "match_status", MATCH_STATUSES, errors)
    for f in ("checks", "exceptions", "prepared_writes", "rollback_plans", "evidence"):
        if f in d:
            _lst(d, f, errors)

    return _vresult(errors, warnings)


def validate_evidence_shape(data: dict) -> dict:
    d, early = _guard_dict(data)
    if early:
        return early
    errors: list[str] = []
    warnings: list[str] = []

    required = ["evidence_id", "source_type", "source_ref", "field_path", "raw_value", "confidence"]
    _check_missing(d, required, errors)

    for f in ("evidence_id", "source_ref", "field_path", "raw_value"):
        if f in d:
            _str(d, f, errors)
    if "source_type" in d:
        _enum(d, "source_type", EVIDENCE_SOURCE_TYPES, errors)
    if "confidence" in d:
        conf = d.get("confidence")
        if not _is_numeric(conf):
            errors.append(f"'confidence' must be a number, got {type(conf).__name__}.")
        elif not (0.0 <= float(conf) <= 1.0):
            errors.append(f"'confidence' must be between 0.0 and 1.0, got {conf}.")

    return _vresult(errors, warnings)
