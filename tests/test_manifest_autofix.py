from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.manifest_autofix import (
    apply_manifest_fix_preview,
    apply_manifest_fix_to_file,
    propose_manifest_fixes,
    write_autofix_report,
)
from src.manifest_template_generator import build_manifest_from_template


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_manifest(manifest_id: str = "test.valid") -> dict:
    return build_manifest_from_template("manual_read_tool", manifest_id, "Test Valid")


def _manifest_with_completion_mismatch(alias_in_step: str = "result", alias_in_completion: str = "reply") -> dict:
    """Single step that outputs `alias_in_step`, completion expects `alias_in_completion`."""
    return {
        "manifest_id": "test.completion_mismatch",
        "name": "Completion Mismatch Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {"id": "read_data", "command": f"[t:g/check -> {alias_in_step}] max_results=5"},
        ],
        "validations": [{"id": "no_errors", "type": "no_errors"}],
        "completion": {"success_outputs": [alias_in_completion]},
        "live_execution": {"enabled": False, "requires_approval": True},
    }


def _manifest_with_validation_mismatch(
    step_alias: str = "result",
    val_output: str = "reply",
) -> dict:
    return {
        "manifest_id": "test.val_mismatch",
        "name": "Validation Mismatch Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {"id": "read_data", "command": f"[t:g/check -> {step_alias}] max_results=5"},
        ],
        "validations": [
            {"id": "reply_exists", "type": "output_exists", "output": val_output},
        ],
        "completion": {"success_outputs": [step_alias]},
        "live_execution": {"enabled": False, "requires_approval": True},
    }


def _manifest_empty_completion(alias: str = "result") -> dict:
    return {
        "manifest_id": "test.empty_completion",
        "name": "Empty Completion Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {"id": "read_data", "command": f"[t:g/check -> {alias}] max_results=5"},
        ],
        "validations": [{"id": "no_errors", "type": "no_errors"}],
        "completion": {},
        "live_execution": {"enabled": False, "requires_approval": True},
    }


def _manifest_with_unused_input(unused: str = "extra") -> dict:
    return {
        "manifest_id": "test.unused_input",
        "name": "Unused Input Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [unused],
        "steps": [
            {"id": "read_data", "command": "[t:g/check -> result] max_results=5"},
        ],
        "validations": [{"id": "no_errors", "type": "no_errors"}],
        "completion": {"success_outputs": ["result"], "acceptable_empty_outputs": ["result"]},
        "live_execution": {"enabled": False, "requires_approval": True},
    }


def _manifest_with_undeclared_input(input_name: str = "message") -> dict:
    return {
        "manifest_id": "test.undeclared_input",
        "name": "Undeclared Input Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {"id": "read_data", "command": f"[t:g/check -> result] query=$inputs.{input_name}"},
        ],
        "validations": [{"id": "no_errors", "type": "no_errors"}],
        "completion": {"success_outputs": ["result"], "acceptable_empty_outputs": ["result"]},
        "live_execution": {"enabled": False, "requires_approval": True},
    }


def _manifest_with_live_execution() -> dict:
    return {
        "manifest_id": "test.live_exec",
        "name": "Live Exec Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {"id": "read_data", "command": "[t:g/check -> result] max_results=5"},
        ],
        "validations": [{"id": "no_errors", "type": "no_errors"}],
        "completion": {"success_outputs": ["result"], "acceptable_empty_outputs": ["result"]},
        "live_execution": {"enabled": True, "requires_approval": True},
    }


def _manifest_with_duplicate_step_id() -> dict:
    return {
        "manifest_id": "test.dup_step",
        "name": "Duplicate Step Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {"id": "read_data", "command": "[t:g/check -> result] max_results=5"},
            {"id": "read_data", "command": "[t:g/check -> result2] max_results=3"},
        ],
        "validations": [{"id": "no_errors", "type": "no_errors"}],
        "completion": {"success_outputs": ["result"], "acceptable_empty_outputs": ["result"]},
        "live_execution": {"enabled": False, "requires_approval": True},
    }


def _manifest_with_unknown_tool() -> dict:
    return {
        "manifest_id": "test.unknown_tool",
        "name": "Unknown Tool Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {"id": "read_data", "command": "[t:g/check -> result] max_results=5"},
        ],
        "validations": [{"id": "no_errors", "type": "no_errors"}],
        "completion": {"success_outputs": ["result"], "acceptable_empty_outputs": ["result"]},
        "live_execution": {"enabled": False, "requires_approval": True},
    }


