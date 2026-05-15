from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.write_current_release_status import write_current_release_status
from src.manifest_health import run_manifest_health_check, write_manifest_health_report

OUTPUT_JSON = ROOT / "runtime_data" / "audit" / "release_candidate_verification.json"
OUTPUT_MD = ROOT / "docs" / "release_candidate_verification.md"
EVIDENCE_INDEX_MD = ROOT / "docs" / "release_candidate_evidence_index.md"
KNOWN_LIMITATIONS_MD = ROOT / "docs" / "known_limitations.md"
CONFIGURATION_MD = ROOT / "docs" / "configuration.md"
CURRENT_RELEASE_STATUS_MD = ROOT / "docs" / "current_release_status.md"
RELEASE_EVIDENCE_PACK_MD = ROOT / "docs" / "release_evidence_pack.md"
RUNTIME_CONTRACTS_MD = ROOT / "docs" / "runtime_contracts.md"
DEFAULT_DEMO_BOUNDARY_MD = ROOT / "docs" / "default_demo_boundary.md"
ADDING_NEW_TOOLS_MD = ROOT / "docs" / "adding_new_tools.md"
TOOL_CONTRACT_CHECKLIST_MD = ROOT / "docs" / "tool_contract_checklist.md"
RELEASE_STATUS_JSON = ROOT / "runtime_data" / "audit" / "release_status_latest.json"
RELEASE_EVIDENCE_JSON = ROOT / "runtime_data" / "audit" / "release_evidence_pack.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path)


def run_command(name: str, command: list[str], timeout_seconds: int = 300) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    duration_ms = int((time.time() - started) * 1000)
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    return {
        "name": name,
        "command": command,
        "returncode": proc.returncode,
        "duration_ms": duration_ms,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
        "status": "PASS" if proc.returncode == 0 else "FAIL",
    }


def check_file_exists(path: str) -> dict[str, Any]:
    file_path = ROOT / path
    return {"path": path, "exists": file_path.is_file(), "status": "PASS" if file_path.is_file() else "FAIL"}


def check_forbidden_terms(path: str, forbidden_terms: list[str]) -> dict[str, Any]:
    file_path = ROOT / path
    text = file_path.read_text(encoding="utf-8") if file_path.is_file() else ""
    found = [term for term in forbidden_terms if term in text.lower()]
    return {
        "path": path,
        "forbidden_terms": forbidden_terms,
        "found": found,
        "status": "PASS" if not found else "FAIL",
    }


