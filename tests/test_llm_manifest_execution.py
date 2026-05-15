import json
import tempfile
import unittest
from pathlib import Path

from runtime.events import create_event
from runtime.llm_adapter import FakeLLMAdapter
from runtime.runtime_engine import RuntimeEngine


SMOKE_MANIFEST_DIR = Path("tests/fixtures/smoke_manifests")


def write_manifest(tmpdir: Path, data: dict, filename: str) -> Path:
    path = tmpdir / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def write_routes(tmpdir: Path, routes: list[dict]) -> Path:
    path = tmpdir / "event_routes.json"
    path.write_text(json.dumps({"routes": routes}, indent=2), encoding="utf-8")
    return path


def build_smoke_engine(tmpdir: Path, llm_adapter: FakeLLMAdapter) -> RuntimeEngine:
    write_routes(
        tmpdir,
        [
            {"event_type": "manual.llm_summarize", "manifest_id": "smoke.llm_summarize", "enabled": True},
            {"event_type": "manual.llm_extract", "manifest_id": "smoke.llm_extract", "enabled": True},
            {"event_type": "manual.llm_classify", "manifest_id": "smoke.llm_classify", "enabled": True},
            {"event_type": "manual.llm_draft", "manifest_id": "smoke.llm_draft", "enabled": True},
        ],
    )
    return RuntimeEngine(
        routes_path=tmpdir / "event_routes.json",
        manifest_dir=SMOKE_MANIFEST_DIR,
        runtime_data_dir=tmpdir / "runtime_data",
        llm_adapter=llm_adapter,
    )


