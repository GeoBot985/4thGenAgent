from __future__ import annotations

import os

from runtime.invoiceops_extraction_tools import (
    invoiceops_extract_invoice_fields,
    invoiceops_validate_invoice_fields,
)

# ---------------------------------------------------------------------------
# Inline fixtures
# ---------------------------------------------------------------------------

_COMPLETE_TEXT = open(
    "tests/fixtures/invoiceops/extraction/complete_invoice.txt", encoding="utf-8"
).read()

_MISSING_PO_TEXT = open(
    "tests/fixtures/invoiceops/extraction/missing_po.txt", encoding="utf-8"
).read()

_BAD_DATE_TEXT = open(
    "tests/fixtures/invoiceops/extraction/bad_date.txt", encoding="utf-8"
).read()

_MINIMAL_TEXT = """
Supplier: Test Supplier Ltd
Invoice Number: TEST-001
Invoice Date: 2024-06-01
PO Number: PO-TEST-001
Currency: ZAR

1  SKU-A  Test Widget  2  50.00  100.00

Subtotal:      100.00
VAT (15%):      15.00
Invoice Total: 115.00
"""

_NO_LINE_ITEMS_TEXT = """
Supplier: Acme Ltd
Invoice Number: INV-999
Invoice Date: 2024-06-01
PO Number: PO-999
Currency: ZAR

Subtotal:      500.00
VAT (15%):      75.00
Invoice Total: 575.00
"""

_MISMATCH_TOTALS_TEXT = """
Supplier: Acme Ltd
Invoice Number: INV-888
Invoice Date: 2024-06-01
PO Number: PO-888
Currency: ZAR

1  SKU-A  Widget  2  50.00  100.00

Subtotal:      100.00
VAT (15%):      15.00
Invoice Total: 999.00
"""

_MINIMAL_VALID_INVOICE = {
    "invoice_id": "INV-TEST-001",
    "supplier_id": "SUP-001",
    "supplier_name": "Acme Ltd",
    "invoice_number": "TEST-001",
    "invoice_date": "2024-06-01",
    "po_number": "PO-001",
    "currency": "ZAR",
    "subtotal": 100.0,
    "tax_total": 15.0,
    "invoice_total": 115.0,
    "line_items": [
        {
            "line_no": 1,
            "description": "Widget A",
            "sku": "SKU-001",
            "quantity": 2.0,
            "unit_price": 50.0,
            "tax_amount": 0.0,
            "line_total": 100.0,
        }
    ],
}


def _copy(base: dict, **overrides) -> dict:
    d = dict(base)
    d.update(overrides)
    return d


# ---------------------------------------------------------------------------
# Extraction — happy path
# ---------------------------------------------------------------------------

def test_extract_complete_invoice_ok() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["ok"] is True
    assert r["error"] == ""


def test_extract_result_type() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["type"] == "invoiceops_invoice"


def test_extract_extractor_metadata() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["metadata"]["extractor"] == "simple_rule_based_v1"


def test_extract_supplier_name() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert "Acme" in r["data"]["invoice"]["supplier_name"]


def test_extract_invoice_number() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["data"]["invoice"]["invoice_number"] == "INV-2024-001"


def test_extract_invoice_date() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["data"]["invoice"]["invoice_date"] == "2024-01-15"


def test_extract_po_number() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["data"]["invoice"]["po_number"] == "PO-2024-042"


def test_extract_currency() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["data"]["invoice"]["currency"] == "ZAR"


def test_extract_subtotal() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["data"]["invoice"]["subtotal"] == 3000.0


def test_extract_tax_total() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["data"]["invoice"]["tax_total"] == 450.0


def test_extract_invoice_total() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["data"]["invoice"]["invoice_total"] == 3450.0


def test_extract_line_items_count() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert len(r["data"]["invoice"]["line_items"]) == 3


def test_extract_line_item_fields() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    item = r["data"]["invoice"]["line_items"][0]
    assert item["line_no"] == 1
    assert item["sku"] == "SKU-WIDGET-A"
    assert item["quantity"] == 10.0
    assert item["unit_price"] == 150.0
    assert item["line_total"] == 1500.0


