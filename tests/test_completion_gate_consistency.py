"""Spec 107 — Completion Gate Consistency Pack.

Regression tests ensuring every terminal TaskFrame ends with a canonical
completion_gate_result matching the spec's state/outcome matrix.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.completion_gate import (
    OUTCOME_COMPLETION_REQUIREMENT_FAILED,
    OUTCOME_DRY_RUN_EXECUTED,
    OUTCOME_EXECUTION_FAILED,
    OUTCOME_LIVE_EXECUTION_BLOCKED,
    OUTCOME_PENDING_APPROVAL,
    OUTCOME_PENDING_ACTION_REJECTED,
    OUTCOME_SUCCESS_NO_DATA,
    OUTCOME_SUCCESS_WITH_DATA,
    OUTCOME_VALIDATION_FAILED,
    apply_completion_result,
    evaluate_completion,
)
from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "completion_gate"

# ---------------------------------------------------------------------------
# Canonical key set required on every completion_gate_result
# ---------------------------------------------------------------------------

CANONICAL_KEYS = {
    "ok",
    "status",
    "outcome",
    "final_state",
    "message",
    "reason_code",
    "required_outputs",
    "missing_outputs",
    "required_pending_actions",
    "missing_pending_actions",
    "required_executed_actions",
    "missing_executed_actions",
    "validation_summary",
    "pending_action_summary",
    "evidence_refs",
    "error_refs",
    "metadata",
}

PENDING_ACTION_SUMMARY_KEYS = {
    "pending_approval",
    "approved",
    "executing",
    "executed",
    "rejected",
    "failed",
}

VALIDATION_SUMMARY_KEYS = {"passed", "failed", "warnings"}


def _load_fixture(name: str):
    path = FIXTURE_DIR / name
    manifest = load_manifest(path)
    frame = create_taskframe(manifest)
    return manifest, frame


def _make_pending_action(output_alias: str, status: str = "PENDING_APPROVAL") -> dict:
    return {
        "action_id": f"pa_{output_alias}",
        "step_id": "stage_action",
        "tool": "test/echo",
        "namespace": "test",
        "action": "echo",
        "output_alias": output_alias,
        "args": {},
        "status": status,
        "side_effect": True,
        "requires_approval": True,
        "created_at": "2026-05-17T00:00:00Z",
    }


def _make_executed_action(output_alias: str) -> dict:
    return {
        "action_id": f"pa_{output_alias}",
        "step_id": "stage_action",
        "tool": "test/echo",
        "namespace": "test",
        "action": "echo",
        "output_alias": output_alias,
        "args": {},
        "status": "EXECUTED",
        "dry_run": True,
        "result_type": "echo_result",
        "executed_at": "2026-05-17T00:00:00Z",
    }


def _assert_canonical_shape(test: unittest.TestCase, result: dict) -> None:
    """Assert the result has all required canonical keys with correct sub-shapes."""
    for key in CANONICAL_KEYS:
        test.assertIn(key, result, f"Canonical key '{key}' missing from result")

    vs = result.get("validation_summary", {})
    test.assertIsInstance(vs, dict)
    for k in VALIDATION_SUMMARY_KEYS:
        test.assertIn(k, vs, f"validation_summary missing key '{k}'")

    ps = result.get("pending_action_summary", {})
    test.assertIsInstance(ps, dict)
    for k in PENDING_ACTION_SUMMARY_KEYS:
        test.assertIn(k, ps, f"pending_action_summary missing key '{k}'")

    test.assertIsInstance(result.get("required_outputs"), list)
    test.assertIsInstance(result.get("missing_outputs"), list)
    test.assertIsInstance(result.get("required_pending_actions"), list)
    test.assertIsInstance(result.get("missing_pending_actions"), list)
    test.assertIsInstance(result.get("required_executed_actions"), list)
    test.assertIsInstance(result.get("missing_executed_actions"), list)
    test.assertIsInstance(result.get("evidence_refs"), list)
    test.assertIsInstance(result.get("error_refs"), list)
    test.assertIsInstance(result.get("metadata"), dict)


class TestCompletionGateConsistency(unittest.TestCase):

    # ------------------------------------------------------------------
    # 1. Read-only success with data → COMPLETED / SUCCESS_WITH_DATA
    # ------------------------------------------------------------------

    def test_read_only_with_data_completes_completed(self):
        manifest, frame = _load_fixture("read_only_with_data.manifest.json")
        frame.state = "VERIFYING"
        frame.outputs["result"] = {"value": "hello"}

        result = evaluate_completion(frame, manifest)
        apply_completion_result(frame, result)

        self.assertTrue(result["ok"])
        self.assertEqual(result["outcome"], OUTCOME_SUCCESS_WITH_DATA)
        self.assertEqual(result["final_state"], "COMPLETED")
        self.assertEqual(frame.state, "COMPLETED")
        _assert_canonical_shape(self, result)

    # ------------------------------------------------------------------
    # 2. Read-only acceptable no-data → COMPLETED_NO_DATA / SUCCESS_NO_DATA
    # ------------------------------------------------------------------

    def test_read_only_no_data_with_acceptable_empty_completes_completed_no_data(self):
        manifest, frame = _load_fixture("read_only_no_data_acceptable.manifest.json")
        frame.state = "VERIFYING"
        frame.outputs["result"] = []  # empty but acceptable

        result = evaluate_completion(frame, manifest)
        apply_completion_result(frame, result)

        self.assertTrue(result["ok"])
        self.assertEqual(result["outcome"], OUTCOME_SUCCESS_NO_DATA)
        self.assertEqual(result["final_state"], "COMPLETED_NO_DATA")
        self.assertEqual(frame.state, "COMPLETED_NO_DATA")
        _assert_canonical_shape(self, result)

    # ------------------------------------------------------------------
    # 3. Empty output not acceptable → FAILED_COMPLETION
    # ------------------------------------------------------------------

    def test_read_only_no_data_without_acceptable_empty_fails_completion(self):
        manifest, frame = _load_fixture("read_only_no_data_unacceptable.manifest.json")
        frame.state = "VERIFYING"
        frame.outputs["result"] = []  # empty and NOT acceptable

        result = evaluate_completion(frame, manifest)

        self.assertFalse(result["ok"])
        self.assertEqual(result["outcome"], OUTCOME_COMPLETION_REQUIREMENT_FAILED)
        self.assertEqual(result["final_state"], "FAILED_COMPLETION")
        _assert_canonical_shape(self, result)

    # ------------------------------------------------------------------
    # 4. Failed validation → FAILED_VALIDATION / VALIDATION_FAILED
    # ------------------------------------------------------------------

    def test_failed_validation_has_failed_validation_completion_result(self):
        manifest, frame = _load_fixture("failed_validation.manifest.json")
        frame.state = "VERIFYING"
        frame.outputs["result"] = {"value": "hello"}
        frame.validations = [{"validation_id": "result_exists", "type": "output_exists", "ok": False, "message": "failed"}]

        result = evaluate_completion(frame, manifest)
        apply_completion_result(frame, result)

        self.assertFalse(result["ok"])
        self.assertEqual(result["outcome"], OUTCOME_VALIDATION_FAILED)
        self.assertEqual(result["final_state"], "FAILED_VALIDATION")
        self.assertEqual(frame.state, "FAILED_VALIDATION")
        _assert_canonical_shape(self, result)

    # ------------------------------------------------------------------
    # 5. Missing required output → FAILED_COMPLETION / COMPLETION_REQUIREMENT_FAILED
    # ------------------------------------------------------------------

    def test_missing_required_output_fails_completion(self):
        manifest, frame = _load_fixture("missing_required_output.manifest.json")
        frame.state = "VERIFYING"
        frame.outputs["result"] = {"value": "hello"}
        # "extra_required" is missing

        result = evaluate_completion(frame, manifest)

        self.assertFalse(result["ok"])
        self.assertEqual(result["outcome"], OUTCOME_COMPLETION_REQUIREMENT_FAILED)
        self.assertIn("extra_required", result["missing_outputs"])
        self.assertEqual(result["final_state"], "FAILED_COMPLETION")
        _assert_canonical_shape(self, result)

    # ------------------------------------------------------------------
    # 6. Expected pending action waits for execute
    # ------------------------------------------------------------------

    def test_expected_pending_action_waits_for_execute(self):
        manifest, frame = _load_fixture("pending_approval_expected.manifest.json")
        frame.state = "WAITING_FOR_EXECUTE"
        frame.pending_actions.append(_make_pending_action("staged_action", "PENDING_APPROVAL"))

        result = evaluate_completion(frame, manifest)
        apply_completion_result(frame, result)

        self.assertTrue(result["ok"])
        self.assertEqual(result["outcome"], OUTCOME_PENDING_APPROVAL)
        self.assertEqual(result["status"], "AWAITING_APPROVAL")
        self.assertEqual(result["final_state"], "WAITING_FOR_EXECUTE")
        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        _assert_canonical_shape(self, result)

    # ------------------------------------------------------------------
    # 7. Unexpected pending action fails or reports consistently
    # ------------------------------------------------------------------

    def test_unexpected_pending_action_fails_or_reports_consistently(self):
        manifest, frame = _load_fixture("pending_approval_unexpected.manifest.json")
        frame.state = "VERIFYING"
        # Pending action staged even though allow_pending_approval=false
        frame.pending_actions.append(_make_pending_action("result", "PENDING_APPROVAL"))

        result = evaluate_completion(frame, manifest)

        # Must not be ok and must have a canonical shape
        self.assertFalse(result["ok"])
        self.assertIsNotNone(result.get("outcome"))
        self.assertIsNotNone(result.get("final_state"))
        _assert_canonical_shape(self, result)

    # ------------------------------------------------------------------
    # 8. Rejected pending action → FAILED_COMPLETION / PENDING_ACTION_REJECTED
    # ------------------------------------------------------------------

    def test_rejected_pending_action_fails_completion_with_rejected_outcome(self):
        manifest, frame = _load_fixture("pending_approval_expected.manifest.json")
        frame.state = "VERIFYING"
        rejected = _make_pending_action("staged_action", "REJECTED")
        rejected["rejected_by"] = "operator"
        frame.pending_actions.append(rejected)

        result = evaluate_completion(frame, manifest)

        self.assertFalse(result["ok"])
        self.assertEqual(result["outcome"], OUTCOME_PENDING_ACTION_REJECTED)
        self.assertEqual(result["final_state"], "FAILED_COMPLETION")
        _assert_canonical_shape(self, result)

    # ------------------------------------------------------------------
    # 9. Approved dry-run execution → COMPLETED / DRY_RUN_EXECUTED
    # ------------------------------------------------------------------

    def test_approved_dry_run_execution_completes_with_executed_outcome(self):
        manifest, frame = _load_fixture("executed_dry_run_expected.manifest.json")
        frame.state = "VERIFYING"
        pa = _make_pending_action("staged_action", "EXECUTED")
        frame.pending_actions.append(pa)
        frame.executed_actions.append(_make_executed_action("staged_action"))
        frame.outputs["staged_action"] = {"dry_run": True, "approved_execution": True}

        result = evaluate_completion(frame, manifest)
        apply_completion_result(frame, result)

        self.assertTrue(result["ok"])
        self.assertEqual(result["outcome"], OUTCOME_DRY_RUN_EXECUTED)
        self.assertEqual(result["final_state"], "COMPLETED")
        self.assertEqual(frame.state, "COMPLETED")
        _assert_canonical_shape(self, result)

    # ------------------------------------------------------------------
    # 10. Live execution blocked → LIVE_EXECUTION_BLOCKED outcome
    # ------------------------------------------------------------------

    def test_blocked_live_execution_records_consistent_completion_result(self):
        manifest, frame = _load_fixture("blocked_live_execution.manifest.json")
        frame.state = "VERIFYING"
        # Simulate a live execution blocked error recorded on the frame
        frame.errors.append({
            "type": "live_execution_blocked",
            "message": "Live execution is blocked.",
            "data": {},
        })

        result = evaluate_completion(frame, manifest)

        self.assertFalse(result["ok"])
        self.assertEqual(result["outcome"], OUTCOME_LIVE_EXECUTION_BLOCKED)
        self.assertEqual(result["final_state"], "FAILED_EXECUTION")
        self.assertEqual(result["status"], "LIVE_BLOCKED")
        _assert_canonical_shape(self, result)

    # ------------------------------------------------------------------
    # 11. Every result always has canonical keys — exhaustive shape check
    # ------------------------------------------------------------------

    def test_completion_gate_result_always_has_canonical_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = {
                "manifest_id": "cg.canonical_shape_check",
                "name": "Canonical Shape Check",
                "version": 1,
                "trigger": {"type": "manual"},
                "inputs": [],
                "steps": [{"id": "s1", "command": "[t:test/echo -> out] message=x"}],
                "validations": [],
                "completion": {"success_outputs": ["out"]},
            }
            path = Path(tmp) / "manifest.manifest.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            manifest = load_manifest(path)

            scenarios = [
                # (frame_setup_fn, frame_state)
                ("with_data", "VERIFYING"),
                ("no_data", "VERIFYING"),
                ("validation_failed", "VERIFYING"),
                ("missing_output", "VERIFYING"),
            ]

            for scenario_name, state in scenarios:
                frame = create_taskframe(manifest)
                frame.state = state

                if scenario_name == "with_data":
                    frame.outputs["out"] = {"value": "x"}
                elif scenario_name == "no_data":
                    pass  # output missing → fail
                elif scenario_name == "validation_failed":
                    frame.validations = [{"validation_id": "v1", "ok": False, "message": "fail"}]
                elif scenario_name == "missing_output":
                    pass  # out not set

                result = evaluate_completion(frame, manifest)
                _assert_canonical_shape(self, result)

    # ------------------------------------------------------------------
    # 12. Orchestrator must stay generic — no domain logic leakage
    # ------------------------------------------------------------------

    def test_completion_gate_does_not_add_domain_logic_to_orchestrator(self):
        import ast
        import pathlib

        orchestrator_path = pathlib.Path(__file__).parent.parent / "runtime" / "orchestrator.py"
        source = orchestrator_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        domain_terms = {
            "customer", "order", "procurement", "invoice",
            "accounting", "shipment", "vendor", "purchase",
        }

        offending = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Name, ast.Attribute)):
                name = node.id if isinstance(node, ast.Name) else node.attr
                if name.lower() in domain_terms:
                    offending.append(name)

        self.assertEqual(
            offending, [],
            f"Domain-specific terms found in orchestrator.py: {offending}. "
            "Orchestrator must remain generic.",
        )


if __name__ == "__main__":
    unittest.main()
