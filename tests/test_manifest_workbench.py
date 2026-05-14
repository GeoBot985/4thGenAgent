from __future__ import annotations

import json
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from src.manifest_workbench import (
    build_manifest_run_comparison,
    build_manifest_step_rows,
    build_manifest_summary,
    build_workbench_run_summary,
    build_workbench_step_result,
    classify_workbench_failure,
    create_test_frame,
    generate_workbench_run_report,
    list_manifest_catalog,
    load_manifest_for_workbench,
    run_workbench_dry_run,
    validate_manifest_for_workbench,
)
from src.operator_ui import OperatorConsole
from runtime.google_sheet_tools import read_range_fixture


ROOT = Path(__file__).resolve().parents[1]
UI_SOURCE = ROOT / "src" / "operator_ui.py"


def _failed_sheet_frame() -> dict:
    return {
        "frame_id": "frame_workbench_failed_sheet",
        "manifest_id": "accounting.payment_reconciliation",
        "state": "FAILED_EXECUTION",
        "current_step_id": "read_payments_sheet",
        "inputs": {"spreadsheet_id": "demo-accounting-sheet", "payments_range": "Payments!A1:H100"},
        "steps": [
            {
                "step_id": "read_payments_sheet",
                "command": "[t:sheet/read_range -> payments_sheet] spreadsheet_id=$inputs.spreadsheet_id; range_name=$inputs.payments_range",
                "kind": "tool",
                "status": "FAILED",
                "output_alias": "payments_sheet",
                "error": "invalid_grant Token has been expired or revoked.",
            }
        ],
        "outputs": {},
        "tool_calls": [
            {
                "step_id": "read_payments_sheet",
                "tool": "sheet/read_range",
                "action": "read_range",
                "namespace": "sheet",
                "args": {"spreadsheet_id": "demo-accounting-sheet", "range_name": "Payments!A1:H100"},
                "ok": False,
                "error": "invalid_grant Token has been expired or revoked.",
            }
        ],
        "llm_calls": [],
        "validations": [],
        "evidence": [],
        "errors": [
            {
                "step_id": "read_payments_sheet",
                "type": "live_tool_execution_failed",
                "message": "invalid_grant Token has been expired or revoked.",
                "data": {"tool": "sheet/read_range", "function": "sheet_read_range"},
            }
        ],
        "pending_actions": [],
        "executed_actions": [],
        "completion_gate_result": {"status": "FAILED_EXECUTION"},
    }


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

    def test_workbench_classifies_invalid_grant_as_external_auth_failure(self):
        failure = classify_workbench_failure("invalid_grant Token has been expired or revoked.")
        self.assertEqual(failure["category"], "external_auth_failure")
        self.assertIn("authentication", failure["title"].lower())
        self.assertIn("expired or revoked", failure["summary"].lower())

    def test_workbench_failure_summary_includes_recommended_action(self):
        frame = _failed_sheet_frame()
        summary = build_workbench_run_summary(frame, {"manifest_id": frame["manifest_id"], "steps": []})
        self.assertEqual(summary["failure_category"], "external_auth_failure")
        self.assertIn("refresh", summary["recommended_action"].lower())
        self.assertEqual(summary["failure_summary"]["failure_title"], "Google Sheets authentication failed")

    def test_workbench_failed_step_result_shows_plain_english_outcome(self):
        frame = _failed_sheet_frame()
        result = build_workbench_step_result({"manifest_id": frame["manifest_id"], "steps": [{"step_id": "read_payments_sheet", "command": frame["steps"][0]["command"], "kind": "tool", "output_alias": "payments_sheet"}]}, frame, "read_payments_sheet")
        self.assertEqual(result["failure"]["category"], "external_auth_failure")
        self.assertTrue(result["step_outcome"]["lines"][0].startswith("Could not read"))
        self.assertIn("External authentication failure", result["step_outcome"]["lines"][1])
        self.assertIn("Refresh the Google authentication token", " ".join(result["step_outcome"]["lines"]))

    def test_workbench_generates_all_required_input_fields(self):
        result = load_manifest_for_workbench("accounting.payment_reconciliation")
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["summary"]["required_inputs"],
            ["spreadsheet_id", "payments_range", "orders_range", "invoices_range", "ledger_range", "recon_runs_range", "recon_exceptions_range"],
        )

    def test_workbench_fixture_mode_marks_fixture_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            runtime_dir = tmpdir / "runtime"
            create_result = create_test_frame(
                "accounting.payment_reconciliation",
                {
                    "spreadsheet_id": "demo-accounting-sheet",
                    "payments_range": "Payments!A1:H20",
                    "orders_range": "Orders!A1:H100",
                    "invoices_range": "Invoices!A1:H100",
                    "ledger_range": "Ledger!A1:H100",
                    "recon_runs_range": "ReconRuns!A1:J100",
                    "recon_exceptions_range": "ReconExceptions!A1:M100",
                },
                runtime_data_dir=str(runtime_dir),
            )
            self.assertTrue(create_result["ok"])

            run_result = run_workbench_dry_run(create_result["frame_id"], "run_until_blocked", runtime_data_dir=str(runtime_dir), fixture_mode=True)
            self.assertTrue(run_result["ok"])
            self.assertIn(run_result["state"], {"WAITING_FOR_EXECUTE", "COMPLETED"})
            self.assertGreater(run_result["completed_steps"], 1)
            self.assertEqual(run_result["failed_steps"], 0)
            self.assertFalse(run_result["run_summary"]["failure_category"])
            self.assertIn(run_result["selected_step"]["output_value"].get("metadata", {}).get("source", ""), {"workbench_fixture"})
            selected = run_result["selected_step"]
            self.assertEqual(selected["output_value"]["metadata"]["source"], "workbench_fixture")
            self.assertTrue(selected["output_value"]["metadata"]["fixture_mode"])
            self.assertFalse(selected["output_value"]["metadata"]["live_external_call"])

    def test_workbench_fixture_resolver_matches_sheet_name_variants(self):
        for range_name in ("Payments!A1:H100", "Payments!A1:H20", "Payments!A1:H5", "Payments", "Orders!A1:H100", "Invoices!A1:H100", "Ledger!A1:H100", "ReconRuns!A1:J100", "ReconExceptions!A1:M100"):
            result = read_range_fixture("demo-accounting-sheet", range_name)
            self.assertTrue(result["ok"], msg=range_name)
            self.assertEqual(result["source"], "workbench_fixture")
            self.assertFalse(result["live_external_call"])
            self.assertTrue(result["fixture_mode"])

    def test_workbench_fixture_mode_avoids_live_sheet_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            runtime_dir = tmpdir / "runtime"
            create_result = create_test_frame(
                "accounting.payment_reconciliation",
                {
                    "spreadsheet_id": "demo-accounting-sheet",
                    "payments_range": "Payments!A:I",
                    "orders_range": "Orders!A:F",
                    "invoices_range": "CustomerInvoices!A:H",
                    "ledger_range": "Ledger!A:I",
                    "recon_runs_range": "ReconRuns!A:J",
                    "recon_exceptions_range": "ReconExceptions!A:M",
                },
                runtime_data_dir=str(runtime_dir),
            )
            self.assertTrue(create_result["ok"])
            import runtime.google_sheet_tools as sheet_tools

            def fail_if_called(*args, **kwargs):
                raise AssertionError("live sheet auth should not be used in fixture mode")

            original = sheet_tools.read_sheet_entries
            sheet_tools.read_sheet_entries = fail_if_called
            try:
                run_result = run_workbench_dry_run(create_result["frame_id"], "run_until_blocked", runtime_data_dir=str(runtime_dir), fixture_mode=True)
            finally:
                sheet_tools.read_sheet_entries = original
            self.assertTrue(run_result["ok"])
            self.assertGreater(run_result["completed_steps"], 0)
            self.assertNotIn("invalid_grant", json.dumps(run_result, default=str).lower())

    def test_workbench_fixture_missing_is_reported_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            runtime_dir = tmpdir / "runtime"
            create_result = create_test_frame(
                "accounting.payment_reconciliation",
                {
                    "spreadsheet_id": "demo-accounting-sheet",
                    "payments_range": "Payments!A:I",
                    "orders_range": "Orders!A:F",
                    "invoices_range": "CustomerInvoices!A:H",
                    "ledger_range": "Ledger!A:I",
                    "recon_runs_range": "ReconRuns!A:J",
                    "recon_exceptions_range": "ReconExceptions!A:M",
                },
                runtime_data_dir=str(runtime_dir),
            )
            self.assertTrue(create_result["ok"])
            import runtime.google_sheet_tools as sheet_tools

            original = sheet_tools.read_range_fixture

            def missing_fixture(*args, **kwargs):
                spreadsheet_id = args[0] if args else kwargs.get("spreadsheet_id", "")
                range_name = args[1] if len(args) > 1 else kwargs.get("range_name", "")
                return {
                    "ok": False,
                    "spreadsheet_id": spreadsheet_id,
                    "range_name": range_name,
                    "rows": [],
                    "row_count": 0,
                    "fixture_mode": True,
                    "live_external_call": False,
                    "source": "workbench_fixture",
                    "error": "Fixture data not available for this tool/range.",
                    "metadata": {"fixture_mode": True, "live_external_call": False, "source": "workbench_fixture"},
                }

            sheet_tools.read_range_fixture = missing_fixture
            try:
                run_result = run_workbench_dry_run(create_result["frame_id"], "run_until_blocked", runtime_data_dir=str(runtime_dir), fixture_mode=True)
            finally:
                sheet_tools.read_range_fixture = original
            self.assertTrue(run_result["ok"])
            self.assertEqual(run_result["run_summary"]["failure_category"], "fixture_missing")
            self.assertIn("Fixture data not available", run_result["run_summary"]["failure_summary"]["failure_summary"])

    def test_workbench_active_frame_matches_latest_run_frame(self):
        captured = {}

        class DummyLabel:
            def configure(self, **kwargs):
                captured.update(kwargs)

        dummy = SimpleNamespace(
            view_mode_var=SimpleNamespace(get=lambda: "Manifest Workbench"),
            last_snapshot={"active_frame": {"frame_id": "frame_ec94", "pending_actions": []}},
            workbench_frame={"frame_id": "frame_323", "pending_actions": []},
            footer_label=DummyLabel(),
            _playback_status=lambda: "idle",
        )

        OperatorConsole._update_footer(dummy)
        self.assertIn("Active Frame: frame_323", captured.get("text", ""))

    def test_workbench_run_aligns_footer_active_frame_with_latest_result(self):
        dummy = SimpleNamespace(
            view_mode_var=SimpleNamespace(get=lambda: "Manifest Workbench"),
            runtime_root="runtime_data",
            workbench_manifest_record={
                "ok": True,
                "manifest_id": "accounting.payment_reconciliation",
                "path": "manifests/accounting.payment_reconciliation.json",
                "manifest": {"manifest_id": "accounting.payment_reconciliation", "steps": []},
                "summary": {"required_inputs": []},
            },
            workbench_result={},
            workbench_frame={},
            workbench_fixture_mode_var=SimpleNamespace(get=lambda: True),
            workbench_selected_step_id="",
            workbench_selected_runtime_step_id="",
            active_frame_id="frame_ec94",
            last_snapshot={"active_frame": {"frame_id": "frame_ec94", "pending_actions": []}},
            _workbench_selected_manifest_target=lambda: "accounting.payment_reconciliation",
            _workbench_selected_frame_id=lambda: "",
            _workbench_validate_inputs=lambda manifest_record: ({"ok": True, "error": ""}, {
                "spreadsheet_id": "demo-accounting-sheet",
                "payments_range": "Payments!A1:H20",
                "orders_range": "Orders!A1:H100",
                "invoices_range": "Invoices!A1:H100",
                "ledger_range": "Ledger!A1:H100",
                "recon_runs_range": "ReconRuns!A1:J100",
                "recon_exceptions_range": "ReconExceptions!A1:M100",
            }),
            _render_workbench_failure=lambda result: (_ for _ in ()).throw(AssertionError(f"unexpected failure: {result}")),
            _render_manifest_workbench_view=lambda: None,
        )

        create_result = {
            "ok": True,
            "frame_id": "frame_b547",
            "manifest_id": "accounting.payment_reconciliation",
            "state": "READY",
            "frame": {
                "frame_id": "frame_b547",
                "pending_actions": [{"action_type": "approve", "status": "PENDING_APPROVAL"}],
            },
        }
        run_result = {
            "ok": True,
            "frame_id": "frame_b547",
            "manifest_id": "accounting.payment_reconciliation",
            "state": "WAITING_FOR_EXECUTE",
            "current_step_id": "read_payments_sheet",
            "frame": {
                "frame_id": "frame_b547",
                "pending_actions": [{"action_type": "approve", "status": "PENDING_APPROVAL"}],
            },
        }

        with patch("src.operator_ui.load_manifest_for_workbench", return_value=dummy.workbench_manifest_record), patch(
            "src.operator_ui.create_test_frame", return_value=create_result
        ), patch("src.operator_ui.run_workbench_dry_run", return_value=run_result):
            OperatorConsole._workbench_run(dummy, "run_until_blocked", require_frame=False)

        self.assertEqual(dummy.active_frame_id, "frame_b547")
        self.assertEqual(dummy.last_snapshot["active_frame"]["frame_id"], "frame_b547")
        self.assertEqual(dummy.workbench_result["frame_id"], "frame_b547")
        self.assertEqual(dummy.workbench_frame["frame_id"], "frame_b547")

    def test_workbench_classification_step_displays_output_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            runtime_dir = tmpdir / "runtime"
            create_result = create_test_frame(
                "llm.classify_customer_message",
                {"message": "Where is my order ORD-10042?"},
                runtime_data_dir=str(runtime_dir),
            )
            self.assertTrue(create_result["ok"])

            run_result = run_workbench_dry_run(create_result["frame_id"], "run_until_blocked", runtime_data_dir=str(runtime_dir))
            self.assertTrue(run_result["ok"])
            result = run_result["selected_step"]
            self.assertEqual(result["output_alias"], "category")
            self.assertEqual(result["output_value"]["label"], "order_status")
            self.assertEqual(result["output_value"]["confidence"], "high")
            self.assertIn("reason", result["output_value"])

    def test_operator_ui_has_manifest_workbench_view_constant(self):
        source = UI_SOURCE.read_text(encoding="utf-8")
        for text in ("Manifest Workbench", "Select manifest file", "Reload manifest catalog", "New manifest", "Edit manifest JSON", "Validate manifest", "Run dry-run test", "Save manifest", "Save manifest as...", "Open manifest manual", "Manifest JSON Editor", "Run until blocked", "Create/open run report", "Use fixture data for external read tools", "Failure category:", "Recommended action:"):
            self.assertIn(text, source)


if __name__ == "__main__":
    unittest.main()
