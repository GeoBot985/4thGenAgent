from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path)


def load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def load_latest_release_verifier(runtime_data_dir: Path) -> dict[str, Any]:
    path = runtime_data_dir / "audit" / "release_candidate_verification.json"
    data = load_json_file(path)
    if data is None:
        raise FileNotFoundError(f"Release verifier output not found: {path}")
    return data


def load_golden_demo_artifacts(runtime_data_dir: Path) -> dict[str, Any]:
    audit_path = runtime_data_dir / "outputs" / "audit" / "golden_demo_audit.json"
    report_path = runtime_data_dir / "outputs" / "reports" / "golden_demo_report.md"
    artifacts: dict[str, Any] = {
        "audit_path": str(audit_path),
        "report_path": str(report_path),
    }
    audit = load_json_file(audit_path)
    if audit:
        artifacts["audit"] = audit
    if report_path.is_file():
        artifacts["report_text"] = report_path.read_text(encoding="utf-8")
    return artifacts


def build_current_release_status_doc(
    verifier: dict[str, Any],
    golden_demo: dict[str, Any],
    runtime_data_dir: Path,
    docs_dir: Path,
) -> str:
    summary = verifier.get("summary", {}) if isinstance(verifier.get("summary"), dict) else {}
    commands = verifier.get("commands", []) if isinstance(verifier.get("commands"), list) else []
    full_pytest = next(
        (
            item
            for item in commands
            if isinstance(item, dict) and item.get("name") in {"bounded_validation_ci", "full_pytest"}
        ),
        {},
    )
    pytest_counts = _extract_pytest_counts(
        str(full_pytest.get("stdout", "")) + str(full_pytest.get("stderr", "")) + str(full_pytest.get("stdout_tail", "")) + str(full_pytest.get("stderr_tail", ""))
    )
    golden_checks = _golden_checks(verifier, golden_demo)
    checks = verifier.get("checks", {}) if isinstance(verifier.get("checks"), dict) else {}
    evidence_paths = _evidence_paths(verifier, runtime_data_dir, docs_dir)

    lines = [
        "# Current Release Status",
        "",
        "## Verdict",
        "",
        f"- {verifier.get('verdict', 'UNKNOWN')}",
        "",
        "## Verification Date",
        "",
        f"- {verifier.get('generated_at', '')}",
        "",
        "## Commands Run",
        "",
        "- bounded validation runner (split pytest subprocesses)",
        "- python scripts/run_golden_demo.py",
        "- python scripts/run_release_verification.py",
        "",
        "## Test Summary",
        "",
        f"- Pytest: {pytest_counts or 'see release verifier output'}",
        f"- Commands Run: {summary.get('command_count', 0)}",
        f"- Passed Commands: {summary.get('passed_commands', 0)}",
        f"- Failed Commands: {summary.get('failed_commands', 0)}",
        f"- Skipped Checks: {summary.get('skipped_checks', 0)}",
        "",
        "## Golden Demo Summary",
        "",
        f"- Customer: {golden_checks.get('customer', 'UNKNOWN')}",
        f"- Procurement: {golden_checks.get('procurement', 'UNKNOWN')}",
        f"- Accounting: {golden_checks.get('accounting', 'UNKNOWN')}",
        f"- Approval gate: {golden_checks.get('approval_gate', 'UNKNOWN')}",
        f"- Report artifacts: {golden_checks.get('report_artifacts', 'UNKNOWN')}",
        "",
        "## Release Verifier Checks",
        "",
        f"- imports: {checks.get('imports', 'UNKNOWN')}",
        f"- default_tool_registry: {checks.get('default_tool_registry', 'UNKNOWN')}",
        f"- optional_rpa_excluded: {checks.get('optional_rpa_excluded', 'UNKNOWN')}",
        f"- default_scenario_pack: {checks.get('default_scenario_pack', 'UNKNOWN')}",
        f"- golden_demo: {checks.get('golden_demo', 'UNKNOWN')}",
        f"- release_artifacts: {checks.get('release_artifacts', 'UNKNOWN')}",
        f"- docs_commands: {checks.get('docs_commands', 'UNKNOWN')}",
        f"- adding_new_tools_doc: {checks.get('adding_new_tools_doc', 'UNKNOWN')}",
        f"- tool_contract_checklist_doc: {checks.get('tool_contract_checklist_doc', 'UNKNOWN')}",
        "",
        "## Known Limitations",
        "",
    ]
    limitations = verifier.get("known_limitations", []) if isinstance(verifier.get("known_limitations"), list) else []
    if limitations:
        for item in limitations:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    lines.extend([
        "",
        "## Evidence Files",
        "",
    ])
    for path in evidence_paths:
        lines.append(f"- {path}")
    return "\n".join(lines)


