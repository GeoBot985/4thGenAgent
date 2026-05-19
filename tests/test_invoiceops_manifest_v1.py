from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from runtime.google_sheet_tools import use_sheet_fixture_mode
from runtime.manifest_loader import load_manifest
from runtime.orchestrator import Orchestrator
from runtime.taskframe import to_dict as taskframe_to_dict
from src.generated_manifest_smoke_runner import smoke_run_manifest_file
from src.manifest_contract_strict import validate_manifest_strict
from src.manifest_health import check_manifest_health


MANIFEST_PATH = Path("manifests/invoiceops.process_supplier_invoice_v1.manifest.json")
FIXTURE_DIR = Path("tests/fixtures/invoiceops/manifest")


def _runtime_dir(tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "runtime_data"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _run_manifest(invoice_file_path: Path, tmp_path: Path) -> dict:
    runtime_dir = _runtime_dir(tmp_path)
    manifest = load_manifest(MANIFEST_PATH)
    orch = Orchestrator(runtime_data_dir=runtime_dir, manifest_dir="manifests")
    inputs = {"invoice_file_path": str(invoice_file_path)}
    frame = orch.create_frame_from_manifest(manifest, inputs=inputs, raw_input=json.dumps(inputs))
    frame = orch.prepare_frame(frame)
    with use_sheet_fixture_mode(True, str(runtime_dir)):
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)
    return taskframe_to_dict(frame)


def _outputs(frame: dict) -> dict:
    return frame.get("outputs", {}) if isinstance(frame, dict) else {}


def _assert_tool_result_shape(result: dict, *, expect_ok: bool = True) -> None:
    assert isinstance(result, dict)
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in result
    if expect_ok:
        assert result["ok"] is True


def test_manifest_passes_strict_validation() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    result = validate_manifest_strict(manifest, manifest_path=str(MANIFEST_PATH), active_catalog=True)
    assert result["ok"] is True, result


def test_manifest_health_check_passes(tmp_path: Path) -> None:
    result = check_manifest_health(
        MANIFEST_PATH,
        runtime_data_dir=_runtime_dir(tmp_path),
        include_smoke=True,
        strict_contract=True,
    )
    assert result["strict_contract"]["ok"] is True, result["strict_contract"]
    assert result["smoke"]["status"] == "PASS", result["smoke"]
    assert result["health"] in {"HEALTHY", "WARNING"}, result


def test_happy_path_invoice_reaches_matched_completion(tmp_path: Path) -> None:
    frame = _run_manifest(FIXTURE_DIR / "happy_path_invoice.txt", tmp_path)
    outputs = _outputs(frame)

    assert frame["state"] == "COMPLETED", frame["state"]
    assert outputs["match_result"]["data"]["match_result"]["match_status"] == "matched"
    assert "prepared_invoice_write" in outputs
    assert "prepared_match_write" in outputs
    assert "prepared_ledger_write" in outputs
    assert "match_report" in outputs
    assert "evidence_bundle" in outputs
    assert "rollback_summary" in outputs
    assert outputs["prepared_invoice_write"]["data"]["prepared_write"]["rollback_plan"]["rollback_type"] == "delete_appended_rows"
    assert outputs["prepared_match_write"]["data"]["prepared_write"]["rollback_plan"]["rollback_type"] == "delete_appended_rows"
    assert outputs["prepared_ledger_write"]["data"]["prepared_write"]["rollback_plan"]["rollback_type"] == "mark_reversed"


def test_missing_po_reaches_exception_completion(tmp_path: Path) -> None:
    frame = _run_manifest(FIXTURE_DIR / "missing_po_invoice.txt", tmp_path)
    outputs = _outputs(frame)

    assert frame["state"] == "COMPLETED", frame["state"]
    assert outputs["match_result"]["data"]["match_result"]["match_status"] == "blocked"
    assert "classified_exceptions" in outputs
    assert "exception_action_plan" in outputs
    assert "exception_report" in outputs
    assert "prepared_exception_write" in outputs
    assert outputs["prepared_exception_write"]["data"]["prepared_write"]["rollback_plan"]["rollback_type"] == "delete_appended_rows"


def test_missing_receipt_reaches_exception_completion(tmp_path: Path) -> None:
    frame = _run_manifest(FIXTURE_DIR / "missing_receipt_invoice.txt", tmp_path)
    outputs = _outputs(frame)

    assert frame["state"] == "COMPLETED", frame["state"]
    assert outputs["match_result"]["data"]["match_result"]["match_status"] == "blocked"
    assert outputs["classified_exceptions"]["data"]["exception_count"] >= 1
    assert "exception_report" in outputs
    assert "prepared_exception_write" in outputs


def test_duplicate_invoice_reaches_blocked_completion(tmp_path: Path) -> None:
    frame = _run_manifest(FIXTURE_DIR / "duplicate_invoice.txt", tmp_path)
    outputs = _outputs(frame)

    assert frame["state"] == "COMPLETED", frame["state"]
    assert outputs["match_result"]["data"]["match_result"]["match_status"] == "blocked"
    assert outputs["duplicate_check"]["data"]["status"] == "fail"
    assert "exception_report" in outputs
    assert "prepared_exception_write" in outputs


