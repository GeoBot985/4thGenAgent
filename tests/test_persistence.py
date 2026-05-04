import json
import tempfile
import unittest
from pathlib import Path

from runtime.manifest_loader import load_manifest
from runtime.persistence import (
    AUDIT_FILE,
    OUTPUTS_FILE,
    SUMMARY_FILE,
    TASKFRAME_FILE,
    ensure_dir,
    get_frame_dir,
    get_runs_dir,
    get_taskframe_path,
    load_taskframe_dict,
    read_json,
    save_taskframe,
    taskframe_exists,
    write_json_atomic,
)
from runtime.taskframe import create_taskframe, json_safe, build_taskframe_summary


class PersistenceTests(unittest.TestCase):
    def test_ensure_dir_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "dir"
            result = ensure_dir(path)
            self.assertTrue(result.is_dir())

    def test_get_runs_dir_returns_runtime_runs_path(self):
        self.assertEqual(get_runs_dir("runtime_data"), Path("runtime_data") / "runs")

    def test_get_frame_dir_returns_frame_path(self):
        self.assertEqual(get_frame_dir("frame_1", "runtime_data"), Path("runtime_data") / "runs" / "frame_1")

    def test_get_taskframe_path_returns_taskframe_json_path(self):
        self.assertEqual(
            get_taskframe_path("frame_1", "runtime_data"),
            Path("runtime_data") / "runs" / "frame_1" / TASKFRAME_FILE,
        )

    def test_write_json_atomic_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            write_json_atomic(path, {"hello": "world"})
            self.assertEqual(read_json(path), {"hello": "world"})

    def test_write_json_atomic_replaces_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            write_json_atomic(path, {"value": 1})
            write_json_atomic(path, {"value": 2})
            self.assertEqual(read_json(path), {"value": 2})

    def test_read_json_reads_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            path.write_text(json.dumps({"value": 1}), encoding="utf-8")
            self.assertEqual(read_json(path), {"value": 1})

    def test_save_taskframe_creates_frame_directory_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
            frame = create_taskframe(manifest)
            frame.outputs["unread_mail"] = [{"id": "1"}]
            frame.audit  # ensure audit exists
            frame_dir = save_taskframe(frame, tmp)

            self.assertTrue(frame_dir.is_dir())
            self.assertTrue((frame_dir / TASKFRAME_FILE).is_file())
            self.assertTrue((frame_dir / AUDIT_FILE).is_file())
            self.assertTrue((frame_dir / OUTPUTS_FILE).is_file())
            self.assertTrue((frame_dir / SUMMARY_FILE).is_file())

    def test_load_taskframe_dict_reads_saved_taskframe(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
            frame = create_taskframe(manifest)
            save_taskframe(frame, tmp)

            data = load_taskframe_dict(frame.frame_id, tmp)
            self.assertEqual(data["frame_id"], frame.frame_id)

    def test_taskframe_exists_returns_true_for_saved_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
            frame = create_taskframe(manifest)
            save_taskframe(frame, tmp)

            self.assertTrue(taskframe_exists(frame.frame_id, tmp))

    def test_taskframe_exists_returns_false_for_missing_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(taskframe_exists("missing", tmp))

    def test_summary_contains_expected_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
            frame = create_taskframe(manifest)
            summary = build_taskframe_summary(frame)

            self.assertEqual(summary["frame_id"], frame.frame_id)
            self.assertEqual(summary["manifest_id"], frame.manifest_id)
            self.assertEqual(summary["state"], frame.state)
            self.assertIn("step_count", summary)
            self.assertIn("output_keys", summary)

    def test_json_safe_handles_path_exception_and_unknown(self):
        class Unknown:
            def __str__(self):
                return "unknown-object"

        self.assertEqual(json_safe(Path("x/y")), str(Path("x/y")))
        self.assertEqual(json_safe(Exception("boom")), "boom")
        self.assertEqual(json_safe(Unknown()), "unknown-object")


if __name__ == "__main__":
    unittest.main()