def build_release_evidence_pack_doc(
    verifier: dict[str, Any],
    golden_demo: dict[str, Any],
    runtime_data_dir: Path,
    docs_dir: Path,
) -> str:
    evidence_paths = _evidence_paths(verifier, runtime_data_dir, docs_dir)
    limiter = verifier.get("known_limitations", []) if isinstance(verifier.get("known_limitations"), list) else []
    golden = golden_demo.get("audit", {}) if isinstance(golden_demo.get("audit"), dict) else {}
    lines = [
        "# Release Evidence Pack",
        "",
        "## What Was Verified",
        "",
        "- The clean-clone release-candidate path",
        "- The default tool registry and tool capability registry",
        "- The tool onboarding guide and tool contract checklist",
        "- The default scenario pack",
        "- The golden demo workflows",
        "- The contract and boundary documentation",
        "- The optional RPA exclusion boundary",
        "",
        "## Where Verifier Outputs Are Stored",
        "",
        f"- Release verifier JSON: `{_display_path(runtime_data_dir / 'audit' / 'release_candidate_verification.json')}`",
        f"- Current release status JSON: `{_display_path(runtime_data_dir / 'audit' / 'release_status_latest.json')}`",
        f"- Release evidence pack JSON: `{_display_path(runtime_data_dir / 'audit' / 'release_evidence_pack.json')}`",
        f"- Release verifier markdown: `{_display_path(docs_dir / 'release_candidate_verification.md')}`",
        f"- Current release status markdown: `{_display_path(docs_dir / 'current_release_status.md')}`",
        f"- Release evidence pack markdown: `{_display_path(docs_dir / 'release_evidence_pack.md')}`",
        "",
        "## Where Golden Demo Outputs Are Stored",
        "",
        f"- Golden demo report: `{_display_path(runtime_data_dir / 'outputs' / 'reports' / 'golden_demo_report.md')}`",
        f"- Golden demo HTML: `{_display_path(runtime_data_dir / 'outputs' / 'reports' / 'golden_demo_report.html')}`",
        f"- Golden demo audit JSON: `{_display_path(runtime_data_dir / 'outputs' / 'audit' / 'golden_demo_audit.json')}`",
        "",
        "## Where Report Artifacts Are Stored",
        "",
        f"- Release artifacts document: `{_display_path(docs_dir / 'release_artifacts.md')}`",
        f"- Runtime contract doc: `{_display_path(docs_dir / 'runtime_contracts.md')}`",
        f"- Tool onboarding guide: `{_display_path(docs_dir / 'adding_new_tools.md')}`",
        f"- Tool contract checklist: `{_display_path(docs_dir / 'tool_contract_checklist.md')}`",
        f"- Default demo boundary doc: `{_display_path(docs_dir / 'default_demo_boundary.md')}`",
        f"- Known limitations doc: `{_display_path(docs_dir / 'known_limitations.md')}`",
        "",
        "## How To Reproduce",
        "",
        "```powershell",
        "python tools/run_bounded_validation.py ci",
        "python scripts/run_golden_demo.py",
        "python scripts/run_release_verification.py",
        "```",
        "",
        "## Deliberately Excluded From Default RC",
        "",
        "- Optional browser-backed RPA tools",
        "- Live WhatsApp/Gmail sending",
        "- Live browser automation",
        "- Unbounded LLM tool choice",
        "- Production credentials",
        "- Real customer and supplier data",
        "",
        "## Notes",
        "",
        f"- Golden demo verdict: {golden.get('verdict', verifier.get('verdict', 'UNKNOWN'))}",
        f"- Known limitations count: {len(limiter)}",
    ]
    return "\n".join(lines)


