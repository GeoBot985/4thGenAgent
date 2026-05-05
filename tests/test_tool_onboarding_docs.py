from pathlib import Path


def test_adding_new_tools_doc_exists() -> None:
    assert Path("docs/adding_new_tools.md").is_file()


def test_adding_new_tools_doc_names_required_sections() -> None:
    text = Path("docs/adding_new_tools.md").read_text(encoding="utf-8")
    required = [
        "Tool classification",
        "Tool registry",
        "Capability registry",
        "Tool health",
        "Tool setup",
        "Live side-effect",
        "Manifest usage",
        "Optional tools",
        "RPA",
    ]
    for item in required:
        assert item.lower() in text.lower()


def test_tool_contract_checklist_exists() -> None:
    assert Path("docs/tool_contract_checklist.md").is_file()


def test_tool_contract_checklist_has_checkboxes() -> None:
    text = Path("docs/tool_contract_checklist.md").read_text(encoding="utf-8")
    assert "- [ ]" in text
    assert "TOOL_REGISTRY" in text
    assert "PendingAction" in text
    assert "health check" in text.lower()
    assert "live execution" in text.lower()
