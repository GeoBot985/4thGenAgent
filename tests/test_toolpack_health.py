from __future__ import annotations

import json
from pathlib import Path


def _write_config(tmp_path: Path, *, enabled: list[str] | None = None, allow_optional: bool = True) -> Path:
    payload = {
        "enabled_toolpacks": enabled or [],
        "disabled_toolpacks": [],
        "allow_optional_toolpacks": allow_optional,
    }
    path = tmp_path / "enabled_toolpacks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_demo_echo_health_returns_structured_result(tmp_path: Path) -> None:
    from src.toolpack_loader import check_toolpack_health

    config_path = _write_config(tmp_path, enabled=["tool_packs/demo_echo/toolpack.json"], allow_optional=True)
    result = check_toolpack_health("demo_echo", config_path=config_path)
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


def test_live_health_is_not_run_by_default(tmp_path: Path) -> None:
    from src.toolpack_loader import check_toolpack_health

    config_path = _write_config(tmp_path, enabled=["tool_packs/demo_echo/toolpack.json"], allow_optional=True)
    result = check_toolpack_health("demo_echo", config_path=config_path, live=False)
    assert result["live_checked"] is False
