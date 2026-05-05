from pathlib import Path


def test_runtime_contract_docs_exist() -> None:
    assert Path("docs/runtime_contracts.md").is_file()


def test_runtime_contract_docs_name_core_contracts() -> None:
    text = Path("docs/runtime_contracts.md").read_text(encoding="utf-8")
    assert "TaskFrame" in text
    assert "Manifest" in text
    assert "ToolResult" in text
    assert "PendingAction" in text
    assert "Event route" in text
    assert "Live execution" in text


def test_runtime_contract_docs_cover_required_lifecycle_states() -> None:
    text = Path("docs/runtime_contracts.md").read_text(encoding="utf-8")
    for state in (
        "CREATED",
        "VALIDATING",
        "READY",
        "RUNNING",
        "WAITING_FOR_INPUT",
        "WAITING_FOR_EXECUTE",
        "EXECUTING_PENDING",
        "VERIFYING",
        "COMPLETED",
        "COMPLETED_NO_DATA",
        "FAILED_VALIDATION",
        "FAILED_EXECUTION",
        "FAILED_COMPLETION",
        "CANCELLED",
        "EXPIRED",
    ):
        assert state in text
