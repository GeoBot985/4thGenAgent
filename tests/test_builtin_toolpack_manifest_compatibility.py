from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCENARIOS = [
    "customer_status_approve_execute_dry_run",
    "procurement_low_stock_happy_path",
    "accounting_payment_reconciliation_happy_path",
]


def _run_demo(scenario_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "demo", "--scenario", scenario_id, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_customer_workflow_still_runs() -> None:
    result = _run_demo("customer_status_approve_execute_dry_run")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


def test_procurement_workflow_still_runs() -> None:
    result = _run_demo("procurement_low_stock_happy_path")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


def test_accounting_workflow_still_runs() -> None:
    result = _run_demo("accounting_payment_reconciliation_happy_path")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


def test_cross_workflow_demo_still_runs() -> None:
    from src.operator_cross_workflow_demo import run_cross_workflow_demo_pack

    result = run_cross_workflow_demo_pack(
        use_real_llm=False,
        allow_test_fake_llm=True,
        skip_llm_preflight=True,
        runtime_data_dir="runtime_data",
        generate_reports=False,
    )
    assert result["ok"] is True


def test_golden_demo_still_runs() -> None:
    result = subprocess.run([sys.executable, "-m", "src.taskframe_cli", "golden-demo"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "Golden demo:" in result.stdout


def test_migrated_tool_call_appears_in_inventory() -> None:
    from src.tool_inventory import build_tool_inventory_report

    report = build_tool_inventory_report(runtime_data_dir=Path("runtime_data"))
    assert any(item["source"] == "migrated_toolpack" for item in report["tools"])


def test_existing_manifests_use_command_syntax_not_module_fields() -> None:
    from runtime.manifest_loader import load_manifest_by_id

    manifest = load_manifest_by_id("customer.status_llm_e2e", "manifests")
    steps = list(getattr(manifest, "steps", []))
    assert steps
    for step in steps:
        assert getattr(step, "command", "")
        metadata = getattr(step, "metadata", {})
        assert "module" not in metadata
        assert "function" not in metadata