def test_extract_line_item_description() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert "Widget Type A" in r["data"]["invoice"]["line_items"][0]["description"]


def test_extract_invoice_id_derived() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["data"]["invoice"]["invoice_id"] == "INV-INV-2024-001"


def test_extract_supplier_id_unknown() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["data"]["invoice"]["supplier_id"] == "UNKNOWN_SUPPLIER"


def test_extract_numeric_totals_are_floats() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    inv = r["data"]["invoice"]
    assert isinstance(inv["subtotal"], float)
    assert isinstance(inv["tax_total"], float)
    assert isinstance(inv["invoice_total"], float)


# ---------------------------------------------------------------------------
# Extraction — warnings
# ---------------------------------------------------------------------------

def test_extract_missing_po_warns() -> None:
    r = invoiceops_extract_invoice_fields(_MISSING_PO_TEXT)
    assert r["ok"] is True
    assert any("po_number" in w for w in r["data"]["extraction_warnings"])


def test_extract_missing_po_empty_string() -> None:
    r = invoiceops_extract_invoice_fields(_MISSING_PO_TEXT)
    assert r["data"]["invoice"]["po_number"] == ""


def test_extract_no_line_items_warns() -> None:
    r = invoiceops_extract_invoice_fields(_NO_LINE_ITEMS_TEXT)
    assert any("line item" in w for w in r["data"]["extraction_warnings"])


def test_extract_currency_default_warns_when_missing() -> None:
    text = _MINIMAL_TEXT.replace("Currency: ZAR\n", "")
    r = invoiceops_extract_invoice_fields(text)
    assert any("currency" in w for w in r["data"]["extraction_warnings"])
    assert r["data"]["invoice"]["currency"] == "ZAR"


def test_extract_bad_date_warns() -> None:
    r = invoiceops_extract_invoice_fields(_BAD_DATE_TEXT)
    assert any("invoice_date" in w for w in r["data"]["extraction_warnings"])


# ---------------------------------------------------------------------------
# Extraction — evidence
# ---------------------------------------------------------------------------

def test_extract_evidence_produced() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT, source_ref="sample.txt")
    assert len(r["data"]["evidence"]) > 0


def test_extract_evidence_has_invoice_number() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT, source_ref="sample.txt")
    ev = {e["field_path"]: e for e in r["data"]["evidence"]}
    assert "invoice.invoice_number" in ev


def test_extract_evidence_raw_value_populated() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT, source_ref="sample.txt")
    ev = {e["field_path"]: e for e in r["data"]["evidence"]}
    assert ev["invoice.invoice_number"]["raw_value"] == "INV-2024-001"


def test_extract_evidence_confidence_in_range() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT, source_ref="sample.txt")
    for item in r["data"]["evidence"]:
        c = item["confidence"]
        assert 0.0 <= c <= 1.0, f"confidence out of range for {item['field_path']}: {c}"


def test_extract_evidence_source_ref_populated() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT, source_ref="tests/sample.txt")
    for item in r["data"]["evidence"]:
        assert item["source_ref"] == "tests/sample.txt"


def test_extract_tool_evidence_present() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert isinstance(r["evidence"], dict)
    assert r["evidence"].get("tool") == "invoiceops/extract_invoice_fields"


def test_extract_tool_evidence_mode_dry_run() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert r["evidence"]["mode"] == "dry_run"


# ---------------------------------------------------------------------------
# Extraction — error cases
# ---------------------------------------------------------------------------

def test_extract_empty_text_fails() -> None:
    r = invoiceops_extract_invoice_fields("")
    assert r["ok"] is False
    assert r["error"] == "INVOICE_TEXT_EMPTY"


def test_extract_whitespace_only_fails() -> None:
    r = invoiceops_extract_invoice_fields("   \n  \t  ")
    assert r["ok"] is False
    assert r["error"] == "INVOICE_TEXT_EMPTY"


