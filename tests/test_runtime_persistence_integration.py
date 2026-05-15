import tempfile
import unittest
from pathlib import Path
import json

from runtime.events import create_event
from runtime.manifest_loader import load_manifest
from runtime.persistence import get_frame_dir, load_taskframe_dict, taskframe_exists
from runtime.run_ledger import find_ledger_record, get_ledger_path
from runtime.runtime_engine import RuntimeEngine


def _write_routes(tmpdir: Path, routes: list[dict]) -> Path:
    path = tmpdir / "event_routes.json"
    path.write_text(json.dumps({"routes": routes}, indent=2), encoding="utf-8")
    return path


def _build_failed_validation_engine(tmpdir: Path) -> RuntimeEngine:
    _write_routes(
        tmpdir,
        [
            {"event_type": "manual.validate_step_fail_fast", "manifest_id": "smoke.validate_step_fail_fast", "enabled": True},
        ],
    )
    return RuntimeEngine(
        routes_path=tmpdir / "event_routes.json",
        manifest_dir=Path("tests/fixtures/smoke_manifests"),
        runtime_data_dir=tmpdir,
        persist_runs=True,
    )


class RuntimePersistenceIntegrationTests(unittest.TestCase):
    def test_runtime_engine_persist_runs_true_saves_frame_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            event = create_event("manual.gmail_check", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)

            frame_dir = get_frame_dir(frame.frame_id, tmp)
            self.assertTrue(frame_dir.is_dir())
            self.assertTrue(taskframe_exists(frame.frame_id, tmp))
            self.assertTrue(get_ledger_path(tmp).is_file())

    def test_runtime_engine_saves_snapshot_after_frame_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            event = create_event("manual.gmail_check", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)

            artifact = load_taskframe_dict(frame.frame_id, tmp)
            self.assertEqual(artifact["frame_id"], frame.frame_id)

    def test_runtime_engine_saves_final_snapshot_after_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            event = create_event("manual.gmail_check", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)

            artifact = load_taskframe_dict(frame.frame_id, tmp)
            self.assertEqual(artifact["state"], frame.state)

    def test_runtime_engine_appends_ledger_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            event = create_event("manual.gmail_check", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)

            record = find_ledger_record(frame.frame_id, tmp)
            self.assertIsNotNone(record)
            self.assertEqual(record["frame_id"], frame.frame_id)

    def test_runtime_engine_artifact_state_matches_returned_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            event = create_event("manual.whatsapp_stage_send", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)
            artifact = load_taskframe_dict(frame.frame_id, tmp)

            self.assertEqual(artifact["state"], frame.state)

    def test_runtime_engine_artifact_outputs_match_returned_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            event = create_event("manual.gmail_check", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)
            artifact = load_taskframe_dict(frame.frame_id, tmp)

            self.assertEqual(artifact["outputs"], frame.outputs)

    def test_runtime_engine_persist_runs_false_writes_no_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=False)
            event = create_event("manual.gmail_check", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)

            self.assertFalse(taskframe_exists(frame.frame_id, tmp))
            self.assertFalse(get_ledger_path(tmp).exists())

    def test_runtime_engine_persistence_works_for_completed_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            event = create_event("manual.gmail_check", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)

            self.assertIn(frame.state, {"COMPLETED", "COMPLETED_NO_DATA"})
            self.assertTrue(taskframe_exists(frame.frame_id, tmp))

    def test_runtime_engine_persistence_works_for_waiting_for_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            event = create_event("manual.whatsapp_stage_send", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
            artifact = load_taskframe_dict(frame.frame_id, tmp)
            self.assertEqual(artifact["state"], "WAITING_FOR_EXECUTE")
            self.assertTrue(artifact["pending_actions"])

    def test_runtime_engine_persistence_works_for_failed_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = _build_failed_validation_engine(Path(tmp))
            event = create_event("manual.validate_step_fail_fast", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)

            self.assertEqual(frame.state, "FAILED_VALIDATION")
            artifact = load_taskframe_dict(frame.frame_id, tmp)
            self.assertEqual(artifact["state"], "FAILED_VALIDATION")

    def test_runtime_engine_persistence_works_with_injected_temp_runtime_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            event = create_event("manual.gmail_check", "manual", payload={})

            frame = engine.handle_event(event, dry_run=True)

            self.assertTrue(Path(tmp).joinpath("runs", frame.frame_id, "taskframe.json").is_file())
            self.assertTrue(Path(tmp).joinpath("runs", "index.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
