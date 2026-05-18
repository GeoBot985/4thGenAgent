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
from runtime.live_execution_safety import build_live_execution_preflight, confirmation_phrase, redact_pending_action_args
from runtime.manifest_loader import load_manifest_by_id
from runtime.pending_actions import get_pending_action, list_pending_actions
from runtime.taskframe_reload import load_taskframe
from runtime.tool_health import load_latest_tool_health_snapshot
from runtime.persistence import persist_frame_update
from src.toolpack_loader import (
    build_external_tool_capabilities,
    build_external_tool_registry,
    check_toolpack_health,
    discover_toolpacks,
    get_builtin_toolpack_path,
    load_toolpack_descriptor,
    validate_toolpack_descriptor,
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

    runtime = sub.add_parser("runtime", help="Inspect runtime environment and governance decisions.")
    runtime_sub = runtime.add_subparsers(dest="runtime_command", required=True)

    runtime_profile = runtime_sub.add_parser("profile", help="Show the resolved runtime profile.")
    runtime_profile.add_argument("--json", action="store_true")

    runtime_governance = runtime_sub.add_parser("governance-check", help="Evaluate runtime governance for a tool.")
    runtime_governance.add_argument("tool_key")
    runtime_governance.add_argument("--env", default="", choices=["", "demo", "dev", "test", "release", "live"])
    runtime_governance.add_argument("--dry-run", action="store_true")
    runtime_governance.add_argument("--live-requested", action="store_true")
    runtime_governance.add_argument("--operation", default="execute")
    runtime_governance.add_argument("--json", action="store_true")

    mh = sub.add_parser("manifest-health", help="Run the active manifest catalog health check.")
    mh.add_argument("--manifest-dir", default="manifests")
    mh.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    mh.add_argument("--no-smoke", action="store_true")
    mh.add_argument("--smoke-limit", type=int, default=None)
    mh.add_argument("--strict", action="store_true")
    mh.add_argument("--json", action="store_true")

    manifests = sub.add_parser("manifests", help="Validate manifest contracts.")
    manifests_sub = manifests.add_subparsers(dest="manifests_command", required=True)
    manifests_validate_strict = manifests_sub.add_parser("validate-strict", help="Validate a manifest using the strict contract.")
    manifests_validate_strict.add_argument("manifest_path")
    manifests_validate_strict.add_argument("--manifest-dir", default="manifests")
    manifests_validate_strict.add_argument("--json", action="store_true")

    manifests_gallery = manifests_sub.add_parser("gallery", help="Run the manifest regression gallery.")
    manifests_gallery_sub = manifests_gallery.add_subparsers(dest="gallery_command", required=True)

    gallery_list = manifests_gallery_sub.add_parser("list", help="List gallery fixtures.")
    gallery_list.add_argument("--gallery-dir", default="tests/fixtures/manifest_regression_gallery")
    gallery_list.add_argument("--json", action="store_true")

    gallery_validate = manifests_gallery_sub.add_parser("validate", help="Validate the gallery index and fixtures.")
    gallery_validate.add_argument("--gallery-dir", default="tests/fixtures/manifest_regression_gallery")
    gallery_validate.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    gallery_validate.add_argument("--no-smoke", action="store_true")
    gallery_validate.add_argument("--no-autofix", action="store_true")
    gallery_validate.add_argument("--no-repair-guidance", action="store_true")
    gallery_validate.add_argument("--json", action="store_true")

    gallery_run = manifests_gallery_sub.add_parser("run", help="Run one gallery fixture.")
    gallery_run.add_argument("--fixture", required=True)
    gallery_run.add_argument("--gallery-dir", default="tests/fixtures/manifest_regression_gallery")
    gallery_run.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    gallery_run.add_argument("--no-smoke", action="store_true")
    gallery_run.add_argument("--no-autofix", action="store_true")
    gallery_run.add_argument("--no-repair-guidance", action="store_true")
    gallery_run.add_argument("--json", action="store_true")

    gallery_report = manifests_gallery_sub.add_parser("report", help="Run the gallery and write reports.")
    gallery_report.add_argument("--gallery-dir", default="tests/fixtures/manifest_regression_gallery")
    gallery_report.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    gallery_report.add_argument("--no-smoke", action="store_true")
    gallery_report.add_argument("--no-autofix", action="store_true")
    gallery_report.add_argument("--no-repair-guidance", action="store_true")
    gallery_report.add_argument("--json", action="store_true")

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

    tools = sub.add_parser("tools", help="Discover, inspect, validate, and health-check tool packs.")
    tools_sub = tools.add_subparsers(dest="tools_command", required=True)

    tools_discover = tools_sub.add_parser("discover", help="Discover configured tool packs.")
    tools_discover.add_argument("--config-path", default="config/enabled_toolpacks.json")
    tools_discover.add_argument("--json", action="store_true")

    tools_list = tools_sub.add_parser("list", help="List registered tools, including external tool packs.")
    tools_list.add_argument("--config-path", default="config/enabled_toolpacks.json")
    tools_list.add_argument("--json", action="store_true")

    tools_inspect = tools_sub.add_parser("inspect", help="Inspect a tool or tool pack by id.")
    tools_inspect.add_argument("tool_or_toolpack_id")
    tools_inspect.add_argument("--config-path", default="config/enabled_toolpacks.json")
    tools_inspect.add_argument("--json", action="store_true")

    tools_validate = tools_sub.add_parser("validate", help="Validate a tool pack descriptor.")
    tools_validate.add_argument("toolpack_path")
    tools_validate.add_argument("--json", action="store_true")

    tools_health = tools_sub.add_parser("health", help="Run tool pack health checks.")
    tools_health.add_argument("toolpack_id")
    tools_health.add_argument("--config-path", default="config/enabled_toolpacks.json")
    tools_health.add_argument("--json", action="store_true")

    tools_lifecycle = tools_sub.add_parser("lifecycle", help="Evaluate the lifecycle readiness of a tool pack.")
    tools_lifecycle.add_argument("toolpack_path")
    tools_lifecycle.add_argument("--env", default="dev", choices=["demo", "dev", "test", "release", "live"])
    tools_lifecycle.add_argument("--config-path", default="config/enabled_toolpacks.json")
    tools_lifecycle.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    tools_lifecycle.add_argument("--no-contract", action="store_true")
    tools_lifecycle.add_argument("--no-health", action="store_true")
    tools_lifecycle.add_argument("--no-manifest-smoke", action="store_true")
    tools_lifecycle.add_argument("--write-report", action="store_true")
    tools_lifecycle.add_argument("--json", action="store_true")

    tools_inventory = tools_sub.add_parser("inventory", help="Build the tool inventory report.")
    tools_inventory.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    tools_inventory.add_argument("--json", action="store_true")

    tools_compat = tools_sub.add_parser("compat-check", help="Compare the legacy registry with migrated tool packs.")
    tools_compat.add_argument("--json", action="store_true")

    tools_scaffold = tools_sub.add_parser("scaffold", help="Generate a new tool pack scaffold.")
    tools_scaffold.add_argument("toolpack_id", help="Snake_case tool pack identifier.")
    tools_scaffold.add_argument("--namespace", default="", help="Tool namespace (defaults to toolpack_id).")
    tools_scaffold.add_argument("--tool", default="", help="Tool action name (defaults to 'run').")
    tools_scaffold.add_argument("--safe-read", action="store_true", help="Generate a safe read-only tool (default).")
    tools_scaffold.add_argument("--side-effect", action="store_true", help="Generate a side-effect tool (requires approval).")
    tools_scaffold.add_argument("--output-dir", default="tool_packs", help="Output directory for scaffold.")
    tools_scaffold.add_argument("--force", action="store_true", help="Overwrite existing scaffold.")
    tools_scaffold.add_argument("--json", action="store_true")

    tools_test = tools_sub.add_parser("test", help="Run contract tests for a tool pack.")
    tools_test.add_argument("toolpack_path", help="Path to toolpack.json.")
    tools_test.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    tools_test.add_argument("--no-manifest-smoke", action="store_true", help="Skip example manifest smoke runs.")
    tools_test.add_argument("--json", action="store_true")

    tools_examples = tools_sub.add_parser("examples", help="Print example manifest steps for a tool pack.")
    tools_examples.add_argument("toolpack_path", help="Path to toolpack.json.")
    tools_examples.add_argument("--json", action="store_true")

    tools_policy = tools_sub.add_parser("policy", help="Show governance policy for a tool pack or all packs.")
    tools_policy.add_argument("toolpack_id", nargs="?", default="", help="Tool pack ID (omit for all).")
    tools_policy.add_argument("--json", action="store_true")

    tools_enable = tools_sub.add_parser("enable", help="Enable a tool pack in one or more environments.")
    tools_enable.add_argument("toolpack_id", help="Tool pack ID to enable.")
    tools_enable.add_argument("--classification", required=True, choices=["core", "optional", "experimental", "high_risk", "blocked"], help="Governance classification.")
    tools_enable.add_argument("--env", default="dev,test", help="Comma-separated environments (demo,dev,test,release,live).")
    tools_enable.add_argument("--by", default="operator", help="Who is enabling this pack.")
    tools_enable.add_argument("--reason", default="", help="Reason for enablement.")
    tools_enable.add_argument("--json", action="store_true")

    tools_disable = tools_sub.add_parser("disable", help="Disable a tool pack in one or more environments.")
    tools_disable.add_argument("toolpack_id", help="Tool pack ID to disable.")
    tools_disable.add_argument("--env", default="", help="Comma-separated environments to disable (omit for all).")
    tools_disable.add_argument("--by", default="operator", help="Who is disabling this pack.")
    tools_disable.add_argument("--reason", default="", help="Reason for disabling.")
    tools_disable.add_argument("--json", action="store_true")

    tools_gov_report = tools_sub.add_parser("governance-report", help="Generate a tool pack governance report.")
    tools_gov_report.add_argument("--json", action="store_true")

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
    if args.command == "runtime":
        return _run_runtime(args)
    if args.command == "manifest-health":
        return _run_manifest_health(args)
    if args.command == "manifests":
        return _run_manifest_commands(args)
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
    if args.command == "tools":
        return _run_tools(args)
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


def _run_runtime(args: argparse.Namespace) -> int:
    command = str(getattr(args, "runtime_command", "") or "")
    if command == "profile":
        return _run_runtime_profile(args)
    if command == "governance-check":
        return _run_runtime_governance_check(args)
    print("Unknown runtime command.")
    return 2


def _run_runtime_profile(args: argparse.Namespace) -> int:
    from runtime.runtime_environment import load_runtime_profile, resolve_runtime_environment

    profile = load_runtime_profile()
    environment = resolve_runtime_environment()
    payload = {
        "ok": True,
        "environment": environment,
        "governance_enforced": bool(profile.get("governance_enforced", True)),
        "allow_unknown_toolpack_in_dev": bool(profile.get("allow_unknown_toolpack_in_dev", False)),
        "allow_high_risk_live_override": bool(profile.get("allow_high_risk_live_override", False)),
        "profile_path": str((ROOT / "config" / "runtime_profile.json").resolve()),
    }
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        return 0
    print(f"Runtime environment: {payload['environment']}")
    print(f"Governance enforced: {str(payload['governance_enforced']).lower()}")
    print(f"Allow unknown toolpack in dev: {str(payload['allow_unknown_toolpack_in_dev']).lower()}")
    print(f"Allow high-risk live override: {str(payload['allow_high_risk_live_override']).lower()}")
    return 0


def _run_runtime_governance_check(args: argparse.Namespace) -> int:
    from runtime.tool_governance import evaluate_tool_governance
    from runtime.tool_registry import ToolNotRegisteredError, get_tool_spec
    from src.toolpack_loader import load_toolpack_descriptor, validate_toolpack_descriptor

    tool_key = str(args.tool_key).strip()
    if "/" not in tool_key:
        payload = {
            "ok": False,
            "decision": "BLOCK",
            "tool": tool_key,
            "environment": "demo",
            "reason": "Tool key must be in namespace/action form.",
        }
        if bool(args.json):
            print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        else:
            print(f"Tool: {tool_key}")
            print("Decision: BLOCK")
            print("Reason: Tool key must be in namespace/action form.")
        return 1
    namespace, action = tool_key.split("/", 1)
    environment = str(args.env or "").strip() or "demo"
    try:
        tool_spec = get_tool_spec(namespace, action)
    except ToolNotRegisteredError:
        tool_spec = _resolve_tool_spec_for_runtime_governance(tool_key)
    decision = evaluate_tool_governance(
        tool_key,
        tool_spec,
        environment=environment,
        dry_run=bool(args.dry_run),
        live_requested=bool(args.live_requested),
        operation=str(args.operation or "execute"),
    )
    if bool(args.json):
        print(json.dumps(decision, separators=(",", ":"), ensure_ascii=False))
        return 0 if decision.get("ok", False) else 1
    print(f"Tool: {decision['tool']}")
    print(f"Environment: {decision['environment']}")
    print(f"Decision: {decision['decision']}")
    print(f"Reason: {decision['reason']}")
    return 0 if decision.get("ok", False) else 1


def _resolve_tool_spec_for_runtime_governance(tool_key: str) -> dict[str, object]:
    namespace, action = tool_key.split("/", 1)
    toolpacks_root = ROOT / "tool_packs"
    for descriptor_path in sorted(toolpacks_root.glob("*/toolpack.json")):
        try:
            descriptor = load_toolpack_descriptor(descriptor_path)
            validation = validate_toolpack_descriptor(descriptor, base_path=descriptor_path.parent)
            for tool in validation.get("descriptor", {}).get("tools", []):
                if str(tool.get("tool", "")) == tool_key:
                    return {
                        "namespace": tool.get("namespace", namespace),
                        "action": tool.get("action", action),
                        "module": tool.get("module", ""),
                        "function": tool.get("function", ""),
                        "side_effect": bool(tool.get("side_effect", False)),
                        "requires_approval": bool(tool.get("requires_approval", False)),
                        "allow_live": bool(tool.get("allow_live", False)),
                        "allow_live_side_effect": bool(tool.get("allow_live_side_effect", False)),
                        "live_guardrail": str(tool.get("live_guardrail", "blocked")),
                        "output_type": str(tool.get("output_type", "")),
                        "required_args": list(tool.get("required_args", [])),
                        "optional_args": list(tool.get("optional_args", [])),
                        "arg_types": dict(tool.get("arg_types", {})),
                        "dry_run_executes": bool(tool.get("dry_run_executes", False)),
                        "source": "external_toolpack",
                        "toolpack_id": str(validation.get("toolpack_id", descriptor.get("toolpack_id", namespace))),
                        "toolpack_name": str(validation.get("descriptor", {}).get("name", descriptor.get("name", ""))),
                        "toolpack_version": str(validation.get("descriptor", {}).get("version", descriptor.get("version", ""))),
                        "toolpack_path": str(descriptor_path),
                        "toolpack_core_or_optional": str(validation.get("descriptor", {}).get("core_or_optional", "optional")),
                        "toolpack_classification": str(validation.get("descriptor", {}).get("risk_class", validation.get("descriptor", {}).get("core_or_optional", "optional"))),
                        "enabled_environments": list((validation.get("descriptor", {}) or {}).get("governance", {}).get("enabled_environments", []))
                        if isinstance((validation.get("descriptor", {}) or {}).get("governance", {}), dict)
                        else [],
                        "governance_required": True,
                    }
        except Exception:
            continue
    return {
        "namespace": namespace,
        "action": action,
        "module": "",
        "function": "",
        "side_effect": False,
        "requires_approval": False,
        "allow_live": False,
        "allow_live_side_effect": False,
        "live_guardrail": "blocked",
        "output_type": "tool_governance_blocked",
        "required_args": [],
        "optional_args": [],
        "arg_types": {},
        "dry_run_executes": False,
        "source": "external_toolpack",
        "toolpack_id": namespace,
        "toolpack_name": namespace,
        "toolpack_version": "",
        "toolpack_path": "",
        "toolpack_core_or_optional": "unknown",
        "toolpack_classification": "unknown",
        "enabled_environments": [],
        "governance_required": True,
    }


def _run_manifest_health(args: argparse.Namespace) -> int:
    from src.manifest_health import run_manifest_health_check, write_manifest_health_report

    result = run_manifest_health_check(
        manifest_dir=args.manifest_dir,
        runtime_data_dir=args.runtime_data_dir,
        include_smoke=not bool(args.no_smoke),
        smoke_limit=args.smoke_limit,
        strict_contract=bool(args.strict),
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
            "strict_failed": summary.get("strict_failed", 0),
            "strict_warnings": summary.get("strict_warnings", 0),
        },
        "strict_contract": bool(args.strict),
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
        if bool(args.strict):
            print(f"Strict failed: {payload['summary']['strict_failed']}")
            print(f"Strict warnings: {payload['summary']['strict_warnings']}")
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


def _run_manifest_commands(args: argparse.Namespace) -> int:
    if getattr(args, "manifests_command", "") == "validate-strict":
        return _run_manifest_validate_strict(args)
    if getattr(args, "manifests_command", "") == "gallery":
        return _run_manifest_gallery(args)
    return 2


def _run_manifest_validate_strict(args: argparse.Namespace) -> int:
    from src.manifest_contract_strict import validate_manifest_strict

    manifest_path = Path(args.manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        payload = {"ok": False, "status": "FAIL", "manifest_id": "", "errors": [str(exc)], "warnings": [], "findings": []}
    else:
        event_routes = _load_json_file(ROOT / "config" / "event_routes.json")
        tool_registry = None
        try:
            from runtime.tool_registry import build_tool_registry

            tool_registry = build_tool_registry(include_external=True, config_path="config/enabled_toolpacks.json")
        except Exception:
            tool_registry = None
        payload = validate_manifest_strict(
            manifest if isinstance(manifest, dict) else {},
            manifest_path=str(manifest_path),
            active_catalog=True,
            event_routes=event_routes,
            tool_registry=tool_registry,
        )

    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    else:
        print(f"Manifest strict validation: {payload.get('status', 'UNKNOWN')}")
        print(f"Manifest: {manifest_path}")
        if payload.get("warnings"):
            print(f"Warnings: {len(payload.get('warnings', []))}")
    if payload.get("errors"):
        print(f"Errors: {len(payload.get('errors', []))}")
    return 0 if payload.get("ok", False) else 1


def _run_manifest_gallery(args: argparse.Namespace) -> int:
    from src.manifest_regression_gallery import (
        iter_gallery_fixtures,
        run_gallery,
        run_gallery_fixture,
        validate_gallery_index,
        write_gallery_report,
    )

    gallery_dir = str(getattr(args, "gallery_dir", "tests/fixtures/manifest_regression_gallery") or "tests/fixtures/manifest_regression_gallery")
    runtime_data_dir = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    no_smoke = bool(getattr(args, "no_smoke", False))
    no_autofix = bool(getattr(args, "no_autofix", False))
    no_repair = bool(getattr(args, "no_repair_guidance", False))
    command = getattr(args, "gallery_command", "")

    if command == "list":
        fixtures = iter_gallery_fixtures(gallery_dir)
        payload = {"ok": True, "gallery_dir": gallery_dir, "fixtures": fixtures}
        if bool(getattr(args, "json", False)):
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"Manifest regression gallery: {gallery_dir}")
            for fixture in fixtures:
                print(f"- {fixture.get('id', '')} ({fixture.get('category', '')})")
        return 0

    if command == "validate":
        result = run_gallery(
            gallery_dir=gallery_dir,
            runtime_data_dir=runtime_data_dir,
            strict=True,
            smoke=not no_smoke,
            repair_guidance=not no_repair,
            autofix=not no_autofix,
        )
        if bool(getattr(args, "json", False)):
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Manifest regression gallery: {gallery_dir}")
            print(f"Status: {result.get('status')}")
            print(f"Passed: {result.get('passed', 0)}")
            print(f"Failed: {result.get('failed', 0)}")
        return 0 if result.get("ok") else 1

    if command == "run":
        try:
            result = run_gallery_fixture(
                str(getattr(args, "fixture", "") or ""),
                gallery_dir=gallery_dir,
                runtime_data_dir=runtime_data_dir,
                strict=True,
                smoke=not no_smoke,
                repair_guidance=not no_repair,
                autofix=not no_autofix,
            )
        except KeyError as exc:
            print(str(exc))
            return 2
        if bool(getattr(args, "json", False)):
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Fixture: {result.get('fixture_id', '')}")
            print(f"Status: {'PASS' if result.get('matched_expectations') else 'FAIL'}")
            print(f"Strict: {result.get('actual', {}).get('strict_status', '')}")
            print(f"Smoke: {result.get('actual', {}).get('smoke_classification', '') or 'SKIPPED'}")
            print(f"Autofix: {result.get('actual', {}).get('autofix', '')}")
            if result.get("errors"):
                print("Errors:")
                for err in result["errors"]:
                    print(f"- {err}")
        return 0 if result.get("matched_expectations") else 1

    if command == "report":
        result = run_gallery(
            gallery_dir=gallery_dir,
            runtime_data_dir=runtime_data_dir,
            strict=True,
            smoke=not no_smoke,
            repair_guidance=not no_repair,
            autofix=not no_autofix,
        )
        report = write_gallery_report(result, runtime_data_dir=runtime_data_dir)
        if bool(getattr(args, "json", False)):
            payload = dict(result)
            payload["report"] = report
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"Manifest regression gallery: {gallery_dir}")
            print(f"Status: {result.get('status')}")
            print(f"Report JSON: {report.get('json_path', '')}")
            print(f"Report MD: {report.get('markdown_path', '')}")
        return 0 if result.get("ok") and report.get("ok") else 1

    index = validate_gallery_index(gallery_dir)
    print(json.dumps(index, indent=2, ensure_ascii=False) if bool(getattr(args, "json", False)) else f"Unknown gallery command: {command}")
    return 0 if index.get("ok") else 1


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _load_frame_for_cli(frame_id: str, runtime_data_dir: str):
    if not str(frame_id or "").strip():
        return None
    try:
        return load_taskframe(frame_id, runtime_data_dir)
    except Exception:
        return None


