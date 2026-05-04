import os
import tempfile
import time
import unittest
from pathlib import Path

from runtime.artifact_cleanup import (
    ArtifactCleaner,
    ArtifactCleanupPlanner,
    file_age_days,
    file_size_bytes,
    get_cleanup_dir,
    get_cleanup_report_path,
    is_temp_file,
    load_taskframe_safe,
    new_cleanup_id,
    frame_is_protected,
)
from runtime.errors import CleanupConfirmationError, CleanupExecutionError
from runtime.manifest_loader import load_manifest
from runtime.persistence import PersistenceManager
from runtime.taskframe import create_taskframe


def _touch_old(path: Path, days: float) -> None:
    timestamp = time.time() - (days * 86400.0)
    os.utime(path, (timestamp, timestamp))


class ArtifactCleanupTests(unittest.TestCase):
    def _make_frame(self, runtime_dir: Path, *, state: str = "COMPLETED", pending: int = 0, executed: int = 0):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = state
        for index in range(pending):
            frame.pending_actions.append({"action_id": f"pa_{index}", "tool": "wa/send", "status": "PENDING_APPROVAL"})
        for index in range(executed):
            frame.executed_actions.append({"action_id": f"ea_{index}", "tool": "wa/send", "status": "EXECUTED"})
        PersistenceManager(runtime_dir).save_snapshot(frame)
        return frame

    def _make_report(self, runtime_dir: Path, frame_id: str, name: str = "run_report.html", days_old: float = 2.0) -> Path:
        report_path = runtime_dir / "runs" / frame_id / "reports" / name
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("<html>report</html>", encoding="utf-8")
        _touch_old(report_path, days_old)
        return report_path

    def test_helpers_return_expected_paths_and_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            cleanup_id = new_cleanup_id()
            self.assertTrue(cleanup_id.startswith("cln_"))
            self.assertEqual(get_cleanup_dir(runtime_dir), runtime_dir / "cleanup")
            self.assertEqual(
                get_cleanup_report_path(cleanup_id, runtime_dir),
                runtime_dir / "cleanup" / f"cleanup_{cleanup_id}.json",
            )

            temp_file = runtime_dir / "sample.tmp"
            temp_file.write_text("abc", encoding="utf-8")
            self.assertGreaterEqual(file_age_days(temp_file), 0.0)
            self.assertEqual(file_size_bytes(temp_file), 3)
            self.assertTrue(is_temp_file("x.tmp"))
            self.assertTrue(is_temp_file("x.bak"))
            self.assertTrue(is_temp_file("x.part"))
            self.assertTrue(is_temp_file("~x"))

    def test_discover_report_candidates_finds_old_report_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame(runtime_dir)
            report_path = self._make_report(runtime_dir, frame.frame_id, days_old=5)
            planner = ArtifactCleanupPlanner(runtime_dir)
            policy = {"mode": "reports_only", "delete_reports": True, "max_report_age_days": 0, "protect_states": [], "protect_pending_actions": True, "protect_live_execution": True, "protect_ready_approval_packs": True}

            candidates = planner.discover_report_candidates(policy)

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["path"], str(report_path))
            self.assertFalse(candidates[0]["protected"])

    def test_discover_report_candidates_skips_new_report_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame(runtime_dir)
            self._make_report(runtime_dir, frame.frame_id, days_old=0)
            planner = ArtifactCleanupPlanner(runtime_dir)
            policy = {"mode": "reports_only", "delete_reports": True, "max_report_age_days": 30, "protect_states": [], "protect_pending_actions": True, "protect_live_execution": True, "protect_ready_approval_packs": True}

            candidates = planner.discover_report_candidates(policy)

            self.assertEqual(candidates, [])

    def test_discover_report_candidates_protects_waiting_for_execute_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame(runtime_dir, state="WAITING_FOR_EXECUTE")
            self._make_report(runtime_dir, frame.frame_id, days_old=5)
            planner = ArtifactCleanupPlanner(runtime_dir)
            policy = {"mode": "reports_only", "delete_reports": True, "max_report_age_days": 0, "protect_states": ["WAITING_FOR_EXECUTE"], "protect_pending_actions": True, "protect_live_execution": True, "protect_ready_approval_packs": True}

            candidates = planner.discover_report_candidates(policy)

            self.assertEqual(len(candidates), 1)
            self.assertTrue(candidates[0]["protected"])
            self.assertIn("WAITING_FOR_EXECUTE", candidates[0]["protection_reason"])

    def test_discover_report_candidates_protects_frame_with_pending_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame(runtime_dir, state="COMPLETED", pending=1)
            self._make_report(runtime_dir, frame.frame_id, days_old=5)
            planner = ArtifactCleanupPlanner(runtime_dir)
            policy = {"mode": "reports_only", "delete_reports": True, "max_report_age_days": 0, "protect_states": [], "protect_pending_actions": True, "protect_live_execution": True, "protect_ready_approval_packs": True}

            candidates = planner.discover_report_candidates(policy)

            self.assertEqual(len(candidates), 1)
            self.assertTrue(candidates[0]["protected"])
            self.assertIn("pending actions", candidates[0]["protection_reason"])

    def test_discover_report_candidates_protects_live_execution_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame(runtime_dir, state="COMPLETED", executed=1)
            self._make_report(runtime_dir, frame.frame_id, days_old=5)
            planner = ArtifactCleanupPlanner(runtime_dir)
            policy = {"mode": "reports_only", "delete_reports": True, "max_report_age_days": 0, "protect_states": [], "protect_pending_actions": True, "protect_live_execution": True, "protect_ready_approval_packs": True}

            candidates = planner.discover_report_candidates(policy)

            self.assertEqual(len(candidates), 1)
            self.assertTrue(candidates[0]["protected"])
            self.assertIn("live execution", candidates[0]["protection_reason"])

    def test_discover_index_candidates_finds_artifact_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            index_path = runtime_dir / "runs" / "artifact_index.json"
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text("{}", encoding="utf-8")
            _touch_old(index_path, 2)
            planner = ArtifactCleanupPlanner(runtime_dir)
            policy = {"mode": "indexes_only", "delete_artifact_index": True, "min_age_days": 0}

            candidates = planner.discover_index_candidates(policy)

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["path"], str(index_path))
            self.assertEqual(candidates[0]["candidate_type"], "artifact_index")

    def test_discover_temp_candidates_finds_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            temp_path = runtime_dir / "runs" / "frame_1" / "notes.tmp"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text("temp", encoding="utf-8")
            _touch_old(temp_path, 2)
            planner = ArtifactCleanupPlanner(runtime_dir)
            policy = {"mode": "temp_only", "delete_temp_files": True, "max_temp_age_days": 0}

            candidates = planner.discover_temp_candidates(policy)

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["path"], str(temp_path))
            self.assertEqual(candidates[0]["candidate_type"], "temp_file")

    def test_discover_empty_dir_candidates_excludes_roots_and_finds_nested_empty_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            (runtime_dir / "empty" / "nested").mkdir(parents=True, exist_ok=True)
            (runtime_dir / "runs").mkdir(parents=True, exist_ok=True)
            (runtime_dir / "cleanup").mkdir(parents=True, exist_ok=True)
            planner = ArtifactCleanupPlanner(runtime_dir)
            policy = {"mode": "derived_artifacts_only", "delete_empty_dirs": True}

            candidates = planner.discover_empty_dir_candidates(policy)

            paths = {item["path"] for item in candidates}
            self.assertIn(str(runtime_dir / "empty" / "nested"), paths)
            self.assertNotIn(str(runtime_dir), paths)
            self.assertNotIn(str(runtime_dir / "runs"), paths)
            self.assertNotIn(str(runtime_dir / "cleanup"), paths)

    def test_discover_approval_pack_candidates_finds_old_used_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame(runtime_dir)
            pack_path = runtime_dir / "runs" / frame.frame_id / "approval_packs" / "pack.json"
            pack_path.parent.mkdir(parents=True, exist_ok=True)
            pack_path.write_text('{"status":"USED"}', encoding="utf-8")
            _touch_old(pack_path, 5)
            planner = ArtifactCleanupPlanner(runtime_dir)
            policy = {
                "mode": "approval_packs_only",
                "delete_expired_approval_packs": True,
                "max_approval_pack_age_days": 0,
                "protect_states": [],
                "protect_pending_actions": True,
                "protect_live_execution": True,
                "protect_ready_approval_packs": True,
            }

            candidates = planner.discover_approval_pack_candidates(policy)

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["path"], str(pack_path))
            self.assertFalse(candidates[0]["protected"])

    def test_discover_approval_pack_candidates_protects_ready_for_confirmation_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame(runtime_dir)
            pack_path = runtime_dir / "runs" / frame.frame_id / "approval_packs" / "pack.json"
            pack_path.parent.mkdir(parents=True, exist_ok=True)
            pack_path.write_text('{"status":"READY_FOR_CONFIRMATION"}', encoding="utf-8")
            _touch_old(pack_path, 5)
            planner = ArtifactCleanupPlanner(runtime_dir)
            policy = {
                "mode": "approval_packs_only",
                "delete_expired_approval_packs": True,
                "max_approval_pack_age_days": 0,
                "protect_states": [],
                "protect_pending_actions": True,
                "protect_live_execution": True,
                "protect_ready_approval_packs": True,
            }

            candidates = planner.discover_approval_pack_candidates(policy)

            self.assertEqual(len(candidates), 1)
            self.assertTrue(candidates[0]["protected"])
            self.assertIn("READY_FOR_CONFIRMATION", candidates[0]["protection_reason"])

    def test_plan_cleanup_is_non_destructive_and_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame(runtime_dir)
            report_path = self._make_report(runtime_dir, frame.frame_id, days_old=5)
            cleaner = ArtifactCleaner(runtime_dir)

            result = cleaner.plan_cleanup({"mode": "reports_only", "max_report_age_days": 0})

            self.assertTrue(result.ok)
            self.assertTrue(result.dry_run)
            self.assertTrue(Path(result.report_path).is_file())
            self.assertTrue(report_path.is_file())
            self.assertGreaterEqual(result.summary["candidate_count"], 1)
            self.assertEqual(result.summary["deleted_count"], 0)

    def test_execute_cleanup_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            cleaner = ArtifactCleaner(tmp)
            with self.assertRaises(CleanupConfirmationError):
                cleaner.execute_cleanup({"mode": "reports_only", "dry_run": False, "confirm_cleanup": False})

    def test_execute_cleanup_deletes_report_files_when_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame(runtime_dir)
            report_path = self._make_report(runtime_dir, frame.frame_id, days_old=5)
            cleaner = ArtifactCleaner(runtime_dir)

            result = cleaner.execute_cleanup({"mode": "reports_only", "dry_run": False, "confirm_cleanup": True, "max_report_age_days": 0})

            self.assertTrue(result.ok)
            self.assertFalse(report_path.exists())
            self.assertGreaterEqual(result.summary["deleted_count"], 1)
            self.assertTrue(Path(result.report_path).is_file())

    def test_execute_cleanup_does_not_delete_protected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame(runtime_dir, state="WAITING_FOR_EXECUTE")
            report_path = self._make_report(runtime_dir, frame.frame_id, days_old=5)
            cleaner = ArtifactCleaner(runtime_dir)

            result = cleaner.execute_cleanup({"mode": "reports_only", "dry_run": False, "confirm_cleanup": True, "max_report_age_days": 0})

            self.assertTrue(report_path.exists())
            self.assertEqual(result.deleted, [])
            self.assertEqual(len(result.protected), 1)

    def test_execute_cleanup_records_deletion_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame(runtime_dir)
            self._make_report(runtime_dir, frame.frame_id, days_old=5)

            class FailingCleaner(ArtifactCleaner):
                def _delete_candidate(self, candidate):  # type: ignore[override]
                    raise CleanupExecutionError("boom")

            cleaner = FailingCleaner(runtime_dir)
            result = cleaner.execute_cleanup({"mode": "reports_only", "dry_run": False, "confirm_cleanup": True, "max_report_age_days": 0})

            self.assertFalse(result.ok)
            self.assertEqual(len(result.errors), 1)
            self.assertIn("boom", result.errors[0]["error"])

    def test_execute_cleanup_rejects_path_outside_runtime_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            cleaner = ArtifactCleaner(runtime_dir)
            outside = Path(tmp).parent / "outside_report.html"
            outside.write_text("outside", encoding="utf-8")
            candidate = {
                "candidate_id": "cc_1",
                "candidate_type": "report",
                "path": str(outside),
                "frame_id": "",
                "reason": "test",
                "protected": False,
                "protection_reason": "",
                "size_bytes": 7,
                "age_days": 10.0,
                "metadata": {},
            }
            cleaner.planner.discover_candidates = lambda policy: [candidate]  # type: ignore[assignment]

            with self.assertRaises(CleanupExecutionError):
                cleaner.execute_cleanup({"mode": "reports_only", "dry_run": False, "confirm_cleanup": True, "max_report_age_days": 0})

    def test_load_taskframe_safe_returns_none_for_missing_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_taskframe_safe("missing", tmp))


if __name__ == "__main__":
    unittest.main()