def write_current_release_status(
    verifier: dict[str, Any] | None = None,
    *,
    runtime_data_dir: str | Path = ROOT / "runtime_data",
    docs_dir: str | Path = ROOT / "docs",
) -> dict[str, Path]:
    runtime_root = Path(runtime_data_dir)
    docs_root = Path(docs_dir)
    runtime_root.mkdir(parents=True, exist_ok=True)
    docs_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "audit").mkdir(parents=True, exist_ok=True)

    verifier_result = verifier or load_latest_release_verifier(runtime_root)
    golden_demo = load_golden_demo_artifacts(runtime_root)

    status_json = build_current_release_status_json(verifier_result, golden_demo, runtime_root, docs_root)
    evidence_json = build_release_evidence_pack_json(verifier_result, golden_demo, runtime_root, docs_root)

    status_json_path = runtime_root / "audit" / "release_status_latest.json"
    evidence_json_path = runtime_root / "audit" / "release_evidence_pack.json"
    status_md_path = docs_root / "current_release_status.md"
    evidence_md_path = docs_root / "release_evidence_pack.md"
    known_limitations_path = docs_root / "known_limitations.md"

    status_json_path.write_text(json.dumps(status_json, indent=2, ensure_ascii=False), encoding="utf-8")
    evidence_json_path.write_text(json.dumps(evidence_json, indent=2, ensure_ascii=False), encoding="utf-8")
    status_md_path.write_text(build_current_release_status_doc(verifier_result, golden_demo, runtime_root, docs_root), encoding="utf-8")
    evidence_md_path.write_text(build_release_evidence_pack_doc(verifier_result, golden_demo, runtime_root, docs_root), encoding="utf-8")
    known_limitations_path.write_text(build_known_limitations_doc(verifier_result), encoding="utf-8")

    return {
        "status_json": status_json_path,
        "evidence_json": evidence_json_path,
        "status_md": status_md_path,
        "evidence_md": evidence_md_path,
        "known_limitations_md": known_limitations_path,
    }


def build_current_release_status_json(
    verifier: dict[str, Any],
    golden_demo: dict[str, Any],
    runtime_data_dir: Path,
    docs_dir: Path,
) -> dict[str, Any]:
    summary = verifier.get("summary", {}) if isinstance(verifier.get("summary"), dict) else {}
    checks = verifier.get("checks", {}) if isinstance(verifier.get("checks"), dict) else {}
    golden_checks = _golden_checks(verifier, golden_demo)
    return {
        "report_type": "current_release_status",
        "generated_at": utc_now(),
        "verification_date": verifier.get("generated_at", ""),
        "verdict": verifier.get("verdict", "UNKNOWN"),
        "commands_run": [
            "pytest",
            "python scripts/run_golden_demo.py",
            "python scripts/run_release_verification.py",
        ],
        "test_summary": {
            "command_count": summary.get("command_count", 0),
            "passed_commands": summary.get("passed_commands", 0),
            "failed_commands": summary.get("failed_commands", 0),
            "skipped_checks": summary.get("skipped_checks", 0),
            "pytest_counts": _extract_pytest_counts(
                _command_output(verifier, "bounded_validation_ci") or _command_output(verifier, "full_pytest")
            ),
        },
        "golden_demo_summary": golden_checks,
        "release_verifier_checks": checks,
        "known_limitations": verifier.get("known_limitations", []),
        "evidence_files": _evidence_paths(verifier, runtime_data_dir, docs_dir),
    }


