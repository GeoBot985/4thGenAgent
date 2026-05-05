from __future__ import annotations


def test_tool_capability_registry_loads():
    from runtime.tool_capability_registry import list_tool_capabilities

    tools = list_tool_capabilities()
    assert tools


def test_required_core_tools_registered():
    from runtime.tool_capability_registry import list_tool_capabilities

    ids = {tool.tool_id for tool in list_tool_capabilities()}
    assert "business_context" in ids
    assert "business_database" in ids
    assert "llm_ollama" in ids
    assert "memory_store" in ids
    assert "report_generator" in ids


def test_rpa_tool_marked_optional_and_live_probe_required():
    from runtime.tool_capability_registry import get_tool_capability

    tool = get_tool_capability("rpa_google_messages")
    assert tool.core_or_optional == "optional"
    assert tool.side_effect_level == "high_risk"
    assert tool.rpa_live_probe_required is True
