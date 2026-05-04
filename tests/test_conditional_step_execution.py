import tempfile
import unittest
from pathlib import Path

from runtime.llm_adapter import FakeLLMAdapter
from runtime.manifest_loader import load_manifest
from runtime.memory_store import MemoryStore
from runtime.orchestrator import Orchestrator
from runtime.validation import run_validation


def statuses(frame):
    return {step.step_id: step.status for step in frame.steps}


class ConditionalStepExecutionTests(unittest.TestCase):
    def test_manifest_loader_stores_when_on_manifeststep(self):
        manifest = load_manifest("manifests/smoke_condition_equals.manifest.json")
        self.assertEqual(manifest.steps[0].when, {"input": "channel", "equals": "whatsapp"})

    def test_create_taskframe_copies_when_to_stepruntime(self):
        manifest = load_manifest("manifests/smoke_condition_equals.manifest.json")
        frame = Orchestrator().create_frame_from_manifest(manifest, inputs={"channel": "whatsapp"})
        self.assertEqual(frame.steps[0].when, {"input": "channel", "equals": "whatsapp"})

    def test_orchestrator_evaluates_condition_before_execution(self):
        manifest = load_manifest("manifests/smoke_condition_skip.manifest.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            orch = Orchestrator(memory_store=store)
            frame = orch.create_frame_from_manifest(manifest, inputs={"channel": "email"})
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].status, "SKIPPED")
            self.assertEqual(frame.steps[1].status, "COMPLETED")
            self.assertIn("STEP_CONDITION_SKIPPED", [event.event_type for event in frame.audit])

    def test_passing_condition_runs_step(self):
        manifest = load_manifest("manifests/smoke_condition_equals.manifest.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            orch = Orchestrator(memory_store=store)
            frame = orch.create_frame_from_manifest(manifest, inputs={"channel": "whatsapp"})
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("saved_channel", frame.outputs)
            self.assertEqual(frame.outputs["saved_channel"]["ok"], True)
            self.assertIn("STEP_CONDITION_PASSED", [event.event_type for event in frame.audit])

    def test_failing_condition_marks_step_skipped(self):
        manifest = load_manifest("manifests/smoke_condition_skip.manifest.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            orch = Orchestrator(memory_store=store)
            frame = orch.create_frame_from_manifest(manifest, inputs={"channel": "email"})
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.steps[0].status, "SKIPPED")
            self.assertNotIn("saved_channel", frame.outputs)

    def test_failing_condition_does_not_write_output(self):
        manifest = load_manifest("manifests/smoke_condition_skip.manifest.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            orch = Orchestrator(memory_store=store)
            frame = orch.create_frame_from_manifest(manifest, inputs={"channel": "email"})
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertNotIn("saved_channel", frame.outputs)

    def test_failing_condition_does_not_call_tool(self):
        manifest = load_manifest("manifests/smoke_condition_skip.manifest.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            orch = Orchestrator(memory_store=store)
            frame = orch.create_frame_from_manifest(manifest, inputs={"channel": "email"})
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.tool_calls, [])

    def test_failing_condition_does_not_call_llm(self):
        manifest = load_manifest("manifests/smoke_condition_skip.manifest.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            orch = Orchestrator(memory_store=store, llm_adapter=FakeLLMAdapter({"draft": "x"}))
            frame = orch.create_frame_from_manifest(manifest, inputs={"channel": "email"})
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.llm_calls, [])

    def test_failing_condition_does_not_call_memory_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            manifest_path = Path(tmp) / "memory_skip.manifest.json"
            manifest_path.write_text(
                """
{
  "manifest_id": "temp.memory_skip",
  "name": "Temp Memory Skip",
  "version": 1,
  "trigger": {"type": "manual"},
  "inputs": ["channel"],
  "steps": [
    {
      "id": "set_whatsapp_memory",
      "when": {"input": "channel", "equals": "whatsapp"},
      "command": "[m:set -> saved_channel] key=\\"test.channel\\"; value=$inputs.channel"
    }
  ],
  "validations": [],
  "completion": {"success_outputs": ["saved_channel"]}
}
                """.strip(),
                encoding="utf-8",
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator(memory_store=store)
            frame = orch.create_frame_from_manifest(manifest, inputs={"channel": "email"})
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertFalse(store.exists("test.channel"))
            self.assertEqual(frame.steps[0].status, "SKIPPED")

    def test_condition_skip_advances_to_next_step(self):
        manifest = load_manifest("manifests/smoke_condition_skip.manifest.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            orch = Orchestrator(memory_store=store)
            frame = orch.create_frame_from_manifest(manifest, inputs={"channel": "email"})
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.current_step_id, None)
            self.assertEqual(statuses(frame)["set_whatsapp_memory"], "SKIPPED")
            self.assertEqual(statuses(frame)["set_fallback_memory"], "COMPLETED")

    def test_condition_evaluation_error_fails_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            manifest_path = Path(tmp) / "bad_condition.manifest.json"
            manifest_path.write_text(
                """
{
  "manifest_id": "temp.bad_condition",
  "name": "Temp Bad Condition",
  "version": 1,
  "trigger": {"type": "manual"},
  "inputs": [],
  "steps": [
    {"id": "draft_reply", "command": "[q:draft -> reply] instruction=\\"Draft\\"; context=\\"Hello\\""},
    {"id": "bad_branch", "when": {"output": "reply", "field": "label", "equals": "x"}, "command": "[m:set -> saved] key=\\"x\\"; value=\\"y\\""},
    {"id": "should_not_run", "command": "[m:set -> later] key=\\"later\\"; value=\\"y\\""}
  ],
  "validations": [],
  "completion": {"success_outputs": ["reply"]}
}
                """.strip(),
                encoding="utf-8",
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator(
                memory_store=store,
                llm_adapter=FakeLLMAdapter({"draft": "hello"}),
            )
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "FAILED_EXECUTION")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertEqual(frame.steps[1].status, "FAILED")
            self.assertEqual(frame.steps[2].status, "PENDING")
            self.assertIn("STEP_CONDITION_FAILED", [event.event_type for event in frame.audit])

    def test_step_status_validation_passes_for_skipped(self):
        manifest = load_manifest("manifests/smoke_condition_skip.manifest.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            orch = Orchestrator(memory_store=store)
            frame = orch.create_frame_from_manifest(manifest, inputs={"channel": "email"})
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            result = run_validation(
                frame,
                {"id": "v1", "type": "step_status", "step": "set_whatsapp_memory", "status": "SKIPPED"},
            )
            self.assertTrue(result.ok)

    def test_smoke_condition_equals_completes_when_channel_whatsapp(self):
        manifest = load_manifest("manifests/smoke_condition_equals.manifest.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            orch = Orchestrator(memory_store=store)
            frame = orch.create_frame_from_manifest(manifest, inputs={"channel": "whatsapp"})
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertTrue(frame.outputs["saved_channel"]["ok"])
            self.assertEqual(store.get("test.channel").value, "whatsapp")

    def test_smoke_condition_skip_completes_when_channel_email(self):
        manifest = load_manifest("manifests/smoke_condition_skip.manifest.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            orch = Orchestrator(memory_store=store)
            frame = orch.create_frame_from_manifest(manifest, inputs={"channel": "email"})
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].status, "SKIPPED")
            self.assertEqual(frame.steps[1].status, "COMPLETED")
            self.assertNotIn("saved_channel", frame.outputs)
            self.assertIn("fallback_channel", frame.outputs)
            self.assertEqual(store.get("test.fallback_channel").value, "email")

    def test_llm_conditional_reply_runs_only_matching_branch(self):
        manifest = load_manifest("manifests/smoke_llm_classify_conditional_reply.manifest.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            orch = Orchestrator(
                memory_store=store,
                llm_adapter=FakeLLMAdapter(
                    {
                        "classify": '{"label": "refund", "confidence": "high", "reason": "Customer asks for refund."}',
                        "draft": "We received your refund request and will review it.",
                    }
                ),
            )
            frame = orch.create_frame_from_manifest(manifest, inputs={"message": "I want a refund for order ORD-10042."})
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.outputs["category"]["label"], "refund")
            self.assertEqual(frame.outputs["reply"], "We received your refund request and will review it.")
            st = statuses(frame)
            self.assertEqual(st["draft_order_status_reply"], "SKIPPED")
            self.assertEqual(st["draft_refund_reply"], "COMPLETED")
            self.assertEqual(st["draft_generic_reply"], "SKIPPED")


if __name__ == "__main__":
    unittest.main()
