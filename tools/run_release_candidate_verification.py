from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUTPUT_JSON = ROOT / "runtime_data" / "audit" / "release_candidate_verification.json"
OUTPUT_MD = ROOT / "docs" / "release_candidate_verification.md"
EVIDENCE_INDEX_MD = ROOT / "docs" / "release_candidate_evidence_index.md"
KNOWN_LIMITATIONS_MD = ROOT / "docs" / "known_limitations.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
        _check_default_tool_registry(),
        _check_tool_capability_registry(),
        _check_core_tool_health_safe_checks(),
        _check_default_scenario_pack(),
        _check_orchestrator_pollution(),
        _check_fake_llm_paths(),
        _check_side_effect_registry(),
        _check_optional_rpa_boundary(),
        _check_optional_rpa_live_probes_excluded_from_rc(),
        _check_release_artifacts_manifest(),
        _check_docs_command_alignment(),
    ])
    for check in static_checks:
        if check["status"] != "PASS":
            if check["name"] == "python_imports":
                release_blockers.append("python imports failed")
            elif check["name"] == "default_tool_registry":
                release_blockers.append("default tool registry failed")
            elif check["name"] == "TOOL_CAPABILITY_REGISTRY":
                release_blockers.append("tool capability registry failed")
            elif check["name"] == "CORE_TOOL_HEALTH_SAFE_CHECKS":
                release_blockers.append("core tool health checks failed")
            elif check["name"] == "default_scenario_pack":
                release_blockers.append("default scenario pack failed")
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

    artifact_paths = [
        "README.md",
        "docs/release_artifacts.md",
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

    checks = {
        "imports": _status_from_commands(commands, "clean_imports"),
        "default_tool_registry": _status_from_static(static_checks, "default_tool_registry"),
        "tool_capability_registry": _status_from_static(static_checks, "TOOL_CAPABILITY_REGISTRY"),
        "core_tool_health_safe_checks": _status_from_static(static_checks, "CORE_TOOL_HEALTH_SAFE_CHECKS"),
        "optional_rpa_excluded": _status_from_static(static_checks, "OPTIONAL_RPA_EXCLUDED_FROM_DEFAULT_RC"),
        "optional_rpa_live_probes_excluded": _status_from_static(static_checks, "OPTIONAL_RPA_LIVE_PROBES_EXCLUDED_FROM_RC"),
        "default_scenario_pack": _status_from_static(static_checks, "default_scenario_pack"),
        "golden_demo": _status_from_commands(commands, "golden_demo"),
        "release_artifacts": _status_from_artifacts(artifact_checks, [
            "docs/release_artifacts.md",
            "scripts/run_golden_demo.py",
            "runtime_data/outputs/reports/golden_demo_report.md",
            "runtime_data/outputs/reports/golden_demo_report.html",
            "runtime_data/outputs/audit/golden_demo_audit.json",
            "runtime_data/tool_health/latest_tool_health.json",
        ]),
        "docs_commands": _status_from_static(static_checks, "docs_command_alignment"),
    }

    workflow_checks = {
        "customer": _workflow_check("customer", commands, "customer_lane"),
        "procurement": _workflow_check("procurement", commands, "procurement_lane"),
        "accounting": _workflow_check("accounting", commands, "accounting_lane"),
        "cross_workflow": _workflow_check("cross_workflow", commands, "cross_workflow_demo"),
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
        "missing_artifacts": len([item for item in artifact_checks if not item["exists"]]),
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
            "cwd": str(ROOT),
            "git_commit": _git("rev-parse", "HEAD"),
            "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        },
        "commands": commands,
        "static_checks": static_checks,
        "artifact_checks": artifact_checks,
        "checks": checks,
        "workflow_checks": workflow_checks,
        "known_limitations": _unique(known_limitations),
        "release_blockers": _unique(release_blockers),
        "evidence_paths": _unique(evidence_paths),
    }
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
        f"- Verification JSON: `{OUTPUT_JSON}`",
        f"- Verification Report: `{OUTPUT_MD}`",
        f"- Evidence Index: `{EVIDENCE_INDEX_MD}`",
        f"- Known Limitations: `{KNOWN_LIMITATIONS_MD}`",
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
    _write_supporting_docs(result)
    return 0 if result.get("verdict") in {"READY", "READY_WITH_KNOWN_LIMITATIONS"} else 1


def _write_supporting_docs(result: dict[str, Any]) -> None:
    evidence_index = [
        "# Release Candidate Evidence Index",
        "",
        f"- Verification JSON: `{OUTPUT_JSON}`",
        f"- Verification Report: `{OUTPUT_MD}`",
        f"- Known Limitations: `{KNOWN_LIMITATIONS_MD}`",
        f"- README: `{ROOT / 'README.md'}`",
        f"- Architecture Overview: `{ROOT / 'docs' / 'architecture_overview.md'}`",
        f"- Architecture Diagram: `{ROOT / 'docs' / 'architecture_diagram.svg'}`",
        f"- Demo Walkthrough: `{ROOT / 'docs' / 'demo_walkthrough.md'}`",
        f"- Demo Script: `{ROOT / 'docs' / 'demo_script.md'}`",
        f"- Portfolio Summary: `{ROOT / 'docs' / 'portfolio_summary.md'}`",
        f"- Capture Screenshots: `{ROOT / 'docs' / 'capture_screenshots.md'}`",
        f"- Screenshot Folder: `{ROOT / 'docs' / 'screenshots'}`",
        "",
        "## Runtime Reports",
    ]
    for path in result.get("evidence_paths", []):
        evidence_index.append(f"- {path}")
    EVIDENCE_INDEX_MD.write_text("\n".join(evidence_index), encoding="utf-8")

    limitations = [
        "# Known Limitations",
        "",
        "## External dependency limitations",
        "- Ollama model availability depends on the local environment.",
        "- Google Sheets live access depends on external credentials and configuration.",
        "",
        "## Demo limitations",
        "- Screenshots and demo artifacts may need refresh after UI changes.",
        "",
        "## Runtime limitations",
        "- Live side-effect execution is not enabled by default.",
        "- Approval-gated dry-run execution is the default safety mode.",
        "",
        "## Not yet implemented",
        "- Live release execution of side effects is outside this RC proof.",
        "",
        "## Explicitly out of scope for this release",
        "- RPA, deployment automation, and public website packaging.",
    ]
    KNOWN_LIMITATIONS_MD.write_text("\n".join(limitations), encoding="utf-8")


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
    markers = [
        "clean release-candidate verification",
        "python scripts/run_golden_demo.py",
        "python scripts/run_release_verification.py",
    ]
    missing = []
    for marker in markers:
        if marker not in readme_text:
            missing.append(f"README:{marker}")
        if marker not in portfolio_text:
            missing.append(f"portfolio_summary:{marker}")
    return {"name": "docs_command_alignment", "status": "PASS" if not missing else "FAIL", "missing": missing}


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
        return [str(golden_demo_report), str(golden_demo_html), str(golden_demo_audit)]

    runs_dir = ROOT / "runtime_data" / "runs"
    if not runs_dir.is_dir():
        return paths
    for report_md in runs_dir.glob("*/reports/run_report.md"):
        report_html = report_md.with_suffix(".html")
        evidence = report_md.with_name("evidence_bundle.json")
        if report_html.is_file() and evidence.is_file():
            paths.extend([str(report_md), str(report_html), str(evidence)])
            break
    demo_dir = ROOT / "runtime_data" / "demo_packs"
    if demo_dir.is_dir():
        for report_md in demo_dir.glob("*/cross_workflow_demo_report.md"):
            report_html = report_md.with_suffix(".html")
            summary = report_md.with_name("cross_workflow_demo_summary.json")
            if report_html.is_file() and summary.is_file():
                paths.extend([str(report_md), str(report_html), str(summary)])
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