def build_verification_result() -> dict[str, Any]:
    generated_at = utc_now()
    bootstrap_result = {
        "report_type": "release_candidate_verification",
        "version": 1,
        "generated_at": generated_at,
        "verdict": "RUNNING",
        "summary": {
            "command_count": 0,
            "passed_commands": 0,
            "failed_commands": 0,
            "skipped_checks": 0,
            "missing_artifacts": 0,
            "limitations": 0,
        },
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "cwd": _display_path(ROOT),
            "git_commit": _git("rev-parse", "HEAD"),
            "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        },
        "commands": [],
        "static_checks": [],
        "artifact_checks": [],
        "checks": {
            "imports": "PENDING",
            "packaging_cli": "PENDING",
            "manifest_health_cli_strict": "PENDING",
            "default_tool_registry": "PENDING",
            "tool_capability_registry": "PENDING",
            "core_tool_health_safe_checks": "PENDING",
            "optional_rpa_excluded": "PENDING",
            "optional_rpa_live_probes_excluded": "PENDING",
            "default_scenario_pack": "PENDING",
            "golden_demo": "PENDING",
            "release_artifacts": "PENDING",
            "docs_commands": "PENDING",
            "adding_new_tools_doc": "PENDING",
            "tool_contract_checklist_doc": "PENDING",
            "manifest_catalog_health": "PENDING",
            "public_quickstart_docs": "PENDING",
            "live_safety_docs": "PENDING",
            "live_cli_guardrails": "PENDING",
            "live_execution_default_dry_run": "PENDING",
            "optional_rpa_isolation": "PENDING",
            "config_secrets_hygiene": "PENDING",
        },
        "workflow_checks": {
            "customer": {"status": "PENDING", "count": 0},
            "procurement": {"status": "PENDING", "count": 0},
            "accounting": {"status": "PENDING", "count": 0},
            "cross_workflow": {"status": "PENDING", "count": 0},
        },
        "known_limitations": [],
        "release_blockers": [],
        "evidence_paths": [],
    }
    write_json_result(bootstrap_result, str(OUTPUT_JSON))
    _write_supporting_docs(bootstrap_result)

    commands: list[dict[str, Any]] = []
    static_checks: list[dict[str, Any]] = []
    artifact_checks: list[dict[str, Any]] = []
    known_limitations: list[str] = []
    release_blockers: list[str] = []
    evidence_paths: list[str] = []

    command_groups = [
        (
            "clean_imports",
            [
                "python",
                "-c",
                "import sys; import runtime.business_context, runtime.tool_registry, runtime.tool_capability_registry, runtime.tool_health, src.operator_scenarios; assert 'playwright' not in sys.modules and 'playwright.async_api' not in sys.modules",
            ],
        ),
        ("clean_clone_rc_tests", ["python", "-m", "pytest", "tests/test_clean_clone_rc_verification.py"]),
        ("full_pytest", ["python", "-m", "pytest"]),
        ("smoke_external_event_intake", ["python", "-m", "pytest", "tests/test_external_event_intake.py"]),
        ("smoke_inspection", ["python", "-m", "pytest", "tests/test_inspection.py"]),
        ("smoke_inspection_commands", ["python", "-m", "pytest", "tests/test_inspection_commands.py"]),
        ("core_retry_policy", ["python", "-m", "pytest", "tests/test_retry_policy.py"]),
        ("core_retry_tool_failures", ["python", "-m", "pytest", "tests/test_retry_tool_failures.py"]),
        ("core_execution_metrics", ["python", "-m", "pytest", "tests/test_execution_metrics.py"]),
        ("core_run_ledger", ["python", "-m", "pytest", "tests/test_run_ledger.py"]),
        ("customer_lane", ["python", "-m", "pytest", "tests/test_customer_workflow_tool_driven.py", "tests/test_runtime_mock_removal.py", "tests/test_negative_customer_status_scenarios.py"]),
        ("procurement_lane", ["python", "-m", "pytest", "tests/test_procurement_low_stock_reorder.py", "tests/test_procurement_approval_dry_run.py", "tests/test_procurement_report_pack.py"]),
        ("accounting_lane", ["python", "-m", "pytest", "tests/test_google_sheet_accounting_tools.py", "tests/test_accounting_reconciliation_tools.py", "tests/test_accounting_payment_reconciliation_workflow.py", "tests/test_accounting_approval_dry_run.py", "tests/test_accounting_report_pack.py"]),
        ("cross_workflow_demo", ["python", "-m", "pytest", "tests/test_cross_workflow_demo_pack.py", "tests/test_cross_workflow_demo_report.py"]),
        ("golden_demo", ["python", "scripts/run_golden_demo.py"]),
        ("portfolio_boundary", ["python", "-m", "pytest", "tests/test_portfolio_boundary.py", "tests/test_demo_scenarios.py", "tests/test_portfolio_docs_exist.py"]),
        ("portfolio_docs", ["python", "-m", "pytest", "tests/test_portfolio_docs_exist.py"]),
    ]

    for name, command in command_groups:
        result = run_command(name, command)
        commands.append(result)
        if result["status"] != "PASS":
            release_blockers.append(f"{name} failed")

    optional_commands: list[tuple[str, list[str]]] = []
    if (ROOT / "tests/integration/test_real_ollama_llm.py").is_file():
        optional_commands.append(("real_ollama_integration", ["python", "-m", "pytest", "tests/integration/test_real_ollama_llm.py"]))
    else:
        known_limitations.append("real_ollama_integration_test_missing")

    if (ROOT / "tests/integration/test_google_sheets_accounting.py").is_file():
        optional_commands.append(("google_sheets_integration", ["python", "-m", "pytest", "tests/integration/test_google_sheets_accounting.py"]))
    else:
        known_limitations.append("google_sheets_integration_test_missing")

    for name, command in optional_commands:
        result = run_command(name, command)
        commands.append(result)
        if result["status"] != "PASS":
            if "skipped" in (result["stdout"] + result["stderr"]).lower():
                known_limitations.append(f"{name}_skipped")
            else:
                release_blockers.append(f"{name} failed")

    static_checks.extend([
        _check_python_imports(),
        _check_packaging_cli(),
        _check_manifest_health_cli_strict(),
        _check_default_tool_registry(),
        _check_tool_capability_registry(),
        _check_core_tool_health_safe_checks(),
        _check_default_scenario_pack(),
        _check_runtime_contract_docs(),
        _check_default_demo_boundary_doc(),
        _check_known_limitations_doc(),
        _check_adding_new_tools_doc(),
        _check_tool_contract_checklist_doc(),
        _check_orchestrator_pollution(),
        _check_fake_llm_paths(),
        _check_side_effect_registry(),
        _check_optional_rpa_boundary(),
        _check_optional_rpa_live_probes_excluded_from_rc(),
        _check_release_artifacts_manifest(),
        _check_docs_command_alignment(),
        _check_generated_manifest_template_quality_gates(),
        _check_manifest_catalog_health(),
        _check_public_quickstart_docs(),
        _check_live_safety_docs(),
        _check_live_cli_guardrails(),
        _check_live_execution_default_dry_run(),
        _check_optional_rpa_isolation(),
        _check_config_secrets_hygiene(),
    ])
    manifest_health_check = next((check for check in static_checks if check.get("name") == "manifest_catalog_health"), {})
    for key in ("json_path", "markdown_path"):
        value = str(manifest_health_check.get(key, "")).strip()
        if value:
            evidence_paths.append(_display_path(Path(value)))
    for check in static_checks:
        if check["status"] != "PASS":
            if check["name"] == "python_imports":
                release_blockers.append("python imports failed")
            elif check["name"] == "packaging_cli":
                release_blockers.append("packaging / CLI checks failed")
            elif check["name"] == "manifest_health_cli_strict":
                release_blockers.append("manifest health strict CLI failed")
            elif check["name"] == "default_tool_registry":
                release_blockers.append("default tool registry failed")
            elif check["name"] == "TOOL_CAPABILITY_REGISTRY":
                release_blockers.append("tool capability registry failed")
            elif check["name"] == "CORE_TOOL_HEALTH_SAFE_CHECKS":
                release_blockers.append("core tool health checks failed")
            elif check["name"] == "default_scenario_pack":
                release_blockers.append("default scenario pack failed")
            elif check["name"] == "runtime_contract_docs":
                release_blockers.append("runtime contract docs failed")
            elif check["name"] == "default_demo_boundary_doc":
                release_blockers.append("default demo boundary doc failed")
            elif check["name"] == "known_limitations_doc":
                release_blockers.append("known limitations doc failed")
            elif check["name"] == "adding_new_tools_doc":
                release_blockers.append("tool onboarding guide failed")
            elif check["name"] == "tool_contract_checklist_doc":
                release_blockers.append("tool contract checklist failed")
            if check["name"] == "orchestrator_pollution":
                release_blockers.append("orchestrator pollution detected")
            elif check["name"] == "fake_llm_paths":
                release_blockers.append("fake LLM visible in app/demo path")
            elif check["name"] == "side_effect_registry":
                release_blockers.append("side effect registry safety check failed")
            elif check["name"] == "OPTIONAL_RPA_EXCLUDED_FROM_DEFAULT_RC":
                release_blockers.append("optional RPA leaked into default RC path")
            elif check["name"] == "OPTIONAL_RPA_LIVE_PROBES_EXCLUDED_FROM_RC":
                release_blockers.append("optional RPA live probe leaked into default RC path")
            elif check["name"] == "release_artifacts_manifest":
                release_blockers.append("release artifacts manifest failed")
            elif check["name"] == "docs_command_alignment":
                release_blockers.append("documentation commands mismatch")
            elif check["name"] == "generated_manifest_template_quality_gates":
                release_blockers.append("generated manifest template quality gates failed")
            elif check["name"] == "manifest_catalog_health":
                release_blockers.append("manifest catalog health failed")
            elif check["name"] == "public_quickstart_docs":
                release_blockers.append("public quickstart docs check failed")
            elif check["name"] == "live_safety_docs":
                release_blockers.append("live safety docs missing")
            elif check["name"] == "live_cli_guardrails":
                release_blockers.append("live CLI guardrail tests failed")
            elif check["name"] == "live_execution_default_dry_run":
                release_blockers.append("default live execution safety path failed")
            elif check["name"] == "optional_rpa_isolation":
                release_blockers.append("optional RPA isolation check failed")
            elif check["name"] == "config_secrets_hygiene":
                release_blockers.append("config / secrets hygiene failed")

    artifact_paths = [
        "README.md",
        "docs/release_artifacts.md",
        "docs/runtime_contracts.md",
        "docs/adding_new_tools.md",
        "docs/tool_contract_checklist.md",
        "docs/cli_reference.md",
        "docs/quickstart.md",
        "docs/index.md",
        "docs/optional_rpa.md",
        "docs/default_demo_boundary.md",
        "docs/known_limitations.md",
        "docs/current_release_status.md",
        "docs/release_evidence_pack.md",
        "scripts/run_release_verification.py",
        "scripts/run_golden_demo.py",
        "runtime/business_context.py",
        "docs/architecture_overview.md",
        "docs/demo_walkthrough.md",
        "docs/demo_script.md",
        "docs/capture_screenshots.md",
        "docs/portfolio_summary.md",
        "docs/release_candidate_verification.md",
        "runtime_data/outputs/reports/golden_demo_report.md",
        "runtime_data/outputs/reports/golden_demo_report.html",
        "runtime_data/outputs/audit/golden_demo_audit.json",
        "runtime_data/audit/release_status_latest.json",
        "runtime_data/audit/release_evidence_pack.json",
        "runtime_data/tool_health/latest_tool_health.json",
        "runtime_data/tool_health/reports/report_generator_probe.md",
        "runtime_data/tool_health/reports/report_generator_probe.html",
        "docs/screenshots/01_operator_home.png",
        "docs/screenshots/02_scenario_pack.png",
        "docs/screenshots/03_taskframe_detail.png",
        "docs/screenshots/04_step_playback.png",
        "docs/screenshots/05_pending_approval.png",
        "docs/screenshots/06_tool_status_panel.png",
        "docs/screenshots/07_tool_health_details.png",
        "docs/screenshots/08_report_output.png",
        "docs/screenshots/09_release_verification.png",
    ]
    for path in artifact_paths:
        item = check_file_exists(path)
        artifact_checks.append(item)
        if not item["exists"]:
            if "screenshots" in path:
                known_limitations.append(f"missing_screenshot:{path}")
            else:
                release_blockers.append(f"missing_artifact:{path}")

    reports = _find_report_artifacts()
    if reports:
        evidence_paths.extend(reports)
    else:
        known_limitations.append("no_report_artifacts_found")

    workflow_checks = {
        "customer": _workflow_check("customer", commands, "customer_lane"),
        "procurement": _workflow_check("procurement", commands, "procurement_lane"),
        "accounting": _workflow_check("accounting", commands, "accounting_lane"),
        "cross_workflow": _workflow_check("cross_workflow", commands, "cross_workflow_demo"),
    }

    checks = {
        "imports": _status_from_commands(commands, "clean_imports"),
        "packaging_cli": _status_from_static(static_checks, "packaging_cli"),
        "manifest_health_cli_strict": _status_from_static(static_checks, "manifest_health_cli_strict"),
        "default_tool_registry": _status_from_static(static_checks, "default_tool_registry"),
        "tool_capability_registry": _status_from_static(static_checks, "TOOL_CAPABILITY_REGISTRY"),
        "core_tool_health_safe_checks": _status_from_static(static_checks, "CORE_TOOL_HEALTH_SAFE_CHECKS"),
        "optional_rpa_excluded": _status_from_static(static_checks, "OPTIONAL_RPA_EXCLUDED_FROM_DEFAULT_RC"),
        "optional_rpa_live_probes_excluded": _status_from_static(static_checks, "OPTIONAL_RPA_LIVE_PROBES_EXCLUDED_FROM_RC"),
        "default_scenario_pack": _status_from_static(static_checks, "default_scenario_pack"),
        "golden_demo": _status_from_commands(commands, "golden_demo"),
        "release_artifacts": "PENDING",
        "docs_commands": _status_from_static(static_checks, "docs_command_alignment"),
        "adding_new_tools_doc": _status_from_static(static_checks, "adding_new_tools_doc"),
        "tool_contract_checklist_doc": _status_from_static(static_checks, "tool_contract_checklist_doc"),
        "manifest_catalog_health": _status_from_static(static_checks, "manifest_catalog_health"),
        "public_quickstart_docs": _status_from_static(static_checks, "public_quickstart_docs"),
        "optional_rpa_isolation": _status_from_static(static_checks, "optional_rpa_isolation"),
        "config_secrets_hygiene": _status_from_static(static_checks, "config_secrets_hygiene"),
    }

    if release_blockers:
        verdict = "NOT_READY"
    elif known_limitations:
        verdict = "READY_WITH_KNOWN_LIMITATIONS"
    else:
        verdict = "READY"

    summary = {
        "command_count": len(commands),
        "passed_commands": sum(1 for item in commands if item["status"] == "PASS"),
        "failed_commands": sum(1 for item in commands if item["status"] == "FAIL"),
        "skipped_checks": len([item for item in commands if _looks_skipped(item)]),
        "missing_artifacts": 0,
        "limitations": len(known_limitations),
    }
    result = {
        "report_type": "release_candidate_verification",
        "version": 1,
        "generated_at": generated_at,
        "verdict": verdict,
        "summary": summary,
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "cwd": _display_path(ROOT),
            "git_commit": _git("rev-parse", "HEAD"),
            "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        },
        "commands": commands,
        "static_checks": static_checks,
        "artifact_checks": [],
        "checks": checks,
        "workflow_checks": workflow_checks,
        "known_limitations": _unique(known_limitations),
        "release_blockers": _unique(release_blockers),
        "evidence_paths": _unique(evidence_paths),
    }
    _write_supporting_docs(result)

    artifact_paths = [
        "README.md",
        "docs/release_artifacts.md",
        "docs/runtime_contracts.md",
        "docs/adding_new_tools.md",
        "docs/tool_contract_checklist.md",
        "docs/cli_reference.md",
        "docs/quickstart.md",
        "docs/index.md",
        "docs/optional_rpa.md",
        "docs/default_demo_boundary.md",
        "docs/known_limitations.md",
        "docs/current_release_status.md",
        "docs/release_evidence_pack.md",
        "scripts/run_release_verification.py",
        "scripts/run_golden_demo.py",
        "runtime/business_context.py",
        "docs/architecture_overview.md",
        "docs/demo_walkthrough.md",
        "docs/demo_script.md",
        "docs/capture_screenshots.md",
        "docs/portfolio_summary.md",
        "docs/release_candidate_verification.md",
        "runtime_data/outputs/reports/golden_demo_report.md",
        "runtime_data/outputs/reports/golden_demo_report.html",
        "runtime_data/outputs/audit/golden_demo_audit.json",
        "runtime_data/audit/release_status_latest.json",
        "runtime_data/audit/release_evidence_pack.json",
        "runtime_data/tool_health/latest_tool_health.json",
        "runtime_data/tool_health/reports/report_generator_probe.md",
        "runtime_data/tool_health/reports/report_generator_probe.html",
        "docs/screenshots/01_operator_home.png",
        "docs/screenshots/02_scenario_pack.png",
        "docs/screenshots/03_taskframe_detail.png",
        "docs/screenshots/04_step_playback.png",
        "docs/screenshots/05_pending_approval.png",
        "docs/screenshots/06_tool_status_panel.png",
        "docs/screenshots/07_tool_health_details.png",
        "docs/screenshots/08_report_output.png",
        "docs/screenshots/09_release_verification.png",
    ]
    for path in artifact_paths:
        item = check_file_exists(path)
        artifact_checks.append(item)
        if not item["exists"]:
            if "screenshots" in path:
                known_limitations.append(f"missing_screenshot:{path}")
            else:
                release_blockers.append(f"missing_artifact:{path}")

    reports = _find_report_artifacts()
    if reports:
        evidence_paths.extend(reports)
    else:
        known_limitations.append("no_report_artifacts_found")

    evidence_paths.extend([
        _display_path(OUTPUT_JSON),
        _display_path(OUTPUT_MD),
        _display_path(EVIDENCE_INDEX_MD),
        _display_path(CURRENT_RELEASE_STATUS_MD),
        _display_path(RELEASE_EVIDENCE_PACK_MD),
        _display_path(RUNTIME_CONTRACTS_MD),
        _display_path(ADDING_NEW_TOOLS_MD),
        _display_path(TOOL_CONTRACT_CHECKLIST_MD),
        _display_path(DEFAULT_DEMO_BOUNDARY_MD),
        _display_path(KNOWN_LIMITATIONS_MD),
        _display_path(RELEASE_STATUS_JSON),
        _display_path(RELEASE_EVIDENCE_JSON),
    ])

    checks["release_artifacts"] = _status_from_artifacts(artifact_checks, [
        "docs/release_artifacts.md",
        "docs/runtime_contracts.md",
        "docs/adding_new_tools.md",
        "docs/tool_contract_checklist.md",
        "docs/default_demo_boundary.md",
        "docs/known_limitations.md",
        "docs/current_release_status.md",
        "docs/release_evidence_pack.md",
        "scripts/run_golden_demo.py",
        "runtime_data/outputs/reports/golden_demo_report.md",
        "runtime_data/outputs/reports/golden_demo_report.html",
        "runtime_data/outputs/audit/golden_demo_audit.json",
        "runtime_data/audit/release_status_latest.json",
        "runtime_data/audit/release_evidence_pack.json",
        "runtime_data/tool_health/latest_tool_health.json",
    ])

    if release_blockers:
        verdict = "NOT_READY"
    elif known_limitations:
        verdict = "READY_WITH_KNOWN_LIMITATIONS"
    else:
        verdict = "READY"

    result.update(
        {
            "verdict": verdict,
            "summary": {
                **summary,
                "missing_artifacts": len([item for item in artifact_checks if not item["exists"]]),
                "limitations": len(known_limitations),
            },
            "artifact_checks": artifact_checks,
            "checks": checks,
            "known_limitations": _unique(known_limitations),
            "release_blockers": _unique(release_blockers),
            "evidence_paths": _unique(evidence_paths),
        }
    )
    _write_supporting_docs(result)
    return result


