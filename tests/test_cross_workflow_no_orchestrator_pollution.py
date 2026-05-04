from pathlib import Path


def test_no_cross_workflow_logic_in_orchestrator():
    text = Path("runtime/orchestrator.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "cross_workflow",
        "demo_pack",
        "customer_support lane",
        "procurement lane",
        "accounting lane",
    ]
    found = [term for term in forbidden if term in text]
    assert not found, f"Cross-workflow logic leaked into orchestrator: {found}"
