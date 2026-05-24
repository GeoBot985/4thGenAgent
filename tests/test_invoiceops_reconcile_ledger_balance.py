from __future__ import annotations

from runtime.invoiceops_reconciliation import reconcile_ledger_register


def test_unbalanced_ledger_returns_unreconciled() -> None:
    plan = {
        "match_status": "matched",
        "source_invoice": {"invoice_total": 200.0},
        "ledger_rows": [
            {"debit_account": "5000", "credit_account": "", "amount": 100.0},
            {"debit_account": "", "credit_account": "2000", "amount": 90.0},
        ],
    }

    result = reconcile_ledger_register(plan)

    assert result["status"] == "UNRECONCILED"
    assert result["ok"] is False
    assert result["critical"] is True


def test_balanced_ledger_is_reconciled() -> None:
    plan = {
        "match_status": "matched",
        "source_invoice": {"invoice_total": 200.0},
        "ledger_rows": [
            {"debit_account": "5000", "credit_account": "", "amount": 200.0},
            {"debit_account": "", "credit_account": "2000", "amount": 200.0},
        ],
    }

    result = reconcile_ledger_register(plan)

    assert result["status"] == "RECONCILED"
    assert result["ok"] is True

