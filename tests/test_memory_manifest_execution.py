import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runtime.events import create_event
from runtime.manifest_loader import load_manifest
from runtime.memory_store import MemoryStore
from runtime.orchestrator import Orchestrator
from runtime.runtime_engine import RuntimeEngine
from runtime.validation import run_validation


class MemoryManifestExecutionTests(unittest.TestCase):
    def test_smoke_memory_set_completes(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            orch = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_memory_set.manifest.json")

            frame = orch.create_frame_from_manifest(manifest, inputs={"key": "supplier.ABC.preferred_channel", "value": "email"})
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(store.get("supplier.ABC.preferred_channel").value, "email")

    def test_smoke_memory_get_completes_after_prior_set(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            orch = Orchestrator(memory_store=store)
            store.set("supplier.ABC.preferred_channel", "email")
            manifest = load_manifest("manifests/smoke_memory_get.manifest.json")

            frame = orch.create_frame_from_manifest(manifest, inputs={"key": "supplier.ABC.preferred_channel"})
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertTrue(frame.outputs["memory_value"]["found"])
            self.assertEqual(frame.outputs["memory_value"]["value"], "email")

    def test_smoke_memory_get_missing_completes_for_missing_key_when_manifest_expects_missing(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            orch = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_memory_get_missing.manifest.json")

            frame = orch.create_frame_from_manifest(manifest, inputs={"key": "supplier.ABC.lead_time_days"})
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertFalse(frame.outputs["memory_value"]["found"])

    def test_memory_set_writes_durable_file(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            orch = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_memory_set.manifest.json")

            frame = orch.create_frame_from_manifest(manifest, inputs={"key": "gobook.default_court", "value": "Court 1"})
            frame = orch.prepare_frame(frame)
            orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(store.get("gobook.default_court").value, "Court 1")

    def test_memory_get_reads_durable_file(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            store.set("gobook.default_court", "Court 1")
            orch = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_memory_get.manifest.json")

            frame = orch.create_frame_from_manifest(manifest, inputs={"key": "gobook.default_court"})
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.outputs["memory_value"]["value"], "Court 1")

    def test_runtime_engine_handles_manual_memory_set_event(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            engine = RuntimeEngine(memory_store=store)
            event = create_event(
                event_type="manual.memory_set",
                source="manual",
                payload={"key": "gobook.default_court", "value": "Court 1"},
            )

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(store.get("gobook.default_court").value, "Court 1")

    def test_runtime_engine_handles_manual_memory_get_event(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            store.set("gobook.default_court", "Court 1")
            engine = RuntimeEngine(memory_store=store)
            event = create_event(
                event_type="manual.memory_get",
                source="manual",
                payload={"key": "gobook.default_court"},
            )

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertTrue(frame.outputs["memory_value"]["found"])
            self.assertEqual(frame.outputs["memory_value"]["value"], "Court 1")

    def test_memory_outputs_are_taskframe_local_but_values_persist_in_store(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            orch = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_memory_set.manifest.json")

            frame = orch.create_frame_from_manifest(manifest, inputs={"key": "supplier.ABC.preferred_channel", "value": "email"})
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertIn("saved_memory", frame.outputs)
            self.assertEqual(store.get("supplier.ABC.preferred_channel").value, "email")

    def test_memory_validation_memory_output_found_passes(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            orch = Orchestrator(memory_store=store)
            store.set("supplier.ABC.preferred_channel", "email")
            manifest = load_manifest("manifests/smoke_memory_get.manifest.json")

            frame = orch.create_frame_from_manifest(manifest, inputs={"key": "supplier.ABC.preferred_channel"})
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertTrue(any(v["type"] == "memory_output_found" and v["ok"] is True for v in frame.validations))

    def test_memory_validation_memory_output_missing_passes(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            orch = Orchestrator(memory_store=store)
            manifest = load_manifest("manifests/smoke_memory_get_missing.manifest.json")

            frame = orch.create_frame_from_manifest(manifest, inputs={"key": "supplier.ABC.lead_time_days"})
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertTrue(any(v["type"] == "memory_output_missing" and v["ok"] is True for v in frame.validations))

    def test_memory_key_exists_passes_and_fails(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            store.set("supplier.ABC.preferred_channel", "email")
            manifest = load_manifest("manifests/smoke_memory_get.manifest.json")
            frame = Orchestrator(memory_store=store).create_frame_from_manifest(manifest, inputs={"key": "supplier.ABC.preferred_channel"})

            ok = run_validation(frame, {"id": "memory_key_exists", "type": "memory_key_exists", "key": "supplier.ABC.preferred_channel"}, memory_store=store)
            fail = run_validation(frame, {"id": "memory_key_exists", "type": "memory_key_exists", "key": "missing.key"}, memory_store=store)

            self.assertTrue(ok.ok)
            self.assertFalse(fail.ok)


if __name__ == "__main__":
    unittest.main()
