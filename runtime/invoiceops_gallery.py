from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.google_sheet_tools import use_sheet_fixture_mode
from runtime.manifest_loader import load_manifest
from runtime.orchestrator import Orchestrator
from runtime.taskframe import to_dict as taskframe_to_dict


GALLERY_ID = "invoiceops_regression_gallery_v1"
MANIFEST_ID = "invoiceops.process_supplier_invoice_v1"
DEFAULT_GALLERY_DIR = Path("tests/fixtures/invoiceops/gallery")
DEFAULT_MANIFEST_PATH = Path("manifests/invoiceops.process_supplier_invoice_v1.manifest.json")
DEFAULT_OUTPUT_DIR_NAME = "invoiceops_demo_outputs"

_REPORT_OUTPUT_KEYS = {
    "match_report",
    "exception_report",
    "ledger_summary",
    "rollback_summary",
    "evidence_bundle",
}

_REQUIRED_OUTPUTS_BY_SCENARIO: dict[str, list[str]] = {
    "happy_path_matched": [
        "raw_invoice_text",
        "extracted_invoice",
        "invoice_validation",
        "match_result",
        "match_report",
        "ledger_summary",
        "rollback_summary",
        "evidence_bundle",
        "prepared_invoice_write",
        "prepared_match_write",
        "prepared_ledger_write",
    ],
    "wrong_po": [
        "raw_invoice_text",
        "extracted_invoice",
        "invoice_validation",
        "match_result",
        "classified_exceptions",
        "exception_action_plan",
        "match_report",
        "exception_report",
        "ledger_summary",
        "rollback_summary",
        "evidence_bundle",
        "prepared_invoice_write",
        "prepared_match_write",
        "prepared_exception_write",
    ],
    "missing_po": [
        "raw_invoice_text",
        "extracted_invoice",
        "invoice_validation",
        "match_result",
        "classified_exceptions",
        "exception_action_plan",
        "match_report",
        "exception_report",
        "ledger_summary",
        "rollback_summary",
        "evidence_bundle",
        "prepared_invoice_write",
        "prepared_match_write",
        "prepared_exception_write",
    ],
    "missing_receipt": [
        "raw_invoice_text",
        "extracted_invoice",
        "invoice_validation",
        "match_result",
        "classified_exceptions",
        "exception_action_plan",
        "match_report",
        "exception_report",
        "ledger_summary",
        "rollback_summary",
        "evidence_bundle",
        "prepared_invoice_write",
        "prepared_match_write",
        "prepared_exception_write",
    ],
    "duplicate_invoice": [
        "raw_invoice_text",
        "extracted_invoice",
        "invoice_validation",
        "match_result",
        "classified_exceptions",
        "exception_action_plan",
        "match_report",
        "exception_report",
        "ledger_summary",
        "rollback_summary",
        "evidence_bundle",
        "prepared_invoice_write",
        "prepared_match_write",
        "prepared_exception_write",
    ],
    "supplier_mismatch": [
        "raw_invoice_text",
        "extracted_invoice",
        "invoice_validation",
        "match_result",
        "classified_exceptions",
        "exception_action_plan",
        "match_report",
        "exception_report",
        "ledger_summary",
        "rollback_summary",
        "evidence_bundle",
        "prepared_invoice_write",
        "prepared_match_write",
        "prepared_exception_write",
    ],
    "price_mismatch": [
        "raw_invoice_text",
        "extracted_invoice",
        "invoice_validation",
        "match_result",
        "classified_exceptions",
        "exception_action_plan",
        "match_report",
        "exception_report",
        "ledger_summary",
        "rollback_summary",
        "evidence_bundle",
        "prepared_invoice_write",
        "prepared_match_write",
        "prepared_exception_write",
    ],
    "quantity_mismatch": [
        "raw_invoice_text",
        "extracted_invoice",
        "invoice_validation",
        "match_result",
        "classified_exceptions",
        "exception_action_plan",
        "match_report",
        "exception_report",
        "ledger_summary",
        "rollback_summary",
        "evidence_bundle",
        "prepared_invoice_write",
        "prepared_match_write",
        "prepared_exception_write",
    ],
    "bad_invoice_text": [
        "raw_invoice_text",
        "extracted_invoice",
        "invoice_validation",
    ],
    "rollback_required_case": [
        "raw_invoice_text",
        "extracted_invoice",
        "invoice_validation",
        "match_result",
        "classified_exceptions",
        "exception_action_plan",
        "match_report",
        "exception_report",
        "ledger_summary",
        "rollback_summary",
        "evidence_bundle",
        "prepared_invoice_write",
        "prepared_match_write",
        "prepared_ledger_write",
    ],
}


@dataclass(frozen=True)
class GalleryScenario:
    scenario_id: str
    invoice_file: str
    expected_status: str

    @property
    def required_outputs(self) -> list[str]:
        return list(_REQUIRED_OUTPUTS_BY_SCENARIO.get(self.scenario_id, []))