def build_release_evidence_pack_json(
    verifier: dict[str, Any],
    golden_demo: dict[str, Any],
    runtime_data_dir: Path,
    docs_dir: Path,
) -> dict[str, Any]:
    golden = golden_demo.get("audit", {}) if isinstance(golden_demo.get("audit"), dict) else {}
    return {
        "report_type": "release_evidence_pack",
        "generated_at": utc_now(),
        "verdict": verifier.get("verdict", "UNKNOWN"),
        "verification_date": verifier.get("generated_at", ""),
        "release_verifier_json": _display_path(runtime_data_dir / "audit" / "release_candidate_verification.json"),
        "current_release_status_json": _display_path(runtime_data_dir / "audit" / "release_status_latest.json"),
        "release_evidence_pack_json": _display_path(runtime_data_dir / "audit" / "release_evidence_pack.json"),
        "golden_demo_audit_json": _display_path(runtime_data_dir / "outputs" / "audit" / "golden_demo_audit.json"),
        "golden_demo_report_md": _display_path(runtime_data_dir / "outputs" / "reports" / "golden_demo_report.md"),
        "golden_demo_report_html": _display_path(runtime_data_dir / "outputs" / "reports" / "golden_demo_report.html"),
        "release_docs": {
            "runtime_contracts": _display_path(docs_dir / "runtime_contracts.md"),
            "adding_new_tools": _display_path(docs_dir / "adding_new_tools.md"),
            "tool_contract_checklist": _display_path(docs_dir / "tool_contract_checklist.md"),
            "current_release_status": _display_path(docs_dir / "current_release_status.md"),
            "release_evidence_pack": _display_path(docs_dir / "release_evidence_pack.md"),
            "known_limitations": _display_path(docs_dir / "known_limitations.md"),
            "default_demo_boundary": _display_path(docs_dir / "default_demo_boundary.md"),
        },
        "golden_demo_summary": {
            "verdict": golden.get("verdict", verifier.get("verdict", "UNKNOWN")),
            "workflow_count": golden.get("summary", {}).get("workflow_count", 0) if isinstance(golden.get("summary"), dict) else 0,
            "pass_count": golden.get("summary", {}).get("pass_count", 0) if isinstance(golden.get("summary"), dict) else 0,
            "fail_count": golden.get("summary", {}).get("fail_count", 0) if isinstance(golden.get("summary"), dict) else 0,
        },
        "excluded_from_default_rc": [
            "Optional browser-backed RPA tools",
            "Live WhatsApp/Gmail sending",
            "Live browser automation",
            "Unbounded LLM tool choice",
            "Production credentials",
            "Real customer and supplier data",
        ],
        "evidence_files": _evidence_paths(verifier, runtime_data_dir, docs_dir),
    }


def build_known_limitations_doc(verifier: dict[str, Any]) -> str:
    limitations = verifier.get("known_limitations", []) if isinstance(verifier.get("known_limitations"), list) else []
    if not limitations:
        limitations = ["None recorded by the release verifier."]
    lines = [
        "# Known Limitations",
        "",
        "The RC demonstrates controlled autonomous business automation in a demo business environment.",
        "It is not presented as production-ready for unsupervised live operations.",
        "",
        "## Default RC Limitations",
        "- The clean-clone release-candidate path uses deterministic fixtures and demo data.",
        "- Live side effects stay approval-gated or dry-run only.",
        "",
        "## Optional Tooling Limitations",
        "- Optional browser-backed RPA remains outside the default RC path.",
        "- Optional tooling may depend on local browser state or external authentication.",
        "",
        "## Live Execution Limitations",
        "- Live execution is disabled by default.",
        "- Live execution requires explicit runtime and manifest policy approval.",
        "",
        "## RPA Limitations",
        "- Browser-backed RPA is local-operator-only and not required for clean-clone verification.",
        "",
        "## LLM Limitations",
        "- The LLM is bounded to extraction, classification, summarisation, drafting, comparison, and exception explanation.",
        "",
        "## Not Production Claims",
        "- This release candidate is not a promise of unsupervised production operation.",
        "",
        "## Deferred Work",
        "- Optional live integration profiles.",
        "- Batch and queue orchestration.",
        "- Scheduler UI polish.",
        "- Expanded business scenario packs.",
        "",
        "## Verifier Notes",
    ]
    for item in limitations:
        lines.append(f"- {item}")
    return "\n".join(lines)