# ---------------------------------------------------------------------------
# test_propose_no_supported_fixes_for_valid_manifest
# ---------------------------------------------------------------------------


def test_propose_no_supported_fixes_for_valid_manifest() -> None:
    manifest = _valid_manifest("test.no_fixes")
    result = propose_manifest_fixes(manifest)
    assert result["ok"] is True
    assert result["supported_count"] == 0
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    assert proposed == []


# ---------------------------------------------------------------------------
# test_propose_completion_output_mismatch_single_alias
# ---------------------------------------------------------------------------


def test_propose_completion_output_mismatch_single_alias() -> None:
    manifest = _manifest_with_completion_mismatch(alias_in_step="result", alias_in_completion="reply")
    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    assert any(p["finding_id"] == "completion_output_missing" for p in proposed)
    fix = next(p for p in proposed if p["finding_id"] == "completion_output_missing")
    assert fix["risk"] == "low"
    assert fix["confidence"] == "high"
    assert len(fix["patches"]) >= 1
    patch = fix["patches"][0]
    assert patch["op"] == "replace"
    assert patch["old_value"] == "reply"
    assert patch["new_value"] == "result"


# ---------------------------------------------------------------------------
# test_no_completion_output_patch_when_multiple_aliases
# ---------------------------------------------------------------------------


def test_no_completion_output_patch_when_multiple_aliases() -> None:
    manifest = {
        "manifest_id": "test.multi_alias",
        "name": "Multi Alias",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {"id": "step_a", "command": "[t:g/check -> result_a] max_results=5"},
            {"id": "step_b", "command": "[t:g/check -> result_b] max_results=5"},
        ],
        "validations": [{"id": "no_errors", "type": "no_errors"}],
        "completion": {"success_outputs": ["wrong_alias"]},
        "live_execution": {"enabled": False, "requires_approval": True},
    }
    result = propose_manifest_fixes(manifest)
    completion_proposals = [
        p for p in result["proposals"] if p["finding_id"] == "completion_output_missing"
    ]
    for p in completion_proposals:
        assert p["status"] == "NOT_SUPPORTED"


# ---------------------------------------------------------------------------
# test_apply_preview_does_not_mutate_original_manifest
# ---------------------------------------------------------------------------


def test_apply_preview_does_not_mutate_original_manifest() -> None:
    manifest = _manifest_with_completion_mismatch()
    original_copy = json.loads(json.dumps(manifest))

    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    assert proposed, "Expected at least one PROPOSED fix"

    preview = apply_manifest_fix_preview(manifest, proposed[0])
    assert preview["ok"] is True
    assert manifest == original_copy, "Original manifest was mutated"


# ---------------------------------------------------------------------------
# test_apply_preview_replaces_completion_output
# ---------------------------------------------------------------------------


def test_apply_preview_replaces_completion_output() -> None:
    manifest = _manifest_with_completion_mismatch(alias_in_step="result", alias_in_completion="reply")
    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    fix = next(p for p in proposed if p["finding_id"] == "completion_output_missing")

    preview = apply_manifest_fix_preview(manifest, fix)
    assert preview["ok"] is True
    assert preview["status"] == "PREVIEW_READY"
    patched = preview["manifest"]
    assert patched["completion"]["success_outputs"][0] == "result"
    assert "before_json" in preview
    assert "after_json" in preview
    assert preview["diff"]  # non-empty diff


# ---------------------------------------------------------------------------
# test_propose_validation_output_mismatch_single_alias
# ---------------------------------------------------------------------------


def test_propose_validation_output_mismatch_single_alias() -> None:
    manifest = _manifest_with_validation_mismatch(step_alias="result", val_output="reply")
    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    val_fix = next(
        (p for p in proposed if p["finding_id"] in ("validation_output_missing", "validation_references_missing_output")),
        None,
    )
    assert val_fix is not None, f"Expected validation output fix, got: {[p['finding_id'] for p in proposed]}"
    assert val_fix["risk"] == "low"
    patch = val_fix["patches"][0]
    assert patch["op"] == "replace"
    assert patch["old_value"] == "reply"
    assert patch["new_value"] == "result"


