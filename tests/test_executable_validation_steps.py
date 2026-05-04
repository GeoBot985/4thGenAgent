import unittest

from runtime.command_parser import parse_command
from runtime.errors import CommandParseError, ValidationEngineError
from runtime.llm_adapter import FakeLLMAdapter
from runtime.manifest_loader import load_manifest
from runtime.models import Manifest, ManifestStep
from runtime.orchestrator import Orchestrator
from runtime.taskframe import create_taskframe
from runtime.validation import find_validation_rule, run_validation_step


class ExecutableValidationStepTests(unittest.TestCase):
    def test_parser_parses_validate_no_runtime_errors(self):
        parsed = parse_command("[validate:no_runtime_errors]")
        self.assertEqual(parsed.kind, "validate")
        self.assertIsNone(parsed.namespace)
        self.assertEqual(parsed.action, "no_runtime_errors")
        self.assertIsNone(parsed.output_alias)
        self.assertEqual(parsed.payload, "")
        self.assertEqual(parsed.args, {})

    def test_parser_rejects_validate_missing_rule(self):
        with self.assertRaises(CommandParseError):
            parse_command("[validate]")

    def test_parser_rejects_validate_empty_rule(self):
        with self.assertRaises(CommandParseError):
            parse_command("[validate:]")

    def test_parser_rejects_validate_rule_with_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command("[validate:no_runtime_errors -> result]")

    def test_parser_rejects_validate_rule_with_payload(self):
        with self.assertRaises(CommandParseError):
            parse_command("[validate:no_runtime_errors] extra")

    def test_find_validation_rule_finds_existing_rule(self):
        manifest = load_manifest("manifests/smoke_validate_step_output_exists.manifest.json")
        rule = find_validation_rule(manifest, "unread_mail_output_exists")
        self.assertEqual(rule["type"], "output_exists")

    def test_find_validation_rule_fails_missing_rule(self):
        manifest = load_manifest("manifests/smoke_validate_step_output_exists.manifest.json")
        with self.assertRaises(ValidationEngineError):
            find_validation_rule(manifest, "missing")

    def test_run_validation_step_passes_valid_output_exists_rule(self):
        manifest = load_manifest("manifests/smoke_validate_step_output_exists.manifest.json")
        frame = create_taskframe(manifest)
        frame.outputs["unread_mail"] = {"dry_run": True}

        result = run_validation_step(frame, manifest, "unread_mail_output_exists")

        self.assertTrue(result.ok)
        self.assertEqual(len(frame.validations), 1)
        self.assertEqual(frame.audit[-1].event_type, "VALIDATION_STEP_PASSED")

    def test_run_validation_step_fails_invalid_output_exists_rule(self):
        manifest = load_manifest("manifests/smoke_validate_step_fail_fast.manifest.json")
        frame = create_taskframe(manifest)

        result = run_validation_step(frame, manifest, "missing_output_exists")

        self.assertFalse(result.ok)
        self.assertEqual(len(frame.validations), 1)
        self.assertEqual(frame.audit[-1].event_type, "VALIDATION_STEP_FAILED")

    def test_run_validation_step_writes_to_frame_validations(self):
        manifest = load_manifest("manifests/smoke_validate_step_output_exists.manifest.json")
        frame = create_taskframe(manifest)
        frame.outputs["unread_mail"] = {"dry_run": True}

        run_validation_step(frame, manifest, "unread_mail_output_exists")

        self.assertEqual(frame.validations[0]["validation_id"], "unread_mail_output_exists")

    def test_orchestrator_executes_validation_step(self):
        manifest = load_manifest("manifests/smoke_validate_step_output_exists.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_next_step(frame, manifest, dry_run=True)
        self.assertEqual(frame.steps[0].status, "COMPLETED")
        self.assertEqual(frame.state, "RUNNING")

        frame = orch.run_next_step(frame, manifest, dry_run=True)
        self.assertEqual(frame.steps[1].status, "COMPLETED")

    def test_validation_step_fail_marks_step_failed(self):
        manifest = load_manifest("manifests/smoke_validate_step_fail_fast.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertEqual(frame.state, "FAILED_VALIDATION")
        self.assertEqual(frame.steps[1].status, "PENDING")

    def test_validation_step_fail_stops_run_until_blocked(self):
        manifest = load_manifest("manifests/smoke_validate_step_fail_fast.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "FAILED_VALIDATION")
        self.assertEqual(frame.steps[1].status, "PENDING")
        self.assertNotIn("unread_mail", frame.outputs)

    def test_successful_validation_step_allows_next_step_to_run(self):
        manifest = load_manifest("manifests/smoke_llm_classify_with_validation_step.manifest.json")
        adapter = FakeLLMAdapter(
            {
                "classify": '{"label": "order_status", "confidence": "high", "reason": "Asks where order is."}',
                "draft": "Your order is being checked. We will update you shortly.",
            }
        )
        orch = Orchestrator(llm_adapter=adapter)
        frame = orch.create_frame_from_manifest(manifest, inputs={"message": "Where is my order ORD-10042?"})
        frame = orch.prepare_frame(frame)

        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.steps[1].status, "COMPLETED")
        self.assertEqual(frame.steps[2].status, "COMPLETED")
        self.assertEqual(frame.outputs["category"]["label"], "order_status")
        self.assertTrue(frame.outputs["reply"])

    def test_final_completion_still_runs_manifest_validations(self):
        manifest = load_manifest("manifests/smoke_validate_step_output_exists.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        validation_ids = [item["validation_id"] for item in frame.validations]
        self.assertGreater(validation_ids.count("unread_mail_output_exists"), 1)

    def test_duplicate_validation_records_are_allowed(self):
        manifest = load_manifest("manifests/smoke_validate_step_output_exists.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertGreaterEqual(len(frame.validations), len(manifest.validations))


if __name__ == "__main__":
    unittest.main()
