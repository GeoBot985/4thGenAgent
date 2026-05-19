from __future__ import annotations

import inspect

import runtime.invoiceops_sheet_tools as _mod
from runtime.invoiceops_sheet_tools import (
    invoiceops_read_exception_register,
    invoiceops_read_invoice_register,
    invoiceops_read_ledger,
    invoiceops_read_po_register,
    invoiceops_read_receipt_register,
    invoiceops_read_supplier_master,
)
from runtime.invoiceops_contracts import (
    validate_exception_shape,
    validate_goods_receipt_shape,
    validate_invoice_shape,
    validate_ledger_row_shape,
    validate_purchase_order_shape,
    validate_supplier_shape,
)

_BAD_DIR = "tests/fixtures/invoiceops/nonexistent_sheets"

# ---------------------------------------------------------------------------
# All six registers read from fixtures
# ---------------------------------------------------------------------------

def test_supplier_master_reads_ok() -> None:
    r = invoiceops_read_supplier_master()
    assert r["ok"] is True
    assert r["error"] == ""


def test_po_register_reads_ok() -> None:
    r = invoiceops_read_po_register()
    assert r["ok"] is True
    assert r["error"] == ""


def test_receipt_register_reads_ok() -> None:
    r = invoiceops_read_receipt_register()
    assert r["ok"] is True
    assert r["error"] == ""


def test_invoice_register_reads_ok() -> None:
    r = invoiceops_read_invoice_register()
    assert r["ok"] is True
    assert r["error"] == ""


def test_ledger_reads_ok() -> None:
    r = invoiceops_read_ledger()
    assert r["ok"] is True
    assert r["error"] == ""


def test_exception_register_reads_ok() -> None:
    r = invoiceops_read_exception_register()
    assert r["ok"] is True
    assert r["error"] == ""


# ---------------------------------------------------------------------------
# Result type and shape
# ---------------------------------------------------------------------------

def test_all_registers_return_correct_type() -> None:
    for fn in (
        invoiceops_read_supplier_master,
        invoiceops_read_po_register,
        invoiceops_read_receipt_register,
        invoiceops_read_invoice_register,
        invoiceops_read_ledger,
        invoiceops_read_exception_register,
    ):
        r = fn()
        assert r["type"] == "invoiceops_sheet_rows", f"{fn.__name__} wrong type"


def test_all_registers_have_toolresult_keys() -> None:
    for fn in (
        invoiceops_read_supplier_master,
        invoiceops_read_po_register,
        invoiceops_read_receipt_register,
        invoiceops_read_invoice_register,
        invoiceops_read_ledger,
        invoiceops_read_exception_register,
    ):
        r = fn()
        for key in ("ok", "type", "data", "evidence", "error", "metadata"):
            assert key in r, f"{fn.__name__} missing key {key!r}"


def test_all_registers_data_has_required_keys() -> None:
    for fn in (
        invoiceops_read_supplier_master,
        invoiceops_read_po_register,
        invoiceops_read_receipt_register,
        invoiceops_read_invoice_register,
        invoiceops_read_ledger,
        invoiceops_read_exception_register,
    ):
        data = fn()["data"]
        for key in ("sheet_name", "rows", "records", "record_count"):
            assert key in data, f"{fn.__name__} data missing {key!r}"


# ---------------------------------------------------------------------------
# Rows convert into records
# ---------------------------------------------------------------------------

def test_supplier_rows_is_2d_list() -> None:
    r = invoiceops_read_supplier_master()
    rows = r["data"]["rows"]
    assert isinstance(rows, list)
    assert all(isinstance(row, list) for row in rows)


def test_supplier_rows_first_row_is_header() -> None:
    r = invoiceops_read_supplier_master()
    header = r["data"]["rows"][0]
    assert "supplier_id" in header
    assert "supplier_name" in header


def test_supplier_records_are_dicts() -> None:
    r = invoiceops_read_supplier_master()
    records = r["data"]["records"]
    assert all(isinstance(rec, dict) for rec in records)