# ---------------------------------------------------------------------------
# test_propose_missing_acceptable_empty_outputs_adds_list
# ---------------------------------------------------------------------------


def test_propose_missing_acceptable_empty_outputs_adds_list() -> None:
    manifest = _manifest_empty_completion(alias="result")
    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    fix = next(
        (p for p in proposed if p["finding_id"] == "completion_empty_without_acceptable_empty"),
        None,
    )
    assert fix is not None, "Expected completion_empty_without_acceptable_empty proposal"
    patch = next(p for p in fix["patches"] if p["path"] == "/completion/acceptable_empty_outputs")
    assert patch["op"] == "add"
    assert "result" in patch["new_value"]


# ---------------------------------------------------------------------------
# test_propose_append_missing_acceptable_empty_output
# ---------------------------------------------------------------------------


def test_propose_append_missing_acceptable_empty_output() -> None:
    manifest = _manifest_empty_completion(alias="result")
    manifest["completion"]["acceptable_empty_outputs"] = []  # exists but empty
    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    fix = next(
        (p for p in proposed if p["finding_id"] == "completion_empty_without_acceptable_empty"),
        None,
    )
    assert fix is not None
    patch = fix["patches"][0]
    assert patch["path"] == "/completion/acceptable_empty_outputs/-"
    assert patch["op"] == "add"
    assert patch["new_value"] == "result"


# ---------------------------------------------------------------------------
# test_propose_remove_unused_simple_input
# ---------------------------------------------------------------------------


def test_propose_remove_unused_simple_input() -> None:
    manifest = _manifest_with_unused_input(unused="extra")
    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    fix = next(
        (p for p in proposed if p["finding_id"] == "input_declared_but_not_used"),
        None,
    )
    assert fix is not None
    patch = fix["patches"][0]
    assert patch["op"] == "remove"
    assert patch["old_value"] == "extra"


# ---------------------------------------------------------------------------
# test_does_not_remove_unused_object_input
# ---------------------------------------------------------------------------


def test_does_not_remove_unused_object_input() -> None:
    manifest = {
        "manifest_id": "test.obj_input",
        "name": "Object Input Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [{"name": "extra", "required": False}],
        "steps": [
            {"id": "read_data", "command": "[t:g/check -> result] max_results=5"},
        ],
        "validations": [{"id": "no_errors", "type": "no_errors"}],
        "completion": {"success_outputs": ["result"], "acceptable_empty_outputs": ["result"]},
        "live_execution": {"enabled": False, "requires_approval": True},
    }
    result = propose_manifest_fixes(manifest)
    obj_fix = next(
        (p for p in result["proposals"] if p["finding_id"] == "input_declared_but_not_used"),
        None,
    )
    # Object inputs should be NOT_SUPPORTED
    if obj_fix is not None:
        assert obj_fix["status"] == "NOT_SUPPORTED"


# ---------------------------------------------------------------------------
# test_propose_add_missing_declared_input
# ---------------------------------------------------------------------------


def test_propose_add_missing_declared_input() -> None:
    manifest = _manifest_with_undeclared_input(input_name="message")
    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    fix = next(
        (p for p in proposed if p["finding_id"] == "input_used_but_not_declared"),
        None,
    )
    assert fix is not None
    add_patch = next(
        (p for p in fix["patches"] if p["op"] == "add" and p.get("new_value") == "message"),
        None,
    )
    assert add_patch is not None


# ---------------------------------------------------------------------------
# test_propose_add_inputs_list_when_missing
# ---------------------------------------------------------------------------


def test_propose_add_inputs_list_when_missing() -> None:
    manifest = _manifest_with_undeclared_input(input_name="message")
    del manifest["inputs"]  # Remove inputs entirely
    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    fix = next(
        (p for p in proposed if p["finding_id"] == "input_used_but_not_declared"),
        None,
    )
    assert fix is not None
    paths = [p["path"] for p in fix["patches"]]
    assert "/inputs" in paths  # creates the list first
    assert "/inputs/-" in paths  # then appends


# ---------------------------------------------------------------------------
# test_propose_disable_live_execution
# ---------------------------------------------------------------------------


