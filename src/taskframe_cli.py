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
from src.live_safety_status import build_live_safety_status
from src.operator_data import build_operator_snapshot
from runtime.live_execution_safety import build_live_execution_preflight, confirmation_phrase, redact_pending_action_args
from runtime.manifest_loader import load_manifest_by_id
from runtime.pending_actions import get_pending_action, list_pending_actions
from runtime.taskframe_reload import load_taskframe
from runtime.tool_health import load_latest_tool_health_snapshot
from runtime.tool_registry import get_tool_spec
from runtime.tool_runner import ToolRunner
from runtime.persistence import persist_frame_update

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

    safety = sub.add_parser("safety-status", help="Show a live execution safety snapshot.")
    safety.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    safety.add_argument("--json", action="store_true")

    pending = sub.add_parser("pending-actions", help="List pending actions and live safety readiness.")
    pending.add_argument("--frame-id", default="")
    pending.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    pending.add_argument("--json", action="store_true")

    preflight = sub.add_parser("live-preflight", help="Run a live execution preflight for one pending action.")
    preflight.add_argument("--frame-id", required=True)
    preflight.add_argument("--action-id", required=True)
    preflight.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    preflight.add_argument("--manifest-dir", default="manifests")
    preflight.add_argument("--json", action="store_true")

    execute = sub.add_parser("execute-approved", help="Execute an approved pending action in dry-run or live mode.")
    execute.add_argument("--frame-id", required=True)
    execute.add_argument("--action-id", required=True)
    execute.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    execute.add_argument("--manifest-dir", default="manifests")
    execute.add_argument("--dry-run", action="store_true")
    execute.add_argument("--live", action="store_true")
    execute.add_argument("--i-understand-live-side-effects", action="store_true")
    execute.add_argument("--confirm", default="")
    execute.add_argument("--json", action="store_true")

    sp = sub.add_parser("safety-pack", help="Build the safety verification pack and live-blocked evidence report.")
    sp.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    sp.add_argument("--manifest-dir", default="manifests")
    sp.add_argument("--no-demo", action="store_true", help="Skip demo runs and use static analysis only.")
    sp.add_argument("--output-dir", default="", help="Override output directory (default: runtime_data/safety_verification).")
    sp.add_argument("--json", action="store_true")

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
    if args.command == "safety-status":
        return _run_safety_status(args)
    if args.command == "pending-actions":
        return _run_pending_actions(args)
    if args.command == "live-preflight":
        return _run_live_preflight(args)
    if args.command == "execute-approved":
        return _run_execute_approved(args)
    if args.command == "safety-pack":
        return _run_safety_pack(args)
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


def _load_frame_for_cli(frame_id: str, runtime_data_dir: str):
    if not str(frame_id or "").strip():
        return None
    try:
        return load_taskframe(frame_id, runtime_data_dir)
    except Exception:
        return None


def _run_safety_status(args: argparse.Namespace) -> int:
    payload = build_live_safety_status(runtime_data_dir=args.runtime_data_dir)
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    else:
        print("Live safety status:")
        print(f"Live execution env enabled: {str(payload.get('live_execution_env_enabled', False)).lower()}")
        print(f"Default mode: {payload.get('default_mode', 'dry_run')}")
        print(f"Optional RPA enabled: {str(payload.get('optional_rpa_enabled', False)).lower()}")
        print(f"Pending action count: {payload.get('pending_action_count', 0)}")
        print(f"Approved pending action count: {payload.get('approved_pending_action_count', 0)}")
        print(f"Live-ready action count: {payload.get('live_ready_action_count', 0)}")
        print(f"Blocked action count: {payload.get('blocked_action_count', 0)}")
        print(f"Tool health snapshot path: {payload.get('tool_health_snapshot_path', '')}")
        print(f"Summary: {payload.get('summary', '')}")
    return 0


