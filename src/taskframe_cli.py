from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from src.config_profiles import (
    copy_profile_example,
    describe_config_profile,
    list_config_lookup_paths,
    load_config_profile,
    resolve_profile_name,
)

VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEMO_SCENARIO = "customer_status_approve_execute_dry_run"
DEFAULT_RUNTIME_DATA_DIR = "runtime_data"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="taskframe",
        description="TaskFrame automation runtime CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="Print the installed TaskFrame runtime version.")

    ui = sub.add_parser("ui", help="Launch the operator UI.")
    ui.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)

    demo = sub.add_parser("demo", help="Run a safe default operator demo scenario.")
    demo.add_argument("--scenario", default=DEFAULT_DEMO_SCENARIO)
    demo.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    demo.add_argument("--reset-dataset", action="store_true")
    demo.add_argument("--report", action="store_true")
    demo.add_argument("--local-llm", action="store_true")
    demo.add_argument("--json", action="store_true")

    sub.add_parser("golden-demo", help="Run the golden demo verification.")

    verify = sub.add_parser("verify", help="Run release verification.")
    verify.add_argument("--full", action="store_true", help="Run the full verification set.")
    verify.add_argument("--quick", action="store_true", help="Placeholder for a future quick verification mode.")

    config = sub.add_parser("config", help="Inspect or initialize configuration profiles.")
    config_sub = config.add_subparsers(dest="config_command", required=True)

    config_show = config_sub.add_parser("show", help="Show the active configuration profile.")
    config_show.add_argument("--profile", default="")
    config_show.add_argument("--config-dir", default="")
    config_show.add_argument("--runtime-data-dir", default="")

    config_paths = config_sub.add_parser("paths", help="Show configuration lookup paths.")
    config_paths.add_argument("--profile", default="")
    config_paths.add_argument("--config-dir", default="")

    config_init = config_sub.add_parser("init", help="Copy an example profile into the user config directory.")
    config_init.add_argument("--profile", default="default")
    config_init.add_argument("--config-dir", default="")
    config_init.add_argument("--force", action="store_true")

    mh = sub.add_parser("manifest-health", help="Run the active manifest catalog health check.")
    mh.add_argument("--manifest-dir", default="manifests")
    mh.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    mh.add_argument("--no-smoke", action="store_true")
    mh.add_argument("--smoke-limit", type=int, default=None)
    mh.add_argument("--strict", action="store_true")
    mh.add_argument("--json", action="store_true")

    rpa = sub.add_parser("rpa", help="Optional RPA tool status, health, and documentation.")
    rpa_sub = rpa.add_subparsers(dest="rpa_command", required=True)

    rpa_sub.add_parser("status", help="Show optional RPA tool status (no live probe).")

    rpa_health = rpa_sub.add_parser("health", help="Check optional RPA tool health.")
    rpa_health.add_argument("--enable-rpa", action="store_true", help="Enable dependency and config checks for optional RPA.")
    rpa_health.add_argument("--live-probe", action="store_true", help="Run a live browser probe (requires --enable-rpa).")

    rpa_sub.add_parser("docs", help="Print path to optional RPA documentation.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(f"taskframe-runtime {VERSION}")
        return 0
    if args.command == "ui":
        return _run_ui(args.runtime_data_dir)
    if args.command == "demo":
        return _run_demo(args)
    if args.command == "golden-demo":
        return _run_golden_demo()
    if args.command == "verify":
        return _run_verify(args)
    if args.command == "config":
        return _run_config(args)
    if args.command == "manifest-health":
        return _run_manifest_health(args)
    if args.command == "rpa":
        return _run_rpa(args)
    parser.print_help()
    return 2


def _run_ui(runtime_data_dir: str) -> int:
    try:
        from src.operator_ui import build_operator_ui

        root = build_operator_ui(runtime_root=runtime_data_dir)
        root.mainloop()
        return 0
    except Exception as exc:
        if _is_tk_failure(exc):
            print("Unable to launch Operator UI. Tkinter may not be available in this Python environment.", file=sys.stderr)
            return 1
        print(f"Unable to launch Operator UI: {exc}", file=sys.stderr)
        return 1


def _run_demo(args: argparse.Namespace) -> int:
    from runtime.llm_adapter import FakeLLMAdapter
    from src.operator_scenario_runner import run_scenario
    from src.operator_scenarios import get_scenario

    scenario_id = str(args.scenario or DEFAULT_DEMO_SCENARIO)
    try:
        scenario = get_scenario(scenario_id)
    except Exception as exc:
        print(f"Scenario: {scenario_id}")
        print(f"State: FAILED")
        print(f"Error: {exc}")
        return 1

    use_local_llm = bool(args.local_llm)
    llm_adapter = None if use_local_llm else FakeLLMAdapter()
    try:
        result = run_scenario(
            scenario_id,
            runtime_data_dir=str(args.runtime_data_dir),
            use_local_llm=use_local_llm,
            reset_dataset=bool(args.reset_dataset),
            generate_report=bool(args.report),
            llm_adapter=llm_adapter,
            allow_test_fake_llm=not use_local_llm,
        )
    except Exception as exc:
        print(f"Scenario: {scenario_id}")
        print("State: FAILED")
        print(f"Error: {exc}")
        if not use_local_llm:
            print("Hint: rerun with --local-llm only if a local Ollama server is available.")
        else:
            print("Hint: rerun without --local-llm for deterministic fake LLM mode.")
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    report_path = _first_non_empty(
        result.get("report_result", {}),
        ("markdown_path", "html_path", "evidence_bundle_path"),
    )
    print(f"Scenario: {scenario_id}")
    print(f"State: {result.get('state', 'UNKNOWN')}")
    print(f"Frame ID: {result.get('frame_id', '')}")
    if report_path:
        print(f"Report: {report_path}")
    else:
        print("Report: not generated")
    if not result.get("ok"):
        error = str(result.get("error", "")).strip()
        if error:
            print(f"Error: {error}")
    return 0 if result.get("ok") else 1


def _run_golden_demo() -> int:
    proc = _run_subprocess([sys.executable, str(ROOT / "scripts" / "run_golden_demo.py")], timeout_seconds=360)
    if proc["returncode"] != 0:
        print("Golden demo: FAILED")
        error = proc["stderr_tail"] or proc["stdout_tail"]
        if error:
            print(f"Error: {error}")
        return 1

    audit_path = ROOT / "runtime_data" / "outputs" / "audit" / "golden_demo_audit.json"
    report_path = ROOT / "runtime_data" / "outputs" / "reports" / "golden_demo_report.md"
    verdict = "READY"
    if audit_path.is_file():
        try:
            payload = json.loads(audit_path.read_text(encoding="utf-8"))
            verdict = str(payload.get("verdict", verdict))
            report_path = Path(str(payload.get("artifacts", {}).get("golden_demo_report_md", report_path)))
        except Exception:
            pass
    print(f"Golden demo: {verdict}")
    print(f"Report: {report_path}")
    print(f"Audit: {audit_path}")
    return 0 if verdict != "FAILED" else 1


def _run_verify(args: argparse.Namespace) -> int:
    if bool(args.quick):
        print("Quick verification is not available yet; running full verification instead.")

    from tools.run_release_candidate_verification import build_verification_result, write_json_result, write_markdown_report

    result = build_verification_result()
    write_json_result(result, str(ROOT / "runtime_data" / "audit" / "release_candidate_verification.json"))
    write_markdown_report(result, str(ROOT / "docs" / "release_candidate_verification.md"))

    verdict = str(result.get("verdict", "FAILED"))
    report_path = ROOT / "docs" / "release_candidate_verification.md"
    json_path = ROOT / "runtime_data" / "audit" / "release_candidate_verification.json"
    print(f"Release verification: {verdict}")
    print(f"Report: {report_path}")
    print(f"JSON: {json_path}")
    return 0 if verdict in {"READY", "READY_WITH_KNOWN_LIMITATIONS"} else 1


def _run_config(args: argparse.Namespace) -> int:
    config_command = str(getattr(args, "config_command", "") or "")
    if config_command == "show":
        profile = load_config_profile(
            resolve_profile_name(args.profile or None),
            config_dir=args.config_dir or None,
            runtime_data_dir=args.runtime_data_dir or None,
        )
        data = describe_config_profile(profile)
        print(f"Profile: {data['profile']}")
        print(f"Config dir: {data['config_dir']}")
        print(f"Runtime data dir: {data['runtime_data_dir']}")
        print(f"LLM provider: {data['llm_provider']}")
        print(f"Google enabled: {str(data['google_enabled']).lower()}")
        print(f"RPA enabled: {str(data['rpa_enabled']).lower()}")
        print(f"Live execution enabled: {str(data['live_execution_enabled']).lower()}")
        return 0

    if config_command == "paths":
        lookup = list_config_lookup_paths(
            resolve_profile_name(args.profile or None),
            config_dir=args.config_dir or None,
        )
        print(f"Explicit config dir: {lookup['explicit_config_dir']}")
        print(f"TASKFRAME_CONFIG_DIR: {lookup['taskframe_config_dir']}")
        print(f"User config dir: {lookup['user_config_dir']}")
        print(f"Repo config examples: {lookup['repo_config_examples']}")
        print(f"Active profile: {lookup['active_profile']}")
        print(f"Active config file: {lookup['active_config_file']}")
        print(f"Runtime data dir: {lookup['runtime_data_dir']}")
        return 0

    if config_command == "init":
        try:
            destination = copy_profile_example(
                resolve_profile_name(args.profile or None),
                force=bool(args.force),
                config_dir=args.config_dir or None,
            )
        except FileExistsError as exc:
            print(str(exc))
            return 1
        except Exception as exc:
            print(f"Unable to initialize config profile: {exc}")
            return 1
        print(f"Created: {destination}")
        print("Next steps:")
        print(f"- Edit {destination}")
        print("- Run 'taskframe config show' to confirm the active profile.")
        return 0

    print("Unknown config command.")
    return 2


def _run_manifest_health(args: argparse.Namespace) -> int:
    from src.manifest_health import run_manifest_health_check, write_manifest_health_report

    result = run_manifest_health_check(
        manifest_dir=args.manifest_dir,
        runtime_data_dir=args.runtime_data_dir,
        include_smoke=not bool(args.no_smoke),
        smoke_limit=args.smoke_limit,
    )
    report = write_manifest_health_report(result, runtime_data_dir=args.runtime_data_dir)
    summary = result.get("summary", {}) if isinstance(result, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    smoke_skipped = int(summary.get("smoke_skipped", 0) or 0)
    payload = {
        "status": result.get("status", "UNKNOWN"),
        "strict": bool(args.strict),
        "summary": {
            "total": summary.get("total", 0),
            "healthy": summary.get("healthy", 0),
            "warnings": summary.get("warnings", 0),
            "failed": summary.get("failed", 0),
        },
        "json_path": report.get("json_path", ""),
        "markdown_path": report.get("markdown_path", ""),
    }

    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    else:
        mode = "strict" if args.strict else "report"
        exit_behavior = (
            "strict mode exits non-zero when failures are found."
            if args.strict
            else "report mode exits 0 even when failures are found."
        )
        print(f"Manifest health: {payload['status']}")
        print(f"Mode: {mode}")
        print(f"Exit behaviour: {exit_behavior}")
        print(f"Total: {payload['summary']['total']}")
        print(f"Healthy: {payload['summary']['healthy']}")
        print(f"Warnings: {payload['summary']['warnings']}")
        print(f"Failed: {payload['summary']['failed']}")
        if smoke_skipped:
            print(f"Smoke skipped: {smoke_skipped}")
        print(f"Report: {payload['markdown_path']}")
        if not args.strict and payload["status"] == "HAS_FAILURES":
            print("Use --strict to fail on manifest catalog errors.")
    if not bool(report.get("ok")):
        return 1
    if bool(args.strict) and int(summary.get("failed", 0) or 0) > 0:
        return 1
    return 0


def _run_rpa(args: argparse.Namespace) -> int:
    rpa_command = str(getattr(args, "rpa_command", "") or "")
    if rpa_command == "status":
        return _run_rpa_status()
    if rpa_command == "health":
        return _run_rpa_health(args)
    if rpa_command == "docs":
        return _run_rpa_docs()
    print("Unknown rpa command.")
    return 2


def _run_rpa_status() -> int:
    playwright_installed = importlib.util.find_spec("playwright") is not None
    rpa_enabled_env = os.environ.get("ENABLE_OPTIONAL_RPA_TOOLS", "").lower() in ("1", "true", "yes")
    profile = os.environ.get("TASKFRAME_PROFILE", "default")

    print("Optional RPA tools: disabled")
    print("Reason: RPA is excluded from the default portfolio path.")
    print(f"Playwright installed: {str(playwright_installed).lower()}")
    print(f"ENABLE_OPTIONAL_RPA_TOOLS: {str(rpa_enabled_env).lower()}")
    print(f"Profile: {profile}")
    print("Live probe: not run")
    print("")
    print("To use optional RPA tools, set ENABLE_OPTIONAL_RPA_TOOLS=true and review docs/optional_rpa.md.")
    return 0


def _run_rpa_health(args: argparse.Namespace) -> int:
    enable_rpa = bool(getattr(args, "enable_rpa", False))
    live_probe = bool(getattr(args, "live_probe", False))

    if live_probe and not enable_rpa:
        print("Error: --live-probe requires --enable-rpa.", file=sys.stderr)
        print("Use: taskframe rpa health --enable-rpa --live-probe", file=sys.stderr)
        print("", file=sys.stderr)
        print("Live browser probes are never run by default. Explicit --enable-rpa is required.", file=sys.stderr)
        return 1

    if not enable_rpa:
        print("Optional RPA health: not run")
        print("RPA is disabled by default.")
        print("Use --enable-rpa to run dependency and config checks.")
        print("Use --live-probe only on a local machine with a prepared browser profile.")
        return 0

    missing: list[str] = []
    details: list[str] = []

    playwright_installed = importlib.util.find_spec("playwright") is not None
    details.append(f"Playwright installed: {str(playwright_installed).lower()}")
    if not playwright_installed:
        missing.append("playwright")

    rpa_package = importlib.util.find_spec("optional_tools") is not None
    details.append(f"Optional RPA package present: {str(rpa_package).lower()}")
    if not rpa_package:
        missing.append("optional_tools")

    profile = os.environ.get("TASKFRAME_PROFILE", "default")
    details.append(f"Config profile: {profile}")
    if profile not in ("rpa-local",):
        details.append("Note: rpa-local profile is recommended for optional RPA tools.")

    print("Optional RPA health: " + ("PASS" if not missing else "MISSING_DEPS"))
    for line in details:
        print(f"  {line}")
    if missing:
        print(f"Missing: {', '.join(missing)}")
        print("Install optional RPA dependencies: pip install -e \".[rpa]\" && playwright install")
    if live_probe:
        print("Live probe: requested but not implemented. Manual browser setup required.")
        print("See docs/optional_rpa.md for live probe requirements.")
    return 0 if not missing else 1


def _run_rpa_docs() -> int:
    doc_path = ROOT / "docs" / "optional_rpa.md"
    print(f"Optional RPA documentation: docs/optional_rpa.md")
    print(f"Full path: {doc_path}")
    print("")
    if doc_path.is_file():
        print("Summary:")
        print("  Optional RPA tools are excluded from the default demo and release path.")
        print("  They require Playwright, a local browser profile, and manual authentication.")
        print("  Do not enable RPA tools against sensitive accounts.")
        print("  See docs/optional_rpa.md for the full guide.")
    else:
        print("Documentation file not found at docs/optional_rpa.md")
    return 0


def _invoke_script_main(script_path: Path) -> dict[str, Any]:
    module_name = f"_taskframe_{script_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        return {"returncode": 1, "stdout_tail": "", "stderr_tail": f"Unable to load script: {script_path}"}
    module = importlib.util.module_from_spec(spec)
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            spec.loader.exec_module(module)
            main_fn = getattr(module, "main", None)
            if not callable(main_fn):
                return {"returncode": 1, "stdout_tail": stdout_buffer.getvalue()[-4000:], "stderr_tail": f"Missing main() in {script_path}"}
            returned = main_fn()
            returncode = int(returned or 0)
    except Exception:
        stderr_buffer.write(traceback.format_exc())
        returncode = 1
    return {
        "returncode": returncode,
        "stdout_tail": stdout_buffer.getvalue()[-4000:],
        "stderr_tail": stderr_buffer.getvalue()[-4000:],
    }


def _run_subprocess(command: list[str], timeout_seconds: int) -> dict[str, Any]:
    import subprocess
    import time

    started = time.time()
    proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout_seconds)
    duration_ms = int((time.time() - started) * 1000)
    return {
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-4000:],
        "duration_ms": duration_ms,
    }


def _first_non_empty(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(data.get(key, "")).strip()
        if value:
            return value
    return ""


def _is_tk_failure(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "tk" in name or "tcl" in name or "no display name" in message or "display" in message and "available" in message


if __name__ == "__main__":
    raise SystemExit(main())
