from __future__ import annotations


def test_demo_echo_health_returns_structured_result() -> None:
    from src.toolpack_loader import check_toolpack_health

    result = check_toolpack_health("demo_echo")
    assert result["ok"] is True
    assert result["toolpack_id"] == "demo_echo"
    assert result["status"] == "ready"
    assert result["health_supported"] is True


def test_health_snapshot_can_include_enabled_external_packs() -> None:
    from runtime.tool_health import check_all_tool_health

    results = check_all_tool_health(include_optional=True, live_rpa=False)
    ids = {result.tool_id for result in results}
    assert "toolpack:demo_echo" in ids


def test_safe_health_check_excludes_disabled_optional_packs() -> None:
    from runtime.tool_health import check_all_tool_health

    results = check_all_tool_health(include_optional=False, live_rpa=False)
    ids = {result.tool_id for result in results}
    assert "toolpack:demo_echo" not in ids


def test_live_health_is_not_run_by_default() -> None:
    from src.toolpack_loader import check_toolpack_health

    result = check_toolpack_health("demo_echo", live=False)
    assert result["live_checked"] is False