def test_supplier_record_count_matches() -> None:
    r = invoiceops_read_supplier_master()
    assert r["data"]["record_count"] == len(r["data"]["records"])


def test_supplier_rows_and_records_consistent() -> None:
    r = invoiceops_read_supplier_master()
    rows = r["data"]["rows"]
    records = r["data"]["records"]
    # rows = header + data rows; records = list of dicts
    assert len(rows) == len(records) + 1


def test_po_rows_is_2d_list() -> None:
    r = invoiceops_read_po_register()
    assert isinstance(r["data"]["rows"], list)
    assert isinstance(r["data"]["rows"][0], list)


def test_po_records_are_dicts() -> None:
    r = invoiceops_read_po_register()
    assert all(isinstance(rec, dict) for rec in r["data"]["records"])


# ---------------------------------------------------------------------------
# Supplier records validate against supplier shape
# ---------------------------------------------------------------------------

def test_supplier_records_valid() -> None:
    r = invoiceops_read_supplier_master()
    for rec in r["data"]["records"]:
        v = validate_supplier_shape(rec)
        assert v["ok"] is True, f"supplier validation failed: {v['errors']}"


def test_supplier_record_count() -> None:
    r = invoiceops_read_supplier_master()
    assert r["data"]["record_count"] == 2


def test_supplier_has_active_supplier() -> None:
    r = invoiceops_read_supplier_master()
    statuses = [rec["status"] for rec in r["data"]["records"]]
    assert "active" in statuses


def test_supplier_has_inactive_supplier() -> None:
    r = invoiceops_read_supplier_master()
    statuses = [rec["status"] for rec in r["data"]["records"]]
    assert "inactive" in statuses


def test_supplier_active_record_fields() -> None:
    r = invoiceops_read_supplier_master()
    active = next(rec for rec in r["data"]["records"] if rec["status"] == "active")
    assert active["supplier_id"] == "SUP-001"
    assert "Acme" in active["supplier_name"]


# ---------------------------------------------------------------------------
# PO records validate against purchase order shape
# ---------------------------------------------------------------------------

def test_po_valid_po_passes_shape_validation() -> None:
    r = invoiceops_read_po_register()
    valid_po = next(rec for rec in r["data"]["records"] if rec["po_number"] == "PO-2024-042")
    v = validate_purchase_order_shape(valid_po)
    assert v["ok"] is True, f"PO validation failed: {v['errors']}"


def test_po_register_has_three_records() -> None:
    r = invoiceops_read_po_register()
    assert r["data"]["record_count"] == 3


def test_po_register_contains_wrong_supplier_po() -> None:
    r = invoiceops_read_po_register()
    supplier_ids = [rec["supplier_id"] for rec in r["data"]["records"]]
    assert "SUP-999" in supplier_ids


def test_po_register_contains_no_receipt_po() -> None:
    r = invoiceops_read_po_register()
    po_numbers = [rec["po_number"] for rec in r["data"]["records"]]
    assert "PO-2024-044" in po_numbers


def test_po_line_items_are_lists() -> None:
    r = invoiceops_read_po_register()
    for rec in r["data"]["records"]:
        assert isinstance(rec["line_items"], list)


# ---------------------------------------------------------------------------
# Receipt records validate against goods receipt shape
# ---------------------------------------------------------------------------

def test_receipt_valid_record_passes_shape_validation() -> None:
    r = invoiceops_read_receipt_register()
    received = next(rec for rec in r["data"]["records"] if rec["status"] == "received")
    v = validate_goods_receipt_shape(received)
    assert v["ok"] is True, f"receipt validation failed: {v['errors']}"


def test_receipt_register_has_two_records() -> None:
    r = invoiceops_read_receipt_register()
    assert r["data"]["record_count"] == 2


def test_receipt_register_has_received_status() -> None:
    r = invoiceops_read_receipt_register()
    statuses = [rec["status"] for rec in r["data"]["records"]]
    assert "received" in statuses