def _run_safety_status(args: argparse.Namespace) -> int:
    from src.live_safety_status import build_live_safety_status

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
    from src.operator_data import build_operator_snapshot

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
    from runtime.tool_runner import ToolRunner

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
    from runtime.tool_runner import ToolRunner

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
        from runtime.tool_registry import get_tool_spec

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


def _run_tools(args: argparse.Namespace) -> int:
    command = str(getattr(args, "tools_command", "") or "")
    if command == "discover":
        return _run_tools_discover(args)
    if command == "list":
        return _run_tools_list(args)
    if command == "inspect":
        return _run_tools_inspect(args)
    if command == "validate":
        return _run_tools_validate(args)
    if command == "health":
        return _run_tools_health(args)
    if command == "lifecycle":
        return _run_tools_lifecycle(args)
    if command == "inventory":
        return _run_tools_inventory(args)
    if command == "compat-check":
        return _run_tools_compat_check(args)
    if command == "scaffold":
        return _run_tools_scaffold(args)
    if command == "test":
        return _run_tools_test(args)
    if command == "examples":
        return _run_tools_examples(args)
    if command == "policy":
        return _run_tools_policy(args)
    if command == "enable":
        return _run_tools_enable(args)
    if command == "disable":
        return _run_tools_disable(args)
    if command == "governance-report":
        return _run_tools_governance_report(args)
    print("Unknown tools command.")
    return 2


