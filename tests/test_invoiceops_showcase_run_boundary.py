from __future__ import annotations

from runtime.invoiceops_showcase_demo import run_showcase_invoice_batch


def test_boundary_run_no_live_writes() -> None:
    result = run_showcase_invoice_batch(live_mode=False)
    assert result["ok"]
    assert result["live_side_effects_performed"] is False
    assert result["live_writes_performed"] == 0


def test_boundary_run_processes_all_invoices() -> None:
    result = run_showcase_invoice_batch(live_mode=False)
    assert result["invoice_count"] == 8
    assert result["invoice_count"] == len(result["invoice_results"])


def test_boundary_run_invoice_limit() -> None:
    result = run_showcase_invoice_batch(live_mode=False, invoice_limit=1)
    assert result["invoice_count"] == 1
    assert result["invoice_results"][0]["invoice_number"] == "INV-001"


def test_boundary_run_inv001_is_matched() -> None:
    result = run_showcase_invoice_batch(live_mode=False, invoice_limit=1)
    inv001 = result["invoice_results"][0]
    assert inv001["match_status"] == "matched"
    assert inv001["posting_status"] == "EXECUTED_VERIFIED"
    assert inv001["reconciliation_status"] == "RECONCILED"
    assert inv001["exception_type"] == ""


def test_boundary_run_exceptions_are_blocked() -> None:
    result = run_showcase_invoice_batch(live_mode=False)
    exceptions = [r for r in result["invoice_results"] if r["match_status"] == "exception"]
    for exc in exceptions:
        assert exc["posting_status"] == "BLOCKED"


def test_boundary_run_matched_has_prepared_writes() -> None:
    result = run_showcase_invoice_batch(live_mode=False)
    matched = [r for r in result["invoice_results"] if r["match_status"] == "matched"]
    assert len(matched) >= 1
    for m in matched:
        assert len(m["prepared_writes"]) > 0


def test_boundary_run_prepared_writes_have_idempotency_keys() -> None:
    result = run_showcase_invoice_batch(live_mode=False)
    for inv in result["invoice_results"]:
        for pw in inv.get("prepared_writes", []):
            assert pw["idempotency_key"], f"Missing idempotency_key in {inv['invoice_number']}"
            assert pw["payload_hash"], f"Missing payload_hash in {inv['invoice_number']}"


def test_boundary_run_result_shape() -> None:
    result = run_showcase_invoice_batch(live_mode=False)
    required_keys = {
        "ok", "demo_run_id", "spreadsheet_id", "profile",
        "invoice_count", "matched_count", "exception_count",
        "blocked_count", "live_writes_performed", "live_side_effects_performed",
        "invoice_results", "warnings", "blockers",
    }
    missing = required_keys - result.keys()
    assert not missing, f"Result missing keys: {missing}"


def test_boundary_run_writes_report(tmp_path) -> None:
    result = run_showcase_invoice_batch(
        live_mode=False,
        write_report=True,
        runtime_data_dir=str(tmp_path),
    )
    assert result["ok"]
    reports = result.get("reports", {})
    assert reports.get("json_latest")
    from pathlib import Path
    assert Path(reports["json_latest"]).is_file()
    assert Path(reports["markdown_latest"]).is_file()
    assert Path(reports["invoice_results"]).is_file()
    assert Path(reports["live_write_summary"]).is_file()