def _run_pending_actions(args: argparse.Namespace) -> int:
    if str(args.frame_id or "").strip():
        frame = _load_frame_for_cli(args.frame_id, args.runtime_data_dir)
    else:
        snapshot = build_operator_snapshot(args.runtime_data_dir)
        frame = snapshot.get("active_frame") if isinstance(snapshot, dict) else None
        if not isinstance(frame, dict):
            frame = None
    if frame is None:
        payload = {"frame_id": args.frame_id or "", "ok": True, "pending_actions": [], "summary": "No pending actions."}
    else:
        if isinstance(frame, dict):
            pending_actions = [dict(item) for item in frame.get("pending_actions", []) if isinstance(item, dict)]
        else:
            pending_actions = [dict(item) for item in list_pending_actions(frame)]
        payload = {
            "frame_id": str(frame.get("frame_id", "")) if isinstance(frame, dict) else str(frame.frame_id),
            "manifest_id": str(frame.get("manifest_id", "")) if isinstance(frame, dict) else str(frame.manifest_id),
            "state": str(frame.get("state", "")) if isinstance(frame, dict) else str(frame.state),
            "ok": True,
            "pending_actions": [
                {
                    "action_id": str(item.get("action_id", "")),
                    "tool": str(item.get("tool", "")),
                    "status": str(item.get("status", "")),
                    "output_alias": str(item.get("output_alias", "")),
                    "guardrail": str(item.get("guardrail", "")),
                    "args": redact_pending_action_args(dict(item.get("args", {}) or {})),
                }
                for item in pending_actions
            ],
            "summary": f"{len(pending_actions)} pending action(s).",
        }
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    else:
        print(f"Frame: {payload.get('frame_id', '') or '<none>'}")
        print(f"Pending actions: {len(payload.get('pending_actions', []))}")
        if payload.get("pending_actions"):
            for item in payload["pending_actions"]:
                print(f"- {item.get('action_id', '')} | {item.get('tool', '')} | {item.get('status', '')}")
        else:
            print("No pending actions.")
    return 0


def _run_live_preflight(args: argparse.Namespace) -> int:
    context = _load_live_context(args.frame_id, args.action_id, args.runtime_data_dir, args.manifest_dir)
    if context is None:
        print("LIVE EXECUTION BLOCKED")
        print(f"Frame: {args.frame_id}")
        print(f"Action: {args.action_id}")
        print("Status: LIVE_BLOCKED")
        print("Blockers:")
        print("- frame_not_found: Frame could not be loaded.")
        return 1
    frame, manifest, pending_action, tool_spec, tool_health, runtime_live_mode = context
    preflight = build_live_execution_preflight(
        frame=frame,
        manifest=manifest,
        pending_action=pending_action,
        tool_spec=tool_spec,
        runtime_live_mode=runtime_live_mode,
        tool_health=tool_health,
    )
    payload = dict(preflight)
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    else:
        _print_live_preflight(payload)
    return 0 if preflight.get("ok", False) else 1


def _run_execute_approved(args: argparse.Namespace) -> int:
    context = _load_live_context(args.frame_id, args.action_id, args.runtime_data_dir, args.manifest_dir)
    if context is None:
        print("LIVE EXECUTION BLOCKED")
        print(f"Frame: {args.frame_id}")
        print(f"Action: {args.action_id}")
        print("Status: LIVE_BLOCKED")
        print("Blockers:")
        print("- frame_not_found: Frame could not be loaded.")
        print(f"Safe option: taskframe execute-approved --frame-id {args.frame_id} --action-id {args.action_id} --dry-run")
        return 1

    frame, manifest, pending_action, tool_spec, tool_health, runtime_live_mode = context
    preflight = build_live_execution_preflight(
        frame=frame,
        manifest=manifest,
        pending_action=pending_action,
        tool_spec=tool_spec,
        runtime_live_mode=runtime_live_mode,
        tool_health=tool_health,
    )

    if not bool(args.live):
        result = _run_dry_run_pending_action(frame, pending_action, args.runtime_data_dir)
        if bool(args.json):
            print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
        else:
            _print_execute_result(result, mode="dry-run")
        return 0 if result.get("ok", False) else 1

    confirm_phrase = confirmation_phrase(str(frame.frame_id), str(pending_action.get("action_id", "")))
    if not runtime_live_mode:
        return _print_live_blocked(
            frame,
            pending_action,
            preflight,
            "TASKFRAME_ENABLE_LIVE_EXECUTION is not enabled.",
        )
    if not bool(args.i_understand_live_side_effects):
        return _print_live_blocked(
            frame,
            pending_action,
            preflight,
            "--i-understand-live-side-effects is required.",
        )
    if str(args.confirm or "").strip() != confirm_phrase:
        return _print_live_blocked(
            frame,
            pending_action,
            preflight,
            "Typed confirmation phrase does not match.",
        )
    if preflight.get("status") != "LIVE_READY_REQUIRES_CONFIRMATION":
        return _print_live_blocked(frame, pending_action, preflight, "Preflight did not pass.")

    runner = ToolRunner(dry_run=False)
    result = runner.execute_live_pending_action(frame, manifest, pending_action, runtime_live_mode=True)
    try:
        persist_frame_update(frame, args.runtime_data_dir)
    except Exception:
        pass
    payload = {
        "ok": bool(result.ok),
        "mode": "live",
        "frame_id": str(frame.frame_id),
        "action_id": str(pending_action.get("action_id", "")),
        "tool": str(pending_action.get("tool", "")),
        "status": str(pending_action.get("status", "")),
        "message": str(result.error or result.type or "Live execution completed."),
        "preflight": preflight,
    }
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    else:
        _print_execute_result(payload, mode="live")
    return 0 if result.ok else 1