def test_receipt_register_has_partial_status() -> None:
    r = invoiceops_read_receipt_register()
    statuses = [rec["status"] for rec in r["data"]["records"]]
    assert "partial" in statuses


# ---------------------------------------------------------------------------
# Invoice register records are readable
# ---------------------------------------------------------------------------

def test_invoice_register_is_readable() -> None:
    r = invoiceops_read_invoice_register()
    assert r["ok"] is True
    assert r["data"]["record_count"] >= 1


def test_invoice_register_records_have_invoice_number() -> None:
    r = invoiceops_read_invoice_register()
    for rec in r["data"]["records"]:
        assert "invoice_number" in rec
        assert rec["invoice_number"]


def test_invoice_register_has_two_records() -> None:
    r = invoiceops_read_invoice_register()
    assert r["data"]["record_count"] == 2


def test_invoice_register_duplicate_detected_as_warning() -> None:
    r = invoiceops_read_invoice_register()
    warnings = r["data"]["validation_warnings"]
    assert any("Duplicate" in w and "invoice_number" in w for w in warnings)


def test_invoice_register_valid_invoice_passes_shape() -> None:
    r = invoiceops_read_invoice_register()
    first = r["data"]["records"][0]
    v = validate_invoice_shape(first)
    assert v["ok"] is True, f"invoice validation failed: {v['errors']}"


# ---------------------------------------------------------------------------
# Ledger rows validate against ledger row shape
# ---------------------------------------------------------------------------

def test_ledger_reads_one_row() -> None:
    r = invoiceops_read_ledger()
    assert r["data"]["record_count"] == 1


def test_ledger_row_passes_shape_validation() -> None:
    r = invoiceops_read_ledger()
    for rec in r["data"]["records"]:
        v = validate_ledger_row_shape(rec)
        assert v["ok"] is True, f"ledger validation failed: {v['errors']}"


def test_ledger_row_source_type() -> None:
    r = invoiceops_read_ledger()
    assert r["data"]["records"][0]["source_type"] == "supplier_invoice"


def test_ledger_row_status() -> None:
    r = invoiceops_read_ledger()
    assert r["data"]["records"][0]["status"] == "posted"


# ---------------------------------------------------------------------------
# Exception rows validate against exception shape
# ---------------------------------------------------------------------------

def test_exception_register_reads_one_row() -> None:
    r = invoiceops_read_exception_register()
    assert r["data"]["record_count"] == 1


def test_exception_row_passes_shape_validation() -> None:
    r = invoiceops_read_exception_register()
    for rec in r["data"]["records"]:
        v = validate_exception_shape(rec)
        assert v["ok"] is True, f"exception validation failed: {v['errors']}"


def test_exception_row_type() -> None:
    r = invoiceops_read_exception_register()
    assert r["data"]["records"][0]["exception_type"] == "amount_mismatch"


def test_exception_row_blocking_is_bool() -> None:
    r = invoiceops_read_exception_register()
    assert isinstance(r["data"]["records"][0]["blocking"], bool)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

def test_supplier_master_evidence_tool() -> None:
    r = invoiceops_read_supplier_master()
    assert r["evidence"]["tool"] == "invoiceops/read_supplier_master"


def test_supplier_master_evidence_mode_dry_run() -> None:
    r = invoiceops_read_supplier_master()
    assert r["evidence"]["mode"] == "dry_run"


def test_all_evidence_mode_dry_run() -> None:
    for fn in (
        invoiceops_read_supplier_master,
        invoiceops_read_po_register,
        invoiceops_read_receipt_register,
        invoiceops_read_invoice_register,
        invoiceops_read_ledger,
        invoiceops_read_exception_register,
    ):
        r = fn()
        assert r["evidence"]["mode"] == "dry_run", f"{fn.__name__} wrong evidence mode"