def _run_tools_discover(args: argparse.Namespace) -> int:
    payload = discover_toolpacks(config_path=args.config_path, include_disabled=True)
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        return 0
    print("Tool pack discovery:")
    print(f"Enabled count: {payload.get('enabled_count', 0)}")
    print(f"Disabled count: {payload.get('disabled_count', 0)}")
    print(f"Registered external tools: {payload.get('registered_tool_count', 0)}")
    for item in payload.get("toolpacks", []):
        print(
            f"- {item.get('toolpack_id', '')} | enabled={str(item.get('enabled', False)).lower()} | "
            f"registered={str(item.get('registered', False)).lower()} | valid={str(item.get('valid', False)).lower()} | "
            f"tools={item.get('tool_count', 0)} | path={item.get('path', '')}"
        )
    return 0


def _run_tools_list(args: argparse.Namespace) -> int:
    from runtime.tool_registry import build_tool_registry

    registry = build_tool_registry(include_external=True, config_path=args.config_path)
    discovery = discover_toolpacks(config_path=args.config_path, include_disabled=True)
    discovered_toolpacks = [
        {
            "toolpack_id": str(item.get("toolpack_id", "")),
            "name": str(item.get("name", item.get("toolpack_id", ""))),
            "path": str(item.get("path", "")),
            "enabled": bool(item.get("enabled", False)),
            "registered": bool(item.get("registered", False)),
            "valid": bool(item.get("valid", False)),
            "tool_count": int(item.get("tool_count", 0) or 0),
            "source": "external_toolpack",
        }
        for item in discovery.get("toolpacks", [])
    ]
    payload = {
        "ok": True,
        "tool_count": len(registry),
        "tools": [
            {
                "tool": tool_key,
                **dict(spec),
            }
            for tool_key, spec in sorted(registry.items())
        ],
        "toolpacks": discovered_toolpacks,
    }
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        return 0
    print("Registered tools:")
    for item in payload["tools"]:
        source = str(item.get("source", "builtin"))
        print(f"- {item['tool']} | source={source} | module={item.get('module', '')} | function={item.get('function', '')}")
    if payload["toolpacks"]:
        print("")
        print("Discovered tool packs:")
        for pack in payload["toolpacks"]:
            print(
                f"- {pack['toolpack_id']} | enabled={str(pack['enabled']).lower()} | "
                f"registered={str(pack['registered']).lower()} | valid={str(pack['valid']).lower()} | "
                f"tools={pack['tool_count']} | path={pack['path']}"
            )
    return 0


