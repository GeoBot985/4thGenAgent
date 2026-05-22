from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "runtime_data" / "validation"
JSON_REPORT_PATH = REPORT_DIR / "bounded_validation_report.json"
MD_REPORT_PATH = REPORT_DIR / "bounded_validation_report.md"


@dataclass(frozen=True)
class ValidationCommand:
    name: str
    description: str
    paths: tuple[str, ...]
    local_marker: str
    ci_marker: str
    timeout_seconds: int
    modes: tuple[str, ...]
    skipped_label: str | None = None


COMMANDS: tuple[ValidationCommand, ...] = (
    ValidationCommand(
        name="quick",
        description="Fast local sanity checks.",
        paths=(
            "tests/test_test_resource_containment.py",
            "tests/test_dev_test_helper.py",
        ),
        local_marker="unit and not slow and not live and not full_ci",
        ci_marker="unit and not slow and not live and not full_ci",
        timeout_seconds=120,
        modes=("quick", "local", "ci"),
    ),
    ValidationCommand(
        name="backend",
        description="Production backend API tests.",
        paths=("tests/test_production_backend_*.py",),
        local_marker="backend and not slow and not live and not full_ci",
        ci_marker="backend and not live and not full_ci",
        timeout_seconds=180,
        modes=("backend", "local", "ci"),
    ),
    ValidationCommand(
        name="manifest_core",
        description="Manifest contract, health, and smoke tests.",
        paths=(
            "tests/test_manifest_*.py",
            "tests/test_event_router.py",
            "tests/test_event_to_manifest_routing.py",
            "tests/test_external_event_intake.py",
            "tests/test_event_idempotency.py",
            "tests/test_generated_manifest_smoke_runner.py",
            "tests/test_event_source_route_alignment.py",
            "tests/test_event_source_contracts.py",
        ),
        local_marker="manifest and smoke and not slow and not live and not full_ci",
        ci_marker="manifest and smoke and not live and not full_ci",
        timeout_seconds=300,
        modes=("manifest", "local", "ci"),
    ),
    ValidationCommand(
        name="manifest_gallery",
        description="Manifest regression gallery tests.",
        paths=("tests/test_manifest_regression_gallery_*.py",),
        local_marker="gallery and not live and not full_ci",
        ci_marker="gallery and not live and not full_ci",
        timeout_seconds=300,
        modes=("manifest", "local", "ci"),
    ),
    ValidationCommand(
        name="toolpack",
        description="Toolpack contract, lifecycle, and governance tests.",
        paths=(
            "tests/test_toolpack_*.py",
            "tests/test_builtin_toolpack_*.py",
            "tests/test_tool_inventory.py",
            "tests/test_tool_registry_compat.py",
            "tests/test_tool_result_contract.py",
            "tests/test_tool_health.py",
            "tests/test_tool_capabilities.py",
        ),
        local_marker="toolpack and not slow and not live and not full_ci",
        ci_marker="toolpack and not live and not full_ci",
        timeout_seconds=300,
        modes=("toolpack", "local", "ci"),
    ),
    ValidationCommand(
        name="runtime",
        description="TaskFrame runtime and orchestration tests.",
        paths=(
            "tests/test_runtime_*.py",
            "tests/test_taskframe_*.py",
            "tests/test_orchestrator.py",
            "tests/test_event_queue_*.py",
            "tests/test_event_queue.py",
            "tests/test_events.py",
            "tests/test_scheduler.py",
            "tests/test_conditions.py",
            "tests/test_completion_gate.py",
            "tests/test_retry_policy.py",
            "tests/test_retry_tool_failures.py",
            "tests/test_run_ledger.py",
            "tests/test_live_execution_safety.py",
        ),
        local_marker="runtime and not slow and not live and not full_ci",
        ci_marker="runtime and not live and not full_ci",
        timeout_seconds=300,
        modes=("runtime", "local", "ci"),
    ),
    ValidationCommand(
        name="reports",
        description="Run reports, evidence bundles, and portfolio packs.",
        paths=(
            "tests/test_*report*.py",
            "tests/test_*evidence*.py",
            "tests/test_*portfolio*.py",
            "tests/test_pilot_*.py",
            "tests/test_safety_verification*.py",
        ),
        local_marker="reports and not slow and not live and not full_ci",
        ci_marker="reports and not live and not full_ci",
        timeout_seconds=300,
        modes=("reports", "local", "ci"),
    ),
    ValidationCommand(
        name="full_ci",
        description="Tests reserved for full CI or overnight validation.",
        paths=(
            "tests/test_release_*.py",
            "tests/test_release_candidate_*.py",
            "tests/test_release_verifier_*.py",
            "tests/test_safety_verification*.py",
            "tests/test_runtime_engine.py",
            "tests/test_toolpack_manifest_execution.py",
            "tests/test_manifest_regression_gallery_*.py",
            "tests/integration/test_google_workspace_live_reads.py",
        ),
        local_marker="full_ci and not live",
        ci_marker="full_ci and not live",
        timeout_seconds=300,
        modes=("ci",),
    ),
)

