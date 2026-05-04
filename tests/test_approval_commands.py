import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from runtime.events import create_event
from runtime.approval_commands import ApprovalCommandRunner
from runtime.command_parser import parse_command
from runtime.errors import CommandParseError
from runtime.manifest_loader import load_manifest
from runtime.persistence import load_taskframe_dict, taskframe_exists
from runtime.run_ledger import find_ledger_record
from runtime.runtime_engine import RuntimeEngine
from runtime.taskframe import create_taskframe


class ApprovalCommandTests(unittest.TestCase):
    def _create_target_frame(self, runtime_dir: Path):
        engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)
        target = engine.handle_event(create_event("manual.whatsapp_stage_send", "manual"), dry_run=True)
        self.assertEqual(target.state, "WAITING_FOR_EXECUTE")
        return target

    def _make_command_frame(self, manifest_path: str, inputs: dict | None = None):
        manifest = load_manifest(manifest_path)
        return create_taskframe(manifest, inputs=inputs or {})

    def test_parser_accepts_approval_commands(self):
        parsed = parse_command("[a:list_pending -> pending] frame_id=$inputs.frame_id")
        self.assertEqual(parsed.kind, "approval")
        self.assertEqual(parsed.namespace, "a")
        self.assertEqual(parsed.action, "list_pending")

        parsed = parse_command('[a:approve -> approval_result] frame_id=$inputs.frame_id; action_id=$inputs.action_id; approved_by="test"; reason="ok"')
        self.assertEqual(parsed.action, "approve")

        parsed = parse_command('[a:reject -> rejection_result] frame_id=$inputs.frame_id; action_id=$inputs.action_id; rejected_by="test"; reason="bad"')
        self.assertEqual(parsed.action, "reject")

        parsed = parse_command("[a:execute_approved -> execution_result] frame_id=$inputs.frame_id")
        self.assertEqual(parsed.action, "execute_approved")

        parsed = parse_command('[a:approve_and_execute -> result] frame_id=$inputs.frame_id; action_id=$inputs.action_id; approved_by="test"')
        self.assertEqual(parsed.action, "approve_and_execute")

    def test_parser_rejects_invalid_approval_commands(self):
        for command in [
            "[a]",
            "[a:approve]",
            "[a:approve ->]",
            "[a:/approve -> result]",
            '[a:delete -> result] frame_id="tf_abc"',
            '[a:resume -> result] frame_id="tf_abc"',
            '[a:approve_all -> result] frame_id="tf_abc"',
            '[a:live_execute -> result] frame_id="tf_abc"',
        ]:
            with self.subTest(command=command):
                with self.assertRaises(CommandParseError):
                    parse_command(command)

    def test_list_pending_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            target = self._create_target_frame(runtime_dir)
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir)
            command_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {
                    "frame_id": target.frame_id,
                    "action_id": target.pending_actions[0]["action_id"],
                    "approved_by": "manual_smoke",
                    "reason": "test",
                },
            )
            command_frame.steps[0].command = "[a:list_pending -> pending] frame_id=$inputs.frame_id"
            command_frame.steps[0].action = "list_pending"
            command_frame.steps[0].output_alias = "pending"
            command_frame.inputs = {"frame_id": target.frame_id}

            result = runner.run_step(command_frame, command_frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(command_frame.outputs["pending"]["frame_id"], target.frame_id)
            self.assertGreaterEqual(command_frame.outputs["pending"]["count"], 1)
            self.assertEqual(command_frame.steps[0].status, "COMPLETED")

    def test_approve_persists_target_and_appends_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            target = self._create_target_frame(runtime_dir)
            action_id = target.pending_actions[0]["action_id"]
            before = load_taskframe_dict(target.frame_id, runtime_dir)
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir)
            command_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {
                    "frame_id": target.frame_id,
                    "action_id": action_id,
                    "approved_by": "manual_smoke",
                    "reason": "test",
                },
            )

            result = runner.run_step(command_frame, command_frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(command_frame.outputs["approval_result"]["status"], "APPROVED")
            self.assertEqual(command_frame.outputs["approval_result"]["frame_id"], target.frame_id)
            after = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(after["pending_actions"][0]["status"], "APPROVED")
            self.assertEqual(after["state"], before["state"])
            self.assertTrue(taskframe_exists(target.frame_id, runtime_dir))
            self.assertIsNotNone(find_ledger_record(target.frame_id, runtime_dir))

    def test_reject_persists_failed_completion_and_blocks_execution_afterward(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            target = self._create_target_frame(runtime_dir)
            action_id = target.pending_actions[0]["action_id"]
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir)
            reject_frame = self._make_command_frame(
                "manifests/smoke_reject_pending_action.manifest.json",
                {
                    "frame_id": target.frame_id,
                    "action_id": action_id,
                    "rejected_by": "manual_smoke",
                    "reason": "bad",
                },
            )

            reject_result = runner.run_step(reject_frame, reject_frame.steps[0])
            self.assertTrue(reject_result.ok)

            rejected = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(rejected["state"], "FAILED_COMPLETION")
            self.assertEqual(rejected["pending_actions"][0]["status"], "REJECTED")

            execute_frame = self._make_command_frame(
                "manifests/smoke_execute_approved_pending_actions.manifest.json",
                {"frame_id": target.frame_id},
            )
            execute_result = runner.run_step(execute_frame, execute_frame.steps[0])
            self.assertFalse(execute_result.ok)
            self.assertEqual(execute_frame.steps[0].status, "FAILED")

    def test_execute_approved_executes_dry_run_and_persists_completed_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            target = self._create_target_frame(runtime_dir)
            action_id = target.pending_actions[0]["action_id"]
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir)
            approve_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {
                    "frame_id": target.frame_id,
                    "action_id": action_id,
                    "approved_by": "manual_smoke",
                    "reason": "test",
                },
            )
            runner.run_step(approve_frame, approve_frame.steps[0])

            execute_frame = self._make_command_frame(
                "manifests/smoke_execute_approved_pending_actions.manifest.json",
                {"frame_id": target.frame_id},
            )
            execute_result = runner.run_step(execute_frame, execute_frame.steps[0])

            self.assertTrue(execute_result.ok)
            self.assertEqual(execute_frame.outputs["execution_result"]["target_frame_state"], "COMPLETED")
            reloaded = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(reloaded["state"], "COMPLETED")
            self.assertEqual(reloaded["pending_actions"][0]["status"], "EXECUTED")

    def test_approve_and_execute_performs_full_dry_run_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            target = self._create_target_frame(runtime_dir)
            action_id = target.pending_actions[0]["action_id"]
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir)
            flow_frame = self._make_command_frame(
                "manifests/smoke_reload_pending_action_flow.manifest.json",
                {
                    "frame_id": target.frame_id,
                    "action_id": action_id,
                    "approved_by": "manual_smoke",
                    "reason": "test",
                },
            )
            flow_frame.steps[0].command = "[a:list_pending -> pending_before] frame_id=$inputs.frame_id"
            flow_frame.steps[0].action = "list_pending"
            flow_frame.steps[0].output_alias = "pending_before"
            flow_frame.steps[1].command = "[a:approve_and_execute -> approval_execution_result] frame_id=$inputs.frame_id; action_id=$inputs.action_id; approved_by=$inputs.approved_by; reason=$inputs.reason"
            flow_frame.steps[1].action = "approve_and_execute"
            flow_frame.steps[1].output_alias = "approval_execution_result"
            flow_frame.steps[2].command = "[a:list_pending -> pending_after] frame_id=$inputs.frame_id"
            flow_frame.steps[2].action = "list_pending"
            flow_frame.steps[2].output_alias = "pending_after"

            first = runner.run_step(flow_frame, flow_frame.steps[0])
            self.assertTrue(first.ok)
            second = runner.run_step(flow_frame, flow_frame.steps[1])
            self.assertTrue(second.ok)
            third = runner.run_step(flow_frame, flow_frame.steps[2])
            self.assertTrue(third.ok)

            self.assertEqual(flow_frame.outputs["approval_execution_result"]["target_frame_state"], "COMPLETED")
            self.assertEqual(flow_frame.outputs["pending_after"]["count"], 0)

    def test_execute_live_approved_requires_confirm_live_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            target = self._create_target_frame(runtime_dir)
            action_id = target.pending_actions[0]["action_id"]
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir)
            approve_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {
                    "frame_id": target.frame_id,
                    "action_id": action_id,
                    "approved_by": "manual_smoke",
                    "reason": "test",
                },
            )
            runner.run_step(approve_frame, approve_frame.steps[0])

            live_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {"frame_id": target.frame_id, "confirm_live": "false"},
            )
            live_frame.steps[0].command = "[a:execute_live_approved -> result] frame_id=$inputs.frame_id; confirm_live=false"
            live_frame.steps[0].action = "execute_live_approved"
            live_frame.steps[0].output_alias = "result"
            result = runner.run_step(live_frame, live_frame.steps[0])
            self.assertFalse(result.ok)
            self.assertIn("confirm_live", result.error)

    def test_execute_live_approved_calls_orchestrator_with_live_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            target = self._create_target_frame(runtime_dir)
            action_id = target.pending_actions[0]["action_id"]
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir)
            approve_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {
                    "frame_id": target.frame_id,
                    "action_id": action_id,
                    "approved_by": "manual_smoke",
                    "reason": "test",
                },
            )
            runner.run_step(approve_frame, approve_frame.steps[0])

            live_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {
                    "frame_id": target.frame_id,
                    "confirm_live": "true",
                },
            )
            live_frame.steps[0].command = "[a:execute_live_approved -> result] frame_id=$inputs.frame_id; confirm_live=true"
            live_frame.steps[0].action = "execute_live_approved"
            live_frame.steps[0].output_alias = "result"

            fake_orchestrator = Mock()
            def _execute(frame, manifest, dry_run, live_mode):
                frame.state = "COMPLETED"
                frame.pending_actions[0]["status"] = "EXECUTED"
                frame.executed_actions.append(
                    {
                        "action_id": action_id,
                        "status": "EXECUTED",
                        "output_alias": target.pending_actions[0]["output_alias"],
                        "tool": target.pending_actions[0]["tool"],
                    }
                )
                return frame

            fake_orchestrator.execute_approved_pending_actions.side_effect = _execute

            with patch.object(runner, "_build_orchestrator", return_value=fake_orchestrator) as build:
                result = runner.run_step(live_frame, live_frame.steps[0])

            self.assertTrue(result.ok)
            build.assert_called_once()
            fake_orchestrator.execute_approved_pending_actions.assert_called_once()
            _, kwargs = fake_orchestrator.execute_approved_pending_actions.call_args
            self.assertEqual(kwargs["dry_run"], False)
            self.assertEqual(kwargs["live_mode"], True)

    def test_missing_target_frame_missing_action_and_wrong_state_fail_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir)
            command_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {"frame_id": "missing", "action_id": "pa_1", "approved_by": "x", "reason": "y"},
            )
            result = runner.run_step(command_frame, command_frame.steps[0])
            self.assertFalse(result.ok)

            target = self._create_target_frame(runtime_dir)
            bad_action_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {"frame_id": target.frame_id, "action_id": "", "approved_by": "x", "reason": "y"},
            )
            bad_action_result = runner.run_step(bad_action_frame, bad_action_frame.steps[0])
            self.assertFalse(bad_action_result.ok)

            no_approved_frame = self._make_command_frame(
                "manifests/smoke_execute_approved_pending_actions.manifest.json",
                {"frame_id": target.frame_id},
            )
            no_approved_result = runner.run_step(no_approved_frame, no_approved_frame.steps[0])
            self.assertFalse(no_approved_result.ok)

            approve_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {
                    "frame_id": target.frame_id,
                    "action_id": target.pending_actions[0]["action_id"],
                    "approved_by": "x",
                    "reason": "y",
                },
            )
            runner.run_step(approve_frame, approve_frame.steps[0])
            execute_frame = self._make_command_frame(
                "manifests/smoke_execute_approved_pending_actions.manifest.json",
                {"frame_id": target.frame_id},
            )
            runner.run_step(execute_frame, execute_frame.steps[0])
            wrong_state_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {
                    "frame_id": target.frame_id,
                    "action_id": target.pending_actions[0]["action_id"],
                    "approved_by": "x",
                    "reason": "y",
                },
            )
            wrong_state_result = runner.run_step(wrong_state_frame, wrong_state_frame.steps[0])
            self.assertFalse(wrong_state_result.ok)

    def test_live_execution_remains_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            target = self._create_target_frame(runtime_dir)
            action_id = target.pending_actions[0]["action_id"]
            approve_runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir)
            approve_frame = self._make_command_frame(
                "manifests/smoke_approve_pending_action.manifest.json",
                {
                    "frame_id": target.frame_id,
                    "action_id": action_id,
                    "approved_by": "manual_smoke",
                    "reason": "test",
                },
            )
            approve_runner.run_step(approve_frame, approve_frame.steps[0])
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir, dry_run_execution_only=False)
            execute_frame = self._make_command_frame(
                "manifests/smoke_execute_approved_pending_actions.manifest.json",
                {"frame_id": target.frame_id},
            )

            result = runner.run_step(execute_frame, execute_frame.steps[0])
            self.assertFalse(result.ok)
            self.assertIn("blocked", result.error.lower())


if __name__ == "__main__":
    unittest.main()
