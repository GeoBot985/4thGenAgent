from pathlib import Path


def test_tool_docs_state_new_tools_do_not_enter_default_rc_automatically() -> None:
    text = Path("docs/default_demo_boundary.md").read_text(encoding="utf-8").lower()
    assert "adding a tool does not automatically add it to the default rc path" in text


def test_tool_docs_state_live_side_effects_blocked_by_default() -> None:
    text = Path("docs/adding_new_tools.md").read_text(encoding="utf-8").lower()
    assert "live side effects" in text
    assert "blocked by default" in text