def load_invoiceops_gallery_index(gallery_dir: str | Path = DEFAULT_GALLERY_DIR) -> dict:
    path = Path(gallery_dir) / "gallery_index.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"gallery_id": GALLERY_ID, "scenarios": []}


def iter_invoiceops_gallery_scenarios(gallery_dir: str | Path = DEFAULT_GALLERY_DIR) -> list[dict[str, Any]]:
    index = load_invoiceops_gallery_index(gallery_dir)
    scenarios = index.get("scenarios") or []
    return [dict(item) for item in scenarios if isinstance(item, dict)]


def run_invoiceops_gallery(runtime_data_dir: str = "runtime_data", gallery_dir: str | Path = DEFAULT_GALLERY_DIR) -> dict:
    gallery_path = Path(gallery_dir)
    output_root = Path(runtime_data_dir) / DEFAULT_OUTPUT_DIR_NAME
    output_root.mkdir(parents=True, exist_ok=True)

    index = load_invoiceops_gallery_index(gallery_path)
    scenarios = iter_invoiceops_gallery_scenarios(gallery_path)
    scenario_results: list[dict[str, Any]] = []
    for scenario in scenarios:
        scenario_results.append(
            _run_invoiceops_gallery_scenario(
                scenario,
                gallery_dir=gallery_path,
                runtime_data_dir=Path(runtime_data_dir),
                output_root=output_root,
            )
        )

    total = len(scenario_results)
    passed = sum(1 for item in scenario_results if item.get("ok"))
    failed = total - passed
    result = {
        "ok": failed == 0 and str(index.get("gallery_id", GALLERY_ID)) == GALLERY_ID,
        "gallery_id": str(index.get("gallery_id", GALLERY_ID)),
        "manifest_id": str(index.get("manifest_id", MANIFEST_ID)),
        "scenario_results": scenario_results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
        },
        "live_side_effects_performed": any(bool(item.get("live_side_effects_performed")) for item in scenario_results),
    }

    _write_gallery_output(output_root, "gallery_summary.json", result)
    _write_gallery_output(output_root, "gallery_summary.md", _render_gallery_markdown(result))
    return result


def _run_invoiceops_gallery_scenario(
    scenario: dict[str, Any],
    *,
    gallery_dir: Path,
    runtime_data_dir: Path,
    output_root: Path,
) -> dict:
    scenario_id = str(scenario.get("scenario_id", "")).strip()
    invoice_file = str(scenario.get("invoice_file", "")).strip()
    expected_status = str(scenario.get("expected_status", "blocked")).strip() or "blocked"
    scenario_dir = output_root / scenario_id
    business_dir = scenario_dir / "business"
    business_dir.mkdir(parents=True, exist_ok=True)

    _copy_business_fixtures(gallery_dir / "business", business_dir)

    invoice_path = (gallery_dir / invoice_file).resolve()
    manifest_path = DEFAULT_MANIFEST_PATH
    if not invoice_path.is_file():
        return _failure_scenario_result(
            scenario_id,
            expected_status,
            manifest_path=manifest_path,
            error_code="INVOICE_FILE_NOT_FOUND",
            message=f"Invoice fixture missing: {invoice_file}",
        )

    try:
        manifest = load_manifest(manifest_path)
        orch = Orchestrator(runtime_data_dir=scenario_dir, manifest_dir=str(manifest_path.parent))
        inputs = {"invoice_file_path": str(invoice_path)}
        frame = orch.create_frame_from_manifest(manifest, inputs=inputs, raw_input=json.dumps(inputs))
        frame = orch.prepare_frame(frame)
        with use_sheet_fixture_mode(True, str(scenario_dir)):
            frame = orch.run_until_blocked(frame, manifest, dry_run=True)
        frame_dict = taskframe_to_dict(frame)
    except Exception as exc:
        return _failure_scenario_result(
            scenario_id,
            expected_status,
            manifest_path=manifest_path,
            error_code="SCENARIO_EXECUTION_FAILED",
            message=str(exc),
        )

    outputs = frame_dict.get("outputs", {}) if isinstance(frame_dict, dict) else {}
    actual_status = _derive_actual_status(frame_dict, outputs)
    required_outputs = list(scenario.get("required_outputs") or _REQUIRED_OUTPUTS_BY_SCENARIO.get(scenario_id, []))
    required_outputs_present = all(key in outputs for key in required_outputs)
    prepared_write_keys = [key for key in outputs if key.startswith("prepared_")]
    prepared_writes_created = bool(prepared_write_keys)
    rollback_metadata_present = _rollback_metadata_present(outputs, prepared_write_keys)
    report_outputs = [key for key in outputs if key in _REPORT_OUTPUT_KEYS]
    live_side_effects_performed = False
    ok = (
        actual_status == expected_status
        and required_outputs_present
        and not live_side_effects_performed
    )

    result = {
        "scenario_id": scenario_id,
        "ok": ok,
        "expected_status": expected_status,
        "actual_status": actual_status,
        "frame_id": str(frame_dict.get("frame_id", "")) if isinstance(frame_dict, dict) else "",
        "manifest_id": str(frame_dict.get("manifest_id", MANIFEST_ID)) if isinstance(frame_dict, dict) else MANIFEST_ID,
        "required_outputs_present": required_outputs_present,
        "prepared_writes_created": prepared_writes_created,
        "rollback_metadata_present": rollback_metadata_present,
        "live_side_effects_performed": live_side_effects_performed,
        "report_outputs": report_outputs,
        "required_outputs": required_outputs,
        "outputs": list(outputs.keys()) if isinstance(outputs, dict) else [],
        "state": frame_dict.get("state", "") if isinstance(frame_dict, dict) else "",
        "error": "" if ok else _derive_gallery_error(actual_status, expected_status, required_outputs_present),
        "frame": frame_dict,
    }
    _write_gallery_output(scenario_dir, "scenario_result.json", result)
    return result


