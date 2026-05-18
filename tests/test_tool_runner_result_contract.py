from __future__ import annotations

from dataclasses import dataclass

from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe
from runtime.tool_runner import ToolRunner, normalize_tool_result


@dataclass
class WorkspaceResultLike:
    ok: bool
    action: str
    output: str = ""
    error: str = ""
    payload: dict | None = None


def _tool_spec() -> dict:
    return {
        "namespace": "fake",
        "action": "read",
        "module": "fake.module",
        "function": "fake_read",
        "side_effect": False,
        "requires_approval": False,
        "allow_live": True,
        "allow_live_side_effect": False,
        "live_guardrail": "blocked",
        "output_type": "fake_read_result",
        "required_args": [],
        "optional_args": [],
        "arg_types": {},
        "source": "external_toolpack",
    }


def test_workspace_result_gets_canonical_evidence() -> None:
    result = normalize_tool_result(
        WorkspaceResultLike(ok=True, action="fake_read", output="ok", payload={"json": [1]}),
        "fake/read",
        _tool_spec(),
        {},
        dry_run=False,
        output_alias="fake_output",
    )

    assert result.ok is True
    assert isinstance(result.evidence, dict)
    assert result.evidence["tool"] == "fake/read"
    assert result.evidence["mode"] == "live"
    assert result.evidence["output_ref"] == "fake_output"
    assert "workspace_result_normalized" in result.metadata["warnings"]


def test_plain_dict_result_gets_wrapped_with_evidence() -> None:
    result = normalize_tool_result({"value": 1}, "fake/read", _tool_spec(), {}, dry_run=False, output_alias="fake_output")

    assert result.ok is True
    assert result.data == {"value": 1}
    assert isinstance(result.evidence, dict)
    assert result.evidence["output_ref"] == "fake_output"
    assert "plain_dict_normalized" in result.metadata["warnings"]


def test_scalar_result_gets_wrapped_with_evidence_warning() -> None:
    result = normalize_tool_result("hello", "fake/read", _tool_spec(), {}, dry_run=False, output_alias="fake_output")

    assert result.ok is True
    assert result.data == "hello"
    assert isinstance(result.evidence, dict)
    assert result.evidence["output_ref"] == "fake_output"
    assert any(warning.endswith("_normalized") for warning in result.metadata["warnings"])


def test_tool_call_record_contains_evidence_ref() -> None:
    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.state = "RUNNING"

    runner = ToolRunner(dry_run=True)
    result = runner.run_step(frame, frame.steps[0])

    assert result.ok is True
    assert frame.tool_calls
    tool_call = frame.tool_calls[0]
    assert tool_call["tool"] == "g/check"
    assert tool_call["evidence_ref"]
    assert tool_call["input_summary"]["arg_count"] >= 0
    assert tool_call["mode"] == "dry_run"
    assert tool_call["source"]


def test_pending_action_execution_records_evidence() -> None:
    manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
    frame = create_taskframe(manifest)
    frame.state = "RUNNING"

    runner = ToolRunner(dry_run=True)
    staged = runner.run_step(frame, frame.steps[0])
    assert staged.ok is True
    assert frame.pending_actions

    pending_action = frame.pending_actions[0]
    pending_action["status"] = "APPROVED"
    executed = runner.execute_pending_action(frame, pending_action)

    assert executed.ok is True
    assert isinstance(executed.evidence, dict)
    assert executed.evidence
    assert frame.tool_calls
    assert frame.tool_calls[-1]["evidence_ref"]