def test_propose_disable_live_execution() -> None:
    manifest = _manifest_with_live_execution()
    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    fix = next(
        (p for p in proposed if p["finding_id"] == "live_execution_enabled"),
        None,
    )
    assert fix is not None
    patch = fix["patches"][0]
    assert patch["op"] == "replace"
    assert patch["path"] == "/live_execution/enabled"
    assert patch["old_value"] is True
    assert patch["new_value"] is False


# ---------------------------------------------------------------------------
# test_propose_duplicate_step_id_rename
# ---------------------------------------------------------------------------


def test_propose_duplicate_step_id_rename() -> None:
    manifest = _manifest_with_duplicate_step_id()
    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    fix = next(
        (p for p in proposed if p["finding_id"] == "duplicate_step_id"),
        None,
    )
    assert fix is not None
    patch = fix["patches"][0]
    assert patch["op"] == "replace"
    assert patch["old_value"] == "read_data"
    assert patch["new_value"] == "read_data_2"


# ---------------------------------------------------------------------------
# test_duplicate_step_id_with_references_not_supported
# ---------------------------------------------------------------------------


def test_duplicate_step_id_with_references_not_supported() -> None:
    manifest = {
        "manifest_id": "test.dup_ref",
        "name": "Dup With Refs",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {"id": "read_data", "command": "[t:g/check -> result] max_results=5"},
            {"id": "read_data", "command": "[t:g/check -> result2] max_results=3", "when": "read_data.ok"},
        ],
        "validations": [
            {"id": "step_done", "type": "step_completed", "step_id": "read_data"},
        ],
        "completion": {"success_outputs": ["result"], "acceptable_empty_outputs": ["result"]},
        "live_execution": {"enabled": False, "requires_approval": True},
    }
    result = propose_manifest_fixes(manifest)
    dup_proposals = [p for p in result["proposals"] if p["finding_id"] == "duplicate_step_id"]
    assert dup_proposals, "Expected at least one duplicate_step_id proposal"
    for p in dup_proposals:
        assert p["status"] == "NOT_SUPPORTED"


# ---------------------------------------------------------------------------
# test_unknown_tool_returns_not_supported
# ---------------------------------------------------------------------------


def test_unknown_tool_returns_not_supported() -> None:
    from src.manifest_authoring_feedback import explain_manifest_failure
    finding = {
        "id": "unknown_tool",
        "severity": "error",
        "location": "steps[0].command",
        "message": "Unknown tool in command.",
        "suggested_fix": "Use a registered tool.",
        "source": "smoke_result",
    }
    guidance = {
        "ok": True,
        "status": "HAS_FINDINGS",
        "severity": "error",
        "summary": "Unknown tool",
        "findings": [finding],
        "next_action": "Fix the tool.",
    }
    manifest = _manifest_with_unknown_tool()
    result = propose_manifest_fixes(manifest, guidance=guidance)
    not_supported = [p for p in result["proposals"] if p["finding_id"] == "unknown_tool"]
    assert not_supported
    assert all(p["status"] == "NOT_SUPPORTED" for p in not_supported)


# ---------------------------------------------------------------------------
# test_command_invalid_returns_not_supported
# ---------------------------------------------------------------------------


def test_command_invalid_returns_not_supported() -> None:
    finding = {
        "id": "command_invalid",
        "severity": "error",
        "location": "steps[0].command",
        "message": "Invalid command.",
        "suggested_fix": "Fix syntax.",
        "source": "smoke_result",
    }
    guidance = {
        "ok": True,
        "status": "HAS_FINDINGS",
        "severity": "error",
        "summary": "Invalid command",
        "findings": [finding],
        "next_action": "Fix syntax.",
    }
    result = propose_manifest_fixes(_valid_manifest("test.cmd_invalid"), guidance=guidance)
    proposals = [p for p in result["proposals"] if p["finding_id"] == "command_invalid"]
    assert proposals
    assert all(p["status"] == "NOT_SUPPORTED" for p in proposals)


# ---------------------------------------------------------------------------
# test_apply_to_file_requires_approval
# ---------------------------------------------------------------------------


def test_apply_to_file_requires_approval(tmp_path: Path) -> None:
    manifest = _manifest_with_completion_mismatch()
    manifest_file = tmp_path / "test.manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    assert proposed

    apply_result = apply_manifest_fix_to_file(manifest_file, proposed[0], approved=False)
    assert apply_result["ok"] is False
    assert apply_result["status"] == "APPROVAL_REQUIRED"
    # File should be unchanged
    on_disk = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert on_disk == manifest


