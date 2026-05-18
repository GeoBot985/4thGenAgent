from __future__ import annotations

from runtime.tool_governance import evaluate_tool_governance


def test_core_tool_allowed_in_demo() -> None:
    result = evaluate_tool_governance(
        "core/read",
        {
            "source": "builtin",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "",
            "toolpack_classification": "core",
        },
        environment="demo",
        dry_run=True,
        live_requested=False,
        operation="execute",
    )
    assert result["ok"] is True
    assert result["decision"] == "ALLOW"


def test_optional_enabled_tool_allowed_in_dev() -> None:
    result = evaluate_tool_governance(
        "gmail/search",
        {
            "source": "external_toolpack",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "google_workspace",
            "toolpack_classification": "optional",
        },
        environment="dev",
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    assert result["ok"] is True
    assert result["decision"] == "ALLOW"


def test_optional_not_enabled_tool_blocked() -> None:
    result = evaluate_tool_governance(
        "google_workspace/read",
        {
            "source": "external_toolpack",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "missing_pack",
            "toolpack_classification": "optional",
        },
        environment="dev",
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    assert result["ok"] is False
    assert result["decision"] == "BLOCK"


def test_blocked_toolpack_blocked_in_all_envs() -> None:
    result = evaluate_tool_governance(
        "blocked/read",
        {
            "source": "external_toolpack",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "",
            "toolpack_classification": "blocked",
        },
        environment="dev",
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    assert result["ok"] is False
    assert result["decision"] == "BLOCK"


def test_high_risk_toolpack_blocked_in_demo() -> None:
    result = evaluate_tool_governance(
        "messages/extract_absa_transactions",
        {
            "source": "external_toolpack",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "",
            "toolpack_classification": "high_risk",
        },
        environment="demo",
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    assert result["ok"] is False
    assert result["decision"] == "BLOCK"


def test_high_risk_toolpack_blocked_in_release() -> None:
    result = evaluate_tool_governance(
        "messages/extract_absa_transactions",
        {
            "source": "external_toolpack",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "",
            "toolpack_classification": "high_risk",
        },
        environment="release",
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    assert result["ok"] is False
    assert result["decision"] == "BLOCK"


def test_experimental_toolpack_blocked_in_release() -> None:
    result = evaluate_tool_governance(
        "pack/inspect",
        {
            "source": "external_toolpack",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "",
            "toolpack_classification": "experimental",
        },
        environment="release",
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    assert result["ok"] is False
    assert result["decision"] == "BLOCK"


def test_unknown_toolpack_policy_blocks_outside_dev() -> None:
    result = evaluate_tool_governance(
        "unknown/read",
        {
            "source": "external_toolpack",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "unknown_pack",
            "toolpack_classification": "unknown",
        },
        environment="release",
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    assert result["ok"] is False
    assert result["decision"] == "BLOCK"


def test_live_side_effect_without_approval_blocked() -> None:
    result = evaluate_tool_governance(
        "sheet/write_rows",
        {
            "source": "builtin",
            "side_effect": True,
            "requires_approval": False,
            "allow_live": False,
            "allow_live_side_effect": False,
            "toolpack_id": "",
            "toolpack_classification": "core",
        },
        environment="dev",
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    assert result["ok"] is False
    assert result["decision"] == "BLOCK"