# ---------------------------------------------------------------------------
# Extraction — ToolResult contract shape
# ---------------------------------------------------------------------------

def test_extract_result_has_all_keys() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_extract_data_has_invoice_key() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert "invoice" in r["data"]


def test_extract_data_has_warnings_key() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert "extraction_warnings" in r["data"]
    assert isinstance(r["data"]["extraction_warnings"], list)


def test_extract_data_has_evidence_key() -> None:
    r = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    assert "evidence" in r["data"]
    assert isinstance(r["data"]["evidence"], list)


# ---------------------------------------------------------------------------
# Validation — happy path
# ---------------------------------------------------------------------------

def test_validate_valid_invoice_ok() -> None:
    r = invoiceops_validate_invoice_fields(_MINIMAL_VALID_INVOICE)
    assert r["ok"] is True
    assert r["data"]["valid"] is True
    assert r["data"]["errors"] == []


def test_validate_result_type() -> None:
    r = invoiceops_validate_invoice_fields(_MINIMAL_VALID_INVOICE)
    assert r["type"] == "invoiceops_invoice_validation"


def test_validate_invoice_preserved_in_data() -> None:
    r = invoiceops_validate_invoice_fields(_MINIMAL_VALID_INVOICE)
    assert r["data"]["invoice"] == _MINIMAL_VALID_INVOICE


def test_validate_evidence_present() -> None:
    r = invoiceops_validate_invoice_fields(_MINIMAL_VALID_INVOICE)
    assert r["evidence"].get("tool") == "invoiceops/validate_invoice_fields"


# ---------------------------------------------------------------------------
# Validation — required field failures
# ---------------------------------------------------------------------------

def test_validate_missing_supplier_name_fails() -> None:
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, supplier_name=""))
    assert r["data"]["valid"] is False
    assert any("supplier_name" in e for e in r["data"]["errors"])


def test_validate_missing_invoice_number_fails() -> None:
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, invoice_number=""))
    assert r["data"]["valid"] is False
    assert any("invoice_number" in e for e in r["data"]["errors"])


def test_validate_missing_po_number_fails() -> None:
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, po_number=""))
    assert r["data"]["valid"] is False
    assert any("po_number" in e for e in r["data"]["errors"])


def test_validate_missing_currency_fails() -> None:
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, currency=""))
    assert r["data"]["valid"] is False
    assert any("currency" in e for e in r["data"]["errors"])


def test_validate_missing_invoice_total_fails() -> None:
    inv = dict(_MINIMAL_VALID_INVOICE)
    inv.pop("invoice_total")
    r = invoiceops_validate_invoice_fields(inv)
    assert r["data"]["valid"] is False
    assert any("invoice_total" in e for e in r["data"]["errors"])


# ---------------------------------------------------------------------------
# Validation — date
# ---------------------------------------------------------------------------

def test_validate_bad_date_fails() -> None:
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, invoice_date="15-01-2024"))
    assert r["data"]["valid"] is False
    assert any("invoice_date" in e for e in r["data"]["errors"])


def test_validate_missing_date_fails() -> None:
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, invoice_date=""))
    assert r["data"]["valid"] is False
    assert any("invoice_date" in e for e in r["data"]["errors"])


# ---------------------------------------------------------------------------
# Validation — line items
# ---------------------------------------------------------------------------

def test_validate_empty_line_items_fails() -> None:
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, line_items=[]))
    assert r["data"]["valid"] is False
    assert any("line_items" in e for e in r["data"]["errors"])


def test_validate_line_item_zero_quantity_fails() -> None:
    bad_item = {**_MINIMAL_VALID_INVOICE["line_items"][0], "quantity": 0.0}
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, line_items=[bad_item]))
    assert r["data"]["valid"] is False
    assert any("quantity" in e for e in r["data"]["errors"])


def test_validate_line_item_zero_total_fails() -> None:
    bad_item = {**_MINIMAL_VALID_INVOICE["line_items"][0], "line_total": 0.0}
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, line_items=[bad_item]))
    assert r["data"]["valid"] is False
    assert any("line_total" in e for e in r["data"]["errors"])