# ---------------------------------------------------------------------------
# test_apply_to_file_checks_old_value_matches
# ---------------------------------------------------------------------------


def test_apply_to_file_checks_old_value_matches(tmp_path: Path) -> None:
    manifest = _manifest_with_completion_mismatch()
    manifest_file = tmp_path / "test.manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    fix = next(p for p in proposed if p["finding_id"] == "completion_output_missing")

    # Tamper with the file so old_value no longer matches
    tampered = json.loads(manifest_file.read_text(encoding="utf-8"))
    tampered["completion"]["success_outputs"][0] = "something_else"
    manifest_file.write_text(json.dumps(tampered, indent=2), encoding="utf-8")

    apply_result = apply_manifest_fix_to_file(manifest_file, fix, approved=True)
    assert apply_result["ok"] is False
    assert apply_result["status"] == "STALE"


# ---------------------------------------------------------------------------
# test_apply_to_file_validates_patched_manifest
# ---------------------------------------------------------------------------


def test_apply_to_file_validates_patched_manifest(tmp_path: Path) -> None:
    manifest = _manifest_with_completion_mismatch()
    manifest_file = tmp_path / "test.manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = propose_manifest_fixes(manifest)
    proposed = [p for p in result["proposals"] if p["status"] == "PROPOSED"]
    fix = next(p for p in proposed if p["finding_id"] == "completion_output_missing")

    apply_result = apply_manifest_fix_to_file(manifest_file, fix, approved=True)
    assert apply_result["ok"] is True
    assert "validation" in apply_result
    val = apply_result["validation"]
    assert "ok" in val
    assert "errors" in val


# ---------------------------------------------------------------------------
# test_write_autofix_report_creates_json_and_markdown
# ---------------------------------------------------------------------------


def test_write_autofix_report_creates_json_and_markdown(tmp_path: Path) -> None:
    manifest = _manifest_with_completion_mismatch()
    result = propose_manifest_fixes(manifest)
    report = write_autofix_report(result, runtime_data_dir=tmp_path)
    assert report["ok"] is True
    assert Path(report["json_path"]).exists()
    assert Path(report["markdown_path"]).exists()
    md_text = Path(report["markdown_path"]).read_text(encoding="utf-8")
    assert "Manifest Auto-Fix Preview Report" in md_text
    json_data = json.loads(Path(report["json_path"]).read_text(encoding="utf-8"))
    assert "proposals" in json_data


# ---------------------------------------------------------------------------
# test_proposals_are_stably_sorted
# ---------------------------------------------------------------------------


def test_proposals_are_stably_sorted() -> None:
    manifest = {
        "manifest_id": "test.sort",
        "name": "Sort Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {"id": "read_data", "command": "[t:g/check -> result] max_results=5"},
        ],
        "validations": [{"id": "no_errors", "type": "no_errors"}],
        "completion": {"success_outputs": ["wrong"]},
        "live_execution": {"enabled": True, "requires_approval": True},
    }
    result = propose_manifest_fixes(manifest)
    proposals = result["proposals"]
    statuses = [p["status"] for p in proposals]
    proposed_idx = [i for i, s in enumerate(statuses) if s == "PROPOSED"]
    not_supported_idx = [i for i, s in enumerate(statuses) if s == "NOT_SUPPORTED"]
    # All PROPOSED come before all NOT_SUPPORTED
    if proposed_idx and not_supported_idx:
        assert max(proposed_idx) < min(not_supported_idx)


# ---------------------------------------------------------------------------
# test_only_low_risk_proposed_fixes_are_applyable
# ---------------------------------------------------------------------------


def test_only_low_risk_proposed_fixes_are_applyable(tmp_path: Path) -> None:
    manifest = _manifest_with_completion_mismatch()
    result = propose_manifest_fixes(manifest)

    for proposal in result["proposals"]:
        if proposal["status"] == "NOT_SUPPORTED":
            # NOT_SUPPORTED proposals must NOT be applyable (approved or not)
            manifest_file = tmp_path / f"test_{proposal['fix_id']}.json"
            manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            apply_result = apply_manifest_fix_to_file(manifest_file, proposal, approved=True)
            assert apply_result["ok"] is False
        elif proposal["status"] == "PROPOSED":
            assert proposal["risk"] == "low"