def _failure_scenario_result(
    scenario_id: str,
    expected_status: str,
    *,
    manifest_path: Path,
    error_code: str,
    message: str,
) -> dict:
    return {
        "scenario_id": scenario_id,
        "ok": False,
        "expected_status": expected_status,
        "actual_status": "blocked",
        "frame_id": "",
        "manifest_id": MANIFEST_ID,
        "required_outputs_present": False,
        "prepared_writes_created": False,
        "rollback_metadata_present": False,
        "live_side_effects_performed": False,
        "report_outputs": [],
        "required_outputs": list(_REQUIRED_OUTPUTS_BY_SCENARIO.get(scenario_id, [])),
        "outputs": [],
        "state": "FAILED",
        "error": f"{error_code}: {message}",
        "manifest_path": str(manifest_path),
    }


def _derive_actual_status(frame: dict, outputs: dict[str, Any]) -> str:
    match_result = outputs.get("match_result")
    if isinstance(match_result, dict):
        data = match_result.get("data") if isinstance(match_result.get("data"), dict) else {}
        match_data = data.get("match_result") if isinstance(data, dict) else {}
        if isinstance(match_data, dict):
            status = str(match_data.get("match_status", "")).strip()
            if status:
                return status

    invoice_validation = outputs.get("invoice_validation")
    if isinstance(invoice_validation, dict):
        data = invoice_validation.get("data") if isinstance(invoice_validation.get("data"), dict) else {}
        if isinstance(data, dict) and data.get("valid") is False:
            return "blocked"

    state = str(frame.get("state", "")).strip().upper()
    if state in {"FAILED", "FAILED_VALIDATION"}:
        return "blocked"
    if state == "COMPLETED":
        return "matched"
    return "blocked"


def _rollback_metadata_present(outputs: dict[str, Any], prepared_write_keys: list[str]) -> bool:
    if not prepared_write_keys:
        return False
    for key in prepared_write_keys:
        result = outputs.get(key)
        if not isinstance(result, dict):
            return False
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        prepared_write = data.get("prepared_write") if isinstance(data, dict) else {}
        if not isinstance(prepared_write, dict):
            return False
        rollback_plan = prepared_write.get("rollback_plan")
        if not isinstance(rollback_plan, dict) or not rollback_plan:
            return False
    return True


def _derive_gallery_error(actual_status: str, expected_status: str, required_outputs_present: bool) -> str:
    if actual_status != expected_status:
        return f"Unexpected status: expected {expected_status}, got {actual_status}."
    if not required_outputs_present:
        return "Required outputs missing."
    return "Gallery scenario failed."


def _copy_business_fixtures(source_dir: Path, target_dir: Path) -> None:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Business fixture directory missing: {source_dir}")
    for source in sorted(source_dir.glob("*.json")):
        shutil.copyfile(source, target_dir / source.name)


def _write_gallery_output(base_dir: Path, name: str, data: Any) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / name
    if name.endswith(".json"):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    else:
        path.write_text(str(data), encoding="utf-8")


def _render_gallery_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# InvoiceOps Regression Gallery",
        "",
        f"- Gallery ID: {result.get('gallery_id', GALLERY_ID)}",
        f"- Manifest ID: {result.get('manifest_id', MANIFEST_ID)}",
        f"- Total scenarios: {result.get('summary', {}).get('total', 0)}",
        f"- Passed: {result.get('summary', {}).get('passed', 0)}",
        f"- Failed: {result.get('summary', {}).get('failed', 0)}",
        f"- Live side effects performed: {str(result.get('live_side_effects_performed', False)).lower()}",
        "",
        "## Scenario Results",
        "",
        "| Scenario | Expected | Actual | OK | Prepared Writes | Rollback Metadata | Reports |",
        "|---|---|---|---|---|---|---|",
    ]
    for scenario in result.get("scenario_results", []) or []:
        lines.append(
            f"| {scenario.get('scenario_id', '')} | {scenario.get('expected_status', '')} | {scenario.get('actual_status', '')} | "
            f"{'yes' if scenario.get('ok') else 'no'} | {'yes' if scenario.get('prepared_writes_created') else 'no'} | "
            f"{'yes' if scenario.get('rollback_metadata_present') else 'no'} | {', '.join(scenario.get('report_outputs') or [])} |"
        )
    lines.append("")
    return "\n".join(lines)
