from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from runtime.invoiceops_gallery import (
    DEFAULT_GALLERY_DIR,
    GALLERY_ID,
    iter_invoiceops_gallery_scenarios,
    load_invoiceops_gallery_index,
    run_invoiceops_gallery,
)


EXPECTED_SCENARIOS = [
    "happy_path_matched",
    "wrong_po",
    "missing_po",
    "missing_receipt",
    "duplicate_invoice",
    "supplier_mismatch",
    "price_mismatch",
    "quantity_mismatch",
    "bad_invoice_text",
    "rollback_required_case",
]


def test_gallery_scenarios_are_discoverable() -> None:
    index = load_invoiceops_gallery_index(DEFAULT_GALLERY_DIR)
    scenarios = iter_invoiceops_gallery_scenarios(DEFAULT_GALLERY_DIR)
    assert index["gallery_id"] == GALLERY_ID
    assert [scenario["scenario_id"] for scenario in scenarios] == EXPECTED_SCENARIOS
    for scenario in scenarios:
        assert (DEFAULT_GALLERY_DIR / scenario["invoice_file"]).is_file()


def test_each_scenario_runs_in_fixture_mode(tmp_path: Path) -> None:
    result = run_invoiceops_gallery(runtime_data_dir=str(tmp_path))
    assert result["ok"] is True, result
    assert result["gallery_id"] == GALLERY_ID
    assert result["summary"]["total"] == len(EXPECTED_SCENARIOS)
    assert result["summary"]["failed"] == 0
    assert result["summary"]["passed"] == len(EXPECTED_SCENARIOS)
    assert result["live_side_effects_performed"] is False
    assert len(result["scenario_results"]) == len(EXPECTED_SCENARIOS)
    for scenario_result in result["scenario_results"]:
        assert scenario_result["live_side_effects_performed"] is False
        assert scenario_result["manifest_id"] == "invoiceops.process_supplier_invoice_v1"
        assert scenario_result["frame_id"]


def test_happy_path_reaches_matched_status(tmp_path: Path) -> None:
    result = run_invoiceops_gallery(runtime_data_dir=str(tmp_path))
    happy = _scenario_result(result, "happy_path_matched")
    assert happy["ok"] is True
    assert happy["expected_status"] == "matched"
    assert happy["actual_status"] == "matched"
    assert happy["prepared_writes_created"] is True
    assert happy["rollback_metadata_present"] is True
    assert {"match_report", "evidence_bundle"}.issubset(set(happy["report_outputs"]))
    assert "prepared_ledger_write" in happy["outputs"]


def test_negative_paths_produce_expected_exception_or_block_status(tmp_path: Path) -> None:
    result = run_invoiceops_gallery(runtime_data_dir=str(tmp_path))
    expected_statuses = {
        "wrong_po": "blocked",
        "missing_po": "blocked",
        "missing_receipt": "blocked",
        "duplicate_invoice": "blocked",
        "supplier_mismatch": "blocked",
        "price_mismatch": "exception",
        "quantity_mismatch": "blocked",
    }
    for scenario_id, expected_status in expected_statuses.items():
        scenario = _scenario_result(result, scenario_id)
        assert scenario["ok"] is True, scenario
        assert scenario["expected_status"] == expected_status
        assert scenario["actual_status"] == expected_status
        assert scenario["prepared_writes_created"] is True
        assert scenario["rollback_metadata_present"] is True
        assert "match_report" in scenario["report_outputs"]
        assert "evidence_bundle" in scenario["report_outputs"]


def test_bad_invoice_text_fails_safely(tmp_path: Path) -> None:
    result = run_invoiceops_gallery(runtime_data_dir=str(tmp_path))
    bad = _scenario_result(result, "bad_invoice_text")
    assert bad["ok"] is True
    assert bad["expected_status"] == "blocked"
    assert bad["actual_status"] == "blocked"
    assert bad["prepared_writes_created"] is False
    assert bad["rollback_metadata_present"] is False
    assert bad["required_outputs_present"] is True
    assert bad["report_outputs"] == []


def test_rollback_required_case_includes_rollback_metadata(tmp_path: Path) -> None:
    result = run_invoiceops_gallery(runtime_data_dir=str(tmp_path))
    rollback = _scenario_result(result, "rollback_required_case")
    assert rollback["ok"] is True
    assert rollback["actual_status"] == "matched"
    assert rollback["prepared_writes_created"] is True
    assert rollback["rollback_metadata_present"] is True
    assert "prepared_ledger_write" in rollback["outputs"]


def test_no_scenario_performs_live_side_effects(tmp_path: Path) -> None:
    live_calls: list[str] = []

    def _trap(name: str):
        def _inner(*args, **kwargs):
            live_calls.append(name)
            raise AssertionError(f"live helper called: {name}")

        return _inner

    with patch("runtime.google_sheet_tools.sheet_read_range", side_effect=_trap("sheet_read_range")), patch(
        "runtime.google_sheet_tools.sheet_write_rows",
        side_effect=_trap("sheet_write_rows"),
    ), patch(
        "runtime.google_sheet_tools.write_sheet_entries",
        side_effect=_trap("write_sheet_entries"),
    ):
        result = run_invoiceops_gallery(runtime_data_dir=str(tmp_path))

    assert result["ok"] is True
    assert live_calls == []
    assert result["live_side_effects_performed"] is False


def test_prepared_writes_are_dry_run_only(tmp_path: Path) -> None:
    result = run_invoiceops_gallery(runtime_data_dir=str(tmp_path))
    for scenario_id in ("happy_path_matched", "wrong_po", "missing_po", "missing_receipt", "duplicate_invoice", "supplier_mismatch", "price_mismatch", "quantity_mismatch", "rollback_required_case"):
        scenario = _scenario_result(result, scenario_id)
        assert scenario["prepared_writes_created"] is True
        frame = scenario["frame"]
        outputs = frame["outputs"]
        for key in [k for k in outputs if k.startswith("prepared_")]:
            prepared_write = outputs[key]["data"]["prepared_write"]
            assert prepared_write["dry_run"] is True
            assert prepared_write["requires_approval"] is True
            assert prepared_write["rollback_plan"]
            assert outputs[key]["metadata"]["dry_run"] is True
            assert outputs[key]["metadata"]["live_side_effect"] is False


def test_reports_and_evidence_bundles_are_produced(tmp_path: Path) -> None:
    result = run_invoiceops_gallery(runtime_data_dir=str(tmp_path))
    for scenario_id in EXPECTED_SCENARIOS:
        scenario = _scenario_result(result, scenario_id)
        if scenario_id == "bad_invoice_text":
            continue
        assert "match_report" in scenario["report_outputs"]
        assert "evidence_bundle" in scenario["report_outputs"]
        assert scenario["required_outputs_present"] is True


def test_gallery_summary_counts_pass_fail_correctly(tmp_path: Path) -> None:
    result = run_invoiceops_gallery(runtime_data_dir=str(tmp_path))
    assert result["summary"] == {"total": 10, "passed": 10, "failed": 0}
    assert result["ok"] is True


def _scenario_result(result: dict, scenario_id: str) -> dict:
    for scenario in result.get("scenario_results", []):
        if scenario.get("scenario_id") == scenario_id:
            return scenario
    raise AssertionError(f"Scenario not found: {scenario_id}")
