from __future__ import annotations

from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe
from runtime.tool_runner import ToolRunner


def _frame() -> object:
    manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
    frame = create_taskframe(manifest)
    frame.state = "RUNNING"
    return frame


def _action(tool: str = "sheet/write_rows", status: str = "APPROVED") -> dict[str, object]:
    namespace, action = tool.split("/", 1)
    return {
        "action_id": "pa_1",
        "step_id": "stage_write",
        "tool": tool,
        "namespace": namespace,
        "action": action,
        "output_alias": "sheet_rows",
        "args": {"rows": [["a", "b"]], "spreadsheet_id": "sheet-1", "range_name": "Sheet1!A1:B2"},
        "status": status,
        "side_effect": True,
        "requires_approval": True,
        "created_at": "2026-05-01T00:00:00Z",
    }


def test_pending_action_execution_rechecks_governance(monkeypatch) -> None:
    frame = _frame()
    action = _action()
    frame.pending_actions.append(action)
    monkeypatch.setattr(
        "runtime.tool_runner.get_tool_spec",
        lambda namespace, action_name: {
            "namespace": namespace,
            "action": action_name,
            "module": "tool_packs.core_reports.tools",
            "function": "report_generate",
            "side_effect": True,
            "requires_approval": True,
            "allow_live": False,
            "allow_live_side_effect": False,
            "live_guardrail": "blocked",
            "output_type": "sheet_write_rows_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
            "dry_run_executes": False,
            "source": "builtin",
            "toolpack_id": "",
            "toolpack_classification": "core",
        },
    )

    runner = ToolRunner(dry_run=True, environment="dev")
    result = runner.execute_pending_action(frame, action)

    assert result.ok is True
    assert action["status"] == "EXECUTED"
    assert action["governance"]["decision"] == "ALLOW"


def test_governance_blocked_pending_action_is_not_executed(monkeypatch) -> None:
    frame = _frame()
    action = _action(tool="gmail/search")
    frame.pending_actions.append(action)
    monkeypatch.setattr(
        "runtime.tool_runner.get_tool_spec",
        lambda namespace, action_name: {
            "namespace": namespace,
            "action": action_name,
            "module": "tool_packs.google_workspace.tools",
            "function": "gmail_search",
            "side_effect": True,
            "requires_approval": True,
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
            "toolpack_classification": "optional",
        },
    )

    runner = ToolRunner(dry_run=True, environment="release")
    result = runner.execute_pending_action(frame, action)

    assert result.ok is False
    assert action["status"] == "FAILED"
    assert not frame.executed_actions


def test_blocked_pending_action_status_becomes_failed(monkeypatch) -> None:
    frame = _frame()
    action = _action(tool="gmail/search")
    frame.pending_actions.append(action)
    monkeypatch.setattr(
        "runtime.tool_runner.get_tool_spec",
        lambda namespace, action_name: {
            "namespace": namespace,
            "action": action_name,
            "module": "tool_packs.google_workspace.tools",
            "function": "gmail_search",
            "side_effect": True,
            "requires_approval": True,
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
            "toolpack_classification": "optional",
        },
    )

    runner = ToolRunner(dry_run=True, environment="release")
    runner.execute_pending_action(frame, action)

    assert action["status"] == "FAILED"
    assert frame.state == "FAILED_EXECUTION"
    assert frame.audit[-1].event_type == "PENDING_ACTION_GOVERNANCE_BLOCKED"


def test_pending_action_records_governance_metadata(monkeypatch) -> None:
    frame = _frame()
    action = _action()
    frame.pending_actions.append(action)
    monkeypatch.setattr(
        "runtime.tool_runner.get_tool_spec",
        lambda namespace, action_name: {
            "namespace": namespace,
            "action": action_name,
            "module": "tool_packs.core_reports.tools",
            "function": "report_generate",
            "side_effect": True,
            "requires_approval": True,
            "allow_live": False,
            "allow_live_side_effect": False,
            "live_guardrail": "blocked",
            "output_type": "sheet_write_rows_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
            "dry_run_executes": False,
            "source": "builtin",
            "toolpack_id": "",
            "toolpack_classification": "core",
        },
    )

    runner = ToolRunner(dry_run=True, environment="dev")
    runner.execute_pending_action(frame, action)

    assert action["governance"]["toolpack_id"] == ""
    assert frame.executed_actions[0]["governance"]["decision"] == "ALLOW"


def test_dry_run_approved_action_allowed_when_policy_allows(monkeypatch) -> None:
    frame = _frame()
    action = _action()
    frame.pending_actions.append(action)
    monkeypatch.setattr(
        "runtime.tool_runner.get_tool_spec",
        lambda namespace, action_name: {
            "namespace": namespace,
            "action": action_name,
            "module": "tool_packs.core_reports.tools",
            "function": "report_generate",
            "side_effect": True,
            "requires_approval": True,
            "allow_live": False,
            "allow_live_side_effect": False,
            "live_guardrail": "blocked",
            "output_type": "sheet_write_rows_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
            "dry_run_executes": False,
            "source": "builtin",
            "toolpack_id": "",
            "toolpack_classification": "core",
        },
    )

    runner = ToolRunner(dry_run=True, environment="dev")
    result = runner.execute_pending_action(frame, action)

    assert result.ok is True
    assert action["status"] == "EXECUTED"