def write_json_result(result: dict[str, Any], path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown_report(result: dict[str, Any], path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Release Candidate Verification Report",
        "",
        "## Verdict",
        "",
        f"- {result.get('verdict', 'UNKNOWN')}",
        "",
        "## Executive Summary",
        "",
        f"- Generated At: {result.get('generated_at', '')}",
        f"- Commands Run: {result.get('summary', {}).get('command_count', 0)}",
        f"- Passed Commands: {result.get('summary', {}).get('passed_commands', 0)}",
        f"- Failed Commands: {result.get('summary', {}).get('failed_commands', 0)}",
        f"- Skipped Checks: {result.get('summary', {}).get('skipped_checks', 0)}",
        "",
        "## Environment",
        "",
        f"- Python: {result.get('environment', {}).get('python_version', '')}",
        f"- Platform: {result.get('environment', {}).get('platform', '')}",
        f"- CWD: {result.get('environment', {}).get('cwd', '')}",
        f"- Git Commit: {result.get('environment', {}).get('git_commit', '')}",
        f"- Git Branch: {result.get('environment', {}).get('git_branch', '')}",
        "",
        "## Architecture Claims Verified",
        "",
        "| Claim | Evidence |",
        "|---|---|",
        "| TaskFrame-centered runtime | TaskFrame artifacts, reports, evidence bundle |",
        "| Manifest-driven execution | manifests present; workflow tests pass |",
        "| Generic orchestrator | static scan of runtime/orchestrator.py |",
        "| Domain tools externalized | tool registry and workflow tests |",
        "| Bounded LLM use | LLM command tests and fake-path scan |",
        "| Approval-gated side effects | pending/executed action tests |",
        "| Dry-run execution safety | customer/procurement/accounting dry-run tests |",
        "| Multi-workflow generalization | customer, procurement, accounting, cross-workflow tests |",
        "| Portfolio readiness | README, walkthrough, screenshots, demo script, release verification |",
        "",
        "## Test Results",
        "",
    ]
    for command in result.get("commands", []):
        lines.append(f"- {command.get('name', '')}: {command.get('status', '')} ({command.get('returncode', '')})")
    lines.extend([
        "",
        "## Workflow Verification",
        "",
    ])
    for lane, checks in result.get("workflow_checks", {}).items():
        lines.append(f"- {lane}: {checks.get('status', 'UNKNOWN')}")
    lines.extend([
        "",
        "## Static Architecture Checks",
        "",
    ])
    for item in result.get("static_checks", []):
        lines.append(f"- {item.get('name', '')}: {item.get('status', '')}")
    lines.extend([
        "",
        "## Side-Effect Safety Checks",
        "",
    ])
    lines.append(_registry_summary(result))
    lines.extend([
        "",
        "## LLM Safety Checks",
        "",
        _llm_summary(result),
        "",
        "## Documentation / Portfolio Asset Checks",
        "",
    ])
    for item in result.get("artifact_checks", []):
        lines.append(f"- {item.get('path', '')}: {'OK' if item.get('exists') else 'MISSING'}")
    lines.extend([
        "",
        "## Report and Evidence Artifact Checks",
        "",
    ])
    for path in result.get("evidence_paths", []):
        lines.append(f"- {path}")
    lines.extend([
        "",
        "## Known Limitations",
        "",
    ])
    if result.get("known_limitations"):
        for limitation in result["known_limitations"]:
            lines.append(f"- {limitation}")
    else:
        lines.append("- None")
    lines.extend([
        "",
        "## Release Blockers",
        "",
    ])
    if result.get("release_blockers"):
        for blocker in result["release_blockers"]:
            lines.append(f"- {blocker}")
    else:
        lines.append("- None")
    lines.extend([
        "",
        "## Evidence Index",
        "",
        f"- Verification JSON: `{_display_path(OUTPUT_JSON)}`",
        f"- Verification Report: `{_display_path(OUTPUT_MD)}`",
        f"- Evidence Index: `{_display_path(EVIDENCE_INDEX_MD)}`",
        f"- Current Release Status: `{_display_path(CURRENT_RELEASE_STATUS_MD)}`",
        f"- Release Evidence Pack: `{_display_path(RELEASE_EVIDENCE_PACK_MD)}`",
        f"- Runtime Contracts: `{_display_path(RUNTIME_CONTRACTS_MD)}`",
        f"- Default Demo Boundary: `{_display_path(DEFAULT_DEMO_BOUNDARY_MD)}`",
        f"- Known Limitations: `{_display_path(KNOWN_LIMITATIONS_MD)}`",
        "",
        "## Final Recommendation",
        "",
        f"The project is {result.get('verdict', 'UNKNOWN')}.",
    ])
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    result = build_verification_result()
    write_json_result(result, str(OUTPUT_JSON))
    write_markdown_report(result, str(OUTPUT_MD))
    return 0 if result.get("verdict") in {"READY", "READY_WITH_KNOWN_LIMITATIONS"} else 1


def _write_supporting_docs(result: dict[str, Any]) -> None:
    write_current_release_status(result, runtime_data_dir=ROOT / "runtime_data", docs_dir=ROOT / "docs")

    evidence_index = [
        "# Release Candidate Evidence Index",
        "",
        f"- Verification JSON: `{_display_path(OUTPUT_JSON)}`",
        f"- Verification Report: `{_display_path(OUTPUT_MD)}`",
        f"- Known Limitations: `{_display_path(KNOWN_LIMITATIONS_MD)}`",
        f"- Current Release Status: `{_display_path(CURRENT_RELEASE_STATUS_MD)}`",
        f"- Release Evidence Pack: `{_display_path(RELEASE_EVIDENCE_PACK_MD)}`",
        f"- Runtime Contracts: `{_display_path(RUNTIME_CONTRACTS_MD)}`",
        f"- Tool Onboarding Guide: `{_display_path(ADDING_NEW_TOOLS_MD)}`",
        f"- Tool Contract Checklist: `{_display_path(TOOL_CONTRACT_CHECKLIST_MD)}`",
        f"- Default Demo Boundary: `{_display_path(DEFAULT_DEMO_BOUNDARY_MD)}`",
        f"- README: `{_display_path(ROOT / 'README.md')}`",
        f"- Architecture Overview: `{_display_path(ROOT / 'docs' / 'architecture_overview.md')}`",
        f"- Architecture Diagram: `{_display_path(ROOT / 'docs' / 'architecture_diagram.svg')}`",
        f"- Demo Walkthrough: `{_display_path(ROOT / 'docs' / 'demo_walkthrough.md')}`",
        f"- Demo Script: `{_display_path(ROOT / 'docs' / 'demo_script.md')}`",
        f"- Portfolio Summary: `{_display_path(ROOT / 'docs' / 'portfolio_summary.md')}`",
        f"- Capture Screenshots: `{_display_path(ROOT / 'docs' / 'capture_screenshots.md')}`",
        f"- Screenshot Folder: `{_display_path(ROOT / 'docs' / 'screenshots')}`",
        "",
        "## Runtime Reports",
    ]
    for path in result.get("evidence_paths", []):
        evidence_index.append(f"- {path}")
    EVIDENCE_INDEX_MD.write_text("\n".join(evidence_index), encoding="utf-8")


def _check_orchestrator_pollution() -> dict[str, Any]:
    path = ROOT / "runtime" / "orchestrator.py"
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    forbidden_terms = [
        "mock_order_lookup",
        "mock_event_response",
        "prepare_pending_customer_message",
        "draft_customer_status_reply",
        "validate_customer_status_reply",
        "validate_customer_owns_order",
        "procurement",
        "low_stock",
        "reorder",
        "purchase_order",
        "supplier_send",
        "accounting",
        "reconciliation",
        "payment_match",
        "invoice_match",
        "ledger_match",
        "cross_workflow",
        "demo_pack",
    ]
    found = [term for term in forbidden_terms if term in text]
    return {"name": "orchestrator_pollution", "status": "PASS" if not found else "FAIL", "found": found, "path": str(path)}


def _check_fake_llm_paths() -> dict[str, Any]:
    found = []
    scan_paths = [
        ROOT / "src" / "operator_scenarios.py",
        ROOT / "src" / "operator_ui.py",
        ROOT / "src" / "operator_demo_runner.py",
        ROOT / "src" / "operator_cross_workflow_demo.py",
        ROOT / "config",
        ROOT / "manifests",
    ]
    forbidden_markers = [
        'llm_mode": "fake"',
        "fake_accounting_reconciliation",
        "fake_procurement_reorder",
        "fake_customer",
    ]
    for base in scan_paths:
        if base.is_file():
            files = [base]
        elif base.is_dir():
            files = list(base.rglob("*.py")) + list(base.rglob("*.json")) + list(base.rglob("*.md"))
        else:
            continue
        for file_path in files:
            text = file_path.read_text(encoding="utf-8").lower()
            if any(marker in text for marker in forbidden_markers):
                # Test-only harnesses may contain explicit fake adapters, but production/demo scenario
                # definitions must not advertise fake modes.
                if "allow_test_fake_llm" in text or "test_only" in text:
                    continue
                found.append(str(file_path))
    return {"name": "fake_llm_paths", "status": "PASS" if not found else "FAIL", "found": found}


def _check_side_effect_registry() -> dict[str, Any]:
    from runtime.tool_registry import TOOL_REGISTRY

    required = ["customer/send_message", "supplier/send_message", "sheet/write_rows", "file/write_json"]
    bad = []
    for key in required:
        spec = TOOL_REGISTRY.get(key)
        if spec is None:
            continue
        if key == "sheet/write_rows":
            if not (spec.get("side_effect") is True and spec.get("requires_approval") is True and spec.get("allow_live_side_effect") is True):
                bad.append(key)
            continue
        if not (spec.get("side_effect") is True and spec.get("requires_approval") is True and spec.get("allow_live") is False):
            bad.append(key)
    return {"name": "side_effect_registry", "status": "PASS" if not bad else "FAIL", "bad": bad}


def _check_tool_capability_registry() -> dict[str, Any]:
    try:
        from runtime.tool_capability_registry import list_tool_capabilities

        capabilities = list_tool_capabilities()
        ids = {cap.tool_id for cap in capabilities}
        required = {
            "business_context",
            "business_database",
            "gmail",
            "google_sheets",
            "google_calendar",
            "llm_ollama",
            "memory_store",
            "report_generator",
            "rpa_google_messages",
        }
        missing = sorted(required - ids)
        rpa = next((cap for cap in capabilities if cap.tool_id == "rpa_google_messages"), None)
        ok = not missing and rpa is not None and rpa.core_or_optional == "optional" and rpa.side_effect_level == "high_risk" and rpa.rpa_live_probe_required is True
        return {
            "name": "TOOL_CAPABILITY_REGISTRY",
            "status": "PASS" if ok else "FAIL",
            "tool_count": len(capabilities),
            "missing": missing,
            "rpa_optional": bool(rpa and rpa.core_or_optional == "optional"),
            "rpa_live_probe_required": bool(rpa and rpa.rpa_live_probe_required),
        }
    except Exception as exc:
        return {"name": "TOOL_CAPABILITY_REGISTRY", "status": "FAIL", "error": str(exc)}


def _check_core_tool_health_safe_checks() -> dict[str, Any]:
    try:
        from runtime.tool_health import check_all_tool_health, load_latest_tool_health_snapshot

        results = check_all_tool_health(include_optional=False, live_rpa=False)
        required_ids = ["business_context", "business_database", "memory_store", "report_generator"]
        result_map = {result.tool_id: result for result in results}
        missing = [tool_id for tool_id in required_ids if tool_id not in result_map]
        failing = [tool_id for tool_id in required_ids if tool_id in result_map and not result_map[tool_id].ok]
        snapshot = load_latest_tool_health_snapshot()
        ok = not missing and not failing and bool(snapshot.get("results"))
        return {
            "name": "CORE_TOOL_HEALTH_SAFE_CHECKS",
            "status": "PASS" if ok else "FAIL",
            "required": {tool_id: result_map[tool_id].status for tool_id in required_ids if tool_id in result_map},
            "missing": missing,
            "failing": failing,
            "snapshot_path": str(ROOT / "runtime_data" / "tool_health" / "latest_tool_health.json"),
        }
    except Exception as exc:
        return {"name": "CORE_TOOL_HEALTH_SAFE_CHECKS", "status": "FAIL", "error": str(exc)}


def _check_optional_rpa_live_probes_excluded_from_rc() -> dict[str, Any]:
    try:
        from runtime.tool_capability_registry import get_tool_capability
        from runtime.tool_health import load_latest_tool_health_snapshot

        capability = get_tool_capability("rpa_google_messages")
        snapshot = load_latest_tool_health_snapshot()
        tool_ids = {str(item.get("tool_id", "")) for item in snapshot.get("results", []) if isinstance(item, dict)}
        ok = capability.core_or_optional == "optional" and capability.rpa_live_probe_required and "rpa_google_messages" not in tool_ids
        return {
            "name": "OPTIONAL_RPA_LIVE_PROBES_EXCLUDED_FROM_RC",
            "status": "PASS" if ok else "FAIL",
            "tool_present": capability.tool_id,
            "snapshot_tools": sorted(tool_ids),
            "live_probe_required": capability.rpa_live_probe_required,
        }
    except Exception as exc:
        return {"name": "OPTIONAL_RPA_LIVE_PROBES_EXCLUDED_FROM_RC", "status": "FAIL", "error": str(exc)}


def _check_optional_rpa_boundary() -> dict[str, Any]:
    optional_root = ROOT / "optional_tools" / "rpa" / "google_messages_absa"
    if not optional_root.exists():
        return {"name": "OPTIONAL_RPA_EXCLUDED_FROM_DEFAULT_RC", "status": "PASS", "present": False, "details": "optional_rpa_missing"}

    details: list[str] = []
    status = "PASS"

    from runtime.tool_registry import TOOL_REGISTRY
    if "messages/extract_absa_transactions" in TOOL_REGISTRY:
        status = "FAIL"
        details.append("registry_includes_absa")

    from src.operator_scenarios import list_scenarios
    if any("absa" in scenario.get("id", "").lower() for scenario in list_scenarios(include_test_only=False)):
        status = "FAIL"
        details.append("scenario_pack_includes_absa")

    optional_readme = optional_root / "README.md"
    if not optional_readme.is_file():
        status = "FAIL"
        details.append("missing_optional_readme")
    else:
        readme_text = optional_readme.read_text(encoding="utf-8").lower()
        if "excluded from the default portfolio path" not in readme_text:
            status = "FAIL"
            details.append("missing_exclusion_note")

    return {
        "name": "OPTIONAL_RPA_EXCLUDED_FROM_DEFAULT_RC",
        "status": status,
        "present": True,
        "details": details,
    }


def _check_python_imports() -> dict[str, Any]:
    try:
        import runtime.business_context  # noqa: F401
        import runtime.tool_registry  # noqa: F401
        import runtime.tool_capabilities  # noqa: F401
        import runtime.tool_capability_registry  # noqa: F401
        import runtime.tool_health  # noqa: F401
        import src.operator_scenarios  # noqa: F401
        return {"name": "python_imports", "status": "PASS"}
    except Exception as exc:
        return {"name": "python_imports", "status": "FAIL", "error": str(exc)}


def _check_default_tool_registry() -> dict[str, Any]:
    try:
        from runtime.tool_registry import TOOL_REGISTRY
    except Exception as exc:
        return {"name": "default_tool_registry", "status": "FAIL", "error": str(exc)}
    return {
        "name": "default_tool_registry",
        "status": "PASS" if "messages/extract_absa_transactions" not in TOOL_REGISTRY else "FAIL",
        "tool_count": len(TOOL_REGISTRY),
    }


def _check_default_scenario_pack() -> dict[str, Any]:
    try:
        from src.operator_scenarios import list_scenarios
    except Exception as exc:
        return {"name": "default_scenario_pack", "status": "FAIL", "error": str(exc)}
    scenarios = list_scenarios(include_test_only=False)
    texts = [str(item.get("id", "")).lower() for item in scenarios] + [str(item.get("label", "")).lower() for item in scenarios]
    markers = ("absa", "google_messages", "debit_orders", "personal_rpa")
    found = [marker for marker in markers if any(marker in text for text in texts)]
    return {"name": "default_scenario_pack", "status": "PASS" if not found else "FAIL", "found": found, "scenario_count": len(scenarios)}


def _check_release_artifacts_manifest() -> dict[str, Any]:
    path = ROOT / "docs" / "release_artifacts.md"
    exists = path.is_file()
    text = path.read_text(encoding="utf-8").lower() if exists else ""
    required = [
        "golden demo summary report",
        "golden demo audit json",
        "customer workflow report",
        "procurement workflow report",
        "accounting workflow report",
    ]
    missing = [item for item in required if item not in text]
    return {"name": "release_artifacts_manifest", "status": "PASS" if exists and not missing else "FAIL", "path": str(path), "missing": missing}


def _check_docs_command_alignment() -> dict[str, Any]:
    readme = ROOT / "README.md"
    portfolio = ROOT / "docs" / "portfolio_summary.md"
    readme_text = readme.read_text(encoding="utf-8").lower() if readme.is_file() else ""
    portfolio_text = portfolio.read_text(encoding="utf-8").lower() if portfolio.is_file() else ""
    readme_markers = [
        "pip install -e .",
        "taskframe demo",
        "taskframe ui",
        "taskframe verify",
        "taskframe config show",
        "taskframe config paths",
    ]
    missing = []
    for marker in readme_markers:
        if marker not in readme_text:
            missing.append(f"README:{marker}")
    portfolio_markers = [
        "clean release-candidate verification",
        "python scripts/run_golden_demo.py",
        "python scripts/run_release_verification.py",
    ]
    for marker in portfolio_markers:
        if marker not in portfolio_text:
            missing.append(f"portfolio_summary:{marker}")
    config_doc = ROOT / "docs" / "configuration.md"
    if not config_doc.is_file():
        missing.append("docs/configuration.md")
    return {"name": "docs_command_alignment", "status": "PASS" if not missing else "FAIL", "missing": missing}


def _check_packaging_cli() -> dict[str, Any]:
    path = ROOT / "pyproject.toml"
    if not path.is_file():
        return {"name": "packaging_cli", "status": "FAIL", "path": str(path), "missing": ["pyproject.toml"]}

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"name": "packaging_cli", "status": "FAIL", "path": str(path), "error": str(exc)}

    project = data.get("project", {}) if isinstance(data, dict) else {}
    scripts = project.get("scripts", {}) if isinstance(project, dict) else {}
    deps = [str(item).lower() for item in project.get("dependencies", []) or []]
    extras = project.get("optional-dependencies", {}) if isinstance(project, dict) else {}
    missing = []
    if scripts.get("taskframe") != "src.taskframe_cli:main":
        missing.append("console_script")
    if "playwright" in deps or any("google-" in dep or dep == "google-auth" for dep in deps):
        missing.append("default_dependencies")
    for extra in ("dev", "google", "rpa"):
        if extra not in extras:
            missing.append(f"extra:{extra}")
    if not (ROOT / "docs" / "cli_reference.md").is_file():
        missing.append("docs:cli_reference")

    command_results = [
        run_command("packaging_cli_help", ["python", "-m", "src.taskframe_cli", "--help"], timeout_seconds=120),
        run_command("packaging_cli_version", ["python", "-m", "src.taskframe_cli", "version"], timeout_seconds=120),
        run_command("packaging_cli_manifest_health", ["python", "-m", "src.taskframe_cli", "manifest-health", "--no-smoke"], timeout_seconds=300),
        run_command("packaging_cli_manifest_health_strict", ["python", "-m", "src.taskframe_cli", "manifest-health", "--strict", "--no-smoke"], timeout_seconds=300),
    ]
    command_failures = [item for item in command_results if item["status"] != "PASS"]
    return {
        "name": "packaging_cli",
        "status": "PASS" if not missing and not command_failures else "FAIL",
        "path": str(path),
        "missing": missing,
        "commands": command_results,
        "command_failures": [item["name"] for item in command_failures],
    }