def _run_tools_inspect(args: argparse.Namespace) -> int:
    target = str(args.tool_or_toolpack_id or "").strip()
    if target.startswith("toolpack:"):
        payload = _inspect_toolpack(target.removeprefix("toolpack:"), config_path=args.config_path)
    elif "/" in target:
        payload = _inspect_tool(target, config_path=args.config_path)
    else:
        payload = _inspect_toolpack(target, config_path=args.config_path)
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        return 0 if payload.get("ok", True) else 1
    print(f"Target: {target}")
    print(f"Status: {payload.get('status', '')}")
    if payload.get("name"):
        print(f"Name: {payload.get('name', '')}")
    if payload.get("description"):
        print(f"Description: {payload.get('description', '')}")
    if payload.get("path"):
        print(f"Path: {payload.get('path', '')}")
    if payload.get("tool"):
        print(f"Tool: {payload.get('tool', '')}")
        print(f"Module: {payload.get('module', '')}")
        print(f"Function: {payload.get('function', '')}")
    return 0 if payload.get("ok", True) else 1


def _run_tools_validate(args: argparse.Namespace) -> int:
    try:
        descriptor = load_toolpack_descriptor(args.toolpack_path)
        payload = validate_toolpack_descriptor(descriptor, base_path=Path(args.toolpack_path).parent)
    except Exception as exc:
        payload = {"ok": False, "toolpack_id": "", "tool_count": 0, "errors": [str(exc)], "warnings": []}
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        return 0 if payload.get("ok", False) else 1
    print(f"Tool pack: {payload.get('toolpack_id', '')}")
    print(f"Status: {'PASS' if payload.get('ok') else 'FAIL'}")
    print(f"Tool count: {payload.get('tool_count', 0)}")
    if payload.get("errors"):
        print("Errors:")
        for item in payload["errors"]:
            print(f"- {item}")
    if payload.get("warnings"):
        print("Warnings:")
        for item in payload["warnings"]:
            print(f"- {item}")
    return 0 if payload.get("ok", False) else 1


