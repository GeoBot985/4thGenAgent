from __future__ import annotations

import json
from pathlib import Path


def test_forbidden_api_scan_passes() -> None:
    from src.google_workspace_safety_scan import scan_google_workspace_pack_for_forbidden_calls

    result = scan_google_workspace_pack_for_forbidden_calls("tool_packs/google_workspace")
    assert result["ok"] is True
    assert result["forbidden_hits"] == []
    assert result["scanned_files"]


def test_no_google_workspace_tool_has_live_side_effects() -> None:
    descriptor = json.loads(Path("tool_packs/google_workspace/toolpack.json").read_text(encoding="utf-8"))
    for tool in descriptor["tools"]:
        assert tool["side_effect"] is False
        assert tool["allow_live_side_effect"] is False


def test_default_registry_import_does_not_require_google_credentials() -> None:
    import runtime.tool_registry as tool_registry

    registry = tool_registry.build_tool_registry(include_external=True, config_path="config/enabled_toolpacks.json")
    assert "google/auth_status" not in registry or registry["google/auth_status"]["allow_live_side_effect"] is False


def test_playwright_is_not_imported_during_default_registry_import() -> None:
    import sys
    before = {name for name in sys.modules if name.startswith("playwright")}
    import runtime.tool_registry  # noqa: F401

    after = {name for name in sys.modules if name.startswith("playwright")}
    assert after == before