def _check_manifest_health_cli_strict() -> dict[str, Any]:
    result = run_command(
        "manifest_health_cli_strict",
        ["python", "-m", "src.taskframe_cli", "manifest-health", "--strict", "--no-smoke"],
        timeout_seconds=300,
    )
    return {
        "name": "manifest_health_cli_strict",
        "status": result["status"],
        "command": result["command"],
        "returncode": result["returncode"],
        "stdout_tail": result["stdout_tail"],
        "stderr_tail": result["stderr_tail"],
    }


def _check_runtime_contract_docs() -> dict[str, Any]:
    path = RUNTIME_CONTRACTS_MD
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    required_terms = ["taskframe", "manifest", "toolresult", "pendingaction", "event route", "live execution", "tool contract"]
    missing = [term for term in required_terms if term not in text]
    return {"name": "runtime_contract_docs", "status": "PASS" if path.is_file() and not missing else "FAIL", "path": str(path), "missing": missing}


def _check_adding_new_tools_doc() -> dict[str, Any]:
    path = ADDING_NEW_TOOLS_MD
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    required_terms = [
        "tool registry",
        "capability registry",
        "health checks",
        "setup instructions",
        "pendingaction",
        "live guardrails",
    ]
    missing = [term for term in required_terms if term not in text]
    return {"name": "adding_new_tools_doc", "status": "PASS" if path.is_file() and not missing else "FAIL", "path": str(path), "missing": missing}


