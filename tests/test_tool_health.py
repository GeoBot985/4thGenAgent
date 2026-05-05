from __future__ import annotations


def test_business_context_health_passes():
    from runtime.tool_health import check_tool_health

    result = check_tool_health("business_context", live=False)
    assert result.ok is True
    assert result.status == "ready"


def test_business_database_health_passes():
    from runtime.tool_health import check_tool_health

    result = check_tool_health("business_database", live=False)
    assert result.ok is True
    assert result.status == "ready"


def test_memory_store_health_passes():
    from runtime.tool_health import check_tool_health

    result = check_tool_health("memory_store", live=False)
    assert result.ok is True
    assert result.status == "ready"


def test_report_generator_health_passes():
    from runtime.tool_health import check_tool_health

    result = check_tool_health("report_generator", live=False)
    assert result.ok is True
    assert result.status == "ready"


def test_external_tool_health_returns_structured_status():
    from runtime.tool_health import check_tool_health

    statuses = {"ready", "needs_auth", "missing_dependency", "misconfigured", "not_run", "unknown"}
    for tool_id in ("gmail", "google_sheets", "google_calendar", "llm_ollama"):
        result = check_tool_health(tool_id, live=False)
        assert result.tool_id == tool_id
        assert result.status in statuses
        assert result.checked_at
        assert isinstance(result.details, dict)


def test_safe_health_check_does_not_run_live_rpa():
    from runtime.tool_health import check_tool_health

    result = check_tool_health("rpa_google_messages", live=False)
    assert result.status in {"disabled_optional", "live_probe_required", "misconfigured", "missing_dependency", "not_run", "needs_auth"}


def test_check_all_tool_health_returns_structured_results():
    from runtime.tool_health import check_all_tool_health

    results = check_all_tool_health(include_optional=False, live_rpa=False)
    assert results
    for result in results:
        assert result.tool_id
        assert result.status
        assert result.checked_at


def test_core_health_snapshot_is_persisted():
    from pathlib import Path

    from runtime.tool_health import check_all_tool_health

    check_all_tool_health(include_optional=False, live_rpa=False)
    assert Path("runtime_data/tool_health/latest_tool_health.json").is_file()