def _run_tools_health(args: argparse.Namespace) -> int:
    payload = check_toolpack_health(args.toolpack_id, config_path=args.config_path, live=False)
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        return 0
    print(f"Tool pack: {payload.get('toolpack_id', '')}")
    print(f"Status: {payload.get('status', '')}")
    print(f"Severity: {payload.get('severity', '')}")
    print(f"Message: {payload.get('message', '')}")
    return 0


def _run_tools_lifecycle(args: argparse.Namespace) -> int:
    from src.toolpack_lifecycle import evaluate_toolpack_lifecycle, write_lifecycle_report

    result = evaluate_toolpack_lifecycle(
        args.toolpack_path,
        environment=str(args.env),
        config_path=args.config_path,
        runtime_data_dir=args.runtime_data_dir,
        include_contract_tests=not bool(args.no_contract),
        include_health=not bool(args.no_health),
        include_manifest_smoke=not bool(args.no_manifest_smoke),
    )
    report_paths = None
    if bool(args.write_report):
        report_paths = write_lifecycle_report(result, runtime_data_dir=args.runtime_data_dir)
        result = dict(result)
        result.update(report_paths)

    if bool(args.json):
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok", False) else 1

    print(f"Tool pack lifecycle: {result.get('toolpack_id', '')}")
    print(f"Environment: {result.get('environment', '')}")
    print(f"Status: {result.get('status', 'UNKNOWN')}")
    print("")
    print("Stages:")
    for key in [
        "discovered",
        "descriptor_valid",
        "contract_test",
        "health_check",
        "governance_policy",
        "enabled_for_environment",
        "registry_integration",
        "example_manifest_smoke",
    ]:
        if key in result.get("stages", {}):
            print(f"  {key}: {result['stages'][key]}")
    print("")
    print("Recommended next action:")
    print(f"  {result.get('recommended_next_action', '')}")
    if report_paths:
        print("")
        print(f"Report JSON: {report_paths.get('json_path', '')}")
        print(f"Report Markdown: {report_paths.get('markdown_path', '')}")
    return 0 if result.get("ok", False) else 1