MODE_ORDER: dict[str, tuple[str, ...]] = {
    "quick": ("quick",),
    "backend": ("backend",),
    "manifest": ("manifest_core", "manifest_gallery"),
    "toolpack": ("toolpack",),
    "runtime": ("runtime",),
    "reports": ("reports",),
    "local": ("quick", "backend", "manifest_core", "manifest_gallery", "toolpack", "runtime", "reports"),
    "ci": ("quick", "backend", "manifest_core", "manifest_gallery", "toolpack", "runtime", "reports", "full_ci"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded validation groups with marker-filtered pytest subprocesses.")
    parser.add_argument("mode", choices=sorted(MODE_ORDER))
    parser.add_argument("--timeout-scale", type=float, default=1.0, help="Scale all per-group timeouts by this factor.")
    parser.add_argument("--continue-on-failure", action="store_true", help="Run all groups even after a failure.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_bounded_validation(args.mode, timeout_scale=float(args.timeout_scale), continue_on_failure=bool(args.continue_on_failure))
    print(f"Validation report written to: {result['report_paths']['markdown']}")
    return 0 if result.get("ok") else 1


def run_bounded_validation(mode: str, *, timeout_scale: float = 1.0, continue_on_failure: bool = False) -> dict[str, Any]:
    if mode not in MODE_ORDER:
        raise ValueError(f"Unsupported validation mode: {mode}")

    selected = set(MODE_ORDER[mode])
    executed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    started_at = utc_now()

    for command in COMMANDS:
        if command.name not in selected:
            skipped.append(
                {
                    "name": command.name,
                    "description": command.description,
                    "status": "SKIPPED",
                    "marker": command.local_marker if mode in {"quick", "backend", "manifest", "toolpack", "runtime", "reports", "local"} else command.ci_marker,
                    "reason": f"Not scheduled in mode '{mode}'.",
                }
            )
            continue

        group_result = run_group(command, mode=mode, timeout_scale=timeout_scale)
        executed.append(group_result)
        print(f"[{group_result['name']}] {group_result['status']} in {group_result['duration_ms'] / 1000:.2f}s")
        if group_result["status"] == "FAIL" and not continue_on_failure:
            break

    still_skipped = [item for item in skipped if item.get("name") not in {row["name"] for row in executed}]
    ended_at = utc_now()
    report = build_report(mode, started_at, ended_at, executed, still_skipped, timeout_scale)
    write_reports(report)
    return report


def run_group(command: ValidationCommand, *, mode: str, timeout_scale: float) -> dict[str, Any]:
    pytest_marker = command.local_marker if mode in {"quick", "backend", "manifest", "toolpack", "runtime", "reports", "local"} else command.ci_marker
    command_paths = _expand_paths(command.paths)
    pytest_command = [
        sys.executable,
        "-m",
        "pytest",
        *command_paths,
        "-m",
        pytest_marker,
        "-q",
    ]
    timeout_seconds = max(1, int(round(command.timeout_seconds * timeout_scale)))
    started = time.time()
    timed_out = False
    print(f"Running: {_display_command(pytest_command)}")
    try:
        completed = subprocess.run(
            pytest_command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        returncode = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
    duration_ms = int(round((time.time() - started) * 1000))
    status = "PASS" if returncode == 0 else "FAIL"
    if timed_out:
        status = "FAIL"
        stderr = f"{stderr}\n[timeout after {timeout_seconds}s]".strip()
    return {
        "name": command.name,
        "description": command.description,
        "status": status,
        "mode": mode,
        "command": pytest_command,
        "marker": pytest_marker,
        "paths": command_paths,
        "timeout_seconds": timeout_seconds,
        "duration_ms": duration_ms,
        "returncode": returncode,
        "timed_out": timed_out,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }


def build_report(
    mode: str,
    started_at: str,
    ended_at: str,
    executed: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    timeout_scale: float,
) -> dict[str, Any]:
    failures = [item for item in executed if item.get("status") != "PASS"]
    duration_ms = _duration_ms(started_at, ended_at)
    report = {
        "report_type": "bounded_validation",
        "version": 1,
        "mode": mode,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": duration_ms,
        "timeout_scale": timeout_scale,
        "ok": not failures,
        "groups": executed,
        "failed_groups": [item.get("name", "") for item in failures],
        "skipped_groups": skipped,
        "errors": [f"{item['name']} failed" for item in failures],
        "summary": {
            "command_count": len(executed),
            "passed_commands": sum(1 for item in executed if item.get("status") == "PASS"),
            "failed_commands": len(failures),
            "skipped_groups": len(skipped),
        },
        "report_paths": {
            "json": str(JSON_REPORT_PATH),
            "markdown": str(MD_REPORT_PATH),
        },
        "commands": executed,
    }
    return report


def write_reports(report: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_REPORT_PATH.write_text(build_markdown(report), encoding="utf-8")


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Bounded Validation Report",
        "",
        f"- Mode: {report.get('mode', '')}",
        f"- Started at: {report.get('started_at', '')}",
        f"- Ended at: {report.get('ended_at', '')}",
        f"- Duration ms: {report.get('duration_ms', 0)}",
        f"- OK: {report.get('ok', False)}",
        f"- Timeout scale: {report.get('timeout_scale', 1.0)}",
        "",
        "## Summary",
        "",
        f"- Commands run: {report.get('summary', {}).get('command_count', 0)}",
        f"- Passed: {report.get('summary', {}).get('passed_commands', 0)}",
        f"- Failed: {report.get('summary', {}).get('failed_commands', 0)}",
        f"- Skipped: {report.get('summary', {}).get('skipped_groups', 0)}",
        "",
        "## Commands",
        "",
    ]
    for item in report.get("groups", []):
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"### {item.get('name', '')}",
                f"- Status: {item.get('status', '')}",
                f"- Marker: `{item.get('marker', '')}`",
                f"- Timeout: {item.get('timeout_seconds', 0)}s",
                f"- Duration: {item.get('duration_ms', 0)}ms",
                f"- Command: `{_display_command(item.get('command', []))}`",
                "",
            ]
        )
    if report.get("skipped_groups"):
        lines.extend(["## Skipped Groups", ""])
        for item in report.get("skipped_groups", []):
            if not isinstance(item, dict):
                continue
            lines.extend([f"- {item.get('name', '')}: {item.get('reason', '')}"])
        lines.append("")
    if report.get("errors"):
        lines.extend(["## Errors", ""])
        for error in report.get("errors", []):
            lines.append(f"- {error}")
        lines.append("")
    return "\n".join(lines)


def _expand_paths(paths: tuple[str, ...]) -> list[str]:
    resolved: list[str] = []
    for pattern in paths:
        matches = sorted({path.relative_to(ROOT).as_posix() for path in ROOT.glob(pattern)})
        if matches:
            resolved.extend(matches)
        else:
            resolved.append(pattern)
    return resolved


def _display_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def _tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _duration_ms(started_at: str, ended_at: str) -> int:
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        return max(0, int(round((end - start).total_seconds() * 1000)))
    except Exception:
        return 0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
