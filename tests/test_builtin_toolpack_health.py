from __future__ import annotations


def test_core_business_toolpack_health_passes() -> None:
    from src.toolpack_loader import check_toolpack_health

    result = check_toolpack_health("core_business")
    assert result["ok"] is True
    assert result["status"] == "ready"


def test_core_memory_toolpack_health_passes() -> None:
    from src.toolpack_loader import check_toolpack_health

    result = check_toolpack_health("core_memory")
    assert result["ok"] is True
    assert result["status"] == "ready"


def test_core_llm_micro_toolpack_health_is_safe_without_live_ollama() -> None:
    from src.toolpack_loader import check_toolpack_health

    result = check_toolpack_health("core_llm_micro", live=False)
    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["live_checked"] is False


def test_core_reports_toolpack_health_passes() -> None:
    from src.toolpack_loader import check_toolpack_health

    result = check_toolpack_health("core_reports")
    assert result["ok"] is True
    assert result["status"] == "ready"


def test_default_all_tool_health_includes_migrated_core_packs() -> None:
    from runtime.tool_health import check_all_tool_health

    results = check_all_tool_health(include_optional=False, live_rpa=False)
    ids = {result.tool_id for result in results}
    for tool_id in ["toolpack:core_business", "toolpack:core_memory", "toolpack:core_llm_micro", "toolpack:core_reports"]:
        assert tool_id in ids


def test_default_all_tool_health_excludes_optional_rpa_live_probes() -> None:
    from runtime.tool_health import check_all_tool_health

    results = check_all_tool_health(include_optional=False, live_rpa=False)
    ids = {result.tool_id for result in results}
    assert "rpa_google_messages" not in ids

