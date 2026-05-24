from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(ROOT),
    )


def test_reconcile_cli_emits_valid_json_for_missing_invoice() -> None:
    result = _run_cli("invoiceops", "reconcile", "--invoice-number", "fake", "--json")
    assert result.returncode in (0, 1), result.stderr
    data = json.loads(result.stdout)
    assert data["invoice_number"] == "fake"
    assert data["status"] in {"MISSING_POSTING_EVIDENCE", "MANUAL_REVIEW_REQUIRED", "UNRECONCILED", "BLOCKED"}
    assert "checks" in data


def test_evidence_pack_cli_emits_valid_json_for_missing_invoice() -> None:
    result = _run_cli("invoiceops", "evidence-pack", "--invoice-number", "fake", "--json")
    assert result.returncode in (0, 1), result.stderr
    data = json.loads(result.stdout)
    assert data["invoice_number"] == "fake"
    assert data["sections"]
    assert data["reconciliation"]["status"] in {"MISSING_POSTING_EVIDENCE", "MANUAL_REVIEW_REQUIRED", "UNRECONCILED", "BLOCKED"}


def test_reconciliation_and_evidence_pack_write_reports(tmp_path: Path) -> None:
    runtime_data_dir = tmp_path / "runtime_data"
    runtime_data_dir.mkdir(parents=True, exist_ok=True)

    reconcile = _run_cli(
        "invoiceops",
        "reconcile",
        "--invoice-number",
        "fake",
        "--runtime-data-dir",
        str(runtime_data_dir),
        "--write-report",
        "--json",
    )
    assert reconcile.returncode in (0, 1), reconcile.stderr
    reconcile_data = json.loads(reconcile.stdout)
    reconcile_json = runtime_data_dir / "invoiceops" / "reconciliation" / "fake_reconciliation.json"
    reconcile_md = runtime_data_dir / "invoiceops" / "reconciliation" / "fake_reconciliation.md"
    assert reconcile_json.is_file()
    assert reconcile_md.is_file()
    assert reconcile_data["report_paths"]["json"] == str(reconcile_json)

    pack = _run_cli(
        "invoiceops",
        "evidence-pack",
        "--invoice-number",
        "fake",
        "--runtime-data-dir",
        str(runtime_data_dir),
        "--write-report",
        "--json",
    )
    assert pack.returncode in (0, 1), pack.stderr
    pack_data = json.loads(pack.stdout)
    pack_json = runtime_data_dir / "invoiceops" / "accounting_evidence" / "fake_accounting_evidence_pack.json"
    pack_md = runtime_data_dir / "invoiceops" / "accounting_evidence" / "fake_accounting_evidence_pack.md"
    assert pack_json.is_file()
    assert pack_md.is_file()
    assert pack_data["report_paths"]["json"] == str(pack_json)

