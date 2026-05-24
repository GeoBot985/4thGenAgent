from __future__ import annotations

from runtime.invoiceops_showcase_demo import (
    run_showcase_invoice_batch,
    build_showcase_dashboard_data,
)


def _get_batch() -> dict:
    return run_showcase_invoice_batch(live_mode=False)


def test_dashboard_builds_from_batch() -> None:
    batch = _get_batch()
    dashboard = build_showcase_dashboard_data(batch_result=batch)
    assert dashboard["ok"]


def test_dashboard_summary_cards_present() -> None:
    batch = _get_batch()
    dashboard = build_showcase_dashboard_data(batch_result=batch)
    required = {
        "invoices_processed", "matched", "exceptions", "blocked",
        "live_writes_performed", "reconciled_postings",
        "manual_review_required", "total_invoice_value",
    }
    assert required.issubset(dashboard["summary_cards"].keys())


def test_dashboard_invoices_processed_count() -> None:
    batch = _get_batch()
    dashboard = build_showcase_dashboard_data(batch_result=batch)
    assert dashboard["summary_cards"]["invoices_processed"] == 8


def test_dashboard_matched_is_one() -> None:
    batch = _get_batch()
    dashboard = build_showcase_dashboard_data(batch_result=batch)
    assert dashboard["summary_cards"]["matched"] == 1


def test_dashboard_exception_count() -> None:
    batch = _get_batch()
    dashboard = build_showcase_dashboard_data(batch_result=batch)
    assert dashboard["summary_cards"]["exceptions"] >= 6


def test_dashboard_invoice_status_table_has_all_rows() -> None:
    batch = _get_batch()
    dashboard = build_showcase_dashboard_data(batch_result=batch)
    table = dashboard["invoice_status_table"]
    assert len(table) == 8
    for row in table:
        assert "invoice_number" in row
        assert "match_status" in row
        assert "posting_status" in row


def test_dashboard_exception_summary_populated() -> None:
    batch = _get_batch()
    dashboard = build_showcase_dashboard_data(batch_result=batch)
    exc_summary = dashboard["exception_summary"]
    assert len(exc_summary) >= 6


def test_dashboard_live_write_safety_summary() -> None:
    batch = _get_batch()
    dashboard = build_showcase_dashboard_data(batch_result=batch)
    safety = dashboard["live_write_safety_summary"]
    assert safety["profile_required"] == "controlled_live_write"
    assert safety["confirmation_required"] is True
    assert safety["rpa_blocked"] is True
    assert safety["gmail_send_blocked"] is True
    assert safety["calendar_mutation_blocked"] is True


def test_dashboard_ledger_summary() -> None:
    batch = _get_batch()
    dashboard = build_showcase_dashboard_data(batch_result=batch)
    ledger = dashboard["ledger_summary"]
    assert ledger["total_debit_rows"] == ledger["total_credit_rows"]
    assert ledger["ledger_balanced"] is True


def test_dashboard_run_id_matches_batch() -> None:
    batch = _get_batch()
    dashboard = build_showcase_dashboard_data(batch_result=batch)
    assert dashboard["run_id"] == batch["demo_run_id"]
