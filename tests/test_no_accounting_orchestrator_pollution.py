from pathlib import Path


def test_no_accounting_logic_in_orchestrator():
    text = Path("runtime/orchestrator.py").read_text(encoding="utf-8").lower()
    forbidden = ["accounting", "reconciliation", "payment_match", "invoice_match", "ledger_match", "recon_run", "recon_exception"]
    found = [term for term in forbidden if term in text]
    assert not found, f"Accounting logic leaked into orchestrator: {found}"