def _golden_checks(verifier: dict[str, Any], golden_demo: dict[str, Any]) -> dict[str, str]:
    audit = golden_demo.get("audit", {}) if isinstance(golden_demo.get("audit"), dict) else {}
    checks = audit.get("checks", {}) if isinstance(audit.get("checks"), dict) else {}
    if checks:
        return {
            "customer": str(checks.get("customer", "UNKNOWN")),
            "procurement": str(checks.get("procurement", "UNKNOWN")),
            "accounting": str(checks.get("accounting", "UNKNOWN")),
            "approval_gate": str(checks.get("approval_gate", "UNKNOWN")),
            "report_artifacts": str(checks.get("report_audit", "UNKNOWN")),
        }
    workflow_checks = verifier.get("workflow_checks", {}) if isinstance(verifier.get("workflow_checks"), dict) else {}
    return {
        "customer": str((workflow_checks.get("customer") or {}).get("status", "UNKNOWN")) if isinstance(workflow_checks.get("customer"), dict) else "UNKNOWN",
        "procurement": str((workflow_checks.get("procurement") or {}).get("status", "UNKNOWN")) if isinstance(workflow_checks.get("procurement"), dict) else "UNKNOWN",
        "accounting": str((workflow_checks.get("accounting") or {}).get("status", "UNKNOWN")) if isinstance(workflow_checks.get("accounting"), dict) else "UNKNOWN",
        "approval_gate": "PASS" if verifier.get("checks", {}).get("golden_demo") == "PASS" else "UNKNOWN",
        "report_artifacts": "PASS" if verifier.get("checks", {}).get("release_artifacts") == "PASS" else "UNKNOWN",
    }


def _command_output(verifier: dict[str, Any], name: str) -> str:
    for item in verifier.get("commands", []):
        if isinstance(item, dict) and item.get("name") == name:
            parts: list[str] = []
            for key in ("stdout_log_path", "stderr_log_path"):
                log_path = item.get(key)
                if log_path:
                    path = Path(str(log_path))
                    if path.is_file():
                        try:
                            parts.append(path.read_text(encoding="utf-8"))
                        except Exception:
                            continue
            if parts:
                return "".join(parts)
            return str(item.get("stdout_tail", "")) + str(item.get("stderr_tail", ""))
    return ""


def _extract_pytest_counts(text: str) -> str:
    match = re.search(r"(?P<passed>\d+) passed(?:, (?P<skipped>\d+) skipped)?", text)
    if not match:
        return ""
    passed = match.group("passed")
    skipped = match.group("skipped") or "0"
    return f"{passed} passed, {skipped} skipped"


def _evidence_paths(verifier: dict[str, Any], runtime_data_dir: Path, docs_dir: Path) -> list[str]:
    base_paths = [
        _display_path(runtime_data_dir / "audit" / "release_candidate_verification.json"),
        _display_path(runtime_data_dir / "audit" / "release_status_latest.json"),
        _display_path(runtime_data_dir / "audit" / "release_evidence_pack.json"),
        _display_path(docs_dir / "release_candidate_verification.md"),
        _display_path(docs_dir / "release_candidate_evidence_index.md"),
        _display_path(docs_dir / "current_release_status.md"),
        _display_path(docs_dir / "release_evidence_pack.md"),
        _display_path(docs_dir / "known_limitations.md"),
        _display_path(docs_dir / "adding_new_tools.md"),
        _display_path(docs_dir / "tool_contract_checklist.md"),
    ]
    evidence = list(verifier.get("evidence_paths", [])) if isinstance(verifier.get("evidence_paths"), list) else []
    for path in base_paths:
        if path not in evidence:
            evidence.append(path)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Write current release status and evidence pack from verifier output.")
    parser.add_argument("--runtime-data", default=str(ROOT / "runtime_data"))
    parser.add_argument("--docs-dir", default=str(ROOT / "docs"))
    args = parser.parse_args()
    write_current_release_status(None, runtime_data_dir=args.runtime_data, docs_dir=args.docs_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