def _print_live_preflight(payload: dict[str, Any]) -> None:
    print(f"Frame: {payload.get('frame_id', '')}")
    print(f"Action: {payload.get('action_id', '')}")
    print(f"Tool: {payload.get('tool', '')}")
    print(f"Status: {payload.get('status', '')}")
    print(f"Severity: {payload.get('severity', '')}")
    if payload.get("blockers"):
        print("Blockers:")
        for blocker in payload["blockers"]:
            print(f"- {blocker.get('id', '')}: {blocker.get('message', '')}")
    if payload.get("warnings"):
        print("Warnings:")
        for warning in payload["warnings"]:
            print(f"- {warning}")
    guardrail = payload.get("guardrail", {})
    print(f"Guardrail: {guardrail.get('name', '')} | ok={str(guardrail.get('ok', False)).lower()}")
    print(f"Confirmation: {payload.get('confirmation_phrase', '')}")
    print(f"Safe option: {payload.get('safe_default_command', '')}")


def _print_execute_result(payload: dict[str, Any], *, mode: str) -> None:
    print(f"Frame: {payload.get('frame_id', '')}")
    print(f"Action: {payload.get('action_id', '')}")
    print(f"Tool: {payload.get('tool', '')}")
    print(f"Mode: {mode}")
    print(f"Status: {payload.get('status', '')}")
    print(f"Message: {payload.get('message', '')}")
    if payload.get("preflight"):
        print(f"Preflight: {payload['preflight'].get('status', '')}")


def _print_live_blocked(frame: Any, pending_action: dict[str, Any], preflight: dict[str, Any], reason: str) -> int:
    print("LIVE EXECUTION BLOCKED")
    print(f"Frame: {getattr(frame, 'frame_id', '') if frame is not None else ''}")
    print(f"Action: {pending_action.get('action_id', '')}")
    print(f"Tool: {pending_action.get('tool', '')}")
    print(f"Status: {preflight.get('status', 'LIVE_BLOCKED')}")
    print("Blockers:")
    blockers = list(preflight.get("blockers", []))
    if reason:
        blockers.insert(0, {"id": "cli_guardrail", "message": reason, "source": "cli"})
    for blocker in blockers:
        print(f"- {blocker.get('id', '')}: {blocker.get('message', '')}")
    print(f"Safe option: {preflight.get('safe_default_command', '')}")
    return 1


def _run_dry_run_pending_action(frame: Any, pending_action: dict[str, Any], runtime_data_dir: str) -> dict[str, Any]:
    approved = pending_action
    if str(approved.get("status", "")) != "APPROVED":
        return {
            "ok": False,
            "mode": "dry-run",
            "frame_id": getattr(frame, "frame_id", ""),
            "action_id": approved.get("action_id", ""),
            "tool": approved.get("tool", ""),
            "status": approved.get("status", ""),
            "message": f"Pending action must be APPROVED before execution: {approved.get('status', '')}",
        }
    runner = ToolRunner(dry_run=True)
    result = runner.execute_pending_action(frame, approved)
    try:
        persist_frame_update(frame, runtime_data_dir)
    except Exception:
        pass
    return {
        "ok": bool(result.ok),
        "mode": "dry-run",
        "frame_id": getattr(frame, "frame_id", ""),
        "action_id": approved.get("action_id", ""),
        "tool": approved.get("tool", ""),
        "status": approved.get("status", ""),
        "message": str(result.error or result.type or "Dry-run execution completed."),
    }