def test_amount_mismatch_reaches_exception_completion(tmp_path: Path) -> None:
    frame = _run_manifest(FIXTURE_DIR / "amount_mismatch_invoice.txt", tmp_path)
    outputs = _outputs(frame)

    assert frame["state"] == "COMPLETED", frame["state"]
    assert outputs["match_result"]["data"]["match_result"]["match_status"] == "exception"
    assert outputs["totals_check"]["data"]["status"] == "fail"
    assert "exception_report" in outputs
    assert "prepared_exception_write" in outputs


def test_prepared_writes_are_created_but_not_executed(tmp_path: Path) -> None:
    frame = _run_manifest(FIXTURE_DIR / "happy_path_invoice.txt", tmp_path)
    outputs = _outputs(frame)

    for key in ("prepared_invoice_write", "prepared_match_write", "prepared_ledger_write"):
        prepared = outputs[key]["data"]["prepared_write"]
        assert prepared["dry_run"] is True
        assert prepared["requires_approval"] is True
        assert prepared["rollback_plan"]
        assert outputs[key]["metadata"]["dry_run"] is True
        assert outputs[key]["metadata"]["live_side_effect"] is False


def test_rollback_metadata_exists_for_every_prepared_write(tmp_path: Path) -> None:
    frame = _run_manifest(FIXTURE_DIR / "happy_path_invoice.txt", tmp_path)
    outputs = _outputs(frame)

    for key in ("prepared_invoice_write", "prepared_match_write", "prepared_ledger_write"):
        prepared = outputs[key]["data"]["prepared_write"]
        rollback_plan = prepared["rollback_plan"]
        assert rollback_plan["rollback_id"]
        assert rollback_plan["rollback_type"] in {"delete_appended_rows", "mark_reversed"}
        assert rollback_plan["steps"]


def test_reports_are_generated_for_matched_and_exception_paths(tmp_path: Path) -> None:
    happy_frame = _run_manifest(FIXTURE_DIR / "happy_path_invoice.txt", tmp_path)
    exception_frame = _run_manifest(FIXTURE_DIR / "missing_po_invoice.txt", tmp_path)

    happy_outputs = _outputs(happy_frame)
    exception_outputs = _outputs(exception_frame)

    for key in ("match_report", "exception_report", "ledger_summary", "rollback_summary", "evidence_bundle"):
        assert key in happy_outputs
    for key in ("match_report", "exception_report", "ledger_summary", "evidence_bundle"):
        assert key in exception_outputs

    assert happy_outputs["match_report"]["data"]["report"]["match_status"] == "matched"
    assert exception_outputs["exception_report"]["data"]["report"]["exception_count"] >= 0


def test_all_outputs_are_toolresult_compatible(tmp_path: Path) -> None:
    frame = _run_manifest(FIXTURE_DIR / "happy_path_invoice.txt", tmp_path)
    outputs = _outputs(frame)
    assert outputs

    for result in outputs.values():
        _assert_tool_result_shape(result)


def test_no_live_side_effects_are_possible(tmp_path: Path) -> None:
    live_write_calls: list[str] = []

    def _trap(name: str):
        def _inner(*args, **kwargs):
            live_write_calls.append(name)
            raise AssertionError(f"live helper called: {name}")

        return _inner

    with patch("runtime.google_sheet_tools.sheet_read_range", side_effect=_trap("sheet_read_range")), patch(
        "runtime.google_sheet_tools.sheet_write_rows",
        side_effect=_trap("sheet_write_rows"),
    ), patch(
        "runtime.google_sheet_tools.write_sheet_entries",
        side_effect=_trap("write_sheet_entries"),
    ):
        frame = _run_manifest(FIXTURE_DIR / "happy_path_invoice.txt", tmp_path)

    assert frame["state"] == "COMPLETED"
    assert live_write_calls == []


def test_manifest_smoke_runner_accepts_fixture_manifest(tmp_path: Path) -> None:
    result = smoke_run_manifest_file(
        MANIFEST_PATH,
        runtime_data_dir=_runtime_dir(tmp_path),
        sample_inputs={"invoice_file_path": str(FIXTURE_DIR / "happy_path_invoice.txt")},
    )
    assert result["ok"] is True, result
    assert result["classification"] in {"DRY_RUN_COMPLETED", "COMPLETED_NO_DATA_ACCEPTED"}


def test_missing_fixture_data_produces_health_warning_or_failure(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["sample_inputs"] = {"invoice_file_path": "tests/fixtures/invoiceops/manifest/does_not_exist.txt"}
    manifest_path = tmp_path / "invoiceops_missing_fixture.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = check_manifest_health(
        manifest_path,
        runtime_data_dir=_runtime_dir(tmp_path),
        include_smoke=True,
        strict_contract=True,
    )
    assert result["health"] in {"WARNING", "FAILED"}
    assert result["smoke"]["status"] in {"FAIL", "SKIPPED"}