def test_validate_line_item_no_description_or_sku_fails() -> None:
    bad_item = {**_MINIMAL_VALID_INVOICE["line_items"][0], "description": "", "sku": ""}
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, line_items=[bad_item]))
    assert r["data"]["valid"] is False


# ---------------------------------------------------------------------------
# Validation — warnings
# ---------------------------------------------------------------------------

def test_validate_unknown_supplier_warns() -> None:
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, supplier_id="UNKNOWN_SUPPLIER"))
    assert any("UNKNOWN_SUPPLIER" in w for w in r["data"]["warnings"])


def test_validate_total_mismatch_warns() -> None:
    r = invoiceops_validate_invoice_fields(
        _copy(_MINIMAL_VALID_INVOICE, subtotal=100.0, tax_total=15.0, invoice_total=999.0)
    )
    assert any("invoice_total" in w or "subtotal" in w for w in r["data"]["warnings"])


def test_validate_line_totals_mismatch_subtotal_warns() -> None:
    item = {**_MINIMAL_VALID_INVOICE["line_items"][0], "line_total": 50.0}
    r = invoiceops_validate_invoice_fields(
        _copy(_MINIMAL_VALID_INVOICE, line_items=[item], subtotal=100.0)
    )
    assert any("subtotal" in w or "line_total" in w for w in r["data"]["warnings"])


# ---------------------------------------------------------------------------
# Validation — ToolResult contract shape
# ---------------------------------------------------------------------------

def test_validate_result_has_all_keys() -> None:
    r = invoiceops_validate_invoice_fields(_MINIMAL_VALID_INVOICE)
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_validate_data_has_valid_key() -> None:
    r = invoiceops_validate_invoice_fields(_MINIMAL_VALID_INVOICE)
    assert "valid" in r["data"]
    assert isinstance(r["data"]["valid"], bool)


def test_validate_data_has_errors_and_warnings() -> None:
    r = invoiceops_validate_invoice_fields(_MINIMAL_VALID_INVOICE)
    assert isinstance(r["data"]["errors"], list)
    assert isinstance(r["data"]["warnings"], list)


def test_validate_ok_is_true_even_when_invoice_invalid() -> None:
    """The tool itself succeeded; invoice validity is in data.valid."""
    r = invoiceops_validate_invoice_fields(_copy(_MINIMAL_VALID_INVOICE, invoice_number=""))
    assert r["ok"] is True
    assert r["data"]["valid"] is False


# ---------------------------------------------------------------------------
# Round-trip: extract then validate
# ---------------------------------------------------------------------------

def test_round_trip_extract_then_validate() -> None:
    extracted = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    invoice = extracted["data"]["invoice"]
    validated = invoiceops_validate_invoice_fields(invoice)
    assert validated["ok"] is True


def test_round_trip_complete_invoice_passes_validation() -> None:
    extracted = invoiceops_extract_invoice_fields(_COMPLETE_TEXT)
    invoice = extracted["data"]["invoice"]
    validated = invoiceops_validate_invoice_fields(invoice)
    # Known issue: supplier_id is UNKNOWN_SUPPLIER → warning, not error
    assert validated["data"]["valid"] is True
    assert validated["data"]["errors"] == []


def test_round_trip_missing_po_fails_validation() -> None:
    extracted = invoiceops_extract_invoice_fields(_MISSING_PO_TEXT)
    invoice = extracted["data"]["invoice"]
    validated = invoiceops_validate_invoice_fields(invoice)
    assert validated["data"]["valid"] is False
    assert any("po_number" in e for e in validated["data"]["errors"])


def test_round_trip_mismatch_totals_warns() -> None:
    extracted = invoiceops_extract_invoice_fields(_MISMATCH_TOTALS_TEXT)
    invoice = extracted["data"]["invoice"]
    validated = invoiceops_validate_invoice_fields(invoice)
    assert any("invoice_total" in w or "subtotal" in w for w in validated["data"]["warnings"])