def _run_tools_inventory(args: argparse.Namespace) -> int:
    from src.tool_inventory import build_tool_inventory_report

    report = build_tool_inventory_report(runtime_data_dir=args.runtime_data_dir)
    payload = {
        "ok": bool(report.get("ok", False)),
        "report_type": report.get("report_type", "tool_inventory"),
        "version": report.get("version", 1),
        "generated_at": report.get("generated_at", ""),
        "summary": report.get("summary", {}),
        "json_path": report.get("json_path", ""),
        "markdown_path": report.get("markdown_path", ""),
        "docs_path": report.get("docs_path", ""),
    }
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        return 0 if payload.get("ok", False) else 1
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    print("Tool inventory:")
    print(f"Total tools: {int(summary.get('total_tools', 0) or 0)}")
    print(f"Migrated tool-pack tools: {int(summary.get('migrated_toolpack_tools', 0) or 0)}")
    print(f"Legacy fallback tools: {int(summary.get('legacy_fallback_tools', 0) or 0)}")
    print(f"External enabled tools: {int(summary.get('external_enabled_tools', 0) or 0)}")
    print(f"Optional disabled tools: {int(summary.get('optional_disabled_tools', 0) or 0)}")
    print(f"Side-effect tools: {int(summary.get('side_effect_tools', 0) or 0)}")
    print(f"Live-side-effect allowed: {int(summary.get('live_side_effect_allowed', 0) or 0)}")
    print(f"JSON: {payload.get('json_path', '')}")
    print(f"Markdown: {payload.get('markdown_path', '')}")
    print(f"Docs: {payload.get('docs_path', '')}")
    return 0 if payload.get("ok", False) else 1


def _run_tools_compat_check(args: argparse.Namespace) -> int:
    from runtime.tool_registry import BUILTIN_LEGACY_TOOL_REGISTRY
    from src.tool_registry_compat import build_compatibility_registry, compare_legacy_and_toolpack_registry
    from src.toolpack_loader import discover_toolpacks

    migrated_registry = build_compatibility_registry()
    result = compare_legacy_and_toolpack_registry(BUILTIN_LEGACY_TOOL_REGISTRY, migrated_registry)
    discovery = discover_toolpacks(include_disabled=True)
    optional_disabled_tools = sum(
        int(item.get("tool_count", 0) or 0)
        for item in discovery.get("toolpacks", [])
        if isinstance(item, dict)
        and str(item.get("core_or_optional", "optional")) == "optional"
        and not bool(item.get("registered", False))
    )
    payload = {
        "ok": bool(result.get("ok", False)),
        "summary": {
            "migrated_toolpack_tools": len(migrated_registry),
            "legacy_fallback_tools": len(BUILTIN_LEGACY_TOOL_REGISTRY),
            "new_tools": len(result.get("new_tools", [])),
            "changed_tools": len(result.get("changed_tools", [])),
            "compatible_tools": len(result.get("compatible_tools", [])),
            "optional_disabled_tools": optional_disabled_tools,
        },
        **result,
    }
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        return 0 if payload.get("ok", False) else 1
    print("Tool Registry Compatibility: " + ("PASS" if payload.get("ok", False) else "FAIL"))
    print(f"Migrated tool-pack tools: {payload['summary']['migrated_toolpack_tools']}")
    print(f"Legacy fallback tools: {payload['summary']['legacy_fallback_tools']}")
    print(f"External enabled tools: {len(build_external_tool_registry())}")
    print(f"Optional disabled tools: {payload['summary']['optional_disabled_tools']}")
    print("Live side-effect allowed: 0")
    if payload.get("warnings"):
        print("Warnings:")
        for item in payload["warnings"]:
            print(f"- {item}")
    if payload.get("changed_tools"):
        print("Changed tools:")
        for item in payload["changed_tools"]:
            print(f"- {item}")
    return 0 if payload.get("ok", False) else 1


