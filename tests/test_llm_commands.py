import unittest

from runtime.command_parser import parse_command
from runtime.errors import CommandParseError
from runtime.llm_adapter import BaseLLMAdapter, FakeLLMAdapter
from runtime.llm_commands import LLMCommandRunner
from runtime.manifest_loader import load_manifest
from runtime.models import Manifest, ManifestStep
from runtime.taskframe import create_taskframe


class BoomAdapter(BaseLLMAdapter):
    provider = "boom"
    model = "boom"

    def generate(self, prompt: str, system: str = "", metadata: dict | None = None) -> str:
        raise RuntimeError("adapter boom")


def make_frame(command: str, trigger: dict | None = None, inputs: dict | None = None) -> tuple:
    manifest = Manifest(
        manifest_id="llm.test",
        name="LLM Test",
        version=1,
        trigger={"type": "manual"},
        inputs=[],
        steps=[ManifestStep(id="step_1", command=command, parsed_command=parse_command(command))],
        validations=[],
        completion={"success_outputs": ["result"]},
        raw={"manifest_id": "llm.test"},
    )
    frame = create_taskframe(manifest, trigger=trigger or {}, inputs=inputs or {})
    frame.state = "READY"
    return frame


class LLMCommandTests(unittest.TestCase):
    def test_parser_parses_llm_commands(self):
        parsed = parse_command('[q:summarize -> summary] text=$inputs.message; max_words=30')
        self.assertEqual(parsed.kind, "llm")
        self.assertEqual(parsed.namespace, "q")
        self.assertEqual(parsed.action, "summarize")

        parsed = parse_command('[q:extract -> extracted] schema="order_ref"; text=$inputs.message')
        self.assertEqual(parsed.action, "extract")

        parsed = parse_command('[q:classify -> category] labels="order_status,refund,other"; text=$inputs.message')
        self.assertEqual(parsed.action, "classify")

        parsed = parse_command('[q:draft -> reply] instruction="Draft reply"; context=$inputs.message')
        self.assertEqual(parsed.action, "draft")

        parsed = parse_command('[q:compare -> comparison] left=$inputs.a; right=$inputs.b; criteria="same meaning"')
        self.assertEqual(parsed.action, "compare")

    def test_parser_rejects_blocked_q_execute(self):
        with self.assertRaises(CommandParseError):
            parse_command('[q:execute -> result] send this email')

    def test_summarize_writes_output(self):
        frame = make_frame('[q:summarize -> summary] text=$inputs.message; max_words=30', inputs={"message": "Hello world"})
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"summarize": "short summary"}))

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertEqual(frame.outputs["summary"], "short summary")
        self.assertEqual(frame.steps[0].status, "COMPLETED")

    def test_extract_parses_json_output(self):
        frame = make_frame('[q:extract -> extracted] schema="order_ref"; text=$inputs.message', inputs={"message": "ORD-10042"})
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"extract": '{"order_ref": "ORD-10042", "confidence": "high"}'}))

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertEqual(frame.outputs["extracted"]["order_ref"], "ORD-10042")
        self.assertEqual(frame.steps[0].status, "COMPLETED")

    def test_classify_parses_json_output(self):
        frame = make_frame(
            '[q:classify -> category] labels="order_status,refund,complaint,other"; text=$inputs.message',
            inputs={"message": "Where is my order?"},
        )
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"classify": '{"label": "order_status", "confidence": "high", "reason": "asks status"}'}))

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertEqual(frame.outputs["category"]["label"], "order_status")

    def test_classify_rejects_label_outside_allowed_labels(self):
        frame = make_frame(
            '[q:classify -> category] labels="order_status,refund,complaint,other"; text=$inputs.message',
            inputs={"message": "Where is my order?"},
        )
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"classify": '{"label": "invalid", "confidence": "high"}'}))

        result = runner.run_step(frame, frame.steps[0])

        self.assertFalse(result.ok)
        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertEqual(frame.state, "FAILED_EXECUTION")

    def test_draft_writes_output(self):
        frame = make_frame(
            '[q:draft -> reply] instruction="Draft a short reply"; context=$inputs.message; tone="plain"',
            inputs={"message": "Please reply"},
        )
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"draft": "Sure, here is a reply."}))

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertEqual(frame.outputs["reply"], "Sure, here is a reply.")

    def test_compare_parses_json_output(self):
        frame = make_frame(
            '[q:compare -> comparison] left=$summary; right=$inputs.evidence; criteria="same order reference"',
            inputs={"evidence": "ORD-10042"},
        )
        frame.outputs["summary"] = "ORD-10042"
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"compare": '{"match": true, "summary": "same order", "differences": []}'}))

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertTrue(frame.outputs["comparison"]["match"])

    def test_llm_command_resolves_inputs_refs(self):
        frame = make_frame('[q:summarize -> summary] text=$inputs.message; max_words=30', inputs={"message": "Hello there"})
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"summarize": "Hello there"}))

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertEqual(frame.outputs["summary"], "Hello there")

    def test_llm_command_resolves_event_refs(self):
        frame = make_frame('[q:summarize -> summary] text=$event.message; max_words=30', trigger={"message": "Hello event"})
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"summarize": "Hello event"}))

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertEqual(frame.outputs["summary"], "Hello event")

    def test_llm_command_resolves_output_refs(self):
        frame = make_frame('[q:compare -> comparison] left=$summary; right=$inputs.evidence; criteria="same order reference"', inputs={"evidence": "ORD-10042"})
        frame.outputs["summary"] = "ORD-10042"
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"compare": '{"match": true, "summary": "same order", "differences": []}'}))

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertEqual(frame.outputs["comparison"]["summary"], "same order")

    def test_llm_command_marks_step_completed_on_success(self):
        frame = make_frame('[q:draft -> reply] instruction="Draft"; context=$inputs.message', inputs={"message": "Hello"})
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"draft": "Hello"}))

        runner.run_step(frame, frame.steps[0])

        self.assertEqual(frame.steps[0].status, "COMPLETED")

    def test_llm_command_marks_step_failed_on_adapter_error(self):
        frame = make_frame('[q:draft -> reply] instruction="Draft"; context=$inputs.message', inputs={"message": "Hello"})
        runner = LLMCommandRunner(adapter=BoomAdapter())

        result = runner.run_step(frame, frame.steps[0])

        self.assertFalse(result.ok)
        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertEqual(frame.state, "FAILED_EXECUTION")

    def test_llm_command_records_frame_llm_calls(self):
        frame = make_frame('[q:draft -> reply] instruction="Draft"; context=$inputs.message', inputs={"message": "Hello"})
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"draft": "Hello"}))

        runner.run_step(frame, frame.steps[0])

        self.assertEqual(len(frame.llm_calls), 1)
        self.assertEqual(frame.llm_calls[0]["action"], "draft")
        self.assertTrue(frame.llm_calls[0]["ok"])

    def test_llm_command_records_audit_events(self):
        frame = make_frame('[q:draft -> reply] instruction="Draft"; context=$inputs.message', inputs={"message": "Hello"})
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"draft": "Hello"}))

        runner.run_step(frame, frame.steps[0])

        event_types = [event.event_type for event in frame.audit]
        self.assertIn("LLM_COMMAND_STARTED", event_types)
        self.assertIn("LLM_COMMAND_COMPLETED", event_types)

    def test_llm_command_does_not_write_memory(self):
        frame = make_frame('[q:draft -> reply] instruction="Draft"; context=$inputs.message', inputs={"message": "Hello"})
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"draft": "Hello"}))

        runner.run_step(frame, frame.steps[0])

        self.assertEqual(frame.pending_actions, [])
        self.assertEqual(frame.tool_calls, [])

    def test_llm_command_does_not_stage_pending_action(self):
        frame = make_frame('[q:draft -> reply] instruction="Draft"; context=$inputs.message', inputs={"message": "Hello"})
        runner = LLMCommandRunner(adapter=FakeLLMAdapter({"draft": "Hello"}))

        runner.run_step(frame, frame.steps[0])

        self.assertEqual(frame.pending_actions, [])
        self.assertEqual(frame.tool_calls, [])

    def test_llm_micro_tool_writes_output_and_llm_call(self):
        frame = make_frame('[q:extract_order_ref -> order_ref] text=$inputs.message', inputs={"message": "Please check ORD-10042."})
        runner = LLMCommandRunner(
            adapter=FakeLLMAdapter({"extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}'})
        )

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertEqual(frame.outputs["order_ref"]["order_ref"], "ORD-10042")
        self.assertEqual(len(frame.llm_calls), 1)
        self.assertTrue(frame.llm_calls[0]["metadata"]["micro_tool"])
        self.assertEqual(frame.steps[0].status, "COMPLETED")

    def test_llm_micro_tool_validation_failure_fails_step(self):
        frame = make_frame('[q:extract_order_ref -> order_ref] text=$inputs.message', inputs={"message": "Please check ORD-10042."})
        runner = LLMCommandRunner(
            adapter=FakeLLMAdapter({"extract_order_ref": '{"order_ref": "BAD-10042", "confidence": "high", "reason": "Detected explicit order reference."}'})
        )

        result = runner.run_step(frame, frame.steps[0])

        self.assertFalse(result.ok)
        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertEqual(frame.state, "FAILED_EXECUTION")
        self.assertTrue(frame.errors)

    def test_llm_micro_tool_does_not_create_pending_action_or_tool_call(self):
        frame = make_frame('[q:extract_order_ref -> order_ref] text=$inputs.message', inputs={"message": "Please check ORD-10042."})
        runner = LLMCommandRunner(
            adapter=FakeLLMAdapter({"extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}'})
        )

        runner.run_step(frame, frame.steps[0])

        self.assertEqual(frame.pending_actions, [])
        self.assertEqual(frame.tool_calls, [])


if __name__ == "__main__":
    unittest.main()
