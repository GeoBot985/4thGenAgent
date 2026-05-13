from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.manifest_workbench import (
    build_manifest_run_comparison,
    build_manifest_step_rows,
    build_manifest_summary,
    create_test_frame,
    generate_workbench_run_report,
    list_manifest_catalog,
    load_manifest_for_workbench,
    run_workbench_dry_run,
    validate_manifest_for_workbench,
)


ROOT = Path(__file__).resolve().parents[1]
UI_SOURCE = ROOT / "src" / "operator_ui.py"


def write_manifest(tmpdir: Path, filename: str, data: dict) -> Path:
    path = tmpdir / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


class ManifestWorkbenchTests(unittest.TestCase):
    def test_manifest_workbench_lists_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(
                tmpdir,
                "workbench_list_runs.manifest.json",
                {
                    "manifest_id": "workbench.list_runs",
                    "name": "Workbench List Runs",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "cleanup_reports", "command": "[i:cleanup_reports -> cleanup_reports]"}],
                    "validations": [{"id": "cleanup_reports_output_exists", "type": "output_exists", "output": "cleanup_reports"}],
                    "completion": {"success_outputs": ["cleanup_reports"]},
                },
            )

            catalog = list_manifest_catalog(str(tmpdir))
            self.assertEqual(len(catalog), 1)
            self.assertEqual(catalog[0]["manifest_id"], "workbench.list_runs")
            self.assertTrue(catalog[0]["ok"])

    def test_manifest_workbench_loads_valid_manifest_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            path = write_manifest(
                tmpdir,
                "workbench_list_runs.manifest.json",
                {
                    "manifest_id": "workbench.list_runs",
                    "name": "Workbench List Runs",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "cleanup_reports", "command": "[i:cleanup_reports -> cleanup_reports]"}],
                    "validations": [{"id": "cleanup_reports_output_exists", "type": "output_exists", "output": "cleanup_reports"}],
                    "completion": {"success_outputs": ["cleanup_reports"]},
                },
            )

            result = load_manifest_for_workbench(str(path))
            self.assertTrue(result["ok"])
            self.assertEqual(result["summary"]["manifest_id"], "workbench.list_runs")
            self.assertEqual(result["summary"]["step_count"], 1)
            self.assertEqual(result["summary"]["validation_count"], 1)
            self.assertEqual(result["summary"]["required_inputs"], [])

    def test_manifest_workbench_reports_invalid_manifest_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            path = write_manifest(
                tmpdir,
                "invalid.manifest.json",
                {
                    "manifest_id": "workbench.invalid",
                    "name": "Broken Manifest",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"command": "[i:list_runs -> run_list] limit=1"}],
                    "validations": [],
                    "completion": {"success_outputs": ["run_list"]},
                },
            )

            result = validate_manifest_for_workbench(str(path))
            self.assertFalse(result["ok"])
            self.assertIn("step", result["error"].lower())

    def test_manifest_workbench_builds_step_rows(self):
        manifest = {
            "manifest_id": "workbench.list_runs",
            "name": "Workbench List Runs",
            "version": 1,
            "trigger": {"type": "manual"},
            "inputs": [],
            "steps": [
                {
                    "id": "list_runs",
                    "command": "[i:list_runs -> run_list] limit=1",
                    "kind": "inspection",
                    "output_alias": "run_list",
                    "when": {"input": "channel", "equals": "web"},
                    "retry": {"max_attempts": 1},
                    "timeout_seconds": 10,
                }
            ],
            "validations": [],
            "completion": {"success_outputs": ["run_list"]},
        }

        rows = build_manifest_step_rows(manifest)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["step_id"], "list_runs")
        self.assertEqual(rows[0]["kind"], "inspection")
        self.assertEqual(rows[0]["output_alias"], "run_list")
        self.assertIn("channel", rows[0]["when_condition"])

    def test_manifest_workbench_rejects_missing_required_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            path = write_manifest(
                tmpdir,
                "workbench_inputs.manifest.json",
                {
                    "manifest_id": "workbench.inputs",
                    "name": "Workbench Inputs",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["customer_id", "message"],
                    "steps": [{"id": "validate_inputs", "command": "[validate:no_errors]"}],
                    "validations": [{"id": "no_errors", "type": "no_errors"}],
                    "completion": {"success_outputs": []},
                },
            )

            result = create_test_frame(str(path), {"customer_id": "CUST-1001"}, runtime_data_dir=str(tmpdir / "runtime"))
            self.assertFalse(result["ok"])
            self.assertIn("message", result["error"])
            self.assertIn("message", result["missing_required_inputs"])

    def test_manifest_workbench_creates_dry_run_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            runtime_dir = tmpdir / "runtime"
            path = write_manifest(
                tmpdir,
                "workbench_list_runs.manifest.json",
                {
                    "manifest_id": "workbench.list_runs",
                    "name": "Workbench List Runs",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "cleanup_reports", "command": "[i:cleanup_reports -> cleanup_reports]"}],
                    "validations": [{"id": "cleanup_reports_output_exists", "type": "output_exists", "output": "cleanup_reports"}],
                    "completion": {"success_outputs": ["cleanup_reports"]},
                },
            )

            create_result = create_test_frame(str(path), {}, runtime_data_dir=str(runtime_dir))
            self.assertTrue(create_result["ok"])
            self.assertTrue(create_result["frame_id"])
            self.assertEqual(create_result["state"], "READY")

            run_result = run_workbench_dry_run(create_result["frame_id"], "run_until_blocked", runtime_data_dir=str(runtime_dir))
            self.assertTrue(run_result["ok"])
            self.assertEqual(run_result["frame_id"], create_result["frame_id"])
            self.assertIn(run_result["state"], {"COMPLETED", "COMPLETED_NO_DATA", "WAITING_FOR_EXECUTE"})
            self.assertIn("comparison", run_result)

    def test_manifest_workbench_run_until_blocked_returns_frame_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            runtime_dir = tmpdir / "runtime"
            path = write_manifest(
                tmpdir,
                "workbench_list_runs.manifest.json",
                {
                    "manifest_id": "workbench.list_runs",
                    "name": "Workbench List Runs",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "cleanup_reports", "command": "[i:cleanup_reports -> cleanup_reports]"}],
                    "validations": [{"id": "cleanup_reports_output_exists", "type": "output_exists", "output": "cleanup_reports"}],
                    "completion": {"success_outputs": ["cleanup_reports"]},
                },
            )

            create_result = create_test_frame(str(path), {}, runtime_data_dir=str(runtime_dir))
            run_result = run_workbench_dry_run(create_result["frame_id"], "run_until_blocked", runtime_data_dir=str(runtime_dir))
            comparison = build_manifest_run_comparison(run_result["summary"], run_result["frame"])
            self.assertTrue(run_result["ok"])
            self.assertEqual(run_result["comparison"]["manifest_expected_steps"], 1)
            self.assertEqual(run_result["comparison"]["runtime_steps_created"], 1)
            self.assertIn(run_result["state"], {"COMPLETED", "COMPLETED_NO_DATA", "WAITING_FOR_EXECUTE"})

    def test_manifest_workbench_report_generation_is_bound_to_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            runtime_dir = tmpdir / "runtime"
            path = write_manifest(
                tmpdir,
                "workbench_list_runs.manifest.json",
                {
                    "manifest_id": "workbench.list_runs",
                    "name": "Workbench List Runs",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "cleanup_reports", "command": "[i:cleanup_reports -> cleanup_reports]"}],
                    "validations": [{"id": "cleanup_reports_output_exists", "type": "output_exists", "output": "cleanup_reports"}],
                    "completion": {"success_outputs": ["cleanup_reports"]},
                },
            )

            create_result = create_test_frame(str(path), {}, runtime_data_dir=str(runtime_dir))
            run_result = run_workbench_dry_run(create_result["frame_id"], "run_until_blocked", runtime_data_dir=str(runtime_dir))
            report = generate_workbench_run_report(run_result["frame_id"], runtime_data_dir=str(runtime_dir))
            self.assertTrue(report["ok"])
            self.assertEqual(report["frame_id"], run_result["frame_id"])
            self.assertTrue(report["html_path"].endswith("run_report.html"))

    def test_operator_ui_has_manifest_workbench_view_constant(self):
        source = UI_SOURCE.read_text(encoding="utf-8")
        for text in ("Manifest Workbench", "Select manifest file", "Reload manifest catalog", "Validate manifest", "Run dry-run test", "Run until blocked", "Create/open run report"):
            self.assertIn(text, source)


if __name__ == "__main__":
    unittest.main()
