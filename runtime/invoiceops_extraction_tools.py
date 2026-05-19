from __future__ import annotations

import re
from typing import Any

from .invoiceops_constants import NUMERIC_TOLERANCE
from .tool_result_contract import build_tool_evidence

_EXTRACT_TOOL = "invoiceops/extract_invoice_fields"
_VALIDATE_TOOL = "invoiceops/validate_invoice_fields"
_EXTRACT_TYPE = "invoiceops_invoice"
_VALIDATE_TYPE = "invoiceops_invoice_validation"
_EXTRACTOR_VERSION = "simple_rule_based_v1"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UNKNOWN_SUPPLIER = "UNKNOWN_SUPPLIER"

_MONTHS: dict[str, str] = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "oct": "10", "nov": "11", "dec": "12",
}

# (regex_pattern, capture_group_index)
_LABEL_RULES: dict[str, list[str]] = {
    "supplier_name": [
        r"Supplier(?:\s+Name)?:\s*(.+)",
        r"From:\s*(.+)",
    ],
    "invoice_number": [
        r"Invoice\s+(?:Number|No\.?|#):\s*(.+)",
        r"Inv(?:oice)?\s*#\s*:\s*(.+)",
    ],
    "invoice_date": [
        r"Invoice\s+Date:\s*(.+)",
        r"Date\s+of\s+Invoice:\s*(.+)",
    ],
    "po_number": [
        r"P\.?O\.?\s+(?:Number|No\.?|#):\s*(.+)",
        r"Purchase\s+Order(?:\s+No\.?)?\s*:\s*(.+)",
    ],
    "currency": [
        r"Currency:\s*(\S+)",
    ],
}

_MONEY_RULES: dict[str, list[str]] = {
    "subtotal": [
        r"Subtotal\s*:\s*R?\s*([\d,]+\.?\d*)",
        r"Sub\s+Total\s*:\s*R?\s*([\d,]+\.?\d*)",
        r"Sub-Total\s*:\s*R?\s*([\d,]+\.?\d*)",
    ],
    "tax_total": [
        r"VAT\s*(?:\([^)]*\))?\s*:\s*R?\s*([\d,]+\.?\d*)",
        r"Tax\s*(?:\([^)]*\))?\s*:\s*R?\s*([\d,]+\.?\d*)",
        r"GST\s*(?:\([^)]*\))?\s*:\s*R?\s*([\d,]+\.?\d*)",
    ],
    "invoice_total": [
        r"Invoice\s+Total\s*:\s*R?\s*([\d,]+\.?\d*)",
        r"Amount\s+Due\s*:\s*R?\s*([\d,]+\.?\d*)",
        r"Total\s+Amount\s*:\s*R?\s*([\d,]+\.?\d*)",
        r"(?<!\w)Total\s*:\s*R?\s*([\d,]+\.?\d*)",
    ],
}

