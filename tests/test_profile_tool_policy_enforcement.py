from __future__ import annotations

import importlib

import pytest


def _module():
    return importlib.import_module("runtime.runtime_environment")


def test_pilot_allows_live_reads_only_for_allowlisted_read_only_tools() -> None:
    module = _module()
    profile = module.load_runtime_profile(profile_name="pilot")
    decision = module.assert_runtime_profile_allows_tool_execution(
        profile,
        "gmail/search",
        {
            "source": "external_toolpack",
            "toolpack_id": "google_workspace_readonly",
            "toolpack_classification": "optional",
            "side_effect": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "tool_class": "gmail",
        },
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    assert decision["ok"] is True

    with pytest.raises(module.RuntimeProfilePolicyError):
        module.assert_runtime_profile_allows_tool_execution(
            profile,
            "gmail/search",
            {
                "source": "external_toolpack",
                "toolpack_id": "unlisted_pack",
                "toolpack_classification": "optional",
                "side_effect": False,
                "allow_live": True,
                "allow_live_side_effect": False,
                "tool_class": "gmail",
            },
            dry_run=False,
            live_requested=True,
            operation="execute",
        )


@pytest.mark.parametrize(
    "tool_key, tool_spec",
    [
        ("sheet/write", {"source": "builtin", "toolpack_id": "", "toolpack_classification": "core", "side_effect": True, "allow_live": False, "allow_live_side_effect": True, "tool_class": "write"}),
        ("g/send", {"source": "builtin", "toolpack_id": "", "toolpack_classification": "core", "side_effect": True, "allow_live": False, "allow_live_side_effect": False, "tool_class": "send"}),
        ("cal/remove", {"source": "builtin", "toolpack_id": "", "toolpack_classification": "core", "side_effect": True, "allow_live": False, "allow_live_side_effect": False, "tool_class": "delete"}),
        ("rpa/click", {"source": "external_toolpack", "toolpack_id": "rpa_google_messages", "toolpack_classification": "high_risk", "side_effect": True, "allow_live": False, "allow_live_side_effect": False, "tool_class": "rpa"}),
        ("mutation/apply", {"source": "external_toolpack", "toolpack_id": "mutation_pack", "toolpack_classification": "experimental", "side_effect": True, "allow_live": False, "allow_live_side_effect": False, "tool_class": "mutation"}),
    ],
)
def test_pilot_blocks_writes_sends_deletes_rpa_and_mutation_tools(tool_key: str, tool_spec: dict[str, object]) -> None:
    module = _module()
    profile = module.load_runtime_profile(profile_name="pilot")

    with pytest.raises(module.RuntimeProfilePolicyError):
        module.assert_runtime_profile_allows_tool_execution(
            profile,
            tool_key,
            tool_spec,
            dry_run=False,
            live_requested=True,
            operation="execute_pending_action",
        )
