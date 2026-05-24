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


def test_showcase_status_emits_valid_json(tmp_path: Path) -> None:
    result = _run_cli(
        "invoiceops", "showcase", "status",
        "--runtime-data-dir", str(tmp_path),
        "--json",
    )
    assert result.returncode in (0, 1), result.stderr
    data = json.loads(result.stdout)
    assert "status" in data
    assert "invoice_fixture_count" in data
    assert data["invoice_fixture_count"] >= 8


def test_showcase_status_needs_config_when_no_id(tmp_path: Path) -> None:
    result = _run_cli(
        "invoiceops", "showcase", "status",
        "--runtime-data-dir", str(tmp_path),
        "--json",
    )
    data = json.loads(result.stdout)
    assert data.get("needs_config") is True


def test_showcase_run_boundary_emits_valid_json(tmp_path: Path) -> None:
    result = _run_cli(
        "invoiceops", "showcase", "run",
        "--profile", "controlled_live_write",
        "--invoice-limit", "1",
        "--runtime-data-dir", str(tmp_path),
        "--json",
    )
    assert result.returncode in (0, 1), result.stderr
    data = json.loads(result.stdout)
    assert "demo_run_id" in data
    assert data.get("live_side_effects_performed") is False


def test_showcase_run_boundary_processes_invoices(tmp_path: Path) -> None:
    result = _run_cli(
        "invoiceops", "showcase", "run",
        "--profile", "controlled_live_write",
        "--runtime-data-dir", str(tmp_path),
        "--json",
    )
    data = json.loads(result.stdout)
    assert data.get("invoice_count", 0) == 8


def test_showcase_run_live_blocked_without_confirm(tmp_path: Path) -> None:
    result = _run_cli(
        "invoiceops", "showcase", "run",
        "--profile", "controlled_live_write",
        "--live",
        "--spreadsheet-id", "SHEET123",
        "--confirm", "WRONG PHRASE",
        "--runtime-data-dir", str(tmp_path),
        "--json",
    )
    data = json.loads(result.stdout)
    assert data.get("ok") is False
    assert data.get("live_side_effects_performed") is False


def test_showcase_run_writes_report(tmp_path: Path) -> None:
    result = _run_cli(
        "invoiceops", "showcase", "run",
        "--profile", "controlled_live_write",
        "--write-report",
        "--runtime-data-dir", str(tmp_path),
        "--json",
    )
    data = json.loads(result.stdout)
    assert data.get("ok")
    assert data.get("reports", {}).get("json_latest")
    assert Path(data["reports"]["json_latest"]).is_file()


def test_showcase_run_invoice_limit_is_respected(tmp_path: Path) -> None:
    result = _run_cli(
        "invoiceops", "showcase", "run",
        "--invoice-limit", "3",
        "--runtime-data-dir", str(tmp_path),
        "--json",
    )
    data = json.loads(result.stdout)
    assert data.get("invoice_count") == 3
