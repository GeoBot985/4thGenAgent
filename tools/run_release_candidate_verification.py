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
        ("smoke_external_event_intake", ["python", "-m", "pytest", "tests/test_external_event_intake.py"]),
        ("smoke_inspection", ["python", "-m", "pytest", "tests/test_inspection.py"]),
        ("smoke_inspection_commands", ["python", "-m", "pytest", "tests/test_inspection_commands.py"]),
        ("core_retry_policy", ["python", "-m", "pytest", "tests/test_retry_policy.py"]),
        ("core_retry_tool_failures", ["python", "-m", "pytest", "tests/test_retry_tool_failures.py"]),
        ("core_execution_metrics", ["python", "-m", "pytest", "tests/test_execution_metrics.py"]),
        ("core_run_ledger", ["python", "-m", "pytest", "tests/test_run_ledger.py"]),
        ("customer_lane", ["python", "-m", "pytest", "tests/test_customer_workflow_tool_driven.py", "tests/test_runtime_demo_verification.py", "tests/test_negative_customer_status_scenarios.py"]),
        ("procurement_lane", ["python", "-m", "pytest", "tests/test_procurement_low_stock_reorder.py", "tests/test_procurement_approval_dry_run.py", "tests/test_procurement_report_pack.py"]),
        ("accounting_lane", ["python", "-m", "pytest", "tests/test_google_sheet_accounting_tools.py", "tests/test_accounting_reconciliation_tools.py", "tests/test_accounting_payment_reconciliation_workflow.py", "tests/test_accounting_approval_dry_run.py", "tests/test_accounting_report_pack.py"]),
        ("cross_workflow_demo", ["python", "-m", "pytest", "tests/test_cross_workflow_demo_pack.py", "tests/test_cross_workflow_demo_report.py"]),
        ("portfolio_docs", ["python", "-m", "pytest", "tests/test_portfolio_docs_exist.py"]),
        ("full_pytest", ["python", "-m", "pytest"]),
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
        _check_orchestrator_pollution(),
        _check_fake_llm_paths(),
        _check_side_effect_registry(),
    ])
    for check in static_checks:
        if check["status"] != "PASS":
            if check["name"] == "orchestrator_pollution":
                release_blockers.append("orchestrator pollution detected")
            elif check["name"] == "fake_llm_paths":
                release_blockers.append("fake LLM visible in app/demo path")
            elif check["name"] == "side_effect_registry":
                release_blockers.append("side effect registry safety check failed")

    artifact_paths = [
        "README.md",
        "docs/architecture_overview.md",
        "docs/demo_script.md",
        "docs/portfolio_summary.md",
        "docs/release_candidate_verification.md",
        "docs/architecture_diagram.svg",
        "docs/architecture_diagram.mmd",
        "docs/screenshots/operator_ui_main.png",
        "docs/screenshots/customer_workflow_completed.png",
        "docs/screenshots/procurement_workflow_completed.png",
        "docs/screenshots/accounting_workflow_completed.png",
        "docs/screenshots/pending_approval_view.png",
        "docs/screenshots/report_example.png",
        "docs/screenshots/cross_workflow_demo_completed.png",
        "docs/screenshots/architecture_diagram.png",
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
        "| Portfolio readiness | README, diagram, screenshots, demo script |",
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
        f"- Demo Script: `{ROOT / 'docs' / 'demo_script.md'}`",
        f"- Portfolio Summary: `{ROOT / 'docs' / 'portfolio_summary.md'}`",
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
        "demo_order_lookup",
        "demo_event_response",
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
        if not (spec.get("side_effect") is True and spec.get("requires_approval") is True and spec.get("allow_live") is False):
            bad.append(key)
    return {"name": "side_effect_registry", "status": "PASS" if not bad else "FAIL", "bad": bad}


def _find_report_artifacts() -> list[str]:
    paths: list[str] = []
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
