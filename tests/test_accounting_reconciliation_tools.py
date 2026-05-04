from runtime.accounting_tools import accounting_build_recon_sheet_rows, accounting_load_invoices, accounting_load_ledger, accounting_load_orders, accounting_load_payments
from runtime.reconciliation_tools import reconciliation_match_payments, reconciliation_validate_result


def test_load_payments_normalizes_rows():
    rows = [["payment_id", "amount", "currency"], ["PAY-1", "12.50", "ZAR"]]
    result = accounting_load_payments(rows)
    assert result["payments"][0]["amount"] == 12.5


def test_load_orders_normalizes_amounts():
    rows = [["order_ref", "order_total", "currency"], ["ORD-1", "12.50", "ZAR"]]
    result = accounting_load_orders(rows)
    assert result["orders"][0]["order_total"] == 12.5


def test_load_invoices_normalizes_amounts():
    rows = [["invoice_id", "invoice_total", "currency"], ["INV-1", "12.50", "ZAR"]]
    result = accounting_load_invoices(rows)
    assert result["invoices"][0]["invoice_total"] == 12.5


def test_load_ledger_normalizes_rows():
    rows = [["ledger_entry_id", "amount", "currency"], ["LED-1", "12.50", "ZAR"]]
    result = accounting_load_ledger(rows)
    assert result["ledger_entries"][0]["amount"] == 12.5


def test_match_payments_clean_match():
    payments = [{"payment_id": "PAY-1", "payment_ref": "EFT-1", "order_ref": "ORD-1", "amount": 10.0, "currency": "ZAR"}]
    orders = [{"order_ref": "ORD-1", "invoice_id": "INV-1", "currency": "ZAR"}]
    invoices = [{"invoice_id": "INV-1", "order_ref": "ORD-1", "invoice_total": 10.0, "currency": "ZAR"}]
    result = reconciliation_match_payments(payments, orders, invoices, [])
    assert result["summary"]["matched_count"] == 1


def test_match_payments_detects_missing_order():
    payments = [{"payment_id": "PAY-1", "payment_ref": "EFT-1", "order_ref": "ORD-X", "amount": 10.0, "currency": "ZAR"}]
    result = reconciliation_match_payments(payments, [], [], [])
    assert any(exc["exception_type"] == "missing_order" for exc in result["exceptions"])


def test_match_payments_detects_missing_invoice():
    payments = [{"payment_id": "PAY-1", "payment_ref": "EFT-1", "order_ref": "ORD-1", "amount": 10.0, "currency": "ZAR"}]
    orders = [{"order_ref": "ORD-1", "currency": "ZAR"}]
    result = reconciliation_match_payments(payments, orders, [], [])
    assert any(exc["exception_type"] == "missing_invoice" for exc in result["exceptions"])


def test_match_payments_detects_amount_mismatch():
    payments = [{"payment_id": "PAY-1", "payment_ref": "EFT-1", "order_ref": "ORD-1", "amount": 9.0, "currency": "ZAR"}]
    orders = [{"order_ref": "ORD-1", "invoice_id": "INV-1", "currency": "ZAR"}]
    invoices = [{"invoice_id": "INV-1", "order_ref": "ORD-1", "invoice_total": 10.0, "currency": "ZAR"}]
    result = reconciliation_match_payments(payments, orders, invoices, [])
    assert any(exc["exception_type"] == "amount_mismatch" for exc in result["exceptions"])


def test_match_payments_detects_currency_mismatch():
    payments = [{"payment_id": "PAY-1", "payment_ref": "EFT-1", "order_ref": "ORD-1", "amount": 10.0, "currency": "USD"}]
    orders = [{"order_ref": "ORD-1", "invoice_id": "INV-1", "currency": "ZAR"}]
    invoices = [{"invoice_id": "INV-1", "order_ref": "ORD-1", "invoice_total": 10.0, "currency": "ZAR"}]
    result = reconciliation_match_payments(payments, orders, invoices, [])
    assert any(exc["exception_type"] == "currency_mismatch" for exc in result["exceptions"])


def test_match_payments_detects_duplicate_payment_ref():
    payments = [
        {"payment_id": "PAY-1", "payment_ref": "EFT-1", "order_ref": "ORD-1", "amount": 10.0, "currency": "ZAR"},
        {"payment_id": "PAY-2", "payment_ref": "EFT-1", "order_ref": "ORD-1", "amount": 10.0, "currency": "ZAR"},
    ]
    result = reconciliation_match_payments(payments, [], [], [])
    assert any(exc["exception_type"] == "duplicate_payment_ref" for exc in result["exceptions"])


def test_match_payments_detects_already_posted():
    payments = [{"payment_id": "PAY-1", "payment_ref": "EFT-1", "order_ref": "ORD-1", "amount": 10.0, "currency": "ZAR"}]
    ledger = [{"source_ref": "EFT-1"}]
    result = reconciliation_match_payments(payments, [], [], ledger)
    assert any(exc["exception_type"] == "already_posted" for exc in result["exceptions"])


def test_reconciliation_summary_counts_match():
    payments = [{"payment_id": "PAY-1", "payment_ref": "EFT-1", "order_ref": "ORD-1", "amount": 10.0, "currency": "ZAR"}]
    orders = [{"order_ref": "ORD-1", "invoice_id": "INV-1", "currency": "ZAR"}]
    invoices = [{"invoice_id": "INV-1", "order_ref": "ORD-1", "invoice_total": 10.0, "currency": "ZAR"}]
    result = reconciliation_match_payments(payments, orders, invoices, [])
    assert result["summary"]["matched_count"] == len(result["matched"])


def test_reconciliation_validate_result_passes_valid_result():
    result = {"recon_run_id": "RECON-1", "matched": [], "exceptions": [], "summary": {"matched_count": 0, "exception_count": 0, "duplicate_count": 0, "amount_mismatch_count": 0, "already_posted_count": 0, "unmatched_count": 0, "status": "matched"}}
    validation = reconciliation_validate_result(result)
    assert validation["ok"] is True


def test_reconciliation_validate_result_fails_bad_counts():
    result = {"recon_run_id": "RECON-1", "matched": [{}], "exceptions": [], "summary": {"matched_count": 0, "exception_count": 0, "duplicate_count": 0, "amount_mismatch_count": 0, "already_posted_count": 0, "unmatched_count": 0, "status": "matched"}}
    validation = reconciliation_validate_result(result)
    assert validation["ok"] is False


def test_build_recon_sheet_rows_outputs_run_and_exception_rows():
    result = {"recon_run_id": "RECON-1", "matched": [], "exceptions": [{"exception_id": "EXC-1", "exception_type": "amount_mismatch", "payment_ref": "EFT-1", "payment_id": "PAY-1", "order_ref": "ORD-1", "invoice_id": "INV-1", "expected_amount": 10.0, "actual_amount": 9.0, "currency": "ZAR", "severity": "high", "message": "msg"}], "summary": {"matched_count": 0, "exception_count": 1, "duplicate_count": 0, "amount_mismatch_count": 1, "already_posted_count": 0, "unmatched_count": 0, "status": "exceptions"}}
    rows = accounting_build_recon_sheet_rows(result, {"summary": "s"}, frame_id="frame-1")
    assert rows["recon_run_rows"]
    assert rows["recon_exception_rows"]

