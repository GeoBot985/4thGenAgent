from __future__ import annotations

import json
from pathlib import Path


TOOLPACK = Path("tool_packs/google_workspace/toolpack.json")


def test_descriptor_exists() -> None:
    assert TOOLPACK.is_file()


def test_descriptor_validates_under_toolpack_loader() -> None:
    from src.toolpack_loader import load_toolpack_descriptor, validate_toolpack_descriptor

    descriptor = load_toolpack_descriptor(TOOLPACK)
    result = validate_toolpack_descriptor(descriptor, base_path=TOOLPACK.parent)
    assert result["ok"] is True
    assert result["toolpack_id"] == "google_workspace"
    assert result["tool_count"] == 7


def test_google_workspace_tool_ids_exist() -> None:
    descriptor = json.loads(TOOLPACK.read_text(encoding="utf-8"))
    tools = {item["tool"] for item in descriptor["tools"]}
    assert tools == {
        "google/auth_status",
        "gmail/list_unread",
        "gmail/search",
        "gmail/read_metadata",
        "calendar/search",
        "calendar/list_upcoming",
        "sheets/read_range",
    }


def test_google_workspace_tools_are_read_only() -> None:
    descriptor = json.loads(TOOLPACK.read_text(encoding="utf-8"))
    assert descriptor["risk_class"] == "read_only_external_api"
    assert descriptor["health_supported"] is True
    for tool in descriptor["tools"]:
        assert tool["side_effect"] is False
        assert tool["requires_approval"] is False
        assert tool["allow_live"] is True
        assert tool["allow_live_side_effect"] is False
        assert tool["live_guardrail"] == "read_only_google_workspace"
        assert tool["output_type"]


def test_google_workspace_tools_have_required_arg_types() -> None:
    descriptor = json.loads(TOOLPACK.read_text(encoding="utf-8"))
    lookup = {tool["tool"]: tool for tool in descriptor["tools"]}
    assert lookup["gmail/list_unread"]["arg_types"] == {"max_results": "int"}
    assert lookup["gmail/search"]["arg_types"] == {"max_results": "int"}
    assert lookup["calendar/search"]["arg_types"] == {"days": "int", "max_results": "int"}
    assert lookup["calendar/list_upcoming"]["arg_types"] == {"days": "int", "max_results": "int"}
    assert lookup["sheets/read_range"]["arg_types"] == {"major_dimension": "str"}