def _run_tools_scaffold(args: argparse.Namespace) -> int:
    from src.toolpack_scaffold import scaffold_toolpack

    toolpack_id = str(args.toolpack_id or "").strip()
    namespace = str(getattr(args, "namespace", "") or "").strip() or None
    tool_name = str(getattr(args, "tool", "") or "").strip() or None
    is_side_effect = bool(getattr(args, "side_effect", False))
    is_safe_read = bool(getattr(args, "safe_read", False)) or not is_side_effect
    output_dir = str(getattr(args, "output_dir", "tool_packs") or "tool_packs")
    force = bool(getattr(args, "force", False))

    result = scaffold_toolpack(
        toolpack_id=toolpack_id,
        namespace=namespace,
        tool_name=tool_name,
        side_effect=is_side_effect,
        safe_read=is_safe_read,
        output_dir=output_dir,
        force=force,
    )

    if bool(args.json):
        print(json.dumps(result, indent=2, ensure_ascii=True, default=str))
        return 0 if result.get("ok") else 1

    if not result.get("ok"):
        print(f"Tool pack scaffold: FAIL", file=sys.stderr)
        for err in result.get("errors", []):
            print(f"Error: {err}", file=sys.stderr)
        return 1

    print(f"Tool pack scaffold created: {result.get('path', '')}")
    print(f"Descriptor: {result.get('toolpack_json', '')}")
    print("")
    print("Files created:")
    for f in result.get("files_created", []):
        print(f"  {f}")
    print("")
    print("Next steps:")
    print(f"  taskframe tools validate {result.get('toolpack_json', '')}")
    print(f"  taskframe tools test {result.get('toolpack_json', '')}")
    for w in result.get("warnings", []):
        print(f"Warning: {w}")
    return 0


def _run_tools_test(args: argparse.Namespace) -> int:
    from src.toolpack_contract_runner import run_toolpack_contract_tests

    result = run_toolpack_contract_tests(
        args.toolpack_path,
        runtime_data_dir=str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR),
        include_manifest_smoke=not bool(getattr(args, "no_manifest_smoke", False)),
    )

    if bool(args.json):
        print(json.dumps(result, indent=2, ensure_ascii=True, default=str))
        return 0 if result.get("ok") else 1

    print(f"Tool pack: {result.get('toolpack_id', args.toolpack_path)}")
    for check in result.get("checks", []):
        print(f"  {check['id']}: {check['status']}")
    for tc in result.get("tool_checks", []):
        tool = tc.get("tool", "")
        import_ok = "PASS" if tc.get("import_ok") else "FAIL"
        smoke_ok = "PASS" if tc.get("smoke_ok") else "FAIL"
        shape_ok = "PASS" if tc.get("result_shape_ok") else "FAIL"
        safety_ok = "PASS" if tc.get("safety_ok") else "FAIL"
        print(f"  {tool}: import={import_ok} smoke={smoke_ok} shape={shape_ok} safety={safety_ok}")
        for err in tc.get("errors", []):
            print(f"    Error: {err}")
    if result.get("errors"):
        print("")
        for err in result["errors"]:
            print(f"Error: {err}")
    return 0 if result.get("ok") else 1


def _run_tools_examples(args: argparse.Namespace) -> int:
    from src.toolpack_loader import load_toolpack_descriptor, validate_toolpack_descriptor

    try:
        descriptor = load_toolpack_descriptor(args.toolpack_path)
        validation = validate_toolpack_descriptor(descriptor, base_path=Path(args.toolpack_path).parent)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    descriptor_data = validation.get("descriptor", {})
    tools = descriptor_data.get("tools", [])
    examples = []
    for tool_spec in tools:
        tool_key = str(tool_spec.get("tool", ""))
        output_alias = str(tool_spec.get("action", "")).replace("/", "_") + "_result"
        args_parts: list[str] = []
        arg_types = dict(tool_spec.get("arg_types", {}))
        for arg in tool_spec.get("required_args", []):
            arg_type = arg_types.get(arg, "str")
            if arg_type == "str":
                args_parts.append(f'{arg}="TEST"')
            elif arg_type == "int":
                args_parts.append(f"{arg}=1")
            elif arg_type == "bool":
                args_parts.append(f"{arg}=false")
            else:
                args_parts.append(f"{arg}=TEST")
        args_str = "; ".join(args_parts)
        examples.append({
            "id": str(tool_spec.get("action", tool_key)),
            "command": f"[t:{tool_key} -> {output_alias}] {args_str}".strip(),
            "side_effect": bool(tool_spec.get("side_effect", False)),
            "requires_approval": bool(tool_spec.get("requires_approval", False)),
        })

    if bool(args.json):
        print(json.dumps(examples, indent=2, ensure_ascii=True))
        return 0

    print(f"Tool pack: {descriptor_data.get('toolpack_id', args.toolpack_path)}")
    print(f"Examples:")
    for ex in examples:
        print(f"  {ex['command']}")
        if ex["requires_approval"]:
            print(f"    (side-effect — requires approval before execution)")
    return 0


def _run_tools_policy(args: argparse.Namespace) -> int:
    from src.toolpack_governance import get_all_policies, get_pack_policy

    if args.toolpack_id:
        policy = get_pack_policy(args.toolpack_id)
        if bool(args.json):
            sys.stdout.write(json.dumps(policy, indent=2, ensure_ascii=True) + "\n")
            return 0
        print(f"Tool pack: {policy['toolpack_id']}")
        print(f"  Classification:       {policy.get('classification', 'unknown')}")
        print(f"  Enabled environments: {', '.join(policy.get('enabled_environments', [])) or 'none'}")
        print(f"  Enabled by:           {policy.get('enabled_by', '')}")
        print(f"  Reason:               {policy.get('reason', '')}")
        if policy.get("errors"):
            for e in policy["errors"]:
                print(f"  WARNING: {e}", file=sys.stderr)
        return 0

    policies = get_all_policies()
    if bool(args.json):
        sys.stdout.write(json.dumps(policies, indent=2, ensure_ascii=True) + "\n")
        return 0
    if not policies:
        print("No governance entries found.")
        return 0
    print(f"{'Tool Pack':<30} {'Classification':<16} {'Environments'}")
    print("-" * 70)
    for p in policies:
        envs = ", ".join(p.get("enabled_environments", [])) or "none"
        print(f"{p.get('toolpack_id', ''):<30} {p.get('classification', ''):<16} {envs}")
    return 0


