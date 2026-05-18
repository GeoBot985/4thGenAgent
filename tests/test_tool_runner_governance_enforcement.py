from __future__ import annotations

from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe
from runtime.tool_runner import ToolRunner


def _make_frame_and_step() -> tuple[object, object]:
    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.state = "RUNNING"
    step = frame.steps[0]
    step.command = "[t:customer/read -> customer]"
    step.namespace = "customer"
    step.action = "read"
    step.output_alias = "customer"
    step.kind = "tool"
    return frame, step


def test_tool_runner_blocks_disabled_external_tool(monkeypatch) -> None:
    frame, step = _make_frame_and_step()

    monkeypatch.setattr(
        "runtime.tool_runner.get_tool_spec",
        lambda namespace, action: {
            "namespace": namespace,
            "action": action,
            "module": "tool_packs.google_workspace.tools",
            "function": "gmail_search",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "live_guardrail": "read_only_google_workspace",
            "output_type": "gmail_message_metadata_list",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
            "dry_run_executes": False,
            "source": "external_toolpack",
            "toolpack_id": "google_workspace",
            "toolpack_name": "Google Workspace Read-Only Tool Pack",
            "toolpack_version": "1.0.0",
            "toolpack_path": "tool_packs/google_workspace/toolpack.json",
            "toolpack_classification": "optional",
        },
    )

    runner = ToolRunner(dry_run=False, environment="release")
    result = runner.run_step(frame, step)

    assert result.ok is False
    assert result.type == "tool_governance_blocked"
    assert step.status == "FAILED"
    assert frame.state == "FAILED_EXECUTION"
    assert any(event.event_type == "TOOL_GOVERNANCE_BLOCKED" for event in frame.audit)
    assert frame.tool_calls[0]["result_type"] == "tool_governance_blocked"


def test_tool_runner_records_governance_block_audit_event(monkeypatch) -> None:
    frame, step = _make_frame_and_step()
    monkeypatch.setattr(
        "runtime.tool_runner.get_tool_spec",
        lambda namespace, action: {
            "namespace": namespace,
            "action": action,
            "module": "tool_packs.google_workspace.tools",
            "function": "gmail_search",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "live_guardrail": "read_only_google_workspace",
            "output_type": "gmail_message_metadata_list",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
            "dry_run_executes": False,
            "source": "external_toolpack",
            "toolpack_id": "google_workspace",
            "toolpack_name": "Google Workspace Read-Only Tool Pack",
            "toolpack_version": "1.0.0",
            "toolpack_path": "tool_packs/google_workspace/toolpack.json",
            "toolpack_classification": "optional",
        },
    )

    runner = ToolRunner(dry_run=False, environment="release")
    runner.run_step(frame, step)

    assert any(event.event_type == "TOOL_GOVERNANCE_BLOCKED" for event in frame.audit)


def test_tool_runner_returns_tool_governance_blocked_result(monkeypatch) -> None:
    frame, step = _make_frame_and_step()
    monkeypatch.setattr(
        "runtime.tool_runner.get_tool_spec",
        lambda namespace, action: {
            "namespace": namespace,
            "action": action,
            "module": "tool_packs.google_workspace.tools",
            "function": "gmail_search",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "live_guardrail": "read_only_google_workspace",
            "output_type": "gmail_message_metadata_list",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
            "dry_run_executes": False,
            "source": "external_toolpack",
            "toolpack_id": "google_workspace",
            "toolpack_name": "Google Workspace Read-Only Tool Pack",
            "toolpack_version": "1.0.0",
            "toolpack_path": "tool_packs/google_workspace/toolpack.json",
            "toolpack_classification": "optional",
        },
    )

    runner = ToolRunner(dry_run=False, environment="release")
    result = runner.run_step(frame, step)

    assert result.type == "tool_governance_blocked"
    assert result.error == "Tool blocked by governance policy."
    assert result.data["tool"] == "customer/read"


def test_tool_runner_allows_enabled_read_only_external_tool(monkeypatch) -> None:
    frame, step = _make_frame_and_step()
    monkeypatch.setattr(
        "runtime.tool_runner.get_tool_spec",
        lambda namespace, action: {
            "namespace": namespace,
            "action": action,
            "module": "tool_packs.google_workspace.tools",
            "function": "gmail_search",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "live_guardrail": "read_only_google_workspace",
            "output_type": "gmail_message_metadata_list",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
            "dry_run_executes": False,
            "source": "external_toolpack",
            "toolpack_id": "google_workspace",
            "toolpack_name": "Google Workspace Read-Only Tool Pack",
            "toolpack_version": "1.0.0",
            "toolpack_path": "tool_packs/google_workspace/toolpack.json",
            "toolpack_classification": "optional",
        },
    )

    runner = ToolRunner(dry_run=True, environment="dev")
    result = runner.run_step(frame, step)

    assert result.ok is True
    assert result.type == "gmail_message_metadata_list"
    assert frame.state in {"RUNNING", "WAITING_FOR_EXECUTE"}


def test_tool_runner_allows_core_builtin_tool(monkeypatch) -> None:
    frame, step = _make_frame_and_step()
    monkeypatch.setattr(
        "runtime.tool_runner.get_tool_spec",
        lambda namespace, action: {
            "namespace": namespace,
            "action": action,
            "module": "tool_packs.core_business.tools",
            "function": "customer_read",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "live_guardrail": "blocked",
            "output_type": "customer_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
            "dry_run_executes": False,
            "source": "builtin",
            "toolpack_id": "",
            "toolpack_name": "",
            "toolpack_version": "",
            "toolpack_path": "",
            "toolpack_classification": "core",
        },
    )

    runner = ToolRunner(dry_run=True, environment="demo")
    result = runner.run_step(frame, step)

    assert result.ok is True
    assert result.type == "customer_result"
    assert step.status == "COMPLETED"