# Matches table rows like: 1  SKU-001  Description text  10  25.00  250.00
_LINE_ITEM_RE = re.compile(
    r"^\s*(\d+)\s+([\w-]+)\s+(.+?)\s+([\d.]+)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s*$",
    re.MULTILINE,
)
# Matches "Line 1  SKU-001  Description  Qty: 5  Unit: 25.00  Total: 125.00"
_LINE_ITEM_LABELED_RE = re.compile(
    r"Line\s+(\d+)\s+([\w-]+)\s+(.+?)\s+Qty:\s*([\d.]+)\s+Unit:\s*([\d,]+\.?\d*)\s+Total:\s*([\d,]+\.?\d*)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

def invoiceops_extract_invoice_fields(raw_text: str, source_ref: str = "") -> dict:
    if not raw_text or not raw_text.strip():
        return _error_result("INVOICE_TEXT_EMPTY", _EXTRACT_TYPE)

    warnings: list[str] = []
    field_evidence: list[dict] = []

    supplier_name, sup_raw = _extract_label(raw_text, "supplier_name")
    invoice_number, inv_num_raw = _extract_label(raw_text, "invoice_number")
    invoice_date_raw, date_raw = _extract_label(raw_text, "invoice_date")
    po_number, po_raw = _extract_label(raw_text, "po_number")
    currency, cur_raw = _extract_label(raw_text, "currency")
    subtotal, sub_raw = _extract_money(raw_text, "subtotal")
    tax_total, tax_raw = _extract_money(raw_text, "tax_total")
    invoice_total, total_raw = _extract_money(raw_text, "invoice_total")
    line_items = _extract_line_items(raw_text)

    # Defaults and warnings
    if not supplier_name:
        warnings.append("supplier_name not found in text; defaulted to empty string")
    if not invoice_number:
        warnings.append("invoice_number not found in text")
    if not po_number:
        warnings.append("po_number not found in text")
    if not currency:
        currency = "ZAR"
        warnings.append("currency not found; defaulted to ZAR")
    if not line_items:
        warnings.append("no line items found in text")

    invoice_date = _normalize_date(invoice_date_raw) if invoice_date_raw else ""
    if invoice_date_raw and not invoice_date:
        warnings.append(f"invoice_date {invoice_date_raw!r} could not be parsed to YYYY-MM-DD")

    invoice_id = f"INV-{invoice_number}" if invoice_number else "INV-UNKNOWN"
    supplier_id = _UNKNOWN_SUPPLIER

    invoice: dict[str, Any] = {
        "invoice_id": invoice_id,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name or "",
        "invoice_number": invoice_number or "",
        "invoice_date": invoice_date,
        "po_number": po_number or "",
        "currency": currency,
        "subtotal": subtotal if subtotal is not None else 0.0,
        "tax_total": tax_total if tax_total is not None else 0.0,
        "invoice_total": invoice_total if invoice_total is not None else 0.0,
        "line_items": line_items,
    }

    # Build per-field evidence
    _add_evidence(field_evidence, "supplier_name", sup_raw, source_ref, 0.85 if sup_raw else 0.0)
    _add_evidence(field_evidence, "invoice_number", inv_num_raw, source_ref, 0.95 if inv_num_raw else 0.0)
    _add_evidence(field_evidence, "invoice_date", date_raw, source_ref, 0.95 if date_raw else 0.0)
    _add_evidence(field_evidence, "po_number", po_raw, source_ref, 0.95 if po_raw else 0.0)
    _add_evidence(field_evidence, "currency", cur_raw, source_ref, 0.95 if cur_raw else 0.5)
    _add_evidence(field_evidence, "subtotal", sub_raw, source_ref, 0.90 if sub_raw else 0.0)
    _add_evidence(field_evidence, "tax_total", tax_raw, source_ref, 0.90 if tax_raw else 0.0)
    _add_evidence(field_evidence, "invoice_total", total_raw, source_ref, 0.90 if total_raw else 0.0)

    tool_evidence = build_tool_evidence(
        tool=_EXTRACT_TOOL,
        mode="dry_run",
        source="builtin",
        operation="extract",
        input_refs=[f"source_ref={source_ref}"] if source_ref else [],
        output_ref=_EXTRACT_TYPE,
        extra={"extractor": _EXTRACTOR_VERSION},
    )

    return {
        "ok": True,
        "type": _EXTRACT_TYPE,
        "data": {
            "invoice": invoice,
            "extraction_warnings": warnings,
            "evidence": field_evidence,
        },
        "evidence": tool_evidence,
        "error": "",
        "metadata": {"extractor": _EXTRACTOR_VERSION},
    }


def invoiceops_validate_invoice_fields(invoice: dict) -> dict:
    if not isinstance(invoice, dict):
        return _error_result("INVALID_INVOICE_INPUT", _VALIDATE_TYPE)

    errors: list[str] = []
    warnings: list[str] = []

    # Required string fields
    for field in ("supplier_name", "invoice_number", "invoice_date", "po_number", "currency"):
        val = invoice.get(field)
        if not val or not str(val).strip():
            errors.append(f"missing required field: {field}")

    # invoice_total required and numeric
    total = invoice.get("invoice_total")
    if total is None or not _is_num(total):
        errors.append("invoice_total must be a number")

    # line_items required and non-empty
    line_items = invoice.get("line_items")
    if not isinstance(line_items, list):
        errors.append("line_items must be a list")
    elif not line_items:
        errors.append("line_items must not be empty")

    # Numeric fields
    for field in ("subtotal", "tax_total"):
        val = invoice.get(field)
        if val is not None and not _is_num(val):
            errors.append(f"{field} must be a number")

    # Date format
    date_val = invoice.get("invoice_date", "")
    if date_val and not _DATE_RE.match(str(date_val)):
        errors.append("invoice_date must be in YYYY-MM-DD format")

    # Line item checks (only if line_items is a valid list)
    if isinstance(line_items, list) and line_items:
        line_total_sum = 0.0
        for i, item in enumerate(line_items):
            if not isinstance(item, dict):
                errors.append(f"line_items[{i}] must be a dict")
                continue
            desc = str(item.get("description", "")).strip()
            sku = str(item.get("sku", "")).strip()
            if not desc and not sku:
                errors.append(f"line_items[{i}] must have description or sku")
            qty = item.get("quantity")
            if _is_num(qty) and float(qty) <= 0:
                errors.append(f"line_items[{i}].quantity must be > 0")
            elif not _is_num(qty):
                errors.append(f"line_items[{i}].quantity must be a number")
            lt = item.get("line_total")
            if _is_num(lt) and float(lt) <= 0:
                errors.append(f"line_items[{i}].line_total must be > 0")
            elif not _is_num(lt):
                errors.append(f"line_items[{i}].line_total must be a number")
            if _is_num(lt):
                line_total_sum += float(lt)

        # Warn if line totals don't sum to subtotal
        subtotal = invoice.get("subtotal")
        if _is_num(subtotal) and float(subtotal) > 0:
            if abs(line_total_sum - float(subtotal)) > NUMERIC_TOLERANCE:
                warnings.append(
                    f"sum of line_totals ({line_total_sum:.4f}) does not equal subtotal ({subtotal})"
                )

    # Warn: totals mismatch
    subtotal = invoice.get("subtotal")
    tax_t = invoice.get("tax_total")
    inv_total = invoice.get("invoice_total")
    if _is_num(subtotal) and _is_num(tax_t) and _is_num(inv_total):
        expected = float(subtotal) + float(tax_t)
        if abs(float(inv_total) - expected) > NUMERIC_TOLERANCE:
            warnings.append(
                f"subtotal + tax_total ({expected:.4f}) does not equal invoice_total ({inv_total})"
            )

    # Warn: unknown supplier
    if invoice.get("supplier_id") == _UNKNOWN_SUPPLIER:
        warnings.append("supplier_id is UNKNOWN_SUPPLIER; supplier lookup not performed")

    # Warn: currency defaulted
    if invoice.get("currency") == "ZAR" and not invoice.get("_currency_explicit"):
        pass  # ZAR is a valid default; only warn if we know it was forced

    valid = not errors

    tool_evidence = build_tool_evidence(
        tool=_VALIDATE_TOOL,
        mode="dry_run",
        source="builtin",
        operation="validation",
        input_refs=[],
        output_ref=_VALIDATE_TYPE,
    )

    return {
        "ok": True,
        "type": _VALIDATE_TYPE,
        "data": {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "invoice": invoice,
        },
        "evidence": tool_evidence,
        "error": "",
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _extract_label(text: str, field: str) -> tuple[str, str]:
    for pattern in _LABEL_RULES.get(field, []):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            if raw:
                return raw, raw
    return "", ""


def _extract_money(text: str, field: str) -> tuple[float | None, str]:
    for pattern in _MONEY_RULES.get(field, []):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            val = _parse_money(raw)
            if val is not None:
                return val, raw
    return None, ""


def _extract_line_items(text: str) -> list[dict]:
    items: list[dict] = []
    # Try labeled format first ("Line 1  SKU  Desc  Qty: N  Unit: N  Total: N")
    for m in _LINE_ITEM_LABELED_RE.finditer(text):
        items.append(_make_line_item(m, labeled=True))
    if items:
        return items
    # Fall back to columnar table format
    for m in _LINE_ITEM_RE.finditer(text):
        items.append(_make_line_item(m, labeled=False))
    return items


def _make_line_item(m: re.Match, *, labeled: bool) -> dict:
    return {
        "line_no": int(m.group(1)),
        "description": m.group(3).strip(),
        "sku": m.group(2).strip(),
        "quantity": _parse_money(m.group(4)) or 0.0,
        "unit_price": _parse_money(m.group(5)) or 0.0,
        "tax_amount": 0.0,
        "line_total": _parse_money(m.group(6)) or 0.0,
    }


def _normalize_date(raw: str) -> str:
    raw = raw.strip()
    if _DATE_RE.match(raw):
        return raw
    # DD/MM/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    # D MMMM YYYY
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$", raw)
    if m:
        month = _MONTHS.get(m.group(2).lower())
        if month:
            return f"{m.group(3)}-{month}-{m.group(1).zfill(2)}"
    # MMMM D, YYYY
    m = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$", raw)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            return f"{m.group(3)}-{month}-{m.group(2).zfill(2)}"
    return ""


def _parse_money(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _add_evidence(
    field_evidence: list[dict],
    field: str,
    raw_value: str,
    source_ref: str,
    confidence: float,
) -> None:
    field_evidence.append({
        "evidence_id": f"EVD-{field}",
        "source_type": "text",
        "source_ref": source_ref or "",
        "field_path": f"invoice.{field}",
        "raw_value": raw_value,
        "confidence": confidence,
    })


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _error_result(error_code: str, result_type: str) -> dict:
    return {
        "ok": False,
        "type": result_type,
        "data": {},
        "evidence": {},
        "error": error_code,
        "metadata": {},
    }