def _run_tools_enable(args: argparse.Namespace) -> int:
    from src.toolpack_governance import enable_pack

    environments = [e.strip() for e in args.env.split(",") if e.strip()]
    result = enable_pack(
        args.toolpack_id,
        classification=args.classification,
        environments=environments,
        enabled_by=args.by,
        reason=args.reason,
    )
    if bool(args.json):
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
        return 0 if result["ok"] else 1
    if not result["ok"]:
        for e in result.get("errors", []):
            print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"Enabled: {result['toolpack_id']}")
    print(f"  Classification: {result['classification']}")
    print(f"  Environments:   {', '.join(result.get('environments', []))}")
    return 0


def _run_tools_disable(args: argparse.Namespace) -> int:
    from src.toolpack_governance import disable_pack

    environments: list[str] | None = None
    if args.env:
        environments = [e.strip() for e in args.env.split(",") if e.strip()]
    result = disable_pack(
        args.toolpack_id,
        environments=environments,
        disabled_by=args.by,
        reason=args.reason,
    )
    if bool(args.json):
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
        return 0 if result["ok"] else 1
    if not result["ok"]:
        for e in result.get("errors", []):
            print(f"Error: {e}", file=sys.stderr)
        return 1
    scope = f"in {args.env}" if args.env else "in all environments"
    print(f"Disabled: {args.toolpack_id} {scope}")
    return 0


def _run_tools_governance_report(args: argparse.Namespace) -> int:
    from src.toolpack_governance import build_governance_report, render_governance_markdown

    report = build_governance_report()
    if bool(args.json):
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
        return 0 if report["ok"] else 1
    print(render_governance_markdown(report))
    return 0 if report["ok"] else 1


def _inspect_tool(tool_key: str, *, config_path: str = "config/enabled_toolpacks.json") -> dict[str, Any]:
    try:
        from runtime.tool_registry import build_tool_registry

        registry = build_tool_registry(include_external=True, config_path=config_path)
        spec = dict(registry[tool_key])
        spec.setdefault("tool", tool_key)
        spec.setdefault("status", "registered")
        spec.setdefault("ok", True)
        return spec
    except Exception as exc:
        discovery = discover_toolpacks(config_path=config_path, include_disabled=True)
        for pack in discovery.get("toolpacks", []):
            try:
                descriptor = load_toolpack_descriptor(pack["path"])
                validation = validate_toolpack_descriptor(descriptor, base_path=Path(pack["path"]).parent)
            except Exception:
                continue
            descriptor_data = validation.get("descriptor", {})
            for tool in descriptor_data.get("tools", []):
                if str(tool.get("tool", "")).strip() != tool_key:
                    continue
                payload = dict(tool)
                payload.setdefault("tool", tool_key)
                payload.setdefault("ok", bool(validation.get("ok", False)))
                payload.setdefault("status", "discovered")
                payload.setdefault("source", "external_toolpack")
                payload.setdefault("toolpack_id", descriptor_data.get("toolpack_id", pack.get("toolpack_id", "")))
                payload.setdefault("toolpack_name", descriptor_data.get("name", pack.get("name", "")))
                payload.setdefault("toolpack_path", str(pack.get("path", "")))
                payload.setdefault("toolpack_core_or_optional", descriptor_data.get("core_or_optional", "optional"))
                payload.setdefault("toolpack_registered", bool(pack.get("registered", False)))
                return payload
        return {"ok": False, "status": "not_found", "tool": tool_key, "error": str(exc)}


def _inspect_toolpack(toolpack_id: str, *, config_path: str = "config/enabled_toolpacks.json") -> dict[str, Any]:
    discovery = discover_toolpacks(config_path=config_path, include_disabled=True)
    entry = next((item for item in discovery.get("toolpacks", []) if str(item.get("toolpack_id", "")) == toolpack_id), None)
    if not entry:
        builtin_path = get_builtin_toolpack_path(toolpack_id)
        if builtin_path is not None:
            entry = {
                "toolpack_id": toolpack_id,
                "path": str(builtin_path),
                "enabled": True,
                "registered": True,
                "valid": True,
                "tool_count": 0,
                "errors": [],
                "warnings": [],
                "core_or_optional": "core",
                "name": toolpack_id,
                "version": "",
            }
    if not entry:
        return {"ok": False, "status": "not_found", "toolpack_id": toolpack_id, "error": "Tool pack not found."}
    health = check_toolpack_health(toolpack_id, config_path=config_path)
    try:
        descriptor = load_toolpack_descriptor(entry["path"])
    except Exception as exc:
        descriptor = {"error": str(exc)}
    payload = {
        "ok": bool(entry.get("valid", False)),
        "status": "registered" if entry.get("registered") else "discovered",
        "toolpack_id": toolpack_id,
        "name": entry.get("name", toolpack_id),
        "description": descriptor.get("description", ""),
        "path": entry.get("path", ""),
        "enabled": entry.get("enabled", False),
        "registered": entry.get("registered", False),
        "valid": entry.get("valid", False),
        "health": health,
        "descriptor": descriptor,
    }
    return payload


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