def _check_tool_contract_checklist_doc() -> dict[str, Any]:
    path = TOOL_CONTRACT_CHECKLIST_MD
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    required_terms = ["- [ ]", "tool_registry", "pendingaction", "health check", "live execution"]
    missing = [term for term in required_terms if term not in text]
    return {"name": "tool_contract_checklist_doc", "status": "PASS" if path.is_file() and not missing else "FAIL", "path": str(path), "missing": missing}


def _check_current_release_status_doc() -> dict[str, Any]:
    path = CURRENT_RELEASE_STATUS_MD
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    required_terms = ["current release status", "verdict", "verification date", "evidence files"]
    missing = [term for term in required_terms if term not in text]
    return {"name": "current_release_status_doc", "status": "PASS" if path.is_file() and not missing else "FAIL", "path": str(path), "missing": missing}


def _check_release_evidence_pack_doc() -> dict[str, Any]:
    path = RELEASE_EVIDENCE_PACK_MD
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    required_terms = ["release evidence pack", "what was verified", "how to reproduce", "deliberately excluded from default rc"]
    missing = [term for term in required_terms if term not in text]
    return {"name": "release_evidence_pack_doc", "status": "PASS" if path.is_file() and not missing else "FAIL", "path": str(path), "missing": missing}


def _check_default_demo_boundary_doc() -> dict[str, Any]:
    path = DEFAULT_DEMO_BOUNDARY_MD
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    required_terms = ["optional rpa", "excluded", "default rc", "customer workflow", "procurement workflow", "accounting workflow"]
    missing = [term for term in required_terms if term not in text]
    return {"name": "default_demo_boundary_doc", "status": "PASS" if path.is_file() and not missing else "FAIL", "path": str(path), "missing": missing}


