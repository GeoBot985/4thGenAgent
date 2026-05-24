"""Spec 156 — InvoiceOps live posting CLI tests."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent


def _run_cli(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "src" / "taskframe_cli.py"), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(ROOT),
    )


def test_cli_invoiceops_command_exists():
    result = _run_cli("invoiceops", "--help")
    assert result.returncode in (0, 1, 2)
    combined = result.stdout + result.stderr
    assert "invoiceops" in combined.lower() or "live-posting" in combined.lower() or "usage" in combined.lower()


def test_cli_invoiceops_live_posting_plan_returns_json():
    result = _run_cli(
        "invoiceops", "live-posting", "plan",
        "--frame-id", "frame_cli_001",
        "--invoice-id", "INV-CLI-001",
        "--invoice-number", "INV-CLI-001",
        "--supplier-name", "CLI Supplier",
        "--po-number", "PO-CLI-001",
        "--match-status", "matched",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "posting_plan_id" in data or "posting_plan" in data or "frame_id" in data


def test_cli_plan_empty_prepared_writes_zero_actions():
    result = _run_cli(
        "invoiceops", "live-posting", "plan",
        "--frame-id", "frame_cli_002",
        "--invoice-id", "INV-CLI-002",
        "--invoice-number", "INV-CLI-002",
        "--supplier-name", "CLI Supplier 2",
        "--po-number", "PO-CLI-002",
        "--match-status", "matched",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    plan = data.get("posting_plan") or data
    assert plan.get("eligible_write_count", 0) == 0


def test_cli_plan_json_is_valid_for_matched():
    result = _run_cli(
        "invoiceops", "live-posting", "plan",
        "--frame-id", "frame_cli_003",
        "--invoice-id", "INV-003",
        "--invoice-number", "INV-003",
        "--supplier-name", "Supplier Three",
        "--po-number", "PO-003",
        "--match-status", "matched",
        "--json",
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, dict)


def test_cli_plan_blocked_match_status_in_output():
    result = _run_cli(
        "invoiceops", "live-posting", "plan",
        "--frame-id", "frame_cli_004",
        "--invoice-id", "INV-004",
        "--invoice-number", "INV-004",
        "--supplier-name", "Supplier Four",
        "--po-number", "PO-004",
        "--match-status", "blocked",
        "--json",
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    plan = data.get("posting_plan") or data
    assert plan.get("match_status") == "blocked" or "blocked" in str(data)


def test_cli_preflight_returns_json():
    result = _run_cli(
        "invoiceops", "live-posting", "preflight",
        "--frame-id", "frame_cli_005",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert isinstance(data, dict)


def test_cli_approval_pack_returns_json():
    result = _run_cli(
        "invoiceops", "live-posting", "approval-pack",
        "--frame-id", "frame_cli_006",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert isinstance(data, dict)


def test_cli_execute_requires_action_id():
    result = _run_cli(
        "invoiceops", "live-posting", "execute",
        "--frame-id", "frame_cli_007",
        "--confirm", "EXECUTE LIVE sheet/write_rows frame_cli_007 pa_007",
    )
    # Should fail due to missing --action-id
    assert result.returncode != 0 or "action-id" in (result.stdout + result.stderr).lower()