class LLMManifestExecutionTests(unittest.TestCase):
    def test_smoke_llm_summarize_completes_with_fake_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            adapter = FakeLLMAdapter({"summarize": "Customer asks for order status on ORD-10042."})
            engine = build_smoke_engine(tmpdir, adapter)
            event = create_event(
                event_type="manual.llm_summarize",
                source="manual",
                payload={"message": "Hi, can you tell me where my order ORD-10042 is?"},
            )

            frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.outputs["summary"], "Customer asks for order status on ORD-10042.")
        self.assertTrue(frame.llm_calls[0]["ok"])

    def test_smoke_llm_extract_completes_with_fake_adapter_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            adapter = FakeLLMAdapter({"extract": '{"order_ref": "ORD-10042", "confidence": "high"}'})
            engine = build_smoke_engine(tmpdir, adapter)
            event = create_event(
                event_type="manual.llm_extract",
                source="manual",
                payload={"message": "Please check order ORD-10042."},
            )

            frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.outputs["extracted"]["order_ref"], "ORD-10042")
        self.assertIn("extracted_has_required_fields", [item["validation_id"] for item in frame.validations])

    def test_smoke_llm_classify_completes_with_fake_adapter_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            adapter = FakeLLMAdapter({"classify": '{"label": "order_status", "confidence": "high", "reason": "Asks where order is."}'})
            engine = build_smoke_engine(tmpdir, adapter)
            event = create_event(
                event_type="manual.llm_classify",
                source="manual",
                payload={"message": "Where is my order ORD-10042?"},
            )

            frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.outputs["category"]["label"], "order_status")
        validation_ids = [item["validation_id"] for item in frame.validations]
        self.assertIn("category_has_required_fields", validation_ids)
        self.assertIn("category_label_is_order_status", validation_ids)
        self.assertIn("category_label_allowed", validation_ids)

    def test_smoke_llm_draft_completes_with_fake_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            adapter = FakeLLMAdapter({"draft": "Sure, here is a short reply."})
            engine = build_smoke_engine(tmpdir, adapter)
            event = create_event(
                event_type="manual.llm_draft",
                source="manual",
                payload={"message": "Please reply to the customer."},
            )

            frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.outputs["reply"], "Sure, here is a short reply.")
        self.assertTrue(frame.llm_calls[0]["ok"])

    def test_runtime_engine_handles_manual_llm_summarize_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            adapter = FakeLLMAdapter({"summarize": "Summary text."})
            engine = build_smoke_engine(tmpdir, adapter)
            event = create_event("manual.llm_summarize", "manual", payload={"message": "Hello"})

            frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "smoke.llm_summarize")
        self.assertEqual(frame.state, "COMPLETED")

    def test_runtime_engine_handles_manual_llm_extract_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            adapter = FakeLLMAdapter({"extract": '{"order_ref": "ORD-10042", "confidence": "high"}'})
            engine = build_smoke_engine(tmpdir, adapter)
            event = create_event("manual.llm_extract", "manual", payload={"message": "Order ORD-10042"})

            frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "smoke.llm_extract")
        self.assertEqual(frame.state, "COMPLETED")

    def test_runtime_engine_handles_manual_llm_classify_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            adapter = FakeLLMAdapter({"classify": '{"label": "order_status", "confidence": "high", "reason": "status"}'})
            engine = build_smoke_engine(tmpdir, adapter)
            event = create_event("manual.llm_classify", "manual", payload={"message": "Where is my order?"})

            frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "smoke.llm_classify")
        self.assertEqual(frame.state, "COMPLETED")

    def test_runtime_engine_handles_manual_llm_draft_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            adapter = FakeLLMAdapter({"draft": "Reply text."})
            engine = build_smoke_engine(tmpdir, adapter)
            event = create_event("manual.llm_draft", "manual", payload={"message": "Please reply."})

            frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "smoke.llm_draft")
        self.assertEqual(frame.state, "COMPLETED")

    def test_llm_extract_order_ref_manifest_completes_with_fake_adapter(self):
        adapter = FakeLLMAdapter(
            {
                "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}'
            }
        )
        engine = RuntimeEngine(llm_adapter=adapter)
        event = create_event("manual.llm_extract_order_ref", "operator_ui", payload={"message": "Please check order ORD-10042."})

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "llm.extract_order_ref")
        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.outputs["order_ref"]["order_ref"], "ORD-10042")

    def test_llm_classify_customer_message_manifest_completes_with_fake_adapter(self):
        adapter = FakeLLMAdapter(
            {
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}'
            }
        )
        engine = RuntimeEngine(llm_adapter=adapter)
        event = create_event("manual.llm_classify_customer_message", "operator_ui", payload={"message": "Where is my order ORD-10042?"})

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "llm.classify_customer_message")
        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.outputs["category"]["label"], "order_status")

    def test_llm_customer_status_reply_manifest_completes_with_fake_adapter(self):
        adapter = FakeLLMAdapter(
            {
                "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Hi, your order ORD-10042 has shipped and is in transit.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches order and shipment facts."}',
            }
        )
        engine = RuntimeEngine(llm_adapter=adapter)
        event = create_event(
            "manual.llm_customer_status_reply",
            "operator_ui",
            payload={"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?"},
        )

        frame = engine.handle_event(event, dry_run=True)

        self.assertEqual(frame.manifest_id, "llm.customer_status_reply")
        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        self.assertIn("draft_reply", frame.outputs)
        self.assertIn("reply_check", frame.outputs)

    def test_bad_json_extraction_fails_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(
                tmpdir,
                {
                    "manifest_id": "temp.llm_extract",
                    "name": "Temp LLM Extract",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["message"],
                    "steps": [
                        {
                            "id": "extract_order_ref",
                            "command": '[q:extract -> extracted] schema="order_ref"; text=$inputs.message',
                        }
                    ],
                    "validations": [
                        {"id": "no_errors", "type": "no_errors"},
                        {"id": "step_completed", "type": "step_completed", "step": "extract_order_ref"},
                        {"id": "extracted_output_exists", "type": "output_exists", "output": "extracted"},
                    ],
                    "completion": {"success_outputs": ["extracted"]},
                },
                "temp_llm_extract.manifest.json",
            )
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.temp_llm_extract", "manifest_id": "temp.llm_extract", "enabled": True},
                ],
            )
            engine = RuntimeEngine(
                routes_path=tmpdir / "event_routes.json",
                manifest_dir=tmpdir,
                llm_adapter=FakeLLMAdapter({"extract": "not json"}),
            )
            event = create_event("manual.temp_llm_extract", "manual", payload={"message": "Order ORD-10042"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.state, "FAILED_EXECUTION")
            self.assertTrue(frame.errors)

    def test_invalid_classification_label_fails_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(
                tmpdir,
                {
                    "manifest_id": "temp.llm_classify",
                    "name": "Temp LLM Classify",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["message"],
                    "steps": [
                        {
                            "id": "classify_message",
                            "command": '[q:classify -> category] labels="order_status,refund,complaint,other"; text=$inputs.message',
                        }
                    ],
                    "validations": [
                        {"id": "no_errors", "type": "no_errors"},
                        {"id": "step_completed", "type": "step_completed", "step": "classify_message"},
                        {"id": "category_output_exists", "type": "output_exists", "output": "category"},
                    ],
                    "completion": {"success_outputs": ["category"]},
                },
                "temp_llm_classify.manifest.json",
            )
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.temp_llm_classify", "manifest_id": "temp.llm_classify", "enabled": True},
                ],
            )
            engine = RuntimeEngine(
                routes_path=tmpdir / "event_routes.json",
                manifest_dir=tmpdir,
                llm_adapter=FakeLLMAdapter({"classify": '{"label": "invalid", "confidence": "high"}'}),
            )
            event = create_event("manual.temp_llm_classify", "manual", payload={"message": "Where is my order?"})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.state, "FAILED_EXECUTION")
            self.assertTrue(frame.errors)


if __name__ == "__main__":
    unittest.main()