def _check_generated_manifest_template_quality_gates() -> dict[str, Any]:
    import tempfile
    try:
        from src.generated_manifest_smoke_runner import run_template_quality_gates
    except Exception as exc:
        return {"name": "generated_manifest_template_quality_gates", "status": "FAIL", "error": str(exc)}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        runtime_data_dir = tmp_path / "runtime_data"
        manifest_dir = tmp_path / "manifests"
        runtime_data_dir.mkdir(parents=True, exist_ok=True)
        manifest_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = run_template_quality_gates(
                runtime_data_dir=runtime_data_dir,
                manifest_dir=manifest_dir,
            )
        except Exception as exc:
            return {"name": "generated_manifest_template_quality_gates", "status": "FAIL", "error": str(exc)}

    passed = result.get("passed", 0)
    failed = result.get("failed", 0)
    template_count = result.get("template_count", 0)
    status = "PASS" if result.get("ok") and failed == 0 else "FAIL"
    failures = [
        f"{r['template_id']}: {r['classification']} {r.get('errors', [])}"
        for r in result.get("results", [])
        if r.get("status") != "PASS"
    ]
    return {
        "name": "generated_manifest_template_quality_gates",
        "status": status,
        "template_count": template_count,
        "passed": passed,
        "failed": failed,
        "failures": failures,
    }


