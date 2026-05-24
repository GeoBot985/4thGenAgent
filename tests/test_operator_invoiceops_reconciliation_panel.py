from __future__ import annotations

from pathlib import Path


OPERATOR_UI = Path("src/operator_ui.py")


def test_operator_ui_includes_invoiceops_post_write_reconciliation_panel() -> None:
    text = OPERATOR_UI.read_text(encoding="utf-8")
    assert "Post-Write Reconciliation" in text
    assert "Run Reconciliation" in text
    assert "Build Accounting Evidence Pack" in text
    assert "Open Reconciliation Report" in text
    assert "Open Evidence Pack" in text
    assert "_run_invoiceops_reconciliation" in text
    assert "_build_invoiceops_accounting_evidence_pack" in text