def test_evidence_operation_is_read() -> None:
    r = invoiceops_read_supplier_master()
    assert r["evidence"]["operation"] == "read"


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def test_fixture_mode_in_metadata() -> None:
    r = invoiceops_read_supplier_master()
    assert r["metadata"]["fixture_mode"] is True


def test_live_mode_false_in_metadata() -> None:
    # demo-sheet-local has no SupplierMaster tab, so this returns an error result.
    # We verify that fixture_mode=False is reflected in metadata regardless.
    r = invoiceops_read_supplier_master(fixture_mode=False, spreadsheet_id="demo-sheet-local")
    assert r["metadata"]["fixture_mode"] is False


# ---------------------------------------------------------------------------
# Missing fixture fails safely
# ---------------------------------------------------------------------------

def test_missing_supplier_fixture_fails_safely() -> None:
    r = invoiceops_read_supplier_master(_fixture_dir=_BAD_DIR)
    assert r["ok"] is False


def test_missing_fixture_error_code() -> None:
    r = invoiceops_read_supplier_master(_fixture_dir=_BAD_DIR)
    assert r["error"] == "SHEET_FIXTURE_NOT_FOUND"


def test_missing_fixture_data_empty() -> None:
    r = invoiceops_read_supplier_master(_fixture_dir=_BAD_DIR)
    assert r["data"] == {}


def test_missing_po_fixture_fails_safely() -> None:
    r = invoiceops_read_po_register(_fixture_dir=_BAD_DIR)
    assert r["ok"] is False
    assert r["error"] == "SHEET_FIXTURE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Live mode does not run by default
# ---------------------------------------------------------------------------

def test_fixture_mode_is_true_by_default() -> None:
    import inspect
    sig = inspect.signature(invoiceops_read_supplier_master)
    assert sig.parameters["fixture_mode"].default is True


def test_no_live_call_with_default_args() -> None:
    # Default call (fixture_mode=True) must not attempt a live network call.
    # We verify by confirming it returns ok=True without a spreadsheet_id.
    r = invoiceops_read_supplier_master()
    assert r["ok"] is True


def test_live_mode_without_spreadsheet_id_fails() -> None:
    r = invoiceops_read_supplier_master(fixture_mode=False, spreadsheet_id="")
    assert r["ok"] is False
    assert r["error"] == "SPREADSHEET_ID_REQUIRED"


def test_all_tools_default_fixture_mode_true() -> None:
    for fn in (
        invoiceops_read_supplier_master,
        invoiceops_read_po_register,
        invoiceops_read_receipt_register,
        invoiceops_read_invoice_register,
        invoiceops_read_ledger,
        invoiceops_read_exception_register,
    ):
        sig = inspect.signature(fn)
        assert sig.parameters["fixture_mode"].default is True, f"{fn.__name__} wrong default"


# ---------------------------------------------------------------------------
# No write tools introduced
# ---------------------------------------------------------------------------

def test_no_write_functions_in_module() -> None:
    write_fns = [
        name for name in dir(_mod)
        if "write" in name.lower() and callable(getattr(_mod, name))
    ]
    assert write_fns == [], f"Unexpected write functions: {write_fns}"


def test_no_write_keyword_in_public_functions() -> None:
    public = [name for name in dir(_mod) if not name.startswith("_") and callable(getattr(_mod, name))]
    write_fns = [name for name in public if "write" in name.lower()]
    assert write_fns == []


# ---------------------------------------------------------------------------
# Validation warnings field present
# ---------------------------------------------------------------------------

def test_validation_warnings_field_in_data() -> None:
    r = invoiceops_read_supplier_master()
    assert "validation_warnings" in r["data"]
    assert isinstance(r["data"]["validation_warnings"], list)


def test_unknown_supplier_in_po_generates_no_crash() -> None:
    # PO-2024-043 has supplier_id=SUP-999 which isn't in the master.
    # The tool should still return ok=True with the records.
    r = invoiceops_read_po_register()
    assert r["ok"] is True
    assert r["data"]["record_count"] == 3


