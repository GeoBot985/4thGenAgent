import tempfile
import unittest
from pathlib import Path

from runtime.events import create_event
from runtime.llm_adapter import FakeLLMAdapter
from runtime.manifest_loader import load_manifest
from runtime.memory_store import MemoryStore
from runtime.orchestrator import Orchestrator
from runtime.taskframe import create_taskframe
from runtime.validation import run_validation


def statuses(frame):
    return {step.step_id: step.status for step in frame.steps}


def set_step_status(frame, step_id: str, status: str) -> None:
    for step in frame.steps:
        if step.step_id == step_id:
            step.status = status
            return
    raise AssertionError(f"Missing step: {step_id}")


class BranchPatternTests(unittest.TestCase):
    def test_smoke_condition_all_completes_when_both_inputs_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_condition_all.manifest.json")
            frame = engine.create_frame_from_manifest(manifest, inputs={"channel": "whatsapp", "priority": "urgent"})
            frame = engine.prepare_frame(frame)
            frame = engine.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("saved_branch", frame.outputs)

    def test_smoke_condition_all_skips_when_one_input_does_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_condition_all.manifest.json")
            frame = engine.create_frame_from_manifest(manifest, inputs={"channel": "email", "priority": "urgent"})
            frame = engine.prepare_frame(frame)
            frame = engine.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.steps[0].status, "SKIPPED")
            self.assertNotIn("saved_branch", frame.outputs)

    def test_smoke_condition_any_completes_when_first_input_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_condition_any.manifest.json")
            frame = engine.create_frame_from_manifest(manifest, inputs={"priority": "urgent", "category": "other"})
            frame = engine.prepare_frame(frame)
            frame = engine.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("escalation_flag", frame.outputs)

    def test_smoke_condition_any_completes_when_second_input_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_condition_any.manifest.json")
            frame = engine.create_frame_from_manifest(manifest, inputs={"priority": "normal", "category": "complaint"})
            frame = engine.prepare_frame(frame)
            frame = engine.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("escalation_flag", frame.outputs)

    def test_smoke_condition_any_skips_when_neither_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_condition_any.manifest.json")
            frame = engine.create_frame_from_manifest(manifest, inputs={"priority": "normal", "category": "other"})
            frame = engine.prepare_frame(frame)
            frame = engine.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.steps[0].status, "SKIPPED")
            self.assertNotIn("escalation_flag", frame.outputs)

    def test_smoke_condition_not_completes_when_input_does_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_condition_not.manifest.json")
            frame = engine.create_frame_from_manifest(manifest, inputs={"channel": "email"})
            frame = engine.prepare_frame(frame)
            frame = engine.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("saved_branch", frame.outputs)

    def test_smoke_condition_not_skips_when_input_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_condition_not.manifest.json")
            frame = engine.create_frame_from_manifest(manifest, inputs={"channel": "whatsapp"})
            frame = engine.prepare_frame(frame)
            frame = engine.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.steps[0].status, "SKIPPED")
            self.assertNotIn("saved_branch", frame.outputs)

    def test_llm_branch_escalation_stages_escalation_for_complaint(self):
        adapter = FakeLLMAdapter(
            {
                "classify": '{"label": "complaint", "confidence": "high", "reason": "Customer complains."}',
                "draft": "We are sorry about the issue and will escalate it.",
            }
        )
        engine = Orchestrator(llm_adapter=adapter)
        manifest = load_manifest("manifests/smoke_llm_branch_escalation.manifest.json")
        frame = engine.create_frame_from_manifest(
            manifest,
            inputs={"message": "I am unhappy with the service.", "support_chat": "Support Lead"},
        )
        frame = engine.prepare_frame(frame)
        frame = engine.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        self.assertEqual(frame.steps[3].status, "STAGED")
        self.assertEqual(frame.pending_actions[0]["tool"], "wa/send")
        self.assertEqual(frame.pending_actions[0]["output_alias"], "escalation_msg")

    def test_llm_branch_escalation_stages_escalation_for_low_confidence(self):
        adapter = FakeLLMAdapter(
            {
                "classify": '{"label": "order_status", "confidence": "low", "reason": "Low confidence."}',
                "draft": "We are sorry about the issue and will escalate it.",
            }
        )
        engine = Orchestrator(llm_adapter=adapter)
        manifest = load_manifest("manifests/smoke_llm_branch_escalation.manifest.json")
        frame = engine.create_frame_from_manifest(
            manifest,
            inputs={"message": "Where is my order?", "support_chat": "Support Lead"},
        )
        frame = engine.prepare_frame(frame)
        frame = engine.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        self.assertEqual(frame.steps[3].status, "STAGED")
        self.assertEqual(frame.pending_actions[0]["tool"], "wa/send")

    def test_llm_branch_escalation_skips_escalation_for_normal_order_status_high_confidence(self):
        adapter = FakeLLMAdapter(
            {
                "classify": '{"label": "order_status", "confidence": "high", "reason": "Order status request."}',
                "draft": "Your order is being checked.",
            }
        )
        engine = Orchestrator(llm_adapter=adapter)
        manifest = load_manifest("manifests/smoke_llm_branch_escalation.manifest.json")
        frame = engine.create_frame_from_manifest(
            manifest,
            inputs={"message": "Where is my order?", "support_chat": "Support Lead"},
        )
        frame = engine.prepare_frame(frame)
        frame = engine.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.steps[3].status, "SKIPPED")
        self.assertEqual(frame.outputs["reply"], "Your order is being checked.")

    def test_channel_branch_reply_stages_whatsapp_when_channel_whatsapp(self):
        adapter = FakeLLMAdapter({"draft": "Confirmed. I will handle it."})
        engine = Orchestrator(llm_adapter=adapter)
        manifest = load_manifest("manifests/smoke_channel_branch_reply.manifest.json")
        frame = engine.create_frame_from_manifest(
            manifest,
            inputs={
                "message": "Please confirm.",
                "channel": "whatsapp",
                "chat": "Cornelia",
                "email": "person@example.com",
            },
        )
        frame = engine.prepare_frame(frame)
        frame = engine.run_until_blocked(frame, manifest, dry_run=True)

        st = statuses(frame)
        self.assertEqual(st["draft_reply"], "COMPLETED")
        self.assertEqual(st["stage_whatsapp_reply"], "STAGED")
        self.assertEqual(st["stage_email_reply"], "PENDING")
        self.assertEqual(frame.pending_actions[0]["tool"], "wa/send")

    def test_channel_branch_reply_stages_email_when_channel_email(self):
        adapter = FakeLLMAdapter({"draft": "Confirmed. I will handle it."})
        engine = Orchestrator(llm_adapter=adapter)
        manifest = load_manifest("manifests/smoke_channel_branch_reply.manifest.json")
        frame = engine.create_frame_from_manifest(
            manifest,
            inputs={
                "message": "Please confirm.",
                "channel": "email",
                "chat": "Cornelia",
                "email": "person@example.com",
            },
        )
        frame = engine.prepare_frame(frame)
        frame = engine.run_until_blocked(frame, manifest, dry_run=True)

        st = statuses(frame)
        self.assertEqual(st["draft_reply"], "COMPLETED")
        self.assertEqual(st["stage_whatsapp_reply"], "SKIPPED")
        self.assertEqual(st["stage_email_reply"], "STAGED")
        self.assertEqual(frame.pending_actions[0]["tool"], "g/send")

    def test_channel_branch_reply_skips_other_channel_branch(self):
        adapter = FakeLLMAdapter({"draft": "Confirmed. I will handle it."})
        engine = Orchestrator(llm_adapter=adapter)
        manifest = load_manifest("manifests/smoke_channel_branch_reply.manifest.json")
        frame = engine.create_frame_from_manifest(
            manifest,
            inputs={
                "message": "Please confirm.",
                "channel": "sms",
                "chat": "Cornelia",
                "email": "person@example.com",
            },
        )
        frame = engine.prepare_frame(frame)
        frame = engine.run_until_blocked(frame, manifest, dry_run=True)

        st = statuses(frame)
        self.assertEqual(st["stage_whatsapp_reply"], "SKIPPED")
        self.assertEqual(st["stage_email_reply"], "SKIPPED")
        self.assertNotIn("sent_reply", frame.outputs)

    def test_one_of_steps_completed_passes_when_exactly_one_completed(self):
        manifest = load_manifest("manifests/smoke_channel_branch_reply.manifest.json")
        frame = create_taskframe(manifest)
        set_step_status(frame, "stage_whatsapp_reply", "COMPLETED")
        set_step_status(frame, "stage_email_reply", "SKIPPED")

        result = run_validation(
            frame,
            {
                "id": "branch_one_of",
                "type": "one_of_steps_completed",
                "steps": ["stage_whatsapp_reply", "stage_email_reply"],
            },
        )
        self.assertTrue(result.ok)

    def test_one_of_steps_completed_fails_when_zero_completed(self):
        manifest = load_manifest("manifests/smoke_channel_branch_reply.manifest.json")
        frame = create_taskframe(manifest)
        set_step_status(frame, "stage_whatsapp_reply", "SKIPPED")
        set_step_status(frame, "stage_email_reply", "SKIPPED")

        result = run_validation(
            frame,
            {
                "id": "branch_one_of",
                "type": "one_of_steps_completed",
                "steps": ["stage_whatsapp_reply", "stage_email_reply"],
            },
        )
        self.assertFalse(result.ok)

    def test_one_of_steps_completed_fails_when_two_completed(self):
        manifest = load_manifest("manifests/smoke_channel_branch_reply.manifest.json")
        frame = create_taskframe(manifest)
        set_step_status(frame, "stage_whatsapp_reply", "COMPLETED")
        set_step_status(frame, "stage_email_reply", "COMPLETED")

        result = run_validation(
            frame,
            {
                "id": "branch_one_of",
                "type": "one_of_steps_completed",
                "steps": ["stage_whatsapp_reply", "stage_email_reply"],
            },
        )
        self.assertFalse(result.ok)

    def test_at_least_one_step_completed_passes_when_one_completed(self):
        manifest = load_manifest("manifests/smoke_channel_branch_reply.manifest.json")
        frame = create_taskframe(manifest)
        set_step_status(frame, "stage_whatsapp_reply", "COMPLETED")
        set_step_status(frame, "stage_email_reply", "SKIPPED")

        result = run_validation(
            frame,
            {
                "id": "branch_any",
                "type": "at_least_one_step_completed",
                "steps": ["stage_whatsapp_reply", "stage_email_reply"],
            },
        )
        self.assertTrue(result.ok)

    def test_at_least_one_step_completed_fails_when_none_completed(self):
        manifest = load_manifest("manifests/smoke_channel_branch_reply.manifest.json")
        frame = create_taskframe(manifest)
        set_step_status(frame, "stage_whatsapp_reply", "SKIPPED")
        set_step_status(frame, "stage_email_reply", "SKIPPED")

        result = run_validation(
            frame,
            {
                "id": "branch_any",
                "type": "at_least_one_step_completed",
                "steps": ["stage_whatsapp_reply", "stage_email_reply"],
            },
        )
        self.assertFalse(result.ok)

    def test_at_least_one_step_completed_passes_when_both_completed(self):
        manifest = load_manifest("manifests/smoke_channel_branch_reply.manifest.json")
        frame = create_taskframe(manifest)
        set_step_status(frame, "stage_whatsapp_reply", "COMPLETED")
        set_step_status(frame, "stage_email_reply", "COMPLETED")

        result = run_validation(
            frame,
            {
                "id": "branch_any",
                "type": "at_least_one_step_completed",
                "steps": ["stage_whatsapp_reply", "stage_email_reply"],
            },
        )
        self.assertTrue(result.ok)

    def test_condition_audit_trace_exists_for_compound_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_condition_all.manifest.json")
            frame = engine.create_frame_from_manifest(manifest, inputs={"channel": "whatsapp", "priority": "urgent"})
            frame = engine.prepare_frame(frame)
            frame = engine.run_until_blocked(frame, manifest, dry_run=True)

            passed_events = [event for event in frame.audit if event.event_type == "STEP_CONDITION_PASSED"]
            self.assertTrue(passed_events)
            trace = passed_events[0].data["trace"]
            self.assertEqual(trace["operator"], "all")
            self.assertEqual(len(trace["children"]), 2)


if __name__ == "__main__":
    unittest.main()
