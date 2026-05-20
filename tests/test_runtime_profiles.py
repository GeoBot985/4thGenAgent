from __future__ import annotations

import importlib

import pytest


def _profile_module():
    return importlib.import_module("runtime.runtime_environment")


def test_default_profile_resolves_to_demo(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    module = _profile_module()
    monkeypatch.delenv("TASKFRAME_PROFILE", raising=False)
    monkeypatch.delenv("TASKFRAME_ENV", raising=False)
    monkeypatch.setattr(module, "RUNTIME_PROFILE_PATH", tmp_path / "runtime_profile.json", raising=False)

    assert module.resolve_runtime_profile_name() == "demo"
    assert module.load_runtime_profile()["profile"] == "demo"


def test_demo_blocks_live_reads_and_live_side_effects(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    module = _profile_module()
    monkeypatch.delenv("TASKFRAME_PROFILE", raising=False)
    monkeypatch.delenv("TASKFRAME_ENV", raising=False)
    monkeypatch.setattr(module, "RUNTIME_PROFILE_PATH", tmp_path / "runtime_profile.json", raising=False)

    profile = module.load_runtime_profile(profile_name="demo")

    with pytest.raises(module.RuntimeProfilePolicyError):
        module.assert_runtime_profile_allows_tool_execution(
            profile,
            "gmail/search",
            {
                "source": "external_toolpack",
                "toolpack_id": "google_workspace_readonly",
                "toolpack_classification": "optional",
                "side_effect": False,
                "allow_live": True,
                "allow_live_side_effect": False,
                "tool_class": "read",
            },
            dry_run=False,
            live_requested=True,
            operation="execute",
        )

    with pytest.raises(module.RuntimeProfilePolicyError):
        module.assert_runtime_profile_allows_tool_execution(
            profile,
            "g/send",
            {
                "source": "builtin",
                "toolpack_id": "",
                "toolpack_classification": "core",
                "side_effect": True,
                "allow_live": False,
                "allow_live_side_effect": False,
                "tool_class": "send",
            },
            dry_run=False,
            live_requested=True,
            operation="execute_pending_action",
        )


def test_pilot_allows_allowlisted_read_only_tools(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    module = _profile_module()
    monkeypatch.delenv("TASKFRAME_PROFILE", raising=False)
    monkeypatch.delenv("TASKFRAME_ENV", raising=False)
    monkeypatch.setattr(module, "RUNTIME_PROFILE_PATH", tmp_path / "runtime_profile.json", raising=False)

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


@pytest.mark.parametrize(
    "tool_key, tool_spec",
    [
        ("sheet/write", {"source": "builtin", "toolpack_id": "", "toolpack_classification": "core", "side_effect": True, "allow_live": False, "allow_live_side_effect": True, "tool_class": "write"}),
        ("g/send", {"source": "builtin", "toolpack_id": "", "toolpack_classification": "core", "side_effect": True, "allow_live": False, "allow_live_side_effect": False, "tool_class": "send"}),
        ("cal/remove", {"source": "builtin", "toolpack_id": "", "toolpack_classification": "core", "side_effect": True, "allow_live": False, "allow_live_side_effect": False, "tool_class": "delete"}),
        ("rpa/click", {"source": "external_toolpack", "toolpack_id": "rpa_google_messages", "toolpack_classification": "high_risk", "side_effect": True, "allow_live": False, "allow_live_side_effect": False, "tool_class": "rpa"}),
        ("custom/mutate", {"source": "external_toolpack", "toolpack_id": "mutator_pack", "toolpack_classification": "experimental", "side_effect": True, "allow_live": False, "allow_live_side_effect": False, "tool_class": "mutation"}),
    ],
)
def test_pilot_blocks_writes_sends_deletes_rpa_and_mutation_tools(monkeypatch: pytest.MonkeyPatch, tmp_path, tool_key: str, tool_spec: dict[str, object]) -> None:
    module = _profile_module()
    monkeypatch.delenv("TASKFRAME_PROFILE", raising=False)
    monkeypatch.delenv("TASKFRAME_ENV", raising=False)
    monkeypatch.setattr(module, "RUNTIME_PROFILE_PATH", tmp_path / "runtime_profile.json", raising=False)

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


def test_live_profile_is_reserved_without_explicit_override(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    module = _profile_module()
    monkeypatch.delenv("TASKFRAME_PROFILE", raising=False)
    monkeypatch.delenv("TASKFRAME_ENV", raising=False)
    monkeypatch.delenv("TASKFRAME_ENABLE_RESERVED_LIVE_PROFILE", raising=False)
    monkeypatch.setattr(module, "RUNTIME_PROFILE_PATH", tmp_path / "runtime_profile.json", raising=False)

    profile = module.load_runtime_profile(profile_name="live")
    assert profile["activation_blocked"] is True
    assert module.check_runtime_profile(profile)["ok"] is False