def _load_live_context(frame_id: str, action_id: str, runtime_data_dir: str, manifest_dir: str) -> tuple[Any, Any, dict[str, Any], dict[str, Any], dict | None, bool] | None:
    try:
        frame = load_taskframe(frame_id, runtime_data_dir)
        pending_action = get_pending_action(frame, action_id)
        manifest = load_manifest_by_id(frame.manifest_id, manifest_dir)
        tool_key = str(pending_action.get("tool", "")).strip()
        tool_spec = _tool_spec_from_key(tool_key)
        tool_health = _resolve_tool_health_snapshot(tool_key)
        runtime_live_mode = _runtime_live_mode_enabled()
        return frame, manifest, pending_action, tool_spec, tool_health, runtime_live_mode
    except Exception:
        return None


def _tool_spec_from_key(tool_key: str) -> dict[str, Any]:
    if not tool_key or "/" not in tool_key:
        return {}
    namespace, action = tool_key.split("/", 1)
    try:
        return get_tool_spec(namespace, action)
    except Exception:
        return {}


def _resolve_tool_health_snapshot(tool_key: str) -> dict | None:
    snapshot = load_latest_tool_health_snapshot()
    if not isinstance(snapshot, dict):
        return None
    by_tool = snapshot.get("by_tool")
    if isinstance(by_tool, dict) and tool_key in by_tool and isinstance(by_tool[tool_key], dict):
        return dict(by_tool[tool_key])
    results = snapshot.get("results", [])
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and str(item.get("tool_id", "")) == tool_key:
                return dict(item)
    return None


def _runtime_live_mode_enabled() -> bool:
    value = os.environ.get("TASKFRAME_ENABLE_LIVE_EXECUTION", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _run_safety_pack(args: argparse.Namespace) -> int:
    from src.safety_verification_pack import (
        build_safety_verification_pack,
        render_safety_verification_markdown,
        write_safety_verification_pack,
    )

    runtime_data_dir = str(args.runtime_data_dir or DEFAULT_RUNTIME_DATA_DIR)
    manifest_dir = str(args.manifest_dir or "manifests")
    run_demo = not bool(getattr(args, "no_demo", False))
    output_dir = str(getattr(args, "output_dir", "") or "").strip()

    try:
        pack = build_safety_verification_pack(
            runtime_data_dir=runtime_data_dir,
            manifest_dir=manifest_dir,
            run_demo=run_demo,
        )
    except Exception as exc:
        print(f"Safety pack: ERROR\nError: {exc}", file=sys.stderr)
        return 1

    if output_dir:
        from pathlib import Path as _Path
        out = _Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_safety_verification_pack(pack, runtime_data_dir=runtime_data_dir)
        except Exception as exc:
            print(f"Safety pack write error: {exc}", file=sys.stderr)
            paths = {}
    else:
        try:
            paths = write_safety_verification_pack(pack, runtime_data_dir=runtime_data_dir)
        except Exception as exc:
            print(f"Safety pack write error: {exc}", file=sys.stderr)
            paths = {}

    if bool(args.json):
        payload = json.dumps(pack, indent=2, ensure_ascii=True, default=str)
        sys.stdout.write(payload + "\n")
        return 0 if pack.get("ok") else 1

    status = str(pack.get("status", "UNKNOWN"))
    summary = pack.get("summary", {}) if isinstance(pack.get("summary"), dict) else {}
    claims_checked = int(summary.get("claims_checked", 0) or 0)
    claims_passed = int(summary.get("claims_passed", 0) or 0)
    claims_failed = int(summary.get("claims_failed", 0) or 0)

    print(f"Safety Verification Pack: {status}")
    print("")
    print(f"Claims checked: {claims_checked}")
    print(f"Claims passed: {claims_passed}")
    print(f"Claims failed: {claims_failed}")

    blockers = pack.get("blockers", []) if isinstance(pack.get("blockers"), list) else []
    if blockers:
        print("")
        print("Blockers:")
        for b in blockers:
            print(f"- {b}")

    evidence_paths = [str(p) for p in (paths.values() if isinstance(paths, dict) else []) if p]
    if evidence_paths:
        print("")
        print("Evidence:")
        for p in evidence_paths:
            print(f"- {p}")

    return 0 if pack.get("ok") else 1


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