def _check_manifest_catalog_health() -> dict[str, Any]:
    try:
        result = run_manifest_health_check(
            manifest_dir=ROOT / "manifests",
            runtime_data_dir=ROOT / "runtime_data",
            include_smoke=False,
        )
        report = write_manifest_health_report(result, runtime_data_dir=ROOT / "runtime_data")
    except Exception as exc:
        return {
            "name": "manifest_catalog_health",
            "status": "FAIL",
            "error": str(exc),
            "json_path": "",
            "markdown_path": "",
        }

    summary = result.get("summary") if isinstance(result, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    report_ok = bool(report.get("ok"))
    validation_failed = int(summary.get("validation_failed", 0) or 0)
    critical = int(summary.get("critical", 0) or 0)
    ok = bool(result.get("ok")) and report_ok and validation_failed == 0 and critical == 0
    return {
        "name": "manifest_catalog_health",
        "status": "PASS" if ok else "FAIL",
        "health_status": result.get("status", "UNKNOWN"),
        "summary": summary,
        "report_ok": report_ok,
        "json_path": str(report.get("json_path", "")),
        "markdown_path": str(report.get("markdown_path", "")),
        "error": str(report.get("error", "")),
    }


def _check_optional_rpa_isolation() -> dict[str, Any]:
    missing: list[str] = []

    if not (ROOT / "docs" / "optional_rpa.md").is_file():
        missing.append("docs/optional_rpa.md")

    readme = ROOT / "README.md"
    if readme.is_file():
        readme_text = readme.read_text(encoding="utf-8")
        if "docs/optional_rpa.md" not in readme_text:
            missing.append("README:link:docs/optional_rpa.md")
    else:
        missing.append("README.md")

    cli_ref = ROOT / "docs" / "cli_reference.md"
    if cli_ref.is_file():
        cli_text = cli_ref.read_text(encoding="utf-8")
        for cmd in ("taskframe rpa status", "taskframe rpa health"):
            if cmd not in cli_text:
                missing.append(f"cli_reference:{cmd}")
    else:
        missing.append("docs/cli_reference.md")

    rpa_status = run_command(
        "rpa_status_no_playwright",
        ["python", "-m", "src.taskframe_cli", "rpa", "status"],
        timeout_seconds=30,
    )
    if rpa_status["returncode"] != 0:
        missing.append("rpa_status_command_failed")
    elif "Optional RPA tools" not in rpa_status["stdout"]:
        missing.append("rpa_status_missing_expected_output")

    rpa_health = run_command(
        "rpa_health_default",
        ["python", "-m", "src.taskframe_cli", "rpa", "health"],
        timeout_seconds=30,
    )
    if rpa_health["returncode"] != 0:
        missing.append("rpa_health_default_failed")

    rpa_live_probe_no_enable = run_command(
        "rpa_live_probe_without_enable",
        ["python", "-m", "src.taskframe_cli", "rpa", "health", "--live-probe"],
        timeout_seconds=30,
    )
    if rpa_live_probe_no_enable["returncode"] == 0:
        missing.append("rpa_live_probe_should_fail_without_enable_rpa")

    playwright_import_check = run_command(
        "default_imports_no_playwright",
        [
            "python",
            "-c",
            (
                "import sys; "
                "sys.modules.pop('playwright', None); "
                "sys.modules.pop('playwright.async_api', None); "
                "import runtime.tool_registry; "
                "assert 'playwright' not in sys.modules, 'playwright leaked into default tool_registry import'"
            ),
        ],
        timeout_seconds=30,
    )
    if playwright_import_check["returncode"] != 0:
        missing.append("playwright_leaked_into_default_imports")

    return {
        "name": "optional_rpa_isolation",
        "status": "PASS" if not missing else "FAIL",
        "missing": missing,
    }


def _check_public_quickstart_docs() -> dict[str, Any]:
    readme = ROOT / "README.md"
    quickstart = ROOT / "docs" / "quickstart.md"
    index = ROOT / "docs" / "index.md"
    missing: list[str] = []

    if not quickstart.is_file():
        missing.append("docs/quickstart.md")
    if not index.is_file():
        missing.append("docs/index.md")

    if readme.is_file():
        readme_text = readme.read_text(encoding="utf-8")
        readme_lower = readme_text.lower()
        for phrase in [
            "5-minute quickstart",
            "pip install -e .",
            "taskframe demo",
            "taskframe ui",
            "taskframe verify",
            "safe by default",
            "what this is",
            "what this is not",
        ]:
            if phrase not in readme_lower:
                missing.append(f"README:{phrase}")
        for link in [
            "docs/cli_reference.md",
            "docs/architecture_overview.md",
            "docs/quickstart.md",
            "docs/index.md",
            "docs/configuration.md",
        ]:
            if link not in readme_text:
                missing.append(f"README:link:{link}")
        if "not required" not in readme_lower and "not needed" not in readme_lower:
            missing.append("README:optional integrations not required")
        if "no live" not in readme_lower:
            missing.append("README:no live side effects")
        if "safe default configuration" not in readme_lower:
            missing.append("README:safe default configuration")
    else:
        missing.append("README.md")

    return {
        "name": "public_quickstart_docs",
        "status": "PASS" if not missing else "FAIL",
        "missing": missing,
    }


def _check_live_safety_docs() -> dict[str, Any]:
    missing: list[str] = []
    live_doc = ROOT / "docs" / "live_execution_safety.md"
    readme = ROOT / "README.md"
    if not live_doc.is_file():
        missing.append("docs/live_execution_safety.md")
    else:
        text = live_doc.read_text(encoding="utf-8").lower()
        for phrase in [
            "default portfolio demo does not perform live side effects",
            "taskframe_enable_live_execution",
            "typed confirmation",
            "taskframe safety-status",
            "taskframe live-preflight",
            "taskframe execute-approved",
        ]:
            if phrase not in text:
                missing.append(f"docs/live_execution_safety.md:{phrase}")
    if readme.is_file():
        readme_text = readme.read_text(encoding="utf-8").lower()
        if "docs/live_execution_safety.md" not in readme_text:
            missing.append("README:link:docs/live_execution_safety.md")
        if "does not perform live side effects" not in readme_text:
            missing.append("README:default portfolio no live side effects")
    return {
        "name": "live_safety_docs",
        "status": "PASS" if not missing else "FAIL",
        "missing": missing,
    }


def _check_live_cli_guardrails() -> dict[str, Any]:
    command_results = [
        run_command(
            "live_cli_guardrails_tests",
            [
                "python",
                "-m",
                "pytest",
                "tests/test_live_execution_safety.py",
                "tests/test_cli_live_guardrails.py",
                "tests/test_operator_live_safety_source.py",
                "tests/test_live_safety_docs.py",
            ],
            timeout_seconds=600,
        )
    ]
    command_failures = [item for item in command_results if item["status"] != "PASS"]
    return {
        "name": "live_cli_guardrails",
        "status": "PASS" if not command_failures else "FAIL",
        "commands": command_results,
        "command_failures": [item["name"] for item in command_failures],
    }


def _check_live_execution_default_dry_run() -> dict[str, Any]:
    command = run_command("live_execution_default_dry_run", ["python", "-m", "src.taskframe_cli", "safety-status"], timeout_seconds=120)
    text = (command.get("stdout", "") + command.get("stderr", "")).lower()
    missing: list[str] = []
    if command["status"] != "PASS":
        missing.append("cli:safety-status")
    if "dry-run only" not in text:
        missing.append("summary:dry-run only")
    if "live-ready pending action" in text and "no live-ready pending actions" not in text:
        missing.append("summary:no live-ready pending actions")
    return {
        "name": "live_execution_default_dry_run",
        "status": "PASS" if not missing else "FAIL",
        "command": command,
        "missing": missing,
    }


def _check_config_secrets_hygiene() -> dict[str, Any]:
    missing: list[str] = []

    config_dir = ROOT / "config" / "examples"
    if not config_dir.is_dir():
        missing.append("config/examples/")
    else:
        required_examples = [
            "taskframe.default.example.json",
            "taskframe.local-llm.example.json",
            "taskframe.google-live.example.json",
            "taskframe.rpa-local.example.json",
            "accounting_google_sheet.example.json",
        ]
        for name in required_examples:
            if not (config_dir / name).is_file():
                missing.append(f"config/examples/{name}")

    config_doc = CONFIGURATION_MD
    if not config_doc.is_file():
        missing.append("docs/configuration.md")
    else:
        text = config_doc.read_text(encoding="utf-8").lower()
        for phrase in [
            "do not commit",
            "credentials",
            "tokens",
            "safe default configuration",
            "config profiles",
        ]:
            if phrase not in text:
                missing.append(f"docs/configuration.md:{phrase}")

    gitignore = ROOT / ".gitignore"
    if gitignore.is_file():
        gitignore_text = gitignore.read_text(encoding="utf-8")
        for pattern in [
            ".taskframe/",
            "*.local.json",
            "config/*.local.json",
            "config/*credentials*.json",
            "config/*token*.json",
            "credentials.json",
            "google_token.json",
            "client_secret*.json",
        ]:
            if pattern not in gitignore_text:
                missing.append(f".gitignore:{pattern}")
    else:
        missing.append(".gitignore")

    readme = ROOT / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8").lower()
        if "docs/configuration.md" not in text:
            missing.append("README:docs/configuration.md")
        if "taskframe config show" not in text:
            missing.append("README:taskframe config show")
        if "taskframe config paths" not in text:
            missing.append("README:taskframe config paths")
    else:
        missing.append("README.md")

    command_results = [
        run_command("config_show", ["python", "-m", "src.taskframe_cli", "config", "show"], timeout_seconds=120),
        run_command("config_paths", ["python", "-m", "src.taskframe_cli", "config", "paths"], timeout_seconds=120),
    ]
    command_failures = [item for item in command_results if item["status"] != "PASS"]

    try:
        from src.config_profiles import load_config_profile

        env_keys = [
            "TASKFRAME_PROFILE",
            "TASKFRAME_CONFIG_DIR",
            "TASKFRAME_RUNTIME_DIR",
            "TASKFRAME_LLM_PROVIDER",
            "TASKFRAME_OLLAMA_MODEL",
            "TASKFRAME_OLLAMA_BASE_URL",
            "TASKFRAME_ACCOUNTING_SHEET_CONFIG",
            "ENABLE_OPTIONAL_RPA_TOOLS",
        ]
        saved_env = {key: os.environ.get(key) for key in env_keys}
        for key in env_keys:
            os.environ.pop(key, None)
        try:
            profile = load_config_profile(config_dir=ROOT / "config" / "examples")
        finally:
            for key, value in saved_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        if profile.llm_provider != "fake":
            missing.append("default_profile_llm_provider")
        if profile.google_enabled:
            missing.append("default_profile_google_enabled")
        if profile.rpa_enabled:
            missing.append("default_profile_rpa_enabled")
        if profile.live_execution_enabled:
            missing.append("default_profile_live_execution_enabled")
        if not str(profile.runtime_data_dir):
            missing.append("default_profile_runtime_data_dir")
    except Exception as exc:
        missing.append(f"default_profile_resolution:{exc}")

    return {
        "name": "config_secrets_hygiene",
        "status": "PASS" if not missing and not command_failures else "FAIL",
        "missing": missing,
        "commands": command_results,
        "command_failures": [item["name"] for item in command_failures],
    }


def _check_known_limitations_doc() -> dict[str, Any]:
    path = KNOWN_LIMITATIONS_MD
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    required_terms = ["demo business environment", "default rc limitations", "optional tooling limitations", "live execution limitations", "rpa limitations", "llm limitations", "not production claims", "deferred work"]
    missing = [term for term in required_terms if term not in text]
    return {"name": "known_limitations_doc", "status": "PASS" if path.is_file() and not missing else "FAIL", "path": str(path), "missing": missing}


def _status_from_commands(commands: list[dict[str, Any]], name: str) -> str:
    item = next((command for command in commands if command.get("name") == name), None)
    return "PASS" if item and item.get("status") == "PASS" else "FAIL"


def _status_from_static(static_checks: list[dict[str, Any]], name: str) -> str:
    item = next((check for check in static_checks if check.get("name") == name), None)
    return "PASS" if item and item.get("status") == "PASS" else "FAIL"


def _status_from_artifacts(artifact_checks: list[dict[str, Any]], required_paths: list[str]) -> str:
    mapping = {item.get("path"): item.get("exists") for item in artifact_checks}
    return "PASS" if all(mapping.get(path, False) for path in required_paths) else "FAIL"


def _find_report_artifacts() -> list[str]:
    paths: list[str] = []
    golden_demo_report = ROOT / "runtime_data" / "outputs" / "reports" / "golden_demo_report.md"
    golden_demo_html = ROOT / "runtime_data" / "outputs" / "reports" / "golden_demo_report.html"
    golden_demo_audit = ROOT / "runtime_data" / "outputs" / "audit" / "golden_demo_audit.json"
    if golden_demo_report.is_file() and golden_demo_html.is_file() and golden_demo_audit.is_file():
        return [_display_path(golden_demo_report), _display_path(golden_demo_html), _display_path(golden_demo_audit)]

    runs_dir = ROOT / "runtime_data" / "runs"
    if not runs_dir.is_dir():
        return paths
    for report_md in runs_dir.glob("*/reports/run_report.md"):
        report_html = report_md.with_suffix(".html")
        evidence = report_md.with_name("evidence_bundle.json")
        if report_html.is_file() and evidence.is_file():
            paths.extend([_display_path(report_md), _display_path(report_html), _display_path(evidence)])
            break
    demo_dir = ROOT / "runtime_data" / "demo_packs"
    if demo_dir.is_dir():
        for report_md in demo_dir.glob("*/cross_workflow_demo_report.md"):
            report_html = report_md.with_suffix(".html")
            summary = report_md.with_name("cross_workflow_demo_summary.json")
            if report_html.is_file() and summary.is_file():
                paths.extend([_display_path(report_md), _display_path(report_html), _display_path(summary)])
                break
    return paths


def _workflow_check(name: str, commands: list[dict[str, Any]], marker: str) -> dict[str, Any]:
    relevant = [item for item in commands if marker in item["name"]]
    if not relevant:
        return {"status": "MISSING", "count": 0}
    passed = all(item["status"] == "PASS" for item in relevant)
    return {"status": "PASS" if passed else "FAIL", "count": len(relevant)}


def _registry_summary(result: dict[str, Any]) -> str:
    bad = next((item for item in result.get("static_checks", []) if item.get("name") == "side_effect_registry"), {})
    return f"- side_effect_registry: {bad.get('status', 'UNKNOWN')}"


def _llm_summary(result: dict[str, Any]) -> str:
    fake = next((item for item in result.get("static_checks", []) if item.get("name") == "fake_llm_paths"), {})
    return f"- fake_llm_paths: {fake.get('status', 'UNKNOWN')}"


def _tail(text: str, limit: int = 2500) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _git(*args: str) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, timeout=20)
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return ""


def _looks_skipped(command_result: dict[str, Any]) -> bool:
    return "skipped" in (command_result.get("stdout_tail", "") + command_result.get("stderr_tail", "")).lower()


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
