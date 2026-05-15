import json
import sys
import tempfile
import types
import unittest
import time
from pathlib import Path

from runtime.errors import ManifestRouteNotFoundError
from runtime.events import create_event
from runtime.llm_adapter import FakeLLMAdapter
from runtime.memory_store import MemoryStore
from runtime.persistence import load_taskframe_dict, taskframe_exists
from runtime.runtime_engine import RuntimeEngine
from runtime.tool_registry import TOOL_REGISTRY


SMOKE_MANIFEST_DIR = Path("tests/fixtures/smoke_manifests")
SMOKE_ROUTES_PATH = SMOKE_MANIFEST_DIR / "event_routes.json"


def write_manifest(tmpdir: Path, manifest_id: str, command: str, validations: list, completion: dict, inputs: list | None = None) -> Path:
    path = tmpdir / f"{manifest_id.replace('.', '_')}.manifest.json"
    path.write_text(
        json.dumps(
            {
                "manifest_id": manifest_id,
                "name": manifest_id,
                "version": 1,
                "trigger": {"type": "manual"},
                "inputs": inputs or [],
                "steps": [{"id": "step_1", "command": command}],
                "validations": validations,
                "completion": completion,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


class FlakyLLMAdapter:
    provider = "fake"
    model = "fake"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, system: str = "", metadata: dict | None = None) -> str:
        self.calls += 1
        if self.calls - 1 < len(self.responses):
            return self.responses[self.calls - 1]
        return self.responses[-1]


def write_routes(tmpdir: Path, routes: list[dict]) -> Path:
    path = tmpdir / "event_routes.json"
    path.write_text(json.dumps({"routes": routes}, indent=2), encoding="utf-8")
    return path


class RuntimeEngineTests(unittest.TestCase):
    def setUp(self):
        self.saved_registry: dict[str, dict | None] = {}
        self._modules_to_cleanup: list[str] = []
        self.fake_module_name = "fake_engine_tools"
        self.fake_module = types.ModuleType(self.fake_module_name)

        def fake_read(limit=5):
            return [{"id": "1", "limit": limit}]

        async def fake_async_read(name: str):
            return {"name": name, "ok": True}

        self.fake_module.fake_read = fake_read
        self.fake_module.fake_async_read = fake_async_read
        sys.modules[self.fake_module_name] = self.fake_module

    def tearDown(self):
        for key, value in self.saved_registry.items():
            if value is None:
                TOOL_REGISTRY.pop(key, None)
            else:
                TOOL_REGISTRY[key] = value
        for module_name in self._modules_to_cleanup:
            sys.modules.pop(module_name, None)
        sys.modules.pop(self.fake_module_name, None)

    def _register_tool(self, key: str, spec: dict) -> None:
        if key not in self.saved_registry:
            self.saved_registry[key] = TOOL_REGISTRY.get(key)
        TOOL_REGISTRY[key] = spec

    def _install_fake_module(self, module_name: str, **attrs) -> None:
        module = types.ModuleType(module_name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[module_name] = module
        self._modules_to_cleanup.append(module_name)

    def test_handle_event_routes_event_to_manifest_and_creates_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(
                tmpdir,
                "smoke.gmail_check",
                "[t:g/check -> unread_mail] max_results=5",
                [
                    {"id": "no_errors", "type": "no_errors"},
                    {"id": "no_step_failed", "type": "no_step_failed"},
                    {"id": "check_mail_step_completed", "type": "step_completed", "step": "step_1"},
                    {"id": "unread_mail_output_exists", "type": "output_exists", "output": "unread_mail"},
                ],
                {"success_outputs": ["unread_mail"], "acceptable_empty_outputs": ["unread_mail"]},
            )
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gmail_check", "manifest_id": "smoke.gmail_check", "enabled": True},
                ],
            )
            engine = RuntimeEngine(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)
            event = create_event("manual.gmail_check", "manual")

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.manifest_id, "smoke.gmail_check")
            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.trigger["event_id"], event.event_id)
            self.assertEqual(frame.inputs, {})

    def test_handle_event_stores_event_fields_in_trigger_and_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(
                tmpdir,
                "smoke.gobook_open_courts",
                "[t:gb/open_courts -> open_slots] date=$inputs.date; start=$inputs.start; end=$inputs.end; slowmo=100",
                [
                    {"id": "date_input_exists", "type": "required_input_exists", "input": "date"},
                    {"id": "start_input_exists", "type": "required_input_exists", "input": "start"},
                    {"id": "end_input_exists", "type": "required_input_exists", "input": "end"},
                    {"id": "open_slots_output_exists", "type": "output_exists", "output": "open_slots"},
                ],
                {"success_outputs": ["open_slots"], "acceptable_empty_outputs": ["open_slots"]},
                inputs=["date", "start", "end"],
            )
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gobook_open_courts", "manifest_id": "smoke.gobook_open_courts", "enabled": True},
                ],
            )
            engine = RuntimeEngine(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)
            event = create_event(
                "manual.gobook_open_courts",
                "manual",
                payload={"date": "2026-05-01", "start": "17:00", "end": "20:00"},
            )

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.trigger["event_type"], "manual.gobook_open_courts")
            self.assertEqual(frame.inputs["date"], "2026-05-01")
            self.assertIn("open_slots", frame.outputs)
            self.assertIn("EVENT_RECEIVED", [item.event_type for item in frame.audit])

    def test_handle_event_runs_dry_run_read_only_task_to_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(
                tmpdir,
                "smoke.gmail_check",
                "[t:g/check -> unread_mail] max_results=5",
                [
                    {"id": "no_errors", "type": "no_errors"},
                    {"id": "no_step_failed", "type": "no_step_failed"},
                    {"id": "check_mail_step_completed", "type": "step_completed", "step": "step_1"},
                    {"id": "unread_mail_output_exists", "type": "output_exists", "output": "unread_mail"},
                ],
                {"success_outputs": ["unread_mail"], "acceptable_empty_outputs": ["unread_mail"]},
            )
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gmail_check", "manifest_id": "smoke.gmail_check", "enabled": True},
                ],
            )
            engine = RuntimeEngine(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)
            event = create_event("manual.gmail_check", "manual")

            frame = engine.handle_event(event, dry_run=True)

            self.assertIn(frame.state, {"COMPLETED", "COMPLETED_NO_DATA"})
            self.assertIn("unread_mail", frame.outputs)

    def test_handle_event_can_stage_side_effect_task(self):
        engine = RuntimeEngine()
        event = create_event("manual.whatsapp_stage_send", "manual")

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "smoke.whatsapp_stage_send")
        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        self.assertEqual(len(frame.pending_actions), 1)
        self.assertEqual(frame.pending_actions[0]["tool"], "wa/send")

    def test_handle_event_returns_waiting_for_execute_for_staged_side_effect(self):
        engine = RuntimeEngine()
        event = create_event("manual.whatsapp_stage_send", "manual")

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")

    def test_handle_event_handles_gobook_payload_refs_through_inputs(self):
        engine = RuntimeEngine()
        event = create_event(
            "manual.gobook_open_courts",
            "manual",
            payload={"date": "2026-05-01", "start": "17:00", "end": "20:00"},
        )

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "smoke.gobook_open_courts")
        self.assertIn("open_slots", frame.outputs)

    def test_handle_event_does_not_execute_live_side_effects(self):
        engine = RuntimeEngine()
        event = create_event("manual.whatsapp_stage_send", "manual")

        frame = engine.handle_event(event, dry_run=False)

        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        self.assertEqual(len(frame.pending_actions), 1)
        self.assertNotIn("sent_msg", frame.outputs)

    def test_handle_event_dry_run_false_can_execute_fake_read_only_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(
                tmpdir,
                "fake.read",
                "[t:fake/read -> rows] limit=$inputs.limit",
                [
                    {"id": "no_errors", "type": "no_errors"},
                    {"id": "no_step_failed", "type": "no_step_failed"},
                    {"id": "rows_output_exists", "type": "output_exists", "output": "rows"},
                ],
                {"success_outputs": ["rows"]},
                inputs=["limit"],
            )
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.fake_read", "manifest_id": "fake.read", "enabled": True},
                ],
            )
            self._register_tool(
                "fake/read",
                {
                    "namespace": "fake",
                    "action": "read",
                    "module": self.fake_module_name,
                    "function": "fake_read",
                    "side_effect": False,
                    "requires_approval": False,
                    "allow_live": True,
                    "output_type": "fake_read_result",
                    "required_args": [],
                    "optional_args": ["limit"],
                    "arg_types": {"limit": "int"},
                },
            )
            engine = RuntimeEngine(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)
            event = create_event("manual.fake_read", "test", payload={"limit": "3"})

            frame = engine.handle_event(event, dry_run=False)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.outputs["rows"], [{"id": "1", "limit": 3}])
            self.assertTrue(frame.tool_calls[0]["live"])

    def test_handle_event_unknown_event_type_fails(self):
        engine = RuntimeEngine()
        event = create_event("manual.unknown", "manual")

        with self.assertRaises(ManifestRouteNotFoundError):
            engine.handle_event(event, dry_run=True)

    def test_runtime_engine_handles_manual_validate_step_output_exists(self):
        engine = RuntimeEngine()
        event = create_event("manual.validate_step_output_exists", "manual")

        frame = engine.handle_event(event, dry_run=True)

        self.assertIn(frame.state, {"COMPLETED", "COMPLETED_NO_DATA"})
        self.assertEqual(frame.steps[1].status, "COMPLETED")
        self.assertIn("unread_mail", frame.outputs)

    def test_runtime_engine_handles_manual_validate_step_fail_fast(self):
        engine = RuntimeEngine()
        event = create_event("manual.validate_step_fail_fast", "manual")

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.state, "FAILED_VALIDATION")
        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertEqual(frame.steps[1].status, "PENDING")

    def test_runtime_engine_handles_manual_llm_classify_with_validation_step(self):
        adapter = FakeLLMAdapter(
            {
                "classify": '{"label": "order_status", "confidence": "high", "reason": "Asks where order is."}',
                "draft": "Your order is being checked. We will update you shortly.",
            }
        )
        engine = RuntimeEngine(llm_adapter=adapter)
        event = create_event(
            "manual.llm_classify_with_validation_step",
            "manual",
            payload={"message": "Where is my order ORD-10042?"},
        )

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.outputs["category"]["label"], "order_status")
        self.assertTrue(frame.outputs["reply"])

    def test_runtime_engine_handles_manual_condition_equals(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = RuntimeEngine(memory_store=store)
            event = create_event("manual.condition_equals", "manual", payload={"channel": "whatsapp"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertEqual(frame.outputs["saved_channel"]["value"], "whatsapp")
            self.assertEqual(frame.inputs["channel"], "whatsapp")

    def test_runtime_engine_handles_manual_condition_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = RuntimeEngine(memory_store=store)
            event = create_event("manual.condition_skip", "manual", payload={"channel": "email"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].status, "SKIPPED")
            self.assertEqual(frame.steps[1].status, "COMPLETED")
            self.assertNotIn("saved_channel", frame.outputs)
            self.assertIn("fallback_channel", frame.outputs)

    def test_runtime_engine_handles_manual_llm_classify_conditional_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            adapter = FakeLLMAdapter(
                {
                    "classify": '{"label": "refund", "confidence": "high", "reason": "Customer asks for refund."}',
                    "draft": "We received your refund request and will review it.",
                }
            )
            engine = RuntimeEngine(memory_store=store, llm_adapter=adapter)
            event = create_event(
                "manual.llm_classify_conditional_reply",
                "manual",
                payload={"message": "I want a refund for order ORD-10042."},
            )

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.outputs["category"]["label"], "refund")
            self.assertEqual(frame.outputs["reply"], "We received your refund request and will review it.")
            statuses = {step.step_id: step.status for step in frame.steps}
            self.assertEqual(statuses["draft_order_status_reply"], "SKIPPED")
            self.assertEqual(statuses["draft_refund_reply"], "COMPLETED")
            self.assertEqual(statuses["draft_generic_reply"], "SKIPPED")

    def test_runtime_engine_handles_manual_condition_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = RuntimeEngine(memory_store=store)
            event = create_event("manual.condition_all", "manual", payload={"channel": "whatsapp", "priority": "urgent"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.manifest_id, "smoke.condition_all")
            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("saved_branch", frame.outputs)

    def test_runtime_engine_handles_manual_condition_any(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = RuntimeEngine(memory_store=store)
            event = create_event("manual.condition_any", "manual", payload={"priority": "urgent", "category": "other"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.manifest_id, "smoke.condition_any")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("escalation_flag", frame.outputs)

    def test_runtime_engine_handles_manual_condition_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = RuntimeEngine(memory_store=store)
            event = create_event("manual.condition_not", "manual", payload={"channel": "email"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.manifest_id, "smoke.condition_not")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("saved_branch", frame.outputs)

    def test_runtime_engine_handles_manual_llm_branch_escalation(self):
        adapter = FakeLLMAdapter(
            {
                "classify": '{"label": "complaint", "confidence": "high", "reason": "Customer complains."}',
                "draft": "We are sorry about the issue and will escalate it.",
            }
        )
        engine = RuntimeEngine(llm_adapter=adapter)
        event = create_event(
            "manual.llm_branch_escalation",
            "manual",
            payload={"message": "I am unhappy with the service.", "support_chat": "Support Lead"},
        )

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "smoke.llm_branch_escalation")
        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        self.assertEqual(frame.steps[3].status, "STAGED")
        self.assertEqual(frame.pending_actions[0]["tool"], "wa/send")

    def test_runtime_engine_handles_manual_channel_branch_reply(self):
        adapter = FakeLLMAdapter({"draft": "Confirmed. I will handle it."})
        engine = RuntimeEngine(llm_adapter=adapter)
        event = create_event(
            "manual.channel_branch_reply",
            "manual",
            payload={
                "message": "Please confirm.",
                "channel": "whatsapp",
                "chat": "Cornelia",
                "email": "person@example.com",
            },
        )

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "smoke.channel_branch_reply")
        statuses = {step.step_id: step.status for step in frame.steps}
        self.assertEqual(statuses["stage_whatsapp_reply"], "STAGED")
        self.assertEqual(statuses["stage_email_reply"], "PENDING")
        self.assertEqual(frame.pending_actions[0]["tool"], "wa/send")

    def test_runtime_engine_handles_manual_condition_numeric_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = RuntimeEngine(memory_store=store)
            event = create_event("manual.condition_numeric_comparison", "manual", payload={"amount": "1500"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.manifest_id, "smoke.condition_numeric_comparison")
            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("high_value_flag", frame.outputs)

    def test_runtime_engine_handles_manual_condition_time_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = RuntimeEngine(memory_store=store)
            event = create_event("manual.condition_time_window", "manual", payload={"requested_time": "18:00"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.manifest_id, "smoke.condition_time_window")
            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("evening_window", frame.outputs)

    def test_runtime_engine_handles_manual_condition_date_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.json")
            engine = RuntimeEngine(memory_store=store)
            event = create_event("manual.condition_date_window", "manual", payload={"requested_date": "2026-05-15"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.manifest_id, "smoke.condition_date_window")
            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("date_window", frame.outputs)

    def test_runtime_engine_handles_manual_gobook_preferred_window(self):
        engine = RuntimeEngine()
        event = create_event(
            "manual.gobook_preferred_window",
            "manual",
            payload={
                "date": "2026-05-01",
                "start": "17:00",
                "end": "20:00",
                "requested_time": "18:00",
            },
        )

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "smoke.gobook_preferred_window")
        self.assertEqual(frame.steps[0].status, "COMPLETED")
        self.assertIn("open_slots", frame.outputs)

    def test_runtime_engine_handles_manual_retry_tool_success_after_failure(self):
        class FlakyTool:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("temporary failure")
                return {"ok": True, "calls": self.calls}

        self.fake_module.flaky_tool = FlakyTool()
        self._register_tool(
            "fake/flaky",
            {
                "namespace": "fake",
                "action": "flaky",
                "module": self.fake_module_name,
                "function": "flaky_tool",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            },
        )
        engine = RuntimeEngine()
        event = create_event("manual.retry_tool_success_after_failure", "manual")

        frame = engine.handle_event(event, dry_run=False)

        self.assertEqual(frame.manifest_id, "smoke.retry_tool_success_after_failure")
        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.steps[0].attempts, 2)
        self.assertEqual(frame.outputs["result"]["calls"], 2)

    def test_runtime_engine_handles_manual_retry_tool_exhausted(self):
        def always_fail():
            raise RuntimeError("permanent failure")

        self.fake_module.always_fail = always_fail
        self._register_tool(
            "fake/always_fail",
            {
                "namespace": "fake",
                "action": "always_fail",
                "module": self.fake_module_name,
                "function": "always_fail",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            },
        )
        engine = RuntimeEngine()
        event = create_event("manual.retry_tool_exhausted", "manual")

        frame = engine.handle_event(event, dry_run=False)

        self.assertEqual(frame.manifest_id, "smoke.retry_tool_exhausted")
        self.assertEqual(frame.state, "FAILED_EXECUTION")
        self.assertEqual(frame.steps[0].attempts, 3)
        self.assertEqual(frame.steps[0].status, "FAILED")

    def test_runtime_engine_handles_manual_retry_llm_success_after_failure(self):
        adapter = FlakyLLMAdapter(["not json", "{\"order_ref\":\"ORD-10042\",\"confidence\":\"high\"}"])
        engine = RuntimeEngine(llm_adapter=adapter)
        event = create_event(
            "manual.retry_llm_success_after_failure",
            "manual",
            payload={"message": "Where is ORD-10042?"},
        )

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "smoke.retry_llm_success_after_failure")
        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.steps[0].attempts, 2)
        self.assertEqual(frame.outputs["extracted"]["order_ref"], "ORD-10042")

    def test_runtime_engine_handles_manual_retry_no_retry_on_validation(self):
        engine = RuntimeEngine()
        event = create_event("manual.retry_no_retry_on_validation", "manual")

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "smoke.retry_no_retry_on_validation")
        self.assertEqual(frame.state, "FAILED_VALIDATION")
        self.assertEqual(frame.steps[0].attempts, 1)

    def test_runtime_engine_handles_manual_timeout_success(self):
        module_name = "fake_runtime_timeout_tools"

        def fake_fast():
            return {"ok": True}

        self._install_fake_module(module_name, fake_fast=fake_fast)
        self._register_tool(
            "fake/fast",
            {
                "namespace": "fake",
                "action": "fast",
                "module": module_name,
                "function": "fake_fast",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            },
        )
        engine = RuntimeEngine()
        event = create_event("manual.timeout_success", "manual")

        frame = engine.handle_event(event, dry_run=False)

        self.assertEqual(frame.manifest_id, "smoke.timeout_success")
        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.steps[0].status, "COMPLETED")
        self.assertIn("result", frame.outputs)
        self.assertIn("STEP_TIMING_RECORDED", [event.event_type for event in frame.audit])

    def test_runtime_engine_handles_manual_timeout_exceeded(self):
        module_name = "fake_runtime_timeout_tools_slow"

        def fake_slow():
            time.sleep(0.05)
            return {"ok": True}

        self._install_fake_module(module_name, fake_slow=fake_slow)
        self._register_tool(
            "fake/slow",
            {
                "namespace": "fake",
                "action": "slow",
                "module": module_name,
                "function": "fake_slow",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            },
        )
        engine = RuntimeEngine()
        event = create_event("manual.timeout_exceeded", "manual")

        frame = engine.handle_event(event, dry_run=False)

        self.assertEqual(frame.manifest_id, "smoke.timeout_exceeded")
        self.assertEqual(frame.state, "FAILED_EXECUTION")
        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertNotIn("result", frame.outputs)
        self.assertIn("STEP_TIMEOUT_EXCEEDED", [event.event_type for event in frame.audit])

    def test_runtime_engine_handles_manual_timeout_retry_success(self):
        module_name = "fake_runtime_timeout_tools_retry"

        class SlowThenFast:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                if self.calls == 1:
                    time.sleep(0.05)
                return {"ok": True, "calls": self.calls}

        self._install_fake_module(module_name, slow_then_fast=SlowThenFast())
        self._register_tool(
            "fake/slow_then_fast",
            {
                "namespace": "fake",
                "action": "slow_then_fast",
                "module": module_name,
                "function": "slow_then_fast",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            },
        )
        engine = RuntimeEngine()
        event = create_event("manual.timeout_retry_success", "manual")

        frame = engine.handle_event(event, dry_run=False)

        self.assertEqual(frame.manifest_id, "smoke.timeout_retry_success")
        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.steps[0].attempts, 2)
        self.assertTrue(frame.attempts[0]["timed_out"])
        self.assertFalse(frame.attempts[1]["timed_out"])

    def test_runtime_engine_accepts_runtime_data_dir_and_persist_runs_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=False)

            self.assertEqual(engine.runtime_data_dir, Path(tmp))
            self.assertFalse(engine.persist_runs)
            self.assertEqual(engine.inspector.runtime_data_dir, Path(tmp))

    def test_runtime_engine_handles_manual_inspection_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)

            created = engine.handle_event(create_event("manual.gmail_check", "manual"), dry_run=True)
            created_snapshot = load_taskframe_dict(created.frame_id, runtime_dir)
            self.assertEqual(created_snapshot["frame_id"], created.frame_id)

            recent = engine.handle_event(create_event("manual.inspect_recent_runs", "manual"), dry_run=True)
            self.assertIn("runs", recent.outputs)
            self.assertTrue(any(item["frame_id"] == created.frame_id for item in recent.outputs["runs"]["runs"]))
            self.assertNotEqual(recent.frame_id, created.frame_id)

            summary = engine.handle_event(
                create_event("manual.inspect_run_summary", "manual", payload={"frame_id": created.frame_id}),
                dry_run=True,
            )
            self.assertEqual(summary.outputs["run_summary"]["frame_id"], created.frame_id)

            outputs = engine.handle_event(
                create_event("manual.inspect_run_outputs", "manual", payload={"frame_id": created.frame_id}),
                dry_run=True,
            )
            self.assertEqual(outputs.outputs["run_outputs"]["frame_id"], created.frame_id)

            pending = engine.handle_event(
                create_event("manual.whatsapp_stage_send", "manual"),
                dry_run=True,
            )
            self.assertEqual(pending.state, "WAITING_FOR_EXECUTE")
            pending_inspection = engine.handle_event(
                create_event("manual.inspect_run_pending_actions", "manual", payload={"frame_id": pending.frame_id}),
                dry_run=True,
            )
            self.assertEqual(pending_inspection.outputs["run_pending_actions"]["count"], 1)
            self.assertEqual(pending_inspection.outputs["run_pending_actions"]["pending_actions"][0]["tool"], "wa/send")

            self.assertTrue(taskframe_exists(created.frame_id, runtime_dir))
            self.assertTrue(taskframe_exists(recent.frame_id, runtime_dir))

    def test_runtime_engine_persist_runs_false_uses_existing_artifacts_without_creating_new_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            writer = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)
            created = writer.handle_event(create_event("manual.gmail_check", "manual"), dry_run=True)
            source_before = load_taskframe_dict(created.frame_id, runtime_dir)

            reader = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False)
            inspected = reader.handle_event(
                create_event("manual.inspect_run_summary", "manual", payload={"frame_id": created.frame_id}),
                dry_run=True,
            )

            self.assertEqual(inspected.outputs["run_summary"]["frame_id"], created.frame_id)
            self.assertFalse(taskframe_exists(inspected.frame_id, runtime_dir))
            self.assertEqual(load_taskframe_dict(created.frame_id, runtime_dir), source_before)

    def test_runtime_engine_handles_manual_approve_pending_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)
            target = engine.handle_event(create_event("manual.whatsapp_stage_send", "manual"), dry_run=True)
            action_id = target.pending_actions[0]["action_id"]

            approval_frame = engine.handle_event(
                create_event(
                    "manual.approve_pending_action",
                    "manual",
                    payload={
                        "frame_id": target.frame_id,
                        "action_id": action_id,
                        "approved_by": "manual_smoke",
                        "reason": "Dry-run approval test",
                    },
                ),
                dry_run=True,
            )

            self.assertEqual(approval_frame.state, "COMPLETED")
            self.assertEqual(approval_frame.outputs["approval_result"]["status"], "APPROVED")
            self.assertEqual(approval_frame.outputs["approval_result"]["frame_id"], target.frame_id)
            self.assertTrue(taskframe_exists(approval_frame.frame_id, runtime_dir))
            reloaded = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(reloaded["pending_actions"][0]["status"], "APPROVED")

    def test_runtime_engine_handles_manual_reject_pending_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)
            target = engine.handle_event(create_event("manual.whatsapp_stage_send", "manual"), dry_run=True)
            action_id = target.pending_actions[0]["action_id"]

            rejection_frame = engine.handle_event(
                create_event(
                    "manual.reject_pending_action",
                    "manual",
                    payload={
                        "frame_id": target.frame_id,
                        "action_id": action_id,
                        "rejected_by": "manual_smoke",
                        "reason": "Wrong recipient",
                    },
                ),
                dry_run=True,
            )

            self.assertEqual(rejection_frame.state, "COMPLETED")
            self.assertEqual(rejection_frame.outputs["rejection_result"]["status"], "REJECTED")
            self.assertTrue(taskframe_exists(rejection_frame.frame_id, runtime_dir))
            reloaded = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(reloaded["state"], "FAILED_COMPLETION")
            self.assertEqual(reloaded["pending_actions"][0]["status"], "REJECTED")

    def test_runtime_engine_handles_manual_execute_approved_pending_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)
            target = engine.handle_event(create_event("manual.whatsapp_stage_send", "manual"), dry_run=True)
            action_id = target.pending_actions[0]["action_id"]
            engine.handle_event(
                create_event(
                    "manual.approve_pending_action",
                    "manual",
                    payload={
                        "frame_id": target.frame_id,
                        "action_id": action_id,
                        "approved_by": "manual_smoke",
                        "reason": "Dry-run approval test",
                    },
                ),
                dry_run=True,
            )

            execution_frame = engine.handle_event(
                create_event(
                    "manual.execute_approved_pending_actions",
                    "manual",
                    payload={"frame_id": target.frame_id},
                ),
                dry_run=True,
            )

            self.assertEqual(execution_frame.state, "COMPLETED")
            self.assertEqual(execution_frame.outputs["execution_result"]["target_frame_state"], "COMPLETED")
            self.assertTrue(taskframe_exists(execution_frame.frame_id, runtime_dir))
            reloaded = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(reloaded["state"], "COMPLETED")
            self.assertEqual(reloaded["pending_actions"][0]["status"], "EXECUTED")

    def test_runtime_engine_handles_manual_reload_pending_action_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)
            target = engine.handle_event(create_event("manual.whatsapp_stage_send", "manual"), dry_run=True)
            action_id = target.pending_actions[0]["action_id"]

            flow = engine.handle_event(
                create_event(
                    "manual.reload_pending_action_flow",
                    "manual",
                    payload={
                        "frame_id": target.frame_id,
                        "action_id": action_id,
                        "approved_by": "manual_smoke",
                        "reason": "One-step dry-run approval flow",
                    },
                ),
                dry_run=True,
            )

            self.assertEqual(flow.state, "COMPLETED")
            self.assertEqual(flow.outputs["approval_execution_result"]["target_frame_state"], "COMPLETED")
            self.assertTrue(taskframe_exists(flow.frame_id, runtime_dir))
            reloaded = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(reloaded["state"], "COMPLETED")

    def test_runtime_engine_passes_runtime_data_dir_into_approval_command_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)
            self.assertEqual(engine.orchestrator.runtime_data_dir, runtime_dir)
            self.assertEqual(engine.orchestrator.manifest_dir, engine.manifest_dir)
            target = engine.handle_event(create_event("manual.whatsapp_stage_send", "manual"), dry_run=True)
            action_id = target.pending_actions[0]["action_id"]
            frame = engine.handle_event(
                create_event(
                    "manual.approve_pending_action",
                    "manual",
                    payload={
                        "frame_id": target.frame_id,
                        "action_id": action_id,
                        "approved_by": "manual_smoke",
                        "reason": "Dry-run approval test",
                    },
                ),
                dry_run=True,
            )

            self.assertEqual(frame.outputs["approval_result"]["artifact_saved"], True)

    def test_runtime_engine_handles_manual_live_sheet_create_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=Path(tmp), persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH)
            event = create_event("manual.live_sheet_create_allowed", "manual", payload={"title": "Runtime Live Smoke"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.manifest_id, "smoke.live_sheet_create_allowed")
            self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
            self.assertEqual(frame.pending_actions[0]["tool"], "sheet/create")

    def test_runtime_engine_handles_manual_live_sheet_write_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=Path(tmp), persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH)
            event = create_event(
                "manual.live_sheet_write_allowed",
                "manual",
                payload={
                    "spreadsheet_id": "sheet-123",
                    "range_name": "Sheet1!A1:B2",
                    "values_json": "[[\"a\", \"b\"]]",
                    "mode": "append",
                },
            )

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.manifest_id, "smoke.live_sheet_write_allowed")
            self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
            self.assertEqual(frame.pending_actions[0]["tool"], "sheet/write")

    def test_runtime_engine_handles_manual_live_side_effect_blocked_by_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=Path(tmp), persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH)
            event = create_event("manual.live_side_effect_blocked_by_manifest", "manual", payload={"title": "Blocked"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.manifest_id, "smoke.live_side_effect_blocked_by_manifest")
            self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
            self.assertEqual(frame.pending_actions[0]["tool"], "sheet/create")

    def test_runtime_engine_handles_manual_live_side_effect_blocked_by_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=Path(tmp), persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH)
            event = create_event("manual.live_side_effect_blocked_by_tool", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.manifest_id, "smoke.live_side_effect_blocked_by_tool")
            self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
            self.assertEqual(frame.pending_actions[0]["tool"], "wa/send")


if __name__ == "__main__":
    unittest.main()
