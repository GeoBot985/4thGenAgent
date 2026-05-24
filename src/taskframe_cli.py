from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import subprocess
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
    ui.add_argument("--safe-start", action="store_true")
    ui.add_argument("--debug-startup", action="store_true")

    demo = sub.add_parser("demo", help="Run a safe default operator demo scenario.")
    demo.add_argument("demo_command", nargs="?", default="run", choices=["run", "cross-workflow-v2"])
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

    validate = sub.add_parser("validate", help="Run bounded validation profiles.")
    validate.add_argument("mode", choices=["quick", "backend", "manifest", "toolpack", "runtime", "reports", "local", "ci"])
    validate.add_argument("--timeout-scale", type=float, default=1.0)
    validate.add_argument("--continue-on-failure", action="store_true")

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
    runtime_governance.add_argument("--env", default="", choices=["", "demo", "dev", "test", "release", "pilot", "live"])
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

    readiness = sub.add_parser("readiness", help="Build the 90% readiness scorecard.")
    readiness.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    readiness.add_argument("--strict", action="store_true")
    readiness.add_argument("--threshold", type=int, default=90)
    readiness.add_argument("--open-report", action="store_true")
    readiness.add_argument("--json", action="store_true")

    portfolio = sub.add_parser("portfolio-pack", help="Build the public-facing portfolio evidence pack.")
    portfolio.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    portfolio.add_argument("--no-story-pack", action="store_true")
    portfolio.add_argument("--no-readiness", action="store_true")
    portfolio.add_argument("--open", action="store_true")
    portfolio.add_argument("--json", action="store_true")

    pilot = sub.add_parser("pilot-readiness", help="Build the controlled pilot readiness scorecard and evidence pack.")
    pilot.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    pilot.add_argument("--write-pack", action="store_true", help="Write the full pilot evidence pack to disk.")
    pilot.add_argument("--strict", action="store_true", help="Exit non-zero if scorecard fails.")
    pilot.add_argument("--json", action="store_true")

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
    tools_lifecycle.add_argument("--env", default="dev", choices=["demo", "dev", "test", "release", "pilot", "live"])
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
    tools_enable.add_argument("--env", default="dev,test", help="Comma-separated environments (demo,dev,test,release,pilot,live).")
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

    readiness_gate = sub.add_parser("readiness-gate", help="Evaluate the 90%+ controlled demo readiness evidence gate.")
    readiness_gate.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    readiness_gate.add_argument("--threshold", type=int, default=90)
    readiness_gate.add_argument("--strict", action="store_true", help="Fail if release verifier evidence is missing.")
    readiness_gate.add_argument("--write-report", action="store_true", help="Write JSON, Markdown, and HTML reports.")
    readiness_gate.add_argument("--since", default="", help="ISO8601 timestamp; all evidence must be newer than this.")
    readiness_gate.add_argument("--json", action="store_true")

    backend_security = sub.add_parser("backend-security", help="Show backend security posture status.")
    backend_security.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    backend_security.add_argument("--json", action="store_true")

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

    # Spec 109 — Event source contracts
    esrc = sub.add_parser("event-sources", help="Inspect and validate event source contracts.")
    esrc_sub = esrc.add_subparsers(dest="esrc_command", required=True)

    esrc_list = esrc_sub.add_parser("list", help="List all registered event source contracts.")
    esrc_list.add_argument("--json", action="store_true")

    esrc_show = esrc_sub.add_parser("show", help="Show contract details for a specific source type.")
    esrc_show.add_argument("source_type", help="Source type (e.g. operator_ui, schedule, gmail).")
    esrc_show.add_argument("--json", action="store_true")

    esrc_validate = esrc_sub.add_parser("validate", help="Validate all registered source contracts.")
    esrc_validate.add_argument("--json", action="store_true")

    esrc_validate_event = esrc_sub.add_parser("validate-event", help="Validate a raw event against its source contract.")
    esrc_validate_event.add_argument("event_json", help="JSON string of event to validate.")
    esrc_validate_event.add_argument("--json", action="store_true")

    esrc_route_alignment = esrc_sub.add_parser("route-alignment", help="Check that all event routes align with source contracts.")
    esrc_route_alignment.add_argument("--routes-path", default="config/event_routes.json")
    esrc_route_alignment.add_argument("--json", action="store_true")

    # Spec 139 — External event source polling
    esrc_status = esrc_sub.add_parser("status", help="Show event source subsystem status.")
    esrc_status.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    esrc_status.add_argument("--json", action="store_true")

    esrc_list2 = esrc_sub.add_parser("list-sources", help="List configured event sources.")
    esrc_list2.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    esrc_list2.add_argument("--json", action="store_true")

    esrc_show2 = esrc_sub.add_parser("show-source", help="Show config and state for a specific event source.")
    esrc_show2.add_argument("source_id", help="Source ID to inspect.")
    esrc_show2.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    esrc_show2.add_argument("--json", action="store_true")

    esrc_health2 = esrc_sub.add_parser("health-check", help="Run preflight health check for an event source.")
    esrc_health2.add_argument("source_id", help="Source ID to health-check.")
    esrc_health2.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    esrc_health2.add_argument("--json", action="store_true")

    esrc_poll = esrc_sub.add_parser("poll", help="Poll a single event source.")
    esrc_poll.add_argument("source_id", help="Source ID to poll.")
    esrc_poll.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    esrc_poll.add_argument("--json", action="store_true")

    esrc_poll_enabled = esrc_sub.add_parser("poll-enabled", help="Poll all enabled event sources.")
    esrc_poll_enabled.add_argument("--limit", type=int, default=10, help="Max sources to poll.")
    esrc_poll_enabled.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    esrc_poll_enabled.add_argument("--json", action="store_true")

    esrc_create_fixture = esrc_sub.add_parser("create-fixture", help="Create a default fixture event source config.")
    esrc_create_fixture.add_argument("source_id", help="Source ID for the new fixture source.")
    esrc_create_fixture.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    esrc_create_fixture.add_argument("--json", action="store_true")

    esrc_enable = esrc_sub.add_parser("enable", help="Enable an event source.")
    esrc_enable.add_argument("source_id", help="Source ID to enable.")
    esrc_enable.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    esrc_enable.add_argument("--json", action="store_true")

    esrc_disable = esrc_sub.add_parser("disable", help="Disable an event source.")
    esrc_disable.add_argument("source_id", help="Source ID to disable.")
    esrc_disable.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    esrc_disable.add_argument("--json", action="store_true")

    esrc_history = esrc_sub.add_parser("history", help="Show recent polling history.")
    esrc_history.add_argument("--source-id", default="", help="Filter by source ID.")
    esrc_history.add_argument("--limit", type=int, default=20)
    esrc_history.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    esrc_history.add_argument("--json", action="store_true")

    # Spec 108 — Event queue inspection and replay
    events = sub.add_parser("events", help="Inspect and replay events from the event queue.")
    events_sub = events.add_subparsers(dest="events_command", required=True)

    events_list = events_sub.add_parser("list", help="List events from the event queue.")
    events_list.add_argument("--status", default="", help="Filter by status.")
    events_list.add_argument("--source", default="", help="Filter by source.")
    events_list.add_argument("--event-type", default="", help="Filter by event type.")
    events_list.add_argument("--limit", type=int, default=100, help="Maximum number of events to return.")
    events_list.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    events_list.add_argument("--json", action="store_true")

    events_show = events_sub.add_parser("show", help="Show detail for a specific event.")
    events_show.add_argument("event_id", help="Event ID to inspect.")
    events_show.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    events_show.add_argument("--json", action="store_true")

    events_replay = events_sub.add_parser("replay-dry-run", help="Replay an event in dry-run mode (safe, creates new frame).")
    events_replay.add_argument("event_id", help="Event ID to replay.")
    events_replay.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    events_replay.add_argument("--manifest-dir", default="manifests")
    events_replay.add_argument("--replayed-by", default="operator", help="Identity of the operator running the replay.")
    events_replay.add_argument("--reason", default="", help="Reason for replay.")
    events_replay.add_argument("--json", action="store_true")

    profile_cmd = sub.add_parser("profile", help="Inspect runtime execution profiles and safety boundaries.")
    profile_sub = profile_cmd.add_subparsers(dest="profile_command", required=True)

    profile_show = profile_sub.add_parser("show", help="Show the active runtime profile.")
    profile_show.add_argument("--profile", default="", help="Explicit profile override.")
    profile_show.add_argument("--config-dir", default="", help="Config directory containing runtime_profile.json.")
    profile_show.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    profile_show.add_argument("--json", action="store_true")

    profile_list = profile_sub.add_parser("list", help="List the built-in runtime profiles.")
    profile_list.add_argument("--json", action="store_true")

    profile_check = profile_sub.add_parser("check", help="Check the active runtime profile for safety.")
    profile_check.add_argument("--profile", default="", help="Explicit profile override.")
    profile_check.add_argument("--config-dir", default="", help="Config directory containing runtime_profile.json.")
    profile_check.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    profile_check.add_argument("--json", action="store_true")

    controlled_live = profile_sub.add_parser("controlled-live-status", help="Show the legacy controlled live read profile status.")
    controlled_live.add_argument("--json", action="store_true")
    controlled_live.add_argument("--check-tools", action="store_true")
    controlled_live.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)

    service = sub.add_parser("service", help="Inspect and run the controlled worker service profile.")
    service_sub = service.add_subparsers(dest="service_command", required=True)

    service_preflight = service_sub.add_parser("preflight", help="Run the service deployment preflight checks.")
    service_preflight.add_argument("--profile", default="service")
    service_preflight.add_argument("--config-dir", default="")
    service_preflight.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    service_preflight.add_argument("--manifest-dir", default="manifests")
    service_preflight.add_argument("--routes-path", default="config/event_routes.json")
    service_preflight.add_argument("--toolpack-config-path", default="config/examples/taskframe.service.toolpacks.example.json")
    service_preflight.add_argument("--json", action="store_true")

    service_status = service_sub.add_parser("status", help="Show the service runtime status.")
    service_status.add_argument("--profile", default="service")
    service_status.add_argument("--config-dir", default="")
    service_status.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    service_status.add_argument("--manifest-dir", default="manifests")
    service_status.add_argument("--routes-path", default="config/event_routes.json")
    service_status.add_argument("--toolpack-config-path", default="config/examples/taskframe.service.toolpacks.example.json")
    service_status.add_argument("--json", action="store_true")

    service_run_once = service_sub.add_parser("run-once", help="Run one bounded service worker cycle after preflight.")
    service_run_once.add_argument("--profile", default="service")
    service_run_once.add_argument("--config-dir", default="")
    service_run_once.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    service_run_once.add_argument("--manifest-dir", default="manifests")
    service_run_once.add_argument("--routes-path", default="config/event_routes.json")
    service_run_once.add_argument("--toolpack-config-path", default="config/examples/taskframe.service.toolpacks.example.json")
    service_run_once.add_argument("--queue-limit", type=int, default=10)
    service_run_once.add_argument("--no-scheduler", action="store_true")
    service_run_once.add_argument("--no-event-sources", action="store_true")
    service_run_once.add_argument("--json", action="store_true")

    runtime_store = sub.add_parser("runtime-store", help="Inspect, validate, back up, and assess the runtime store.")
    runtime_store_sub = runtime_store.add_subparsers(dest="runtime_store_command", required=True)

    runtime_store_status = runtime_store_sub.add_parser("status", help="Show runtime store health, version, and lock summary.")
    runtime_store_status.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    runtime_store_status.add_argument("--manifest-dir", default="manifests")
    runtime_store_status.add_argument("--json", action="store_true")

    runtime_store_locks = runtime_store_sub.add_parser("locks", help="List runtime store locks.")
    runtime_store_locks.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    runtime_store_locks.add_argument("--json", action="store_true")

    runtime_store_cleanup_locks = runtime_store_sub.add_parser("cleanup-locks", help="Remove expired runtime store locks.")
    runtime_store_cleanup_locks.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    runtime_store_cleanup_locks.add_argument("--json", action="store_true")

    runtime_store_check = runtime_store_sub.add_parser("check", help="Validate the runtime store layout and artifacts.")
    runtime_store_check.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    runtime_store_check.add_argument("--manifest-dir", default="manifests")
    runtime_store_check.add_argument("--json", action="store_true")

    runtime_store_index = runtime_store_sub.add_parser("index", help="Rebuild the runtime store index.")
    runtime_store_index.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    runtime_store_index.add_argument("--manifest-dir", default="manifests")
    runtime_store_index.add_argument("--json", action="store_true")

    runtime_store_backup = runtime_store_sub.add_parser("backup", help="Write a safe runtime store backup archive.")
    runtime_store_backup.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    runtime_store_backup.add_argument("--manifest-dir", default="manifests")
    runtime_store_backup.add_argument("--json", action="store_true")

    runtime_store_restore = runtime_store_sub.add_parser("restore", help="Validate and restore a runtime store backup into a target folder.")
    runtime_store_restore.add_argument("--backup", required=True)
    runtime_store_restore.add_argument("--target", required=True)
    runtime_store_restore.add_argument("--validate-only", action="store_true", default=True)
    runtime_store_restore.add_argument("--manifest-dir", default="manifests")
    runtime_store_restore.add_argument("--json", action="store_true")

    runtime_store_retention = runtime_store_sub.add_parser("retention-plan", help="Build a dry-run runtime store retention plan.")
    runtime_store_retention.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    runtime_store_retention.add_argument("--manifest-dir", default="manifests")
    runtime_store_retention.add_argument("--json", action="store_true")

    runtime_store_cleanup = runtime_store_sub.add_parser("cleanup", help="Dry-run runtime store cleanup.")
    runtime_store_cleanup.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    runtime_store_cleanup.add_argument("--manifest-dir", default="manifests")
    runtime_store_cleanup.add_argument("--dry-run", action="store_true", default=True)
    runtime_store_cleanup.add_argument("--json", action="store_true")

    persistence = sub.add_parser("persistence", help="Inspect and manage TaskFrame persistence backends.")
    persistence_sub = persistence.add_subparsers(dest="persistence_command", required=True)
    for name, help_text in (
        ("status", "Show active persistence backend status."),
        ("init", "Initialize the configured persistence backend."),
        ("migrate-json", "Backfill SQLite from JSON runtime artifacts."),
        ("verify", "Verify the configured persistence backend."),
    ):
        persistence_cmd = persistence_sub.add_parser(name, help=help_text)
        persistence_cmd.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
        persistence_cmd.add_argument("--json", action="store_true")

    artifacts = sub.add_parser("artifacts", help="Manage runtime artifacts and retention policies.")
    artifacts_sub = artifacts.add_subparsers(dest="artifacts_command", required=True)
    
    artifacts_status = artifacts_sub.add_parser("status", help="Show artifact inventory status.")
    artifacts_status.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    artifacts_status.add_argument("--json", action="store_true")

    artifacts_plan = artifacts_sub.add_parser("plan-cleanup", help="Generate a dry-run artifact retention plan.")
    artifacts_plan.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    artifacts_plan.add_argument("--json", action="store_true")

    artifacts_cleanup = artifacts_sub.add_parser("cleanup", help="Execute artifact cleanup.")
    artifacts_cleanup.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    artifacts_cleanup.add_argument("--confirm", action="store_true", help="Confirm execution of cleanup.")
    artifacts_cleanup.add_argument("--json", action="store_true")

    monitor = sub.add_parser("monitor", help="Inspect operational monitoring and run health.")
    monitor_sub = monitor.add_subparsers(dest="monitor_command", required=True)
    monitor_snapshot = monitor_sub.add_parser("snapshot", help="Build the consolidated operational monitoring snapshot.")
    monitor_snapshot.add_argument("--profile", default="service")
    monitor_snapshot.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    monitor_snapshot.add_argument("--threshold-failed-frames", type=int, default=10)
    monitor_snapshot.add_argument("--heartbeat-stale-seconds", type=int, default=600)
    monitor_snapshot.add_argument("--max-cycle-duration-ms", type=int, default=1000)
    monitor_snapshot.add_argument("--write-report", action="store_true")
    monitor_snapshot.add_argument("--json", action="store_true")

    monitor_alerts = monitor_sub.add_parser("alerts", help="Show alert candidates from the operational monitoring snapshot.")
    monitor_alerts.add_argument("--profile", default="service")
    monitor_alerts.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    monitor_alerts.add_argument("--threshold-failed-frames", type=int, default=10)
    monitor_alerts.add_argument("--heartbeat-stale-seconds", type=int, default=600)
    monitor_alerts.add_argument("--max-cycle-duration-ms", type=int, default=1000)
    monitor_alerts.add_argument("--write-report", action="store_true")
    monitor_alerts.add_argument("--json", action="store_true")
    for name, help_text in (
        ("summary", "Show a monitoring summary."),
        ("failed", "List failed runs."),
        ("pending", "List pending runs."),
        ("stuck", "List stuck runs."),
        ("blocked", "List blocked runs."),
        ("tools", "Show aggregated tool health."),
        ("report", "Write an operational monitoring report."),
    ):
        monitor_cmd_parser = monitor_sub.add_parser(name, help=help_text)
        monitor_cmd_parser.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
        monitor_cmd_parser.add_argument("--profile", default="")
        monitor_cmd_parser.add_argument("--limit", type=int, default=20)
        monitor_cmd_parser.add_argument("--rebuild", action="store_true")
        monitor_cmd_parser.add_argument("--json", action="store_true")

    recover = sub.add_parser("recover", help="Assess safe retry and resume options.")
    recover_sub = recover.add_subparsers(dest="recover_command", required=True)

    recover_assess = recover_sub.add_parser("assess", help="Assess recovery for a frame.")
    recover_assess.add_argument("frame_id", help="TaskFrame ID to assess.")
    recover_assess.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    recover_assess.add_argument("--manifest-dir", default="manifests")
    recover_assess.add_argument("--profile", default="")
    recover_assess.add_argument("--dry-run", action="store_true", default=True)
    recover_assess.add_argument("--json", action="store_true")

    recover_retry = recover_sub.add_parser("retry-step", help="Assess retry safety for a failed step.")
    recover_retry.add_argument("frame_id", help="TaskFrame ID to assess.")
    recover_retry.add_argument("--step", required=True, help="Step ID to retry.")
    recover_retry.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    recover_retry.add_argument("--manifest-dir", default="manifests")
    recover_retry.add_argument("--profile", default="")
    recover_retry.add_argument("--dry-run", action="store_true", default=True)
    recover_retry.add_argument("--json", action="store_true")

    recover_resume = recover_sub.add_parser("resume", help="Assess resume safety for a frame.")
    recover_resume.add_argument("frame_id", help="TaskFrame ID to assess.")
    recover_resume.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    recover_resume.add_argument("--manifest-dir", default="manifests")
    recover_resume.add_argument("--profile", default="")
    recover_resume.add_argument("--dry-run", action="store_true", default=True)
    recover_resume.add_argument("--json", action="store_true")

    # Spec 137 — Durable event queue
    queue = sub.add_parser("queue", help="Manage and inspect the durable event queue.")
    queue_sub = queue.add_subparsers(dest="queue_command", required=True)

    queue_status = queue_sub.add_parser("status", help="Show durable queue health summary.")
    queue_status.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    queue_status.add_argument("--json", action="store_true")

    queue_list = queue_sub.add_parser("list", help="List durable queue records.")
    queue_list.add_argument("--status", default="", help="Filter by status (PENDING, CLAIMED, PROCESSING, COMPLETED, FAILED_RETRYABLE, FAILED_PERMANENT, DEAD_LETTER, CANCELLED).")
    queue_list.add_argument("--limit", type=int, default=20, help="Max records to return.")
    queue_list.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    queue_list.add_argument("--json", action="store_true")

    queue_enqueue = queue_sub.add_parser("enqueue-fixture", help="Enqueue a safe local fixture event.")
    queue_enqueue.add_argument("fixture_name", help="Fixture name (e.g. customer_status, order_status).")
    queue_enqueue.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    queue_enqueue.add_argument("--json", action="store_true")

    queue_process_next = queue_sub.add_parser("process-next", help="Process one PENDING queue item into a TaskFrame.")
    queue_process_next.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    queue_process_next.add_argument("--worker-id", default="local")
    queue_process_next.add_argument("--json", action="store_true")

    queue_process_batch = queue_sub.add_parser("process-batch", help="Process a batch of PENDING queue items.")
    queue_process_batch.add_argument("--limit", type=int, default=10, help="Max items to process.")
    queue_process_batch.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    queue_process_batch.add_argument("--worker-id", default="local")
    queue_process_batch.add_argument("--json", action="store_true")

    queue_retry = queue_sub.add_parser("retry", help="Retry a FAILED_RETRYABLE queue item.")
    queue_retry.add_argument("queue_id", help="Queue ID to retry.")
    queue_retry.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    queue_retry.add_argument("--json", action="store_true")

    queue_cancel = queue_sub.add_parser("cancel", help="Cancel a non-terminal queue item.")
    queue_cancel.add_argument("queue_id", help="Queue ID to cancel.")
    queue_cancel.add_argument("--reason", default="Cancelled by operator.")
    queue_cancel.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    queue_cancel.add_argument("--json", action="store_true")

    queue_dead_letter = queue_sub.add_parser("dead-letter", help="List DEAD_LETTER queue items.")
    queue_dead_letter.add_argument("--limit", type=int, default=20)
    queue_dead_letter.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    queue_dead_letter.add_argument("--json", action="store_true")

    queue_recover = queue_sub.add_parser("recover-stale", help="Recover stale CLAIMED/PROCESSING items.")
    queue_recover.add_argument("--stale-timeout-minutes", type=int, default=15)
    queue_recover.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    queue_recover.add_argument("--json", action="store_true")

    # Spec 138 — Scheduler
    sched = sub.add_parser("schedule", help="Manage and inspect the scheduler subsystem.")
    sched_sub = sched.add_subparsers(dest="schedule_command", required=True)

    sched_status = sched_sub.add_parser("status", help="Show scheduler panel summary.")
    sched_status.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    sched_status.add_argument("--json", action="store_true")

    sched_list = sched_sub.add_parser("list", help="List schedules.")
    sched_list.add_argument("--enabled-only", action="store_true")
    sched_list.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    sched_list.add_argument("--json", action="store_true")

    sched_enable = sched_sub.add_parser("enable", help="Enable a schedule.")
    sched_enable.add_argument("schedule_id")
    sched_enable.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    sched_enable.add_argument("--json", action="store_true")

    sched_disable = sched_sub.add_parser("disable", help="Disable a schedule.")
    sched_disable.add_argument("schedule_id")
    sched_disable.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    sched_disable.add_argument("--json", action="store_true")

    sched_tick = sched_sub.add_parser("tick", help="Run one scheduler tick (always dry-run).")
    sched_tick.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    sched_tick.add_argument("--json", action="store_true")

    sched_load = sched_sub.add_parser("load-fixture", help="Load a schedule fixture JSON file.")
    sched_load.add_argument("fixture_path", help="Path to the fixture JSON file.")
    sched_load.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    sched_load.add_argument("--json", action="store_true")

    sched_runs = sched_sub.add_parser("runs", help="List recent schedule run records.")
    sched_runs.add_argument("--schedule-id", default="", help="Filter by schedule ID.")
    sched_runs.add_argument("--limit", type=int, default=20)
    sched_runs.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    sched_runs.add_argument("--json", action="store_true")

    # Spec 140 — Local worker supervisor
    wkr = sub.add_parser("worker", help="Manage and inspect the local worker supervisor.")
    wkr_sub = wkr.add_subparsers(dest="worker_command", required=True)

    wkr_status = wkr_sub.add_parser("status", help="Show worker status, lock, and last cycle.")
    wkr_status.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    wkr_status.add_argument("--json", action="store_true")

    wkr_health = wkr_sub.add_parser("health", help="Check worker dependency health.")
    wkr_health.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    wkr_health.add_argument("--json", action="store_true")

    wkr_run_once = wkr_sub.add_parser("run-once", help="Run one bounded worker cycle.")
    wkr_run_once.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    wkr_run_once.add_argument("--worker-id", default="local-worker-1")
    wkr_run_once.add_argument("--no-scheduler", action="store_true", help="Disable scheduler tick.")
    wkr_run_once.add_argument("--no-event-sources", action="store_true", help="Disable event-source polling.")
    wkr_run_once.add_argument("--queue-limit", type=int, default=10, help="Max queue items to process.")
    wkr_run_once.add_argument("--json", action="store_true")

    wkr_soak = wkr_sub.add_parser("soak", help="Run a bounded worker soak test.")
    wkr_soak.add_argument("--profile", default="service")
    wkr_soak.add_argument("--cycles", type=int, default=20)
    wkr_soak.add_argument("--sleep-seconds", type=float, default=0.1)
    wkr_soak.add_argument("--max-runtime-seconds", type=float, default=300.0)
    wkr_soak.add_argument("--queue-limit", type=int, default=10)
    wkr_soak.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    wkr_soak.add_argument("--fail-fast", action="store_true")
    wkr_soak.add_argument("--write-report", dest="write_report", action="store_true", default=True)
    wkr_soak.add_argument("--no-write-report", dest="write_report", action="store_false")
    wkr_soak.add_argument("--json", action="store_true")

    wkr_loop = wkr_sub.add_parser("run-loop", help="Run a bounded worker loop.")
    wkr_loop.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    wkr_loop.add_argument("--worker-id", default="local-worker-1")
    wkr_loop.add_argument("--max-cycles", type=int, default=3)
    wkr_loop.add_argument("--sleep-seconds", type=float, default=5.0)
    wkr_loop.add_argument("--max-runtime-seconds", type=float, default=300.0)
    wkr_loop.add_argument("--json", action="store_true")

    wkr_stop = wkr_sub.add_parser("stop", help="Request graceful worker stop.")
    wkr_stop.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    wkr_stop.add_argument("--worker-id", default="local-worker-1")
    wkr_stop.add_argument("--json", action="store_true")

    wkr_cycles = wkr_sub.add_parser("cycles", help="Show recent worker cycle history.")
    wkr_cycles.add_argument("--limit", type=int, default=10)
    wkr_cycles.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    wkr_cycles.add_argument("--json", action="store_true")

    wkr_clear_lock = wkr_sub.add_parser("clear-stale-lock", help="Clear a stale worker lock.")
    wkr_clear_lock.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    wkr_clear_lock.add_argument("--json", action="store_true")

    # Spec 155 — Live Side-Effect Approval Execution Model
    lse = sub.add_parser("live-side-effect", help="Governed live side-effect approval execution (v1: sheet/write_rows only).")
    lse_sub = lse.add_subparsers(dest="lse_command", required=True)

    lse_preflight = lse_sub.add_parser("preflight", help="Run the live side-effect preflight (15+ checks, no execution).")
    lse_preflight.add_argument("--frame-id", required=True)
    lse_preflight.add_argument("--action-id", required=True)
    lse_preflight.add_argument("--tool", default="sheet/write_rows")
    lse_preflight.add_argument("--profile", default="controlled_live_write")
    lse_preflight.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    lse_preflight.add_argument("--json", action="store_true")

    lse_execute = lse_sub.add_parser("execute", help="Execute an approved live side effect (requires typed confirmation).")
    lse_execute.add_argument("--frame-id", required=True)
    lse_execute.add_argument("--action-id", required=True)
    lse_execute.add_argument("--tool", default="sheet/write_rows")
    lse_execute.add_argument("--profile", default="controlled_live_write")
    lse_execute.add_argument("--confirm", required=True, help="Typed confirmation phrase: 'EXECUTE LIVE <tool> <frame_id> <action_id>'")
    lse_execute.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    lse_execute.add_argument("--dry-run-fallback", action="store_true", help="Simulate execution without calling any external API.")
    lse_execute.add_argument("--json", action="store_true")

    lse_verify = lse_sub.add_parser("verify", help="Post-execution verification for the latest ledger entry.")
    lse_verify.add_argument("--frame-id", required=True)
    lse_verify.add_argument("--action-id", required=True)
    lse_verify.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    lse_verify.add_argument("--json", action="store_true")

    lse_report = lse_sub.add_parser("report", help="Show the live execution ledger report.")
    lse_report.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    lse_report.add_argument("--limit", type=int, default=20)
    lse_report.add_argument("--json", action="store_true")

    lse_rollback = lse_sub.add_parser("rollback-plan", help="Show the rollback plan for a ledger entry (display only, no auto-rollback).")
    lse_rollback.add_argument("--idempotency-key", required=True)
    lse_rollback.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    lse_rollback.add_argument("--json", action="store_true")

    # Spec 156 — InvoiceOps Live Sheet Write Pilot
    invoiceops = sub.add_parser("invoiceops", help="InvoiceOps bookkeeping workflow commands.")
    invoiceops_sub = invoiceops.add_subparsers(dest="invoiceops_command", required=True)

    iolsp = invoiceops_sub.add_parser("live-posting", help="InvoiceOps live sheet posting pilot commands.")
    iolsp_sub = iolsp.add_subparsers(dest="iolsp_command", required=True)

    iolsp_plan = iolsp_sub.add_parser("plan", help="Build a live posting plan from completed InvoiceOps outputs.")
    iolsp_plan.add_argument("--frame-id", required=True)
    iolsp_plan.add_argument("--invoice-id", default="")
    iolsp_plan.add_argument("--invoice-number", default="")
    iolsp_plan.add_argument("--supplier-name", default="")
    iolsp_plan.add_argument("--po-number", default="")
    iolsp_plan.add_argument("--match-status", default="matched", choices=["matched", "exception", "blocked"])
    iolsp_plan.add_argument("--profile", default="controlled_live_write")
    iolsp_plan.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    iolsp_plan.add_argument("--json", action="store_true")

    iolsp_preflight = iolsp_sub.add_parser("preflight", help="Run live posting preflight (no execution).")
    iolsp_preflight.add_argument("--frame-id", required=True)
    iolsp_preflight.add_argument("--action-id", default="")
    iolsp_preflight.add_argument("--profile", default="controlled_live_write")
    iolsp_preflight.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    iolsp_preflight.add_argument("--json", action="store_true")

    iolsp_approval = iolsp_sub.add_parser("approval-pack", help="Build an approval pack for operator review.")
    iolsp_approval.add_argument("--frame-id", required=True)
    iolsp_approval.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    iolsp_approval.add_argument("--json", action="store_true")

    iolsp_execute = iolsp_sub.add_parser("execute", help="Execute one approved posting action (requires typed confirmation).")
    iolsp_execute.add_argument("--frame-id", required=True)
    iolsp_execute.add_argument("--action-id", required=True)
    iolsp_execute.add_argument("--profile", default="controlled_live_write")
    iolsp_execute.add_argument("--confirm", required=True, help="Typed confirmation phrase.")
    iolsp_execute.add_argument("--dry-run-fallback", action="store_true")
    iolsp_execute.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    iolsp_execute.add_argument("--json", action="store_true")

    iolsp_verify = iolsp_sub.add_parser("verify", help="Post-execution verification for a live posting.")
    iolsp_verify.add_argument("--frame-id", required=True)
    iolsp_verify.add_argument("--action-id", required=True)
    iolsp_verify.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    iolsp_verify.add_argument("--json", action="store_true")

    iolsp_report = iolsp_sub.add_parser("report", help="Show the InvoiceOps live posting ledger report.")
    iolsp_report.add_argument("--frame-id", default="")
    iolsp_report.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    iolsp_report.add_argument("--json", action="store_true")

    invoiceops_reconcile = invoiceops_sub.add_parser("reconcile", help="Reconcile posted InvoiceOps rows and build a reconciliation report.")
    invoiceops_reconcile.add_argument("--frame-id", default="")
    invoiceops_reconcile.add_argument("--invoice-number", default="")
    invoiceops_reconcile.add_argument("--posting-plan-id", default="")
    invoiceops_reconcile.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    invoiceops_reconcile.add_argument("--profile", default="service")
    invoiceops_reconcile.add_argument("--fixture-mode", action="store_true", default=True)
    invoiceops_reconcile.add_argument("--write-report", action="store_true")
    invoiceops_reconcile.add_argument("--json", action="store_true")

    invoiceops_evidence = invoiceops_sub.add_parser("evidence-pack", help="Build an InvoiceOps accounting evidence pack (read-only).")
    invoiceops_evidence.add_argument("--frame-id", default="")
    invoiceops_evidence.add_argument("--invoice-number", default="")
    invoiceops_evidence.add_argument("--posting-plan-id", default="")
    invoiceops_evidence.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    invoiceops_evidence.add_argument("--profile", default="service")
    invoiceops_evidence.add_argument("--fixture-mode", action="store_true", default=True)
    invoiceops_evidence.add_argument("--write-report", action="store_true")
    invoiceops_evidence.add_argument("--json", action="store_true")

    # Spec 158 — InvoiceOps Live Bookkeeping Showcase Demo Pack
    iosc = invoiceops_sub.add_parser("showcase", help="InvoiceOps live bookkeeping showcase demo commands.")
    iosc_sub = iosc.add_subparsers(dest="iosc_command", required=True)

    iosc_status = iosc_sub.add_parser("status", help="Show showcase configuration status (no API calls).")
    iosc_status.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    iosc_status.add_argument("--config-dir", default="")
    iosc_status.add_argument("--spreadsheet-id", default="")
    iosc_status.add_argument("--json", action="store_true")

    iosc_run = iosc_sub.add_parser("run", help="Run the showcase demo (boundary mode by default; live requires confirmation).")
    iosc_run.add_argument("--profile", default="controlled_live_write")
    iosc_run.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    iosc_run.add_argument("--config-dir", default="")
    iosc_run.add_argument("--spreadsheet-id", default="")
    iosc_run.add_argument("--invoice-limit", type=int, default=0)
    iosc_run.add_argument("--live", action="store_true", help="Execute live Google Sheets writes (requires --confirm).")
    iosc_run.add_argument("--reset-sheet", action="store_true", help="Reset showcase sheet before run.")
    iosc_run.add_argument("--confirm", default="", help="Typed confirmation phrase for live execution.")
    iosc_run.add_argument("--write-report", action="store_true")
    iosc_run.add_argument("--json", action="store_true")

    iosc_setup = iosc_sub.add_parser("setup-sheet", help="Seed the showcase Google Sheet with master data (requires confirmation).")
    iosc_setup.add_argument("--profile", default="controlled_live_write")
    iosc_setup.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    iosc_setup.add_argument("--config-dir", default="")
    iosc_setup.add_argument("--spreadsheet-id", required=True)
    iosc_setup.add_argument("--confirm", required=True, help="Typed confirmation phrase.")
    iosc_setup.add_argument("--json", action="store_true")

    iosc_report = iosc_sub.add_parser("open-report", help="Open the latest showcase demo report.")
    iosc_report.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    iosc_report.add_argument("--json", action="store_true")

    # Spec 154 — Governed Live Read Proof Pack
    live_read = sub.add_parser("live-read", help="Governed live-read proof and boundary checks.")
    live_read_sub = live_read.add_subparsers(dest="live_read_command", required=True)

    lr_status = live_read_sub.add_parser("status", help="Show live-read profile status (no API calls).")
    lr_status.add_argument("--profile", default="controlled_live_read")
    lr_status.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    lr_status.add_argument("--config-dir", default="")
    lr_status.add_argument("--json", action="store_true")

    lr_proof = live_read_sub.add_parser("proof", help="Run the governed live-read proof pack.")
    lr_proof.add_argument("--profile", default="controlled_live_read")
    lr_proof.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    lr_proof.add_argument("--config-dir", default="")
    lr_proof.add_argument("--spreadsheet-range", default="Sheet1!A1:D10")
    lr_proof.add_argument("--gmail-query", default="in:inbox")
    lr_proof.add_argument("--calendar-query", default="upcoming")
    lr_proof.add_argument("--no-live-probes", action="store_true", help="Validate config/profile/tool boundaries only (no API calls).")
    lr_proof.add_argument("--write-report", action="store_true", help="Write JSON and Markdown reports to runtime_data/live_read_proof/.")
    lr_proof.add_argument("--json", action="store_true")

    lr_blocked = live_read_sub.add_parser("blocked-side-effects", help="Prove that side-effect tools are blocked (no real API calls).")
    lr_blocked.add_argument("--profile", default="controlled_live_read")
    lr_blocked.add_argument("--runtime-data-dir", default=DEFAULT_RUNTIME_DATA_DIR)
    lr_blocked.add_argument("--config-dir", default="")
    lr_blocked.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(f"taskframe-runtime {VERSION}")
        return 0
    if args.command == "ui":
        return _run_ui(args)
    if args.command == "demo":
        return _run_demo(args)
    if args.command == "golden-demo":
        return _run_golden_demo()
    if args.command == "verify":
        return _run_verify(args)
    if args.command == "validate":
        return _run_validate(args)
    if args.command == "config":
        return _run_config(args)
    if args.command == "runtime":
        return _run_runtime(args)
    if args.command == "manifest-health":
        return _run_manifest_health(args)
    if args.command == "readiness":
        return _run_readiness(args)
    if args.command == "portfolio-pack":
        return _run_portfolio_pack(args)
    if args.command == "pilot-readiness":
        return _run_pilot_readiness(args)
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
    if args.command == "readiness-gate":
        return _run_readiness_gate(args)
    if args.command == "backend-security":
        return _run_backend_security(args)
    if args.command == "safety-pack":
        return _run_safety_pack(args)
    if args.command == "tools":
        return _run_tools(args)
    if args.command == "rpa":
        return _run_rpa(args)
    if args.command == "event-sources":
        return _run_event_sources(args)
    if args.command == "events":
        return _run_events(args)
    if args.command == "profile":
        return _run_profile(args)
    if args.command == "service":
        return _run_service(args)
    if args.command == "runtime-store":
        return _run_runtime_store(args)
    if args.command == "persistence":
        return _run_persistence(args)
    if args.command == "artifacts":
        return _run_artifacts(args)
    if args.command == "monitor":
        return _run_monitor(args)
    if args.command == "recover":
        return _run_recover(args)
    if args.command == "queue":
        return _run_queue(args)
    if args.command == "schedule":
        return _run_schedule(args)
    if args.command == "worker":
        return _run_worker(args)
    if args.command == "live-side-effect":
        return _run_live_side_effect(args)
    if args.command == "invoiceops":
        return _run_invoiceops(args)
    if args.command == "live-read":
        return _run_live_read(args)
    parser.print_help()
    return 2


def _run_ui(args: argparse.Namespace) -> int:
    try:
        from src.operator_ui import build_operator_ui

        root = build_operator_ui(
            runtime_root=str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR),
            safe_start=bool(getattr(args, "safe_start", False)),
            debug_startup=bool(getattr(args, "debug_startup", False)),
        )
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
    from src.operator_cross_workflow_demo import run_cross_workflow_demo_pack
    from src.operator_scenarios import get_scenario

    if str(getattr(args, "demo_command", "run")) == "cross-workflow-v2":
        result = run_cross_workflow_demo_pack(
            pack_id="cross_workflow_business_demo_v2",
            runtime_data_dir=str(args.runtime_data_dir),
            reset_dataset=bool(args.reset_dataset),
            generate_reports=True,
            use_real_llm=False,
            allow_test_fake_llm=True,
        )
        story = result.get("story_pack_result", {}) if isinstance(result, dict) else {}
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("Cross-Workflow Business Automation Demo v2")
            print(f"Pack ID: {result.get('pack_id', '')}")
            print(f"Pack Run ID: {result.get('pack_run_id', '')}")
            print(f"Final Status: {'PASS' if result.get('ok') else 'FAIL'}")
            print(f"Story Markdown Path: {story.get('index_markdown_path', '')}")
            print(f"Story HTML Path: {story.get('index_html_path', '')}")
            print(f"Evidence Manifest Path: {story.get('evidence_manifest_path', '')}")
            if not result.get("ok"):
                error = str(result.get("error", "")).strip()
                if error:
                    print(f"Error: {error}")
        return 0 if result.get("ok") else 1

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


def _run_validate(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        str(ROOT / "tools" / "run_bounded_validation.py"),
        str(args.mode),
        "--timeout-scale",
        str(float(args.timeout_scale)),
    ]
    if bool(args.continue_on_failure):
        command.append("--continue-on-failure")
    result = subprocess.run(command, cwd=str(ROOT))
    return int(result.returncode)


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
    from runtime.runtime_environment import describe_runtime_profile, load_runtime_profile, resolve_runtime_environment

    profile = load_runtime_profile()
    environment = resolve_runtime_environment()
    payload = describe_runtime_profile(profile)
    payload.update(
        {
            "ok": True,
            "environment": environment,
            "profile_path": str((ROOT / "config" / "runtime_profile.json").resolve()),
            "source_path": payload.get("profile_path", ""),
        }
    )
    if bool(args.json):
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        return 0
    print(f"Runtime profile: {payload['profile']}")
    print(f"Runtime environment: {payload['environment']}")
    print(f"Profile source: {payload['source']}")
    print(f"Governance enforced: {str(payload['governance_enforced']).lower()}")
    print(f"Fixture mode: {str(payload['fixture_mode']).lower()}")
    print(f"Dry-run default: {str(payload['dry_run_default']).lower()}")
    print(f"Allow live reads: {str(payload['allow_live_reads']).lower()}")
    print(f"Allow live side effects: {str(payload['allow_live_side_effects']).lower()}")
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


def _run_readiness_gate(args: argparse.Namespace) -> int:
    from src.readiness_evidence_gate import build_readiness_gate, write_gate_report

    since = str(getattr(args, "since", "") or "").strip() or None
    result = build_readiness_gate(
        runtime_data_dir=str(args.runtime_data_dir),
        threshold=int(getattr(args, "threshold", 90) or 90),
        strict=bool(args.strict),
        since=since,
    )

    report_paths: dict = {}
    if bool(args.write_report):
        report_paths = write_gate_report(result, runtime_data_dir=str(args.runtime_data_dir))

    if bool(args.json):
        payload = dict(result)
        if report_paths:
            payload["report_paths"] = report_paths
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("Readiness Evidence Gate")
        print(f"Claim:          {result.get('claim', '')}")
        print(f"Verdict:        {result.get('status', '')}")
        print(f"Classification: {result.get('classification', '')}")
        print(f"Overall Score:  {result.get('overall_score', 0):.1f} (threshold: {result.get('threshold', 90)})")
        print(f"Claim Allowed:  {'Yes' if result.get('claim_allowed') else 'No'}")
        blocking = result.get("blocking_failures", [])
        if blocking:
            print(f"Blocking Failures ({len(blocking)}):")
            for bf in blocking:
                print(f"  - {bf}")
        else:
            print("Blocking Failures: none")
        warnings_list = result.get("warnings", [])
        if warnings_list:
            print(f"Warnings ({len(warnings_list)}):")
            for w in warnings_list:
                print(f"  {w}")
        if report_paths:
            print(f"Report JSON:     {report_paths.get('json_path', '')}")
            print(f"Report Markdown: {report_paths.get('markdown_path', '')}")
            print(f"Report HTML:     {report_paths.get('html_path', '')}")
        print()
        print(result.get("disclaimer", ""))

    return 0 if result.get("ok", False) else 1


def _run_backend_security(args: argparse.Namespace) -> int:
    from src.backend_security import BackendSecurityConfig, get_security_status, load_security_config

    config: BackendSecurityConfig = load_security_config()
    status = get_security_status(config, runtime_data_dir=str(args.runtime_data_dir))

    if bool(args.json):
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        ok_str = "PASS" if status.get("ok") else "FAIL"
        print(f"Backend Security Status: {ok_str}")
        print(f"Security Headers:        {'enabled' if status.get('security_headers_enabled') else 'disabled'}")
        print(f"CORS:                    {'enabled' if status.get('cors_enabled') else 'disabled'}")
        print(f"Allowed Origin Count:    {status.get('allowed_origin_count', 0)}")
        print(f"Auth Required:           {'yes' if status.get('auth_required') else 'no'}")
        print(f"Token Hash Count:        {status.get('token_hash_count', 0)}")
        print(f"Token Record Count:      {status.get('token_record_count', 0)}")
        print(f"Plaintext Dev Token:     {'allowed' if status.get('plaintext_dev_token_allowed') else 'blocked'}")
        print(f"Expired Token Count:     {status.get('expired_token_count', 0)}")
        print(f"Auth Scopes:             {status.get('known_scope_count', 0)} known, {status.get('mapped_route_count', 0)} mapped routes")
        tokens_unknown = status.get("tokens_with_unknown_scopes", 0)
        if tokens_unknown:
            print(f"Tokens w/ Unknown Scope: {tokens_unknown}")
        errors = status.get("errors", [])
        warnings_list = status.get("warnings", [])
        if errors:
            print(f"Errors ({len(errors)}):")
            for e in errors:
                print(f"  - {e}")
        if warnings_list:
            print(f"Warnings ({len(warnings_list)}):")
            for w in warnings_list:
                print(f"  - {w}")

    return 0 if status.get("ok", False) else 1


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


def _run_readiness(args: argparse.Namespace) -> int:
    from src.readiness_scorecard import build_readiness_scorecard

    result = build_readiness_scorecard(
        runtime_data_dir=str(args.runtime_data_dir),
        strict=bool(args.strict),
        threshold=int(getattr(args, "threshold", 90) or 90),
    )
    report_paths = result.get("report_paths", {}) if isinstance(result, dict) else {}
    payload = {
        "ok": bool(result.get("ok", False)),
        "status": result.get("status", ""),
        "threshold": int(result.get("threshold", 90) or 90),
        "overall_score": result.get("overall_score", 0),
        "blocking_areas": result.get("blocking_areas", []),
        "report_paths": report_paths,
        "generated_at": result.get("generated_at", ""),
        "areas": result.get("areas", {}),
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("90% Readiness Scorecard")
        print(f"Overall Score: {payload['overall_score']}")
        print(f"Threshold: {payload['threshold']}")
        print(f"Status: {payload['status']}")
        print(f"Blocking Areas: {', '.join(payload['blocking_areas']) or 'none'}")
        print(f"JSON Path: {report_paths.get('json_path', '')}")
        print(f"Markdown Path: {report_paths.get('markdown_path', '')}")
        print(f"HTML Path: {report_paths.get('html_path', '')}")
    if bool(args.open_report) and report_paths.get("html_path"):
        from src.operator_reports import open_report_html

        open_report_html(report_paths["html_path"])
    return 0 if (not bool(args.strict) or bool(result.get("ok", False))) else 1


def _run_portfolio_pack(args: argparse.Namespace) -> int:
    from src.operator_reports import open_report_html
    from src.portfolio_evidence_pack import build_portfolio_evidence_pack

    result = build_portfolio_evidence_pack(
        runtime_data_dir=str(args.runtime_data_dir),
        include_latest_story_pack=not bool(args.no_story_pack),
        include_latest_readiness_scorecard=not bool(args.no_readiness),
    )
    payload = {
        "ok": bool(result.get("ok", False)),
        "pack_id": result.get("pack_id", ""),
        "pack_run_id": result.get("pack_run_id", ""),
        "pack_dir": result.get("pack_dir", ""),
        "index_markdown_path": result.get("index_markdown_path", ""),
        "index_html_path": result.get("index_html_path", ""),
        "summary_json_path": result.get("summary_json_path", ""),
        "architecture_path": result.get("architecture_path", ""),
        "demo_script_path": result.get("demo_script_path", ""),
        "tool_inventory_path": result.get("tool_inventory_path", ""),
        "workflow_proof_path": result.get("workflow_proof_path", ""),
        "screenshot_checklist_path": result.get("screenshot_checklist_path", ""),
        "linked_artifacts": result.get("linked_artifacts", []),
        "errors": result.get("errors", []),
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("TaskFrame Runtime — Controlled Business Automation Evidence Pack")
        print(f"Pack ID: {payload['pack_id']}")
        print(f"Pack Run ID: {payload['pack_run_id']}")
        print(f"Status: {'PASS' if payload['ok'] else 'FAIL'}")
        print(f"Pack Folder: {payload['pack_dir']}")
        print(f"Index Markdown Path: {payload['index_markdown_path']}")
        print(f"Index HTML Path: {payload['index_html_path']}")
        print(f"Summary JSON Path: {payload['summary_json_path']}")
        if payload["errors"]:
            print(f"Errors: {', '.join(str(item) for item in payload['errors'])}")
    if bool(args.open) and payload.get("index_html_path"):
        open_report_html(payload["index_html_path"])
    return 0 if payload.get("ok") else 1


def _run_pilot_readiness(args: argparse.Namespace) -> int:
    from src.pilot_readiness import build_pilot_readiness_scorecard, write_pilot_evidence_pack

    runtime_data_dir = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    write_pack = bool(getattr(args, "write_pack", False))

    scorecard = build_pilot_readiness_scorecard(runtime_data_dir=runtime_data_dir)

    pack_result: dict = {}
    if write_pack:
        pack_result = write_pilot_evidence_pack(runtime_data_dir=runtime_data_dir, scorecard=scorecard)

    payload = {
        "ok": bool(scorecard.get("ok", False)),
        "status": scorecard.get("status", ""),
        "overall_score": scorecard.get("overall_score", 0),
        "threshold": scorecard.get("threshold", 80),
        "mandatory_failures": scorecard.get("mandatory_failures", []),
        "claim": scorecard.get("claim", ""),
        "generated_at": scorecard.get("generated_at", ""),
    }
    if write_pack:
        payload["pack_dir"] = pack_result.get("pack_dir", "")
        payload["pack_errors"] = pack_result.get("errors", [])

    if bool(getattr(args, "json", False)):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("TaskFrame — Controlled Pilot Readiness Gate")
        print(f"Overall Score: {payload['overall_score']}%")
        print(f"Threshold:     {payload['threshold']}%")
        print(f"Status:        {payload['status']}")
        if payload["mandatory_failures"]:
            print("Mandatory Failures:")
            for f in payload["mandatory_failures"]:
                print(f"  - {f}")
        else:
            print("Mandatory Failures: none")
        if write_pack:
            print(f"Evidence Pack: {payload.get('pack_dir', '')}")
        print("")
        print(f"Claim: {payload['claim']}")

    strict = bool(getattr(args, "strict", False))
    return 0 if (not strict or payload["ok"]) else 1


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


def _run_event_sources(args: argparse.Namespace) -> int:
    cmd = str(getattr(args, "esrc_command", "") or "")
    if cmd == "list":
        return _run_esrc_list(args)
    if cmd == "show":
        return _run_esrc_show(args)
    if cmd == "validate":
        return _run_esrc_validate(args)
    if cmd == "validate-event":
        return _run_esrc_validate_event(args)
    if cmd == "route-alignment":
        return _run_esrc_route_alignment(args)
    # Spec 139 commands
    if cmd == "status":
        return _run_esrc_status(args)
    if cmd == "list-sources":
        return _run_esrc_list_sources(args)
    if cmd == "show-source":
        return _run_esrc_show_source(args)
    if cmd == "health-check":
        return _run_esrc_health_check(args)
    if cmd == "poll":
        return _run_esrc_poll(args)
    if cmd == "poll-enabled":
        return _run_esrc_poll_enabled(args)
    if cmd == "create-fixture":
        return _run_esrc_create_fixture(args)
    if cmd == "enable":
        return _run_esrc_enable(args)
    if cmd == "disable":
        return _run_esrc_disable(args)
    if cmd == "history":
        return _run_esrc_history(args)
    print(f"Unknown event-sources command: {cmd}", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# Spec 139 — Event source polling CLI handlers
# ---------------------------------------------------------------------------

def _run_esrc_status(args: argparse.Namespace) -> int:
    from src.operator_event_sources_panel import build_event_sources_panel

    rdd = getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR)
    panel = build_event_sources_panel(runtime_data_dir=rdd)
    if args.json:
        print(json.dumps(panel, indent=2, ensure_ascii=False))
        return 0 if panel.get("ok") else 1
    summary = panel.get("summary") or {}
    print("Event Source Status")
    print(f"  Sources configured : {summary.get('source_count', 0)}")
    print(f"  Sources enabled    : {summary.get('enabled_count', 0)}")
    print(f"  Needs auth         : {summary.get('needs_auth_count', 0)}")
    print(f"  Last poll at       : {summary.get('last_poll_at', '-')}")
    if panel.get("warnings"):
        for w in panel["warnings"]:
            print(f"  WARNING: {w}")
    return 0 if panel.get("ok") else 1


def _run_esrc_list_sources(args: argparse.Namespace) -> int:
    from runtime.event_sources.event_source_state import list_event_sources

    rdd = getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR)
    sources = list_event_sources(rdd)
    payload = {"ok": True, "count": len(sources), "sources": sources}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print(f"Event Sources — {len(sources)} source(s)")
    print("")
    for s in sources:
        enabled_str = "enabled" if s.get("enabled") else "disabled"
        print(f"  {s.get('source_id', ''):<30} [{enabled_str:<8}] {s.get('adapter', ''):<15} {s.get('name', '')}")
    return 0


def _run_esrc_show_source(args: argparse.Namespace) -> int:
    from runtime.event_sources.event_source_state import get_event_source, get_event_source_state

    rdd = getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR)
    source_id = str(args.source_id or "").strip()
    config = get_event_source(source_id, rdd)
    if config is None:
        msg = {"ok": False, "error": f"Source not found: {source_id!r}"}
        if args.json:
            print(json.dumps(msg, indent=2))
        else:
            print(f"Error: {msg['error']}", file=sys.stderr)
        return 1
    state = get_event_source_state(source_id, rdd)
    payload = {"ok": True, "config": config, "state": state}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print(f"Source: {source_id}")
    for key, val in config.items():
        print(f"  {key}: {val}")
    print("State:")
    for key, val in state.items():
        print(f"  {key}: {val}")
    return 0


def _run_esrc_health_check(args: argparse.Namespace) -> int:
    from runtime.event_sources.event_source_state import get_event_source
    from runtime.event_sources.polling_engine import _get_adapter

    rdd = getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR)
    source_id = str(args.source_id or "").strip()
    config = get_event_source(source_id, rdd)
    if config is None:
        msg = {"ok": False, "error": f"Source not found: {source_id!r}"}
        if args.json:
            print(json.dumps(msg, indent=2))
        else:
            print(f"Error: {msg['error']}", file=sys.stderr)
        return 1
    adapter_id = str(config.get("adapter") or "")
    try:
        adapter = _get_adapter(adapter_id)
    except ValueError as exc:
        msg = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(msg, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1
    result = adapter.health(config, str(rdd))
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    status = result.get("status", "unknown")
    print(f"Health check for {source_id}: {status}")
    if not result.get("ok"):
        print(f"  Error: {result.get('error', '')}")
    return 0 if result.get("ok") else 1


def _run_esrc_poll(args: argparse.Namespace) -> int:
    from runtime.event_sources.polling_engine import poll_event_source

    rdd = getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR)
    source_id = str(args.source_id or "").strip()
    result = poll_event_source(source_id, rdd)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    ok_str = "OK" if result.get("ok") else "FAILED"
    print(f"Poll {source_id}: {ok_str}")
    if result.get("ok"):
        print(f"  raw_count       : {result.get('raw_count', 0)}")
        print(f"  event_count     : {result.get('event_count', 0)}")
        print(f"  enqueued_count  : {result.get('enqueued_count', 0)}")
        print(f"  duplicate_count : {result.get('duplicate_count', 0)}")
        if result.get("warnings"):
            for w in result["warnings"]:
                print(f"  WARNING: {w}")
    else:
        print(f"  Error: {result.get('error', '')}")
    return 0 if result.get("ok") else 1


def _run_esrc_poll_enabled(args: argparse.Namespace) -> int:
    from runtime.event_sources.polling_engine import poll_enabled_event_sources

    rdd = getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR)
    limit = int(getattr(args, "limit", 10) or 10)
    result = poll_enabled_event_sources(rdd, limit=limit)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    print(f"Polled {result.get('sources_polled', 0)} enabled source(s)")
    print(f"  Enqueued   : {result.get('total_enqueued', 0)}")
    print(f"  Duplicates : {result.get('total_duplicates', 0)}")
    if result.get("failed_sources"):
        print(f"  Failed     : {', '.join(result['failed_sources'])}")
    return 0 if result.get("ok") else 1


def _run_esrc_create_fixture(args: argparse.Namespace) -> int:
    from runtime.event_sources.event_source_contract import build_fixture_source_config
    from runtime.event_sources.event_source_state import create_event_source

    rdd = getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR)
    source_id = str(args.source_id or "").strip()
    config = build_fixture_source_config(
        source_id=source_id,
        name=f"Fixture: {source_id}",
        event_source="fixture_customer_inbox",
        event_type="customer_message_received",
        fixture_path="tests/fixtures/event_sources/customer_messages.json",
        enabled=True,
    )
    result = create_event_source(config, rdd)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if result.get("ok"):
        print(f"Created fixture event source: {source_id}")
    else:
        print(f"Error: {result.get('error', '')}", file=sys.stderr)
    return 0 if result.get("ok") else 1


def _run_esrc_enable(args: argparse.Namespace) -> int:
    from runtime.event_sources.event_source_state import enable_event_source

    rdd = getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR)
    source_id = str(args.source_id or "").strip()
    result = enable_event_source(source_id, rdd)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if result.get("ok"):
        print(f"Enabled: {source_id}")
    else:
        print(f"Error: {result.get('error', '')}", file=sys.stderr)
    return 0 if result.get("ok") else 1


def _run_esrc_disable(args: argparse.Namespace) -> int:
    from runtime.event_sources.event_source_state import disable_event_source

    rdd = getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR)
    source_id = str(args.source_id or "").strip()
    result = disable_event_source(source_id, rdd)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if result.get("ok"):
        print(f"Disabled: {source_id}")
    else:
        print(f"Error: {result.get('error', '')}", file=sys.stderr)
    return 0 if result.get("ok") else 1


def _run_esrc_history(args: argparse.Namespace) -> int:
    from runtime.event_sources.event_source_state import list_event_source_history

    rdd = getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR)
    source_id = str(getattr(args, "source_id", "") or "").strip()
    limit = int(getattr(args, "limit", 20) or 20)
    kwargs = {}
    if source_id:
        kwargs["source_id"] = source_id
    history = list_event_source_history(rdd, limit=limit, **kwargs)
    payload = {"ok": True, "count": len(history), "history": history}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print(f"Event Source History — {len(history)} record(s)")
    print("")
    for h in history:
        ok_str = "OK" if h.get("ok") else "FAIL"
        print(
            f"  [{ok_str}] {h.get('source_id', ''):<30} "
            f"raw={h.get('raw_count', 0)} evt={h.get('event_count', 0)} "
            f"enq={h.get('enqueued_count', 0)} dup={h.get('duplicate_count', 0)} "
            f"  {h.get('created_at', '')}"
        )
    return 0


def _run_esrc_list(args: argparse.Namespace) -> int:
    from runtime.event_source_registry import list_event_source_contracts

    contracts = list_event_source_contracts()
    payload = {"ok": True, "count": len(contracts), "contracts": contracts}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print(f"Event Source Contracts — {len(contracts)} source(s)")
    print("")
    for c in contracts:
        print(
            f"  {c.get('source_type', ''):<20} {c.get('delivery_mode', ''):<8} "
            f"side_effect={c.get('side_effect_level', ''):<8} {c.get('display_name', '')}"
        )
    return 0


def _run_esrc_show(args: argparse.Namespace) -> int:
    from runtime.event_source_registry import get_event_source_contract

    source_type = str(args.source_type or "").strip()
    contract = get_event_source_contract(source_type)
    if contract is None:
        payload = {"ok": False, "source_type": source_type, "error": f"No contract found for source '{source_type}'."}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"Contract not found: {source_type}", file=sys.stderr)
        return 1
    payload = {"ok": True, **contract}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print(f"Source Contract: {source_type}")
    print(f"  Display Name:       {contract.get('display_name', '')}")
    print(f"  Description:        {contract.get('description', '')}")
    print(f"  Delivery Mode:      {contract.get('delivery_mode', '')}")
    print(f"  Side Effect Level:  {contract.get('side_effect_level', '')}")
    print(f"  Required Payload:   {', '.join(contract.get('required_payload_fields', [])) or '(none)'}")
    print(f"  Optional Payload:   {', '.join(contract.get('optional_payload_fields', [])) or '(none)'}")
    print(f"  Allowed Event Types: {', '.join(contract.get('allowed_event_types', [])) or '(any)'}")
    return 0


def _run_esrc_validate(args: argparse.Namespace) -> int:
    from runtime.event_source_registry import validate_all_event_source_contracts

    result = validate_all_event_source_contracts()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    print(f"Event Source Contracts Validation: {'PASS' if result.get('ok') else 'FAIL'}")
    print(f"  Contracts checked: {result.get('count', 0)}")
    if result.get("missing_builtin_sources"):
        print(f"  Missing built-in sources: {', '.join(result['missing_builtin_sources'])}")
    for r in result.get("results", []):
        status = "PASS" if r.get("ok") else "FAIL"
        print(f"  {r.get('source_type', '')}: {status}")
        for err in r.get("errors", []):
            print(f"    Error: {err}")
    return 0 if result.get("ok") else 1


def _run_esrc_validate_event(args: argparse.Namespace) -> int:
    from runtime.event_source_registry import validate_event_against_source_contract

    try:
        event = json.loads(str(args.event_json or "{}"))
    except json.JSONDecodeError as exc:
        payload = {"ok": False, "errors": [f"Invalid JSON: {exc}"]}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"Invalid event JSON: {exc}", file=sys.stderr)
        return 1

    result = validate_event_against_source_contract(event)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    status = "PASS" if result.get("ok") else "FAIL"
    print(f"Event Source Contract Validation: {status}")
    print(f"  Source: {result.get('source_type', '')}")
    print(f"  Contract found: {str(result.get('contract_found', False)).lower()}")
    for err in result.get("errors", []):
        print(f"  Error: {err}")
    for w in result.get("warnings", []):
        print(f"  Warning: {w}")
    return 0 if result.get("ok") else 1


def _run_esrc_route_alignment(args: argparse.Namespace) -> int:
    from runtime.event_source_route_alignment import validate_event_source_route_alignment

    routes_path = str(getattr(args, "routes_path", "config/event_routes.json") or "config/event_routes.json")
    result = validate_event_source_route_alignment(routes_path=Path(routes_path) if routes_path else None)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    ok_str = "PASS" if result.get("ok") else "FAIL"
    print(f"Route-Contract Alignment: {ok_str}")
    print(f"  Routes checked:    {result.get('route_count', 0)}")
    print(f"  Contracts loaded:  {result.get('contract_count', 0)}")
    if result.get("mismatches"):
        print(f"  Mismatches:")
        for m in result["mismatches"]:
            print(f"    [{m.get('status', '')}] {m.get('route_id', '')}: {m.get('message', '')}")
    if result.get("unused_contracts"):
        print(f"  Unused contracts: {', '.join(result['unused_contracts'])}")
    if result.get("warnings"):
        for w in result["warnings"]:
            print(f"  Warning: {w}")
    return 0 if result.get("ok") else 1


def _run_events(args: argparse.Namespace) -> int:
    cmd = str(args.events_command or "")
    if cmd == "list":
        return _run_events_list(args)
    if cmd == "show":
        return _run_events_show(args)
    if cmd == "replay-dry-run":
        return _run_events_replay_dry_run(args)
    print(f"Unknown events command: {cmd}", file=sys.stderr)
    return 2


def _run_events_list(args: argparse.Namespace) -> int:
    from runtime.event_queue_inspector import list_event_queue

    result = list_event_queue(
        runtime_data_dir=args.runtime_data_dir,
        status=str(args.status or "") or None,
        source=str(args.source or "") or None,
        event_type=str(args.event_type or "") or None,
        limit=int(args.limit or 100),
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0

    events = result.get("events") or []
    print(f"Event Queue — {result.get('count', 0)} event(s)")
    print("")
    if not events:
        print("No events found.")
        return 0

    print(f"{'Received At':<26}  {'Event ID':<38}  {'Source':<20}  {'Event Type':<30}  {'Status':<24}  {'Route':<20}  {'Frame'}")
    print("-" * 180)
    for ev in events:
        print(
            f"{str(ev.get('received_at', ''))[:26]:<26}  "
            f"{str(ev.get('event_id', '')):<38}  "
            f"{str(ev.get('source', '')):<20}  "
            f"{str(ev.get('event_type', '')):<30}  "
            f"{str(ev.get('status', '')):<24}  "
            f"{str(ev.get('route_id') or ''):<20}  "
            f"{str(ev.get('linked_frame_id') or '')}"
        )
    return 0


def _run_events_show(args: argparse.Namespace) -> int:
    from runtime.event_queue_inspector import get_event_detail

    result = get_event_detail(args.event_id, runtime_data_dir=args.runtime_data_dir)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0 if result.get("ok") else 1

    if not result.get("ok"):
        print(f"Event not found: {args.event_id}", file=sys.stderr)
        return 1

    qr = result.get("queue_record") or result.get("event_record") or {}
    fr = result.get("failure_reason") or {}
    print(f"Event Detail: {args.event_id}")
    print("")
    print(f"  Source:         {qr.get('source', '')}")
    print(f"  Event Type:     {qr.get('event_type', '')}")
    print(f"  Status:         {qr.get('status', '')}")
    print(f"  Route:          {result.get('route_id') or '—'}")
    print(f"  Manifest:       {result.get('manifest_id') or '—'}")
    print(f"  Linked Frame:   {result.get('linked_frame_id') or '—'}")
    print(f"  Frame State:    {result.get('frame_state') or '—'}")
    print(f"  Received At:    {qr.get('received_at', '')}")
    print(f"  Attempt Count:  {qr.get('attempt_count', 0)}")
    if fr.get("failure_code"):
        print(f"  Failure Code:   {fr['failure_code']}")
        print(f"  Failure Reason: {fr['failure_reason']}")
    errors = result.get("errors") or []
    if errors:
        print(f"  Errors:")
        for e in errors:
            print(f"    - {e}")
    replay_history = result.get("replay_history") or []
    if replay_history:
        print(f"  Replay History:")
        for h in replay_history:
            print(f"    Attempt {h.get('attempt')}: {h.get('status')} — frame={h.get('replay_frame_id')} at {h.get('replayed_at')}")
    payload = qr.get("payload") or {}
    if payload:
        print(f"  Payload:")
        print(f"    {json.dumps(payload, indent=4, ensure_ascii=False)[:500]}")
    return 0


def _run_events_replay_dry_run(args: argparse.Namespace) -> int:
    from runtime.event_queue import replay_event_dry_run

    result = replay_event_dry_run(
        args.event_id,
        runtime_data_dir=args.runtime_data_dir,
        manifest_dir=args.manifest_dir,
        replayed_by=str(args.replayed_by or "operator"),
        reason=str(args.reason or ""),
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0 if result.get("ok") else 1

    ok = result.get("ok", False)
    print(f"Replay Dry-Run: {'OK' if ok else 'FAILED'}")
    print(f"  Event ID:       {result.get('event_id', '')}")
    print(f"  Status:         {result.get('status', '')}")
    print(f"  Original Frame: {result.get('original_frame_id') or '—'}")
    print(f"  Replay Frame:   {result.get('replay_frame_id') or '—'}")
    print(f"  Manifest:       {result.get('manifest_id') or '—'}")
    errors = result.get("errors") or []
    if errors:
        print(f"  Errors:")
        for e in errors:
            print(f"    - {e}")
    return 0 if ok else 1


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


def _run_profile(args: argparse.Namespace) -> int:
    command = str(getattr(args, "profile_command", "") or "")
    if command == "show":
        return _run_profile_show(args)
    if command == "list":
        return _run_profile_list(args)
    if command == "check":
        return _run_profile_check(args)
    if command == "controlled-live-status":
        return _run_controlled_live_status(args)
    print("Unknown profile command.", file=sys.stderr)
    return 2


def _run_profile_show(args: argparse.Namespace) -> int:
    from runtime.runtime_environment import describe_runtime_profile, load_runtime_profile

    runtime_data_dir = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    profile_name = str(getattr(args, "profile", "") or "") or None
    config_dir = str(getattr(args, "config_dir", "") or "") or None
    profile = load_runtime_profile(profile_name=profile_name, path=ROOT / "config" / "runtime_profile.json" if not config_dir else Path(config_dir) / "runtime_profile.json")
    payload = describe_runtime_profile(profile)
    payload.update(
        {
            "ok": True,
            "runtime_data_dir": runtime_data_dir,
            "source_path": payload.get("profile_path", ""),
        }
    )
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print(f"Active profile: {payload['profile']}")
    print(f"Source: {payload['source']}")
    print(f"Runtime data dir: {runtime_data_dir}")
    print(f"Fixture mode: {str(payload['fixture_mode']).lower()}")
    print(f"Live reads: {str(payload['allow_live_reads']).lower()}")
    print(f"Live side effects: {str(payload['allow_live_side_effects']).lower()}")
    print(f"Allowed toolpacks: {', '.join(payload.get('allowed_toolpacks', [])) or '(none)'}")
    print(f"Blocked tool classes: {', '.join(payload.get('blocked_tool_classes', [])) or '(none)'}")
    print(f"Safe for demo: {str(payload['safe_for_demo']).lower()}")
    print(f"Safe for pilot: {str(payload['safe_for_pilot']).lower()}")
    print(f"Safe for release: {str(payload['safe_for_release']).lower()}")
    return 0


def _run_profile_list(args: argparse.Namespace) -> int:
    from runtime.runtime_environment import list_runtime_profiles

    payload = {"ok": True, "profiles": list_runtime_profiles()}
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print("Runtime Profiles")
    print("")
    for item in payload["profiles"]:
        print(
            f"  {item['profile']:<8} fixture={str(item['fixture_mode']).lower():<5} "
            f"dry_run={str(item['dry_run_default']).lower():<5} "
            f"live_reads={str(item['allow_live_reads']).lower():<5} "
            f"side_effects={str(item['allow_live_side_effects']).lower():<5} "
            f"demo={str(item['safe_for_demo']).lower():<5} "
            f"pilot={str(item['safe_for_pilot']).lower():<5} "
            f"release={str(item['safe_for_release']).lower():<5}"
        )
    return 0


def _run_profile_check(args: argparse.Namespace) -> int:
    from runtime.runtime_environment import check_runtime_profile, load_runtime_profile

    profile_name = str(getattr(args, "profile", "") or "") or None
    config_dir = str(getattr(args, "config_dir", "") or "") or None
    profile = load_runtime_profile(profile_name=profile_name, path=ROOT / "config" / "runtime_profile.json" if not config_dir else Path(config_dir) / "runtime_profile.json")
    result = check_runtime_profile(profile)
    if bool(args.json):
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    print(f"Active profile: {result['profile']}")
    print(f"Source: {result['source']}")
    print(f"Fixture mode: {str(result['fixture_mode']).lower()}")
    print(f"Live reads: {str(result['allow_live_reads']).lower()}")
    print(f"Live side effects: {str(result['allow_live_side_effects']).lower()}")
    print(f"Allowed toolpacks: {', '.join(result.get('allowed_toolpacks', [])) or '(none)'}")
    print(f"Blocked tool classes: {', '.join(result.get('blocked_tool_classes', [])) or '(none)'}")
    print(f"Safe for demo: {str(result['safe_for_demo']).lower()}")
    print(f"Safe for pilot: {str(result['safe_for_pilot']).lower()}")
    print(f"Safe for release: {str(result['safe_for_release']).lower()}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"  - {blocker.get('message', '')}")
    return 0 if result.get("ok") else 1


def _run_service(args: argparse.Namespace) -> int:
    command = str(getattr(args, "service_command", "") or "")
    if command == "preflight":
        return _run_service_preflight(args)
    if command == "status":
        return _run_service_status(args)
    if command == "run-once":
        return _run_service_run_once(args)
    print("Unknown service command.", file=sys.stderr)
    return 2


def _service_paths(args: argparse.Namespace) -> dict[str, Any]:
    profile_name = str(getattr(args, "profile", "service") or "service")
    config_dir = str(getattr(args, "config_dir", "") or "") or None
    runtime_data_dir = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    manifest_dir = str(getattr(args, "manifest_dir", "manifests") or "manifests")
    routes_path = str(getattr(args, "routes_path", "config/event_routes.json") or "config/event_routes.json")
    toolpack_config_path = str(getattr(args, "toolpack_config_path", "config/examples/taskframe.service.toolpacks.example.json") or "config/examples/taskframe.service.toolpacks.example.json")
    return {
        "profile_name": profile_name,
        "config_dir": config_dir,
        "runtime_data_dir": runtime_data_dir,
        "manifest_dir": manifest_dir,
        "routes_path": routes_path,
        "toolpack_config_path": toolpack_config_path,
    }


def _run_service_preflight(args: argparse.Namespace) -> int:
    from runtime.service_runtime import build_service_preflight, write_service_preflight_report

    paths = _service_paths(args)
    try:
        result = build_service_preflight(**paths)
        report_paths = write_service_preflight_report(result, runtime_data_dir=paths["runtime_data_dir"])
        result["report_paths"] = report_paths
    except Exception as exc:
        result = {"ok": False, "profile": paths["profile_name"], "worker_identity": {}, "checks": [], "blockers": [{"id": "service_preflight_failed", "message": str(exc)}], "warnings": []}
    if bool(args.json):
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    print(f"Service preflight: {'PASS' if result.get('ok') else 'FAIL'}")
    print(f"Profile: {result.get('profile', '')}")
    worker_identity = result.get("worker_identity") or {}
    if worker_identity:
        print(f"Worker ID: {worker_identity.get('worker_id', '')}")
        print(f"Runtime instance ID: {worker_identity.get('runtime_instance_id', '')}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"  - {blocker.get('message', '')}")
    return 0 if result.get("ok") else 1


def _run_service_status(args: argparse.Namespace) -> int:
    from runtime.service_runtime import build_service_status, write_service_status_report

    paths = _service_paths(args)
    try:
        result = build_service_status(**paths)
        report_paths = write_service_status_report(result, runtime_data_dir=paths["runtime_data_dir"])
        result["report_paths"] = report_paths
    except Exception as exc:
        result = {"ok": False, "error": str(exc), "profile": paths["profile_name"], "worker_identity": {}, "enabled_toolpacks": [], "last_worker_cycle": {}, "latest_monitoring_snapshot": {}, "latest_recovery_summary": {}}
    if bool(args.json):
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    print(f"Service profile: {result.get('profile', '')}")
    print(f"Runtime data dir: {result.get('runtime_data_dir', '')}")
    worker_identity = result.get("worker_identity") or {}
    print(f"Worker ID: {worker_identity.get('worker_id', '')}")
    print(f"Live reads: {result.get('live_read_status', '')}")
    print(f"Live side effects: {result.get('live_side_effect_status', '')}")
    print(f"Enabled toolpacks: {', '.join(result.get('enabled_toolpacks', [])) or '(none)'}")
    last_cycle = result.get("last_worker_cycle") or {}
    if last_cycle:
        print(f"Last worker cycle: {last_cycle.get('cycle_id', '')} ({last_cycle.get('ok', False)})")
    return 0


def _run_service_run_once(args: argparse.Namespace) -> int:
    from runtime.service_runtime import run_service_once

    paths = _service_paths(args)
    try:
        result = run_service_once(
            profile_name=paths["profile_name"],
            runtime_data_dir=paths["runtime_data_dir"],
            config_dir=paths["config_dir"],
            manifest_dir=paths["manifest_dir"],
            routes_path=paths["routes_path"],
            toolpack_config_path=paths["toolpack_config_path"],
            queue_limit=int(getattr(args, "queue_limit", 10)),
            no_scheduler=bool(getattr(args, "no_scheduler", False)),
            no_event_sources=bool(getattr(args, "no_event_sources", False)),
        )
    except Exception as exc:
        result = {"ok": False, "error": str(exc), "profile": paths["profile_name"], "worker_identity": {}, "preflight": {}, "worker_cycle": {}, "service_cycle_record_path": ""}
    if bool(args.json):
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    print(f"Service run-once: {'OK' if result.get('ok') else 'FAIL'}")
    worker_identity = result.get("worker_identity") or {}
    print(f"Worker ID: {worker_identity.get('worker_id', '')}")
    worker_cycle = result.get("worker_cycle") or {}
    if worker_cycle:
        print(f"Cycle ID: {worker_cycle.get('cycle_id', '')}")
        print(f"Queue processed: {worker_cycle.get('queue_items_processed', 0)}")
    if result.get("service_cycle_record_path"):
        print(f"Service cycle record: {result.get('service_cycle_record_path')}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"  - {blocker.get('message', '')}")
    return 0 if result.get("ok") else 1


def _run_runtime_store(args: argparse.Namespace) -> int:
    command = str(getattr(args, "runtime_store_command", "") or "")
    if command == "status":
        return _run_runtime_store_status(args)
    if command == "locks":
        return _run_runtime_store_locks(args)
    if command == "cleanup-locks":
        return _run_runtime_store_cleanup_locks(args)
    if command == "check":
        return _run_runtime_store_check(args)
    if command == "index":
        return _run_runtime_store_index(args)
    if command == "backup":
        return _run_runtime_store_backup(args)
    if command == "restore":
        return _run_runtime_store_restore(args)
    if command == "retention-plan":
        return _run_runtime_store_retention_plan(args)
    if command == "cleanup":
        return _run_runtime_store_cleanup(args)
    print("Unknown runtime-store command.", file=sys.stderr)
    return 2


def _runtime_store_profile_name() -> str:
    try:
        from runtime.runtime_environment import load_runtime_profile

        profile = load_runtime_profile()
        return str(profile.get("profile", "") or "demo")
    except Exception:
        return "demo"


def _run_runtime_store_status(args: argparse.Namespace) -> int:
    from runtime.runtime_store import load_runtime_store_index, validate_runtime_store

    payload = validate_runtime_store(args.runtime_data_dir, manifest_dir=args.manifest_dir)
    index = load_runtime_store_index(args.runtime_data_dir)
    active_locks = payload.get("active_locks", [])
    expired_locks = payload.get("expired_locks", [])
    output = {
        "ok": bool(payload.get("ok", False)),
        "runtime_data_dir": str(args.runtime_data_dir),
        "artifact_counts": payload.get("artifact_counts", {}),
        "index_runtime_version": int(index.get("runtime_version", 1) or 1),
        "taskframes_indexed": len(payload.get("taskframes", [])),
        "locks_active": len(active_locks),
        "locks_expired": len(expired_locks),
        "versioned_artifacts": int(payload.get("versioned_artifacts", 0) or 0),
        "warnings": [issue.get("message", "") for issue in payload.get("issues", []) if issue.get("severity") == "warning"],
    }
    if bool(args.json):
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print("Runtime Store: PASS" if output["ok"] else "Runtime Store: FAIL")
        print(f"TaskFrames indexed: {output['taskframes_indexed']}")
        print(f"Locks active: {output['locks_active']}")
        print(f"Expired locks: {output['locks_expired']}")
        print(f"Versioned artifacts: {output['versioned_artifacts']}")
        warnings = output["warnings"]
        print(f"Warnings: {', '.join(warnings) if warnings else 'none'}")
    return 0 if output["ok"] else 1


def _run_runtime_store_locks(args: argparse.Namespace) -> int:
    from runtime.runtime_locking import list_runtime_locks, _lock_is_expired

    locks = list_runtime_locks(args.runtime_data_dir)
    active = []
    expired = []
    for record in locks:
        if _lock_is_expired(record):
            expired.append(record)
            continue
        active.append(record)
    payload = {"ok": True, "locks": locks, "active_count": len(active), "expired_count": len(expired)}
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("Runtime Store Locks")
        print(f"Active locks: {len(active)}")
        print(f"Expired locks: {len(expired)}")
        for record in locks:
            print(f"- {record.get('resource_key', '')} ({record.get('lock_id', '')})")
    return 0


def _run_runtime_store_cleanup_locks(args: argparse.Namespace) -> int:
    from runtime.runtime_locking import cleanup_expired_runtime_locks

    payload = cleanup_expired_runtime_locks(args.runtime_data_dir)
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("Runtime Store Cleanup Locks")
        print(f"Removed: {len(payload.get('removed', []))}")
        print(f"Active: {payload.get('active_count', 0)}")
    return 0


def _run_runtime_store_check(args: argparse.Namespace) -> int:
    from runtime.errors import RuntimeStoreError
    from runtime.runtime_store import validate_runtime_store

    try:
        payload = validate_runtime_store(args.runtime_data_dir, manifest_dir=args.manifest_dir)
    except RuntimeStoreError as exc:
        payload = {"ok": False, "error": str(exc), "runtime_data_dir": str(args.runtime_data_dir), "artifact_counts": {}, "issues": []}
    payload["ok"] = bool(payload.get("ok", False))
    payload["active_profile"] = _runtime_store_profile_name()
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("Runtime Store Check")
        print(f"Runtime data dir: {payload.get('runtime_data_dir', '')}")
        print(f"Ok: {str(payload.get('ok', False)).lower()}")
        print(f"TaskFrames: {payload.get('artifact_counts', {}).get('taskframes', 0)}")
        print(f"Reports: {payload.get('artifact_counts', {}).get('reports', 0)}")
        print(f"Approval packs: {payload.get('artifact_counts', {}).get('approval_packs', 0)}")
        print(f"Evidence: {payload.get('artifact_counts', {}).get('evidence', 0)}")
        print("Live data protected: true")
        if payload.get("issues"):
            print("Issues:")
            for issue in payload["issues"]:
                print(f"- {issue.get('category', '')}: {issue.get('message', '')}")
    return 0 if payload.get("ok") else 1


def _run_runtime_store_index(args: argparse.Namespace) -> int:
    from runtime.errors import RuntimeStoreError
    from runtime.runtime_store import rebuild_runtime_store_index

    try:
        payload = rebuild_runtime_store_index(args.runtime_data_dir, manifest_dir=args.manifest_dir, persist=True)
    except RuntimeStoreError as exc:
        payload = {"ok": False, "error": str(exc), "artifact_counts": {}}
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("Runtime Store Index")
        print(f"Index path: {Path(args.runtime_data_dir) / 'indexes' / 'runtime_store_index.json'}")
        print(f"Ok: {str(payload.get('ok', False)).lower()}")
        print(f"TaskFrames: {payload.get('artifact_counts', {}).get('taskframes', 0)}")
    return 0 if payload.get("ok") else 1


def _run_runtime_store_backup(args: argparse.Namespace) -> int:
    from runtime.errors import RuntimeStoreError
    from runtime.runtime_store import backup_runtime_store

    try:
        payload = backup_runtime_store(args.runtime_data_dir, manifest_dir=args.manifest_dir)
    except RuntimeStoreError as exc:
        payload = {"ok": False, "error": str(exc), "manifest": {}}
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("Runtime Store Backup")
        print(f"Backup path: {payload.get('backup_path', '')}")
        print(f"Manifest path: {payload.get('manifest_path', '')}")
        print(f"Contains pending actions: {str(payload.get('manifest', {}).get('contains_pending_actions', False)).lower()}")
    return 0 if payload.get("ok") else 1


def _run_runtime_store_restore(args: argparse.Namespace) -> int:
    from runtime.errors import RuntimeStoreError
    from runtime.runtime_store import restore_runtime_store_backup

    try:
        payload = restore_runtime_store_backup(args.backup, args.target, validate_only=bool(args.validate_only), manifest_dir=args.manifest_dir)
    except RuntimeStoreError as exc:
        payload = {"ok": False, "error": str(exc), "backup_path": str(args.backup), "target_path": str(args.target), "validate_only": bool(args.validate_only)}
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("Runtime Store Restore")
        print(f"Backup: {payload.get('backup_path', '')}")
        print(f"Target: {payload.get('target_path', '')}")
        print(f"Validate only: {str(payload.get('validate_only', False)).lower()}")
        print(f"Ok: {str(payload.get('ok', False)).lower()}")
    return 0 if payload.get("ok") else 1


def _run_runtime_store_retention_plan(args: argparse.Namespace) -> int:
    from runtime.errors import RuntimeStoreError
    from runtime.runtime_store import build_runtime_store_retention_plan

    try:
        payload = build_runtime_store_retention_plan(args.runtime_data_dir, manifest_dir=args.manifest_dir)
    except RuntimeStoreError as exc:
        payload = {"ok": False, "error": str(exc), "candidate_count": 0, "protected_count": 0}
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("Runtime Store Retention Plan")
        print(f"Dry run: {str(payload.get('dry_run', True)).lower()}")
        print(f"Candidate count: {payload.get('candidate_count', 0)}")
        print(f"Protected count: {payload.get('protected_count', 0)}")
    return 0


def _run_runtime_store_cleanup(args: argparse.Namespace) -> int:
    from runtime.errors import RuntimeStoreError
    from runtime.runtime_store import cleanup_runtime_store

    try:
        payload = cleanup_runtime_store(args.runtime_data_dir, manifest_dir=args.manifest_dir, dry_run=bool(args.dry_run))
    except RuntimeStoreError as exc:
        payload = {"ok": False, "error": str(exc), "candidate_count": 0, "protected_count": 0, "cleanup_performed": False, "dry_run": True}
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("Runtime Store Cleanup")
        print(f"Dry run: {str(payload.get('dry_run', True)).lower()}")
        print(f"Candidate count: {payload.get('candidate_count', 0)}")
        print(f"Cleanup performed: {str(payload.get('cleanup_performed', False)).lower()}")
    return 0


def _run_persistence(args: argparse.Namespace) -> int:
    from runtime.persistence_backends.migration import (
        init_persistence,
        migrate_json_to_sqlite,
        persistence_status,
        verify_persistence,
    )

    command = str(getattr(args, "persistence_command", "") or "")
    runtime_data_dir = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    if command == "status":
        payload = persistence_status(runtime_data_dir)
    elif command == "init":
        payload = init_persistence(runtime_data_dir)
    elif command == "migrate-json":
        payload = migrate_json_to_sqlite(runtime_data_dir)
    elif command == "verify":
        payload = verify_persistence(runtime_data_dir)
    else:
        print("Unknown persistence command.", file=sys.stderr)
        return 2

    if bool(getattr(args, "json", False)):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("ok", False) else 1

    print("TaskFrame Persistence")
    print(f"Backend: {payload.get('active_backend', payload.get('backend', 'filesystem'))}")
    if payload.get("sqlite_path"):
        print(f"SQLite path: {payload.get('sqlite_path')}")
    if "db_exists" in payload:
        print(f"DB exists: {str(payload.get('db_exists')).lower()}")
    if "schema_version" in payload:
        print(f"Schema version: {payload.get('schema_version')}")
    for key, label in (
        ("taskframe_count", "TaskFrames"),
        ("event_count", "Events"),
        ("run_ledger_count", "Run ledger records"),
        ("last_write_timestamp", "Last write"),
    ):
        if key in payload:
            print(f"{label}: {payload.get(key)}")
    if payload.get("migrated"):
        print(f"Migrated: {json.dumps(payload.get('migrated'), sort_keys=True)}")
    if payload.get("warnings"):
        print("Warnings:")
        for warning in payload.get("warnings", []):
            print(f"- {warning}")
    if payload.get("error"):
        print(f"Error: {payload.get('error')}")
    return 0 if payload.get("ok", False) else 1


def _run_monitor(args: argparse.Namespace) -> int:
    command = str(getattr(args, "monitor_command", "") or "")
    if command == "snapshot":
        return _run_monitor_snapshot(args)
    if command == "alerts":
        return _run_monitor_alerts(args)
    if command == "summary":
        return _run_monitor_summary(args)
    if command == "failed":
        return _run_monitor_filtered(args, "failed")
    if command == "pending":
        return _run_monitor_filtered(args, "pending")
    if command == "stuck":
        return _run_monitor_filtered(args, "stuck")
    if command == "blocked":
        return _run_monitor_filtered(args, "blocked")
    if command == "tools":
        return _run_monitor_tools(args)
    if command == "report":
        return _run_monitor_report(args)
    print("Unknown monitor command.", file=sys.stderr)
    return 2


def _build_monitoring_snapshot_payload(args: argparse.Namespace, *, write_report: bool = False) -> dict[str, Any]:
    from runtime.monitoring_snapshot import build_monitoring_snapshot

    runtime_data_dir = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    profile = str(getattr(args, "profile", "service") or "service")
    payload = build_monitoring_snapshot(
        runtime_data_dir=runtime_data_dir,
        profile_name=profile,
        threshold_failed_frames=int(getattr(args, "threshold_failed_frames", 10) or 10),
        heartbeat_stale_seconds=int(getattr(args, "heartbeat_stale_seconds", 600) or 600),
        max_cycle_duration_ms=int(getattr(args, "max_cycle_duration_ms", 1000) or 1000),
        write_report=write_report or bool(getattr(args, "write_report", False)),
    )
    payload["runtime_data_dir"] = runtime_data_dir
    payload["profile"] = profile
    return payload


def _run_monitor_snapshot(args: argparse.Namespace) -> int:
    payload = _build_monitoring_snapshot_payload(args, write_report=bool(getattr(args, "write_report", False)))
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("ok", True) else 1
    print("Operational Monitoring Snapshot")
    print(f"Status: {payload.get('status', 'UNKNOWN')}")
    print(f"Profile: {payload.get('profile', '')}")
    print(f"Generated at: {payload.get('generated_at', '')}")
    print(f"Blockers: {len(payload.get('blockers', []))}")
    print(f"Warnings: {len(payload.get('warnings', []))}")
    print(f"Alert candidates: {len(payload.get('alert_candidates', []))}")
    for candidate in payload.get("alert_candidates", [])[:5]:
        if isinstance(candidate, dict):
            print(f"- [{candidate.get('severity', '')}] {candidate.get('title', '')}")
    if payload.get("report_paths"):
        print(f"Report: {payload.get('report_paths', {}).get('snapshot_json', '')}")
    return 0 if payload.get("ok", True) else 1


def _run_monitor_alerts(args: argparse.Namespace) -> int:
    payload = _build_monitoring_snapshot_payload(args, write_report=bool(getattr(args, "write_report", False)))
    result = {
        "ok": bool(payload.get("ok", True)),
        "profile": payload.get("profile", ""),
        "generated_at": payload.get("generated_at", ""),
        "alert_candidates": list(payload.get("alert_candidates", [])),
        "blockers": list(payload.get("blockers", [])),
        "warnings": list(payload.get("warnings", [])),
        "report_paths": payload.get("report_paths", {}) if bool(getattr(args, "write_report", False)) else {},
    }
    if bool(args.json):
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok", True) else 1
    print("Operational Monitoring Alert Candidates")
    print(f"Status: {payload.get('status', 'UNKNOWN')}")
    for candidate in result.get("alert_candidates", [])[:10]:
        if isinstance(candidate, dict):
            print(f"- [{candidate.get('severity', '')}] {candidate.get('title', '')}: {candidate.get('message', '')}")
    if not result.get("alert_candidates"):
        print("(none)")
    return 0 if result.get("ok", True) else 1


def _build_monitoring_payload(args: argparse.Namespace) -> dict[str, Any]:
    from runtime.operational_monitoring import aggregate_tool_health, build_monitoring_summary

    runtime_data_dir = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    profile = str(getattr(args, "profile", "") or "") or None
    limit = int(getattr(args, "limit", 20) or 20)
    rebuild = bool(getattr(args, "rebuild", False))
    summary = build_monitoring_summary(runtime_data_dir, profile_name=profile, limit=limit, rebuild=rebuild)
    summary["tool_health"] = aggregate_tool_health(runtime_data_dir, refresh=rebuild)
    summary["runtime_data_dir"] = runtime_data_dir
    summary["profile"] = profile or summary.get("profile", "demo")
    summary["limit"] = limit
    summary["rebuild"] = rebuild
    return summary


def _run_monitor_summary(args: argparse.Namespace) -> int:
    payload = _build_monitoring_payload(args)
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    print("Operational Monitoring Summary")
    print(f"Runtime data dir: {payload.get('runtime_data_dir', '')}")
    print(f"Profile: {payload.get('profile', '')}")
    print(f"Total indexed runs: {summary.get('total_indexed_runs', 0)}")
    print(f"Healthy count: {summary.get('healthy_count', 0)}")
    print(f"Pending count: {summary.get('pending_count', 0)}")
    print(f"Warning count: {summary.get('warning_count', 0)}")
    print(f"Failed count: {summary.get('failed_count', 0)}")
    print(f"Stuck count: {summary.get('stuck_count', 0)}")
    print(f"Blocked count: {summary.get('blocked_count', 0)}")
    print(f"Tool health status: {payload.get('tool_health', {}).get('status', 'unknown')}")
    print(f"Runtime store validation status: {payload.get('runtime_store_status', {}).get('ok', False)}")
    print(f"Live-read readiness status: {payload.get('live_read_readiness', {}).get('status', 'blocked')}")
    newest = payload.get("newest_failure", {}) if isinstance(payload.get("newest_failure", {}), dict) else {}
    oldest = payload.get("oldest_pending_approval", {}) if isinstance(payload.get("oldest_pending_approval", {}), dict) else {}
    print(f"Newest failure: {newest.get('frame_id', '') or 'none'}")
    print(f"Oldest pending approval: {oldest.get('frame_id', '') or 'none'}")
    return 0


def _run_monitor_filtered(args: argparse.Namespace, health: str) -> int:
    payload = _build_monitoring_payload(args)
    key_map = {
        "failed": "latest_failed_runs",
        "pending": "latest_pending_runs",
        "stuck": "latest_stuck_runs",
        "blocked": "latest_blocked_runs",
    }
    rows = list(payload.get(key_map[health], [])) if isinstance(payload.get(key_map[health], []), list) else []
    result = {
        "ok": True,
        "health": health,
        "runtime_data_dir": payload.get("runtime_data_dir", ""),
        "profile": payload.get("profile", ""),
        "limit": payload.get("limit", 20),
        "runs": rows,
    }
    if bool(args.json):
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print(f"Operational Monitoring: {health.title()}")
    for row in rows[: int(payload.get("limit", 20) or 20)]:
        print(
            f"- {row.get('frame_id', '')} | manifest={row.get('manifest_id', '')} | state={row.get('state', '')} | "
            f"health={row.get('health', '')} | {row.get('failure_category', row.get('stale_warning', ''))} | "
            f"{row.get('recommended_action', '')} | {row.get('report_path', '')}"
        )
    if not rows:
        print("(none)")
    return 0


def _run_monitor_tools(args: argparse.Namespace) -> int:
    payload = _build_monitoring_payload(args)
    tool_health = payload.get("tool_health", {}) if isinstance(payload.get("tool_health", {}), dict) else {}
    if bool(args.json):
        print(json.dumps(tool_health, indent=2, ensure_ascii=False))
        return 0
    print("Tool Health")
    print(f"Status: {tool_health.get('status', 'unknown')}")
    summary = tool_health.get("summary", {}) if isinstance(tool_health.get("summary", {}), dict) else {}
    for key in ("total", "ready", "needs_auth", "missing_dependency", "misconfigured", "failing", "disabled_optional", "unknown"):
        print(f"{key.replace('_', ' ').title()}: {summary.get(key, 0)}")
    if tool_health.get("recommended_action"):
        print(f"Recommended action: {tool_health.get('recommended_action', '')}")
    return 0


def _run_monitor_report(args: argparse.Namespace) -> int:
    from runtime.operational_monitoring import build_operational_monitoring_report

    runtime_data_dir = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    profile = str(getattr(args, "profile", "") or "") or None
    limit = int(getattr(args, "limit", 20) or 20)
    rebuild = bool(getattr(args, "rebuild", False))
    report = build_operational_monitoring_report(runtime_data_dir, profile_name=profile, limit=limit, rebuild=rebuild)
    if bool(args.json):
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    print("Operational Monitoring Report")
    print(f"JSON: {report.get('json_path', '')}")
    print(f"Markdown: {report.get('markdown_path', '')}")
    print(f"HTML: {report.get('html_path', '')}")
    return 0


def _run_recover(args: argparse.Namespace) -> int:
    command = str(getattr(args, "recover_command", "") or "")
    if command == "assess":
        return _run_recover_assess(args)
    if command == "retry-step":
        return _run_recover_retry_step(args)
    if command == "resume":
        return _run_recover_resume(args)
    print("Unknown recover command.", file=sys.stderr)
    return 2


def _recover_payload(args: argparse.Namespace) -> dict[str, Any]:
    from runtime.recovery import recover_assess, recover_resume, recover_retry_step

    runtime_data_dir = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    manifest_dir = str(getattr(args, "manifest_dir", "manifests") or "manifests")
    profile = str(getattr(args, "profile", "") or "") or None
    frame_id = str(getattr(args, "frame_id", "") or "")
    dry_run = bool(getattr(args, "dry_run", True))
    if getattr(args, "recover_command", "") == "retry-step":
        return recover_retry_step(
            frame_id,
            step_id=str(getattr(args, "step", "") or ""),
            runtime_data_dir=runtime_data_dir,
            manifest_dir=manifest_dir,
            profile_name=profile,
            dry_run=dry_run,
        )
    if getattr(args, "recover_command", "") == "resume":
        return recover_resume(
            frame_id,
            runtime_data_dir=runtime_data_dir,
            manifest_dir=manifest_dir,
            profile_name=profile,
            dry_run=dry_run,
        )
    return recover_assess(
        frame_id,
        runtime_data_dir=runtime_data_dir,
        manifest_dir=manifest_dir,
        profile_name=profile,
    )


def _run_recover_assess(args: argparse.Namespace) -> int:
    try:
        payload = _recover_payload(args)
    except Exception as exc:
        payload = {"ok": False, "error": str(exc), "frame_id": str(getattr(args, "frame_id", "") or ""), "dry_run": True}
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("ok", True) else 1
    print("Recovery Assessment")
    print(f"Frame ID: {payload.get('frame_id', '')}")
    print(f"Recovery status: {payload.get('recovery_status', '')}")
    print(f"Safe to retry: {str(payload.get('safe_to_retry', False)).lower()}")
    print(f"Safe to resume: {str(payload.get('safe_to_resume', False)).lower()}")
    print(f"Side-effect risk: {payload.get('side_effect_risk', '')}")
    print(f"Recommended action: {payload.get('recommended_action', '')}")
    print(f"Command suggestion: {payload.get('command_suggestion', '')}")
    print(f"Dry run: {str(payload.get('dry_run', True)).lower()}")
    return 0 if payload.get("ok", True) else 1


def _run_recover_retry_step(args: argparse.Namespace) -> int:
    try:
        payload = _recover_payload(args)
    except Exception as exc:
        payload = {
            "ok": False,
            "error": str(exc),
            "frame_id": str(getattr(args, "frame_id", "") or ""),
            "step_id": str(getattr(args, "step", "") or ""),
            "dry_run": True,
        }
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("ok", True) else 1
    print("Recovery Retry Step")
    print(f"Frame ID: {payload.get('frame_id', '')}")
    print(f"Step ID: {payload.get('step_id', '')}")
    print(f"Recovery status: {payload.get('recovery_status', '')}")
    print(f"Safe to retry: {str(payload.get('safe_to_retry', False)).lower()}")
    print(f"Dry run: {str(payload.get('dry_run', True)).lower()}")
    print(f"Command suggestion: {payload.get('command_suggestion', '')}")
    return 0 if payload.get("ok", True) else 1


def _run_recover_resume(args: argparse.Namespace) -> int:
    try:
        payload = _recover_payload(args)
    except Exception as exc:
        payload = {"ok": False, "error": str(exc), "frame_id": str(getattr(args, "frame_id", "") or ""), "dry_run": True}
    if bool(args.json):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("ok", True) else 1
    print("Recovery Resume")
    print(f"Frame ID: {payload.get('frame_id', '')}")
    print(f"Recovery status: {payload.get('recovery_status', '')}")
    print(f"Safe to resume: {str(payload.get('safe_to_resume', False)).lower()}")
    print(f"Dry run: {str(payload.get('dry_run', True)).lower()}")
    print(f"Command suggestion: {payload.get('command_suggestion', '')}")
    return 0 if payload.get("ok", True) else 1


def _run_controlled_live_status(args: argparse.Namespace) -> int:
    from src.live_profile_status import build_controlled_live_profile_status
    runtime_data_dir = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    status = build_controlled_live_profile_status(runtime_data_dir=runtime_data_dir)
    if bool(args.json):
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    print(f"Profile ID: {status['profile_id']}")
    print(f"Live reads allowed: {str(status['allow_live_reads']).lower()}")
    print(f"Live side effects allowed: {str(status['allow_live_side_effects']).lower()}")
    print(f"Governance OK: {str(status['governance_ok']).lower()}")
    gw = status.get("google_workspace_readiness", {})
    print(f"Google Workspace available: {str(gw.get('available', False)).lower()}")
    print(f"Google Workspace health OK: {str(gw.get('health_ok', False)).lower()}")
    print(f"Blocked tool classes: {', '.join(status.get('blocked_tool_classes', []))}")
    if status.get("errors"):
        for err in status["errors"]:
            print(f"ERROR: {err}")
    if bool(getattr(args, "check_tools", False)):
        print("\nAllowed live read tools:")
        for tool in status.get("allowed_read_tools", []):
            print(f"  {tool}")
        print("\nBlocked side effect tools:")
        for tool in status.get("blocked_side_effect_tools", []):
            print(f"  {tool}")
    return 0 if status.get("ok") else 1


def _run_artifacts(args: argparse.Namespace) -> int:
    command = str(getattr(args, "artifacts_command", "") or "")
    if command == "status":
        return _run_artifacts_status(args)
    if command == "plan-cleanup":
        return _run_artifacts_plan_cleanup(args)
    if command == "cleanup":
        return _run_artifacts_cleanup(args)
    print("Unknown artifacts command.", file=sys.stderr)
    return 2


def _run_artifacts_status(args: argparse.Namespace) -> int:
    from runtime.artifact_retention import build_retention_plan
    try:
        plan = build_retention_plan(args.runtime_data_dir)
    except Exception as exc:
        plan = {"ok": False, "errors": [str(exc)]}
        
    if bool(args.json):
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0 if plan.get("ok") else 1
        
    if not plan.get("ok"):
        print("Artifact Status: FAIL")
        for err in plan.get("errors", []):
             print(f"- {err}")
        return 1
        
    summary = plan.get("summary", {})
    print("Runtime Artifact Status")
    print(f"Directory: {plan.get('runtime_data_dir')}")
    print(f"Total items: {summary.get('total_items', 0)}")
    print(f"Total size: {summary.get('total_size_bytes', 0) / (1024*1024):.2f} MB")
    print(f"Protected items: {summary.get('protected_items', 0)}")
    print(f"Delete candidates: {summary.get('delete_candidates', 0)}")
    print("\nLargest groups:")
    for k, v in list(summary.get("top_groups_by_size", {}).items())[:5]:
        print(f"  {k}: {v / (1024*1024):.2f} MB")
        
    if plan.get("warnings"):
        print("\nWarnings:")
        for w in plan["warnings"]:
            print(f"- {w}")
    return 0


def _run_artifacts_plan_cleanup(args: argparse.Namespace) -> int:
    from runtime.artifact_retention import build_retention_plan
    try:
        plan = build_retention_plan(args.runtime_data_dir)
    except Exception as exc:
        plan = {"ok": False, "errors": [str(exc)]}
        
    if bool(args.json):
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0 if plan.get("ok") else 1
        
    if not plan.get("ok"):
        print("Cleanup Plan: FAIL")
        for err in plan.get("errors", []):
             print(f"- {err}")
        return 1
        
    summary = plan.get("summary", {})
    print("Artifact Cleanup Plan (Dry Run)")
    print(f"Directory: {plan.get('runtime_data_dir')}")
    print(f"Delete candidates: {summary.get('delete_candidates', 0)}")
    print(f"Reclaimable size: {summary.get('delete_candidate_size_bytes', 0) / (1024*1024):.2f} MB")
    if plan.get("warnings"):
        print("\nWarnings:")
        for w in plan["warnings"]:
            print(f"- {w}")
    return 0


def _run_artifacts_cleanup(args: argparse.Namespace) -> int:
    from runtime.artifact_retention import build_retention_plan, execute_retention_cleanup
    try:
        plan = build_retention_plan(args.runtime_data_dir)
        res = execute_retention_cleanup(plan, confirm=bool(args.confirm))
    except Exception as exc:
        res = {"ok": False, "errors": [str(exc)]}
        
    if bool(args.json):
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res.get("ok") else 1
        
    if not res.get("ok"):
        print("Artifact Cleanup: FAIL")
        for err in res.get("errors", []):
             print(f"- {err}")
        if not bool(args.confirm):
             print("\nHint: You must provide --confirm to execute cleanup.")
        return 1
        
    print("Artifact Cleanup: SUCCESS")
    print(f"Items deleted: {res.get('deleted_count', 0)}")
    print(f"Space reclaimed: {res.get('reclaimed_bytes', 0) / (1024*1024):.2f} MB")
    print(f"Items skipped: {res.get('skipped_count', 0)}")
    return 0


_QUEUE_FIXTURES: dict[str, dict] = {
    "customer_status": {
        "event_id": "fixture-customer-status-001",
        "source": "operator_ui",
        "event_type": "customer.status_check",
        "payload": {
            "customer_id": "CUST-1001",
            "request_type": "status_check",
            "channel": "fixture",
        },
    },
    "order_status": {
        "event_id": "fixture-order-status-001",
        "source": "operator_ui",
        "event_type": "order.status_check",
        "payload": {
            "order_id": "ORD-5001",
            "request_type": "status_check",
            "channel": "fixture",
        },
    },
    "system_health": {
        "event_id": "fixture-system-health-001",
        "source": "system",
        "event_type": "system.health_check",
        "payload": {
            "check_type": "health",
            "channel": "fixture",
        },
    },
}


def _run_queue(args: Any) -> int:
    import datetime

    from runtime.event_queue import (
        cancel_event,
        enqueue_event,
        list_queue,
        queue_health,
        recover_stale_queue_items,
        retry_event,
    )
    from runtime.event_queue_runner import process_next_queued_event, process_queued_events

    rd = getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR)
    use_json = bool(getattr(args, "json", False))
    cmd = args.queue_command

    if cmd == "status":
        try:
            result = queue_health(rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        print("Queue Status")
        print(f"  Backend:              {result.get('backend', 'unknown')}")
        print(f"  Total records:        {result.get('total', 0)}")
        print(f"  Pending:              {result.get('pending_count', 0)}")
        print(f"  Failed (retryable):   {result.get('failed_retryable_count', 0)}")
        print(f"  Dead-letter:          {result.get('dead_letter_count', 0)}")
        if result.get("oldest_pending_created_at"):
            print(f"  Oldest pending at:    {result['oldest_pending_created_at']}")
        for status, count in sorted((result.get("counts_by_status") or {}).items()):
            print(f"  {status:25s} {count}")
        return 0 if result.get("ok") else 1

    if cmd == "list":
        status_filter = str(getattr(args, "status", "") or "").strip() or None
        limit = int(getattr(args, "limit", 20))
        try:
            result = list_queue(status=status_filter, limit=limit, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "records": []}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        records = result.get("records", [])
        print(f"Queue records ({len(records)} shown):")
        for r in records:
            print(f"  {r.get('queue_id', '')[:8]}..  {r.get('status', ''):20s}  {r.get('source', '')}:{r.get('event_type', '')}  attempt={r.get('attempt_count', 0)}")
        return 0

    if cmd == "enqueue-fixture":
        fixture_name = str(getattr(args, "fixture_name", "")).strip()
        fixture = _QUEUE_FIXTURES.get(fixture_name)
        if fixture is None:
            available = ", ".join(sorted(_QUEUE_FIXTURES.keys()))
            if use_json:
                print(json.dumps({"ok": False, "error": f"Unknown fixture: {fixture_name}", "available": available}))
            else:
                print(f"Unknown fixture '{fixture_name}'. Available: {available}")
            return 1
        import uuid as _uuid
        event = dict(fixture)
        event["event_id"] = f"fixture-{fixture_name}-{_uuid.uuid4().hex[:8]}"
        try:
            result = enqueue_event(event, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        if result.get("ok"):
            print(f"Enqueued fixture '{fixture_name}': queue_id={result.get('queue_id', '')[:8]}...")
        else:
            print(f"Fixture '{fixture_name}' not enqueued: {result.get('error') or 'duplicate (dedupe key already active)'}")
        return 0 if result.get("ok") else 0

    if cmd == "process-next":
        worker_id = str(getattr(args, "worker_id", "local") or "local")
        try:
            result = process_next_queued_event(runtime_data_dir=rd, worker_id=worker_id)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        if result.get("no_pending_event"):
            print("No PENDING events in queue.")
            return 0
        if result.get("ok"):
            print(f"Processed: queue_id={result.get('queue_id', '')[:8]}...  frame_id={result.get('frame_id', '')[:8] if result.get('frame_id') else 'n/a'}  status={result.get('status', '')}")
        else:
            print(f"Failed: queue_id={result.get('queue_id', '')[:8]}...  category={result.get('failure_category', '')}  error={result.get('error', {}).get('message', '')}")
        return 0 if result.get("ok") or result.get("no_pending_event") else 1

    if cmd == "process-batch":
        limit = int(getattr(args, "limit", 10))
        worker_id = str(getattr(args, "worker_id", "local") or "local")
        try:
            result = process_queued_events(limit=limit, runtime_data_dir=rd, worker_id=worker_id)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        print(f"Batch complete: processed={result.get('processed', 0)}  completed={result.get('completed', 0)}  failed={result.get('failed', 0)}")
        return 0

    if cmd == "retry":
        queue_id = str(getattr(args, "queue_id", "")).strip()
        try:
            result = retry_event(queue_id, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        if result.get("ok"):
            print(f"Retried: queue_id={queue_id[:8]}...  new status=PENDING")
        else:
            print(f"Retry failed: {result.get('error', 'unknown error')}")
        return 0 if result.get("ok") else 1

    if cmd == "cancel":
        queue_id = str(getattr(args, "queue_id", "")).strip()
        reason = str(getattr(args, "reason", "Cancelled by operator."))
        try:
            result = cancel_event(queue_id, reason=reason, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        if result.get("ok"):
            print(f"Cancelled: queue_id={queue_id[:8]}...")
        else:
            print(f"Cancel failed: {result.get('error', 'unknown error')}")
        return 0 if result.get("ok") else 1

    if cmd == "dead-letter":
        limit = int(getattr(args, "limit", 20))
        try:
            result = list_queue(status="DEAD_LETTER", limit=limit, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "records": []}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        records = result.get("records", [])
        print(f"Dead-letter records ({len(records)}):")
        for r in records:
            print(f"  {r.get('queue_id', '')[:8]}..  attempts={r.get('attempt_count', 0)}  category={r.get('failure_category', '')}  {r.get('source', '')}:{r.get('event_type', '')}")
        return 0

    if cmd == "recover-stale":
        timeout = int(getattr(args, "stale_timeout_minutes", 15))
        try:
            result = recover_stale_queue_items(runtime_data_dir=rd, stale_timeout_minutes=timeout)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        recovered = result.get("recovered", [])
        print(f"Stale recovery complete: {len(recovered)} item(s) recovered.")
        for item in recovered:
            print(f"  {item.get('queue_id', '')[:8]}..  {item.get('old_status', '')} → {item.get('new_status', '')}")
        return 0

    return 2


def _run_schedule(args: Any) -> int:
    from runtime.scheduler_store import (
        enable_schedule,
        disable_schedule,
        list_schedules,
        list_schedule_runs,
        load_schedule_fixture,
    )
    from runtime.scheduler_engine import run_scheduler_tick
    from src.operator_scheduler_panel import build_scheduler_panel

    cmd = str(getattr(args, "schedule_command", "") or "")
    rd = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    use_json = bool(getattr(args, "json", False))

    if cmd == "status":
        try:
            result = build_scheduler_panel(runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        total = result.get("total_schedules", 0)
        enabled = result.get("enabled_count", 0)
        print(f"Scheduler: {total} schedule(s) total, {enabled} enabled, {result.get('disabled_count', 0)} disabled")
        for s in result.get("schedules", []):
            status_flag = "ON" if s.get("enabled") else "OFF"
            print(f"  [{status_flag}] {s.get('schedule_id', '')}  {s.get('name', '')}  ({s.get('schedule_type', '')} {s.get('time_of_day', '') or str(s.get('interval_minutes', ''))}min)  last={s.get('last_scheduled_for', 'never')}")
        return 0

    if cmd == "list":
        enabled_only = bool(getattr(args, "enabled_only", False))
        try:
            records = list_schedules(enabled_only=enabled_only, runtime_data_dir=rd)
        except Exception as exc:
            if use_json:
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
                return 1
            print(f"Error: {exc}")
            return 1
        if use_json:
            print(json.dumps({"ok": True, "schedules": records, "count": len(records)}, indent=2, ensure_ascii=False))
            return 0
        print(f"{len(records)} schedule(s):")
        for s in records:
            status_flag = "ON" if s.get("enabled") else "OFF"
            print(f"  [{status_flag}] {s.get('schedule_id', '')}  {s.get('name', '')}  event_type={s.get('event_type', '')}")
        return 0

    if cmd == "enable":
        schedule_id = str(getattr(args, "schedule_id", "")).strip()
        try:
            result = enable_schedule(schedule_id, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        if result.get("ok"):
            print(f"Enabled: {schedule_id}")
        else:
            print(f"Error: {result.get('error', 'unknown')}")
        return 0 if result.get("ok") else 1

    if cmd == "disable":
        schedule_id = str(getattr(args, "schedule_id", "")).strip()
        try:
            result = disable_schedule(schedule_id, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        if result.get("ok"):
            print(f"Disabled: {schedule_id}")
        else:
            print(f"Error: {result.get('error', 'unknown')}")
        return 0 if result.get("ok") else 1

    if cmd == "tick":
        try:
            result = run_scheduler_tick(runtime_data_dir=rd, dry_run=True)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        print(f"Scheduler tick (dry-run): checked={result.get('schedules_checked', 0)}  windows={result.get('windows_found', 0)}  enqueued={result.get('enqueued', 0)}  skipped={result.get('skipped', 0)}")
        return 0

    if cmd == "load-fixture":
        fixture_path = str(getattr(args, "fixture_path", "")).strip()
        try:
            result = load_schedule_fixture(fixture_path, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        if result.get("ok"):
            print(f"Loaded fixture: {result.get('schedule_id', '')}")
        else:
            print(f"Error: {result.get('error', 'unknown')}")
        return 0 if result.get("ok") else 1

    if cmd == "runs":
        schedule_id = str(getattr(args, "schedule_id", "") or "").strip()
        limit = int(getattr(args, "limit", 20))
        try:
            runs = list_schedule_runs(schedule_id=schedule_id or None, limit=limit, runtime_data_dir=rd)
        except Exception as exc:
            if use_json:
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
                return 1
            print(f"Error: {exc}")
            return 1
        if use_json:
            print(json.dumps({"ok": True, "runs": runs, "count": len(runs)}, indent=2, ensure_ascii=False))
            return 0
        print(f"{len(runs)} run record(s):")
        for r in runs:
            print(f"  {r.get('schedule_id', '')}  scheduled_for={r.get('scheduled_for', '')}  status={r.get('status', '')}  queue_id={r.get('queue_id', '')[:8] if r.get('queue_id') else ''}")
        return 0

    return 2


def _run_worker(args: Any) -> int:
    from runtime.worker.worker_engine import (
        build_worker_health,
        build_worker_status,
        clear_stale_worker_lock,
        request_worker_stop,
        run_worker_loop,
        run_worker_once,
        _read_recent_cycles,
    )
    from runtime.worker.worker_contract import DEFAULT_WORKER_CONFIG

    cmd = str(getattr(args, "worker_command", "") or "")
    rd = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    use_json = bool(getattr(args, "json", False))

    if cmd == "status":
        try:
            result = build_worker_status(rd)
            from runtime.worker.worker_hardening import build_worker_hardening_status, write_worker_hardening_report

            hardening = build_worker_hardening_status(runtime_data_dir=rd)
            result["hardening"] = {
                "ok": bool(hardening.get("ok", False)),
                "classification": hardening.get("classification", "BLOCKED"),
                "anomalies": list(hardening.get("anomalies", [])),
                "recommendations": list(hardening.get("recommendations", [])),
            }
            result["report_paths"] = write_worker_hardening_report(hardening, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        print(f"Worker Status")
        print(f"  Worker ID:            {result.get('worker_id', '')}")
        print(f"  Status:               {result.get('status', 'STOPPED')}")
        print(f"  PID:                  {result.get('pid', 0)}")
        print(f"  Locked:               {result.get('locked', False)}")
        print(f"  Lock ID:              {result.get('lock_id', '')[:16] or 'none'}")
        print(f"  Last heartbeat:       {result.get('last_heartbeat_at', 'never')}")
        print(f"  Cycle count:          {result.get('cycle_count', 0)}")
        print(f"  Last cycle started:   {result.get('last_cycle_started_at', 'never')}")
        print(f"  Last cycle completed: {result.get('last_cycle_completed_at', 'never')}")
        last = result.get("last_cycle_summary") or {}
        hardening = result.get("hardening") or {}
        print(f"  Hardening:            {hardening.get('classification', 'BLOCKED')}")
        if last:
            print(f"  Last cycle OK:        {last.get('ok', True)}")
            print(f"  Queue processed:      {last.get('queue_items_processed', 0)}")
        if result.get("last_error"):
            print(f"  Last error:           {result['last_error']}")
        return 0

    if cmd == "health":
        try:
            result = build_worker_health(rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "checks": {}, "warnings": []}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        print("Worker Health")
        for k, v in sorted((result.get("checks") or {}).items()):
            flag = "OK" if v else "FAIL"
            print(f"  [{flag}] {k}")
        print(f"  Service ready: {result.get('service_ready', False)}")
        print(f"  Soak ready:    {result.get('soak_ready', False)}")
        for w in result.get("warnings") or []:
            print(f"  WARN: {w}")
        return 0 if result.get("ok") else 1

    if cmd == "run-once":
        worker_id = str(getattr(args, "worker_id", "local-worker-1") or "local-worker-1")
        no_scheduler = bool(getattr(args, "no_scheduler", False))
        no_event_sources = bool(getattr(args, "no_event_sources", False))
        queue_limit = int(getattr(args, "queue_limit", 10))

        config = {
            **DEFAULT_WORKER_CONFIG,
            "worker_id": worker_id,
            "mode": "run_once",
            "features": {
                "recover_stale_queue": True,
                "run_scheduler_tick": not no_scheduler,
                "poll_event_sources": not no_event_sources,
                "process_queue": True,
            },
            "limits": {
                **DEFAULT_WORKER_CONFIG.get("limits", {}),
                "max_queue_items_per_cycle": queue_limit,
            },
        }
        try:
            result = run_worker_once(config, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        ok_flag = "OK" if result.get("ok") else "FAIL"
        print(f"Worker run-once: {ok_flag}")
        print(f"  Cycle ID:              {result.get('cycle_id', '')}")
        print(f"  Duration:              {result.get('duration_ms', 0)}ms")
        print(f"  Stale recovered:       {result.get('stale_queue_recovered', 0)}")
        print(f"  Schedule events:       {result.get('schedule_events_enqueued', 0)}")
        print(f"  Sources polled:        {result.get('event_sources_polled', 0)}")
        print(f"  Queue processed:       {result.get('queue_items_processed', 0)}")
        print(f"  Queue completed:       {result.get('queue_items_completed', 0)}")
        print(f"  Queue failed:          {result.get('queue_items_failed', 0)}")
        if result.get("warnings"):
            for w in result["warnings"]:
                print(f"  WARN: {w}")
        if result.get("errors"):
            for e in result["errors"]:
                print(f"  ERROR: {e}")
        return 0 if result.get("ok") else 1

    if cmd == "soak":
        from runtime.worker.worker_soak import run_worker_soak

        profile_name = str(getattr(args, "profile", "service") or "service")
        cycles = int(getattr(args, "cycles", 20))
        sleep_seconds = float(getattr(args, "sleep_seconds", 0.1))
        max_runtime_seconds = float(getattr(args, "max_runtime_seconds", 300.0))
        queue_limit = int(getattr(args, "queue_limit", 10))
        fail_fast = bool(getattr(args, "fail_fast", False))
        write_report = bool(getattr(args, "write_report", True))
        try:
            result = run_worker_soak(
                profile_name=profile_name,
                cycles=cycles,
                sleep_seconds=sleep_seconds,
                max_runtime_seconds=max_runtime_seconds,
                queue_limit=queue_limit,
                runtime_data_dir=rd,
                fail_fast=fail_fast,
                write_report=write_report,
            )
        except Exception as exc:
            result = {
                "ok": False,
                "error": str(exc),
                "profile": profile_name,
                "worker_id": "",
                "cycles_requested": cycles,
                "cycles_completed": 0,
                "cycles_failed": 0,
                "cycles_no_work": 0,
                "duration_ms": 0,
                "max_cycle_duration_ms": 0,
                "average_cycle_duration_ms": 0.0,
                "stale_lock_detected": False,
                "live_side_effects_performed": False,
                "classifications": {},
                "blockers": [],
                "warnings": [],
                "report_paths": {},
            }
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        print(f"Worker soak: {'OK' if result.get('ok') else 'FAIL'}")
        print(f"  Profile:           {result.get('profile', '')}")
        print(f"  Worker ID:         {result.get('worker_id', '')}")
        print(f"  Cycles completed:  {result.get('cycles_completed', 0)} / {result.get('cycles_requested', 0)}")
        print(f"  Cycles failed:     {result.get('cycles_failed', 0)}")
        print(f"  No work cycles:    {result.get('cycles_no_work', 0)}")
        print(f"  Max cycle ms:      {result.get('max_cycle_duration_ms', 0)}")
        print(f"  Average cycle ms:   {result.get('average_cycle_duration_ms', 0)}")
        if result.get("report_paths"):
            print(f"  Report:            {result.get('report_paths', {}).get('json', '')}")
        for warning in result.get("warnings") or []:
            print(f"  WARN: {warning}")
        for blocker in result.get("blockers") or []:
            if isinstance(blocker, dict):
                print(f"  BLOCKER: {blocker.get('message', '')}")
        return 0 if result.get("ok") else 1

    if cmd == "run-loop":
        worker_id = str(getattr(args, "worker_id", "local-worker-1") or "local-worker-1")
        max_cycles = int(getattr(args, "max_cycles", 3))
        sleep_seconds = float(getattr(args, "sleep_seconds", 5.0))
        max_runtime_seconds = float(getattr(args, "max_runtime_seconds", 300.0))

        config = {
            **DEFAULT_WORKER_CONFIG,
            "worker_id": worker_id,
            "mode": "bounded_loop",
            "cycle": {
                "max_cycles": max_cycles,
                "sleep_seconds": sleep_seconds,
                "max_runtime_seconds": max_runtime_seconds,
            },
        }
        try:
            result = run_worker_loop(config, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        ok_flag = "OK" if result.get("ok") else "FAIL"
        print(f"Worker run-loop: {ok_flag}")
        print(f"  Cycles run:     {result.get('cycles_run', 0)} / {result.get('max_cycles', max_cycles)}")
        print(f"  Stopped early:  {result.get('stopped_early', False)}")
        if result.get("stop_reason"):
            print(f"  Stop reason:    {result['stop_reason']}")
        return 0 if result.get("ok") else 1

    if cmd == "stop":
        worker_id = str(getattr(args, "worker_id", "local-worker-1") or "local-worker-1")
        try:
            result = request_worker_stop(worker_id, runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        if result.get("ok"):
            print(f"Stop request written for worker {worker_id!r}.")
        else:
            print(f"Stop request failed: {result.get('error', 'unknown')}")
        return 0 if result.get("ok") else 1

    if cmd == "cycles":
        limit = int(getattr(args, "limit", 10))
        try:
            cycles = _read_recent_cycles(rd, limit=limit)
        except Exception as exc:
            if use_json:
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
                return 1
            print(f"Error: {exc}")
            return 1
        if use_json:
            print(json.dumps({"ok": True, "cycles": cycles, "count": len(cycles)}, indent=2, ensure_ascii=False))
            return 0
        print(f"Recent cycles ({len(cycles)}):")
        for c in cycles:
            ok_flag = "OK" if c.get("ok") else "FAIL"
            print(
                f"  [{ok_flag}] {c.get('cycle_id', '')}  "
                f"dur={c.get('duration_ms', 0)}ms  "
                f"q={c.get('queue_items_processed', 0)}/{c.get('queue_items_completed', 0)}  "
                f"src={c.get('event_sources_polled', 0)}"
            )
        return 0

    if cmd == "clear-stale-lock":
        try:
            result = clear_stale_worker_lock(runtime_data_dir=rd)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        if result.get("ok"):
            cleared = result.get("cleared")
            if cleared:
                print(f"Cleared stale lock: worker={cleared.get('worker_id')!r} pid={cleared.get('pid')}")
            else:
                print(result.get("message", "No stale lock to clear."))
        else:
            print(f"Could not clear lock: {result.get('message') or result.get('error', 'unknown')}")
        return 0 if result.get("ok") else 1

    return 2


def _run_invoiceops(args: Any) -> int:
    from runtime.invoiceops_live_posting import (
        build_invoiceops_live_posting_plan,
        run_invoiceops_live_posting_preflight,
        execute_invoiceops_live_sheet_posting,
        verify_invoiceops_live_posting,
        render_invoiceops_live_posting_markdown,
        write_invoiceops_live_posting_report,
    )
    from runtime.invoiceops_reconciliation import build_invoiceops_reconciliation_result
    from runtime.invoiceops_accounting_evidence_pack import build_accounting_evidence_pack
    from runtime.invoiceops_posting_approval_pack import build_invoiceops_posting_approval_pack
    from runtime.invoiceops_posting_ledger import build_posting_ledger_report

    cmd = str(getattr(args, "invoiceops_command", "") or "")
    rd = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    as_json = bool(getattr(args, "json", False))
    fixture_mode = bool(getattr(args, "fixture_mode", True))
    profile = str(getattr(args, "profile", "service") or "service")

    if cmd == "reconcile":
        result = build_invoiceops_reconciliation_result(
            frame_id=str(getattr(args, "frame_id", "") or ""),
            invoice_number=str(getattr(args, "invoice_number", "") or ""),
            posting_plan_id=str(getattr(args, "posting_plan_id", "") or ""),
            runtime_data_dir=rd,
            profile=profile,
            fixture_mode=fixture_mode,
            write_report=bool(getattr(args, "write_report", False)),
        )
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"InvoiceOps Reconciliation: {result.get('status', '')}")
            print(f"  Invoice: {result.get('invoice_number', '')}")
            print(f"  Supplier: {result.get('supplier_name', '')}")
        return 0 if result.get("ok", False) else 1

    if cmd == "evidence-pack":
        result = build_accounting_evidence_pack(
            frame_id=str(getattr(args, "frame_id", "") or ""),
            invoice_number=str(getattr(args, "invoice_number", "") or ""),
            posting_plan_id=str(getattr(args, "posting_plan_id", "") or ""),
            runtime_data_dir=rd,
            profile=profile,
            fixture_mode=fixture_mode,
            write_report=bool(getattr(args, "write_report", False)),
        )
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"InvoiceOps Evidence Pack: {result.get('pack_id', '')}")
            print(f"  Status: {result.get('status', '')}")
        return 0 if result.get("ok", False) else 1

    if cmd == "live-posting":
        sub_cmd = str(getattr(args, "iolsp_command", "") or "")
        frame_id = str(getattr(args, "frame_id", "") or "")

        if sub_cmd == "plan":
            result = build_invoiceops_live_posting_plan(
                frame_id=frame_id,
                invoice_id=str(getattr(args, "invoice_id", "") or ""),
                invoice_number=str(getattr(args, "invoice_number", "") or ""),
                supplier_name=str(getattr(args, "supplier_name", "") or ""),
                po_number=str(getattr(args, "po_number", "") or ""),
                match_status=str(getattr(args, "match_status", "matched") or "matched"),
                prepared_writes=[],
            )
            if as_json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"InvoiceOps Live Posting Plan: {result.get('posting_plan_id')}")
                print(f"  Eligible writes: {result.get('eligible_write_count', 0)}")
                print(f"  Blocked writes: {result.get('blocked_write_count', 0)}")
                print(f"  Pending actions: {len(result.get('pending_actions', []))}")
            return 0

        if sub_cmd == "preflight":
            empty_plan = build_invoiceops_live_posting_plan(
                frame_id=frame_id,
                prepared_writes=[],
            )
            result = run_invoiceops_live_posting_preflight(
                posting_plan=empty_plan,
                action_id=str(getattr(args, "action_id", "") or "") or None,
                profile_name=str(getattr(args, "profile", "controlled_live_write") or "controlled_live_write"),
                runtime_data_dir=rd,
            )
            if as_json:
                print(json.dumps(result, indent=2, default=str))
            else:
                ok_str = "PASS" if result.get("plan_ok") else "FAIL"
                print(f"InvoiceOps Live Posting Preflight: {ok_str}")
                for b in result.get("plan_blockers", []):
                    print(f"  BLOCKED: {b}")
            return 0

        if sub_cmd == "approval-pack":
            empty_plan = build_invoiceops_live_posting_plan(
                frame_id=frame_id,
                prepared_writes=[],
            )
            result = build_invoiceops_posting_approval_pack(posting_plan=empty_plan)
            if as_json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"InvoiceOps Approval Pack: {result.get('posting_plan_id')}")
                print(f"  Summary: {result.get('human_summary', '')}")
                print(f"  Checklist items: {len(result.get('approval_checklist', []))}")
            return 0

        if sub_cmd == "execute":
            action_id = str(getattr(args, "action_id", "") or "")
            confirm = str(getattr(args, "confirm", "") or "")
            dry_run_fallback = bool(getattr(args, "dry_run_fallback", False))
            empty_plan = build_invoiceops_live_posting_plan(
                frame_id=frame_id,
                prepared_writes=[],
            )
            result = execute_invoiceops_live_sheet_posting(
                posting_plan=empty_plan,
                action_id=action_id,
                typed_confirmation=confirm,
                runtime_data_dir=rd,
                dry_run_fallback=dry_run_fallback,
            )
            if as_json:
                print(json.dumps(result, indent=2, default=str))
            else:
                status = "EXECUTED" if result.get("executed") else "BLOCKED/FAILED"
                print(f"InvoiceOps Live Posting Execution: {status}")
                print(f"  Error: {result.get('error_code', '') or 'none'}")
            return 0 if result.get("ok") else 1

        if sub_cmd == "verify":
            action_id = str(getattr(args, "action_id", "") or "")
            result = {"ok": False, "verified": False, "errors": ["No execution result found."]}
            if as_json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"InvoiceOps Verify: {'PASS' if result.get('verified') else 'FAIL'}")
            return 0 if result.get("ok") else 1

        if sub_cmd == "report":
            report = build_posting_ledger_report(runtime_data_dir=rd)
            if as_json:
                print(json.dumps(report, indent=2, default=str))
            else:
                print(f"InvoiceOps Live Posting Ledger: {report['total_entries']} entries")
                print(f"  Verified: {report['executed_verified_count']}")
                print(f"  Failed: {report['failed_count']}")
            return 0

        return 2

    if cmd == "showcase":
        return _run_invoiceops_showcase(args, rd=rd, as_json=as_json, profile=profile)

    return 2


def _run_invoiceops_showcase(args: Any, *, rd: str, as_json: bool, profile: str) -> int:
    from runtime.invoiceops_showcase_demo import (
        get_showcase_status,
        run_showcase_invoice_batch,
        build_showcase_demo_dataset,
    )

    sub_cmd = str(getattr(args, "iosc_command", "") or "")
    spreadsheet_id = str(getattr(args, "spreadsheet_id", "") or "")
    config_dir = str(getattr(args, "config_dir", "") or "")

    if sub_cmd == "status":
        result = get_showcase_status(
            runtime_data_dir=rd,
            config_dir=config_dir,
            spreadsheet_id=spreadsheet_id,
        )
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"InvoiceOps Showcase Status: {result.get('status', '')}")
            print(f"  Spreadsheet ID: {result.get('spreadsheet_id', '') or '(not configured)'}")
            print(f"  Fixture invoices: {result.get('invoice_fixture_count', 0)}")
            print(f"  Allowed tabs: {len(result.get('allowed_tabs', []))}")
            if result.get("needs_config"):
                print("  NOTE: Configure spreadsheet_id in ~/.taskframe/invoiceops_showcase.json")
        return 0 if result.get("ok") else 1

    if sub_cmd == "run":
        live_mode = bool(getattr(args, "live", False))
        confirm = str(getattr(args, "confirm", "") or "")
        invoice_limit = int(getattr(args, "invoice_limit", 0) or 0)
        write_report = bool(getattr(args, "write_report", False))
        result = run_showcase_invoice_batch(
            profile=profile,
            runtime_data_dir=rd,
            config_dir=config_dir,
            spreadsheet_id=spreadsheet_id,
            invoice_limit=invoice_limit,
            live_mode=live_mode,
            confirm=confirm,
            write_report=write_report,
        )
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            ok_str = "OK" if result.get("ok") else "FAIL"
            print(f"InvoiceOps Showcase Run: {ok_str}")
            print(f"  Run ID: {result.get('demo_run_id', '')}")
            print(f"  Invoices: {result.get('invoice_count', 0)}")
            print(f"  Matched: {result.get('matched_count', 0)}")
            print(f"  Exceptions: {result.get('exception_count', 0)}")
            print(f"  Blocked: {result.get('blocked_count', 0)}")
            print(f"  Live writes: {result.get('live_writes_performed', 0)}")
            if result.get("blockers"):
                for b in result["blockers"]:
                    print(f"  BLOCKED: {b}")
        return 0 if result.get("ok") else 1

    if sub_cmd == "setup-sheet":
        confirm = str(getattr(args, "confirm", "") or "")
        from runtime.invoiceops_showcase_demo import (
            CONFIRMATION_TEMPLATE,
            build_showcase_demo_dataset,
            create_or_reset_showcase_google_sheet,
        )
        expected = CONFIRMATION_TEMPLATE.format(spreadsheet_id=spreadsheet_id)
        if confirm != expected:
            result = {
                "ok": False,
                "error": "CONFIRMATION_REQUIRED",
                "expected": expected,
                "received": confirm,
            }
            if as_json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"Showcase setup blocked: confirmation required.")
                print(f"  Expected: {expected!r}")
            return 1
        sheet_spec = create_or_reset_showcase_google_sheet(
            spreadsheet_id=spreadsheet_id,
            allow_reset=True,
            live_mode=True,
        )
        dataset = build_showcase_demo_dataset()
        result = {
            "ok": True,
            "spreadsheet_id": spreadsheet_id,
            "sheet_spec": sheet_spec,
            "supplier_count": len(dataset["supplier_master"]),
            "po_count": len(dataset["po_register"]),
            "gr_count": len(dataset["goods_receipts"]),
            "note": "Sheet structure spec returned. Actual Google Sheets API calls require credentials.",
        }
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"InvoiceOps Showcase Setup: {'OK' if result.get('ok') else 'FAIL'}")
            print(f"  Spreadsheet: {spreadsheet_id}")
            print(f"  Tabs to create: {len(sheet_spec.get('tabs_to_create', []))}")
        return 0 if result.get("ok") else 1

    if sub_cmd == "open-report":
        import os as _os
        from pathlib import Path as _Path
        report_dir = _Path(rd) / "invoiceops" / "showcase"
        latest = report_dir / "showcase_demo_latest.md"
        if latest.is_file():
            _os.startfile(str(latest)) if hasattr(_os, "startfile") else print(str(latest))
            result = {"ok": True, "path": str(latest)}
        else:
            result = {"ok": False, "error": "no_report_found", "report_dir": str(report_dir)}
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(result.get("path") or result.get("error", ""))
        return 0 if result.get("ok") else 1

    return 2


def _run_live_side_effect(args: Any) -> int:
    from runtime.live_side_effect_execution import (
        build_live_side_effect_preflight,
        execute_approved_live_side_effect,
        live_side_effect_confirmation_phrase,
        render_live_execution_markdown,
        verify_live_side_effect_result,
    )
    from runtime.live_execution_ledger import build_ledger_report, get_ledger_entry

    cmd = str(getattr(args, "lse_command", "") or "")
    profile = str(getattr(args, "profile", "controlled_live_write") or "controlled_live_write")
    rd = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    as_json = bool(getattr(args, "json", False))

    from src.controlled_live_profile import CONTROLLED_LIVE_WRITE_PROFILE
    profile_data = CONTROLLED_LIVE_WRITE_PROFILE if profile == "controlled_live_write" else {}

    if cmd == "preflight":
        frame_id = str(getattr(args, "frame_id", "") or "")
        action_id = str(getattr(args, "action_id", "") or "")
        tool = str(getattr(args, "tool", "sheet/write_rows") or "sheet/write_rows")
        pending_action = {
            "frame_id": frame_id,
            "action_id": action_id,
            "tool": tool,
            "status": "APPROVED",
        }
        result = build_live_side_effect_preflight(
            pending_action=pending_action,
            profile_name=profile,
            profile_data=profile_data,
            runtime_data_dir=rd,
        )
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            ok_str = "PASS" if result["ok"] else "FAIL"
            print(f"Live side-effect preflight: {ok_str}")
            print(f"Confirmation phrase: {result.get('confirmation_phrase', '')}")
            for c in result.get("checks", []):
                mark = "ok" if c.get("ok") else "FAIL"
                print(f"  [{mark}] {c['name']}: {c.get('message', '')}")
        return 0 if result.get("ok") else 1

    if cmd == "execute":
        frame_id = str(getattr(args, "frame_id", "") or "")
        action_id = str(getattr(args, "action_id", "") or "")
        tool = str(getattr(args, "tool", "sheet/write_rows") or "sheet/write_rows")
        confirm = str(getattr(args, "confirm", "") or "")
        dry_run_fallback = bool(getattr(args, "dry_run_fallback", False))
        pending_action = {
            "frame_id": frame_id,
            "action_id": action_id,
            "tool": tool,
            "status": "APPROVED",
        }
        result = execute_approved_live_side_effect(
            pending_action=pending_action,
            profile_name=profile,
            profile_data=profile_data,
            typed_confirmation=confirm,
            runtime_data_dir=rd,
            dry_run_fallback=dry_run_fallback,
        )
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            status = "EXECUTED" if result.get("executed") else "BLOCKED/FAILED"
            print(f"Live side-effect execution: {status}")
            print(render_live_execution_markdown(result))
        return 0 if result.get("ok") else 1

    if cmd == "verify":
        frame_id = str(getattr(args, "frame_id", "") or "")
        action_id = str(getattr(args, "action_id", "") or "")
        result = {"ok": False, "checks": [], "failed_checks": [], "tool": "", "verified_at": ""}
        # Look up the most recent execution result for this action from ledger
        from runtime.live_execution_ledger import read_ledger_entries, LEDGER_STATUS_EXECUTED
        entries = read_ledger_entries(runtime_data_dir=rd)
        exec_entry = None
        for e in reversed(entries):
            if str(e.get("action_id") or "") == action_id and e.get("status") == LEDGER_STATUS_EXECUTED:
                exec_entry = e
                break
        if exec_entry:
            pending_action = {"frame_id": frame_id, "action_id": action_id, "tool": exec_entry.get("tool", ""), "target_ref": exec_entry.get("target_ref", "")}
            result = verify_live_side_effect_result(
                execution_result=exec_entry.get("execution_result") or {"ok": True, "type": "sheet_write_rows"},
                pending_action=pending_action,
            )
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            ok_str = "PASS" if result["ok"] else "FAIL"
            print(f"Post-execution verification: {ok_str}")
            for c in result.get("checks", []):
                mark = "ok" if c.get("ok") else "FAIL"
                print(f"  [{mark}] {c['name']}: {c.get('message', '')}")
        return 0 if result.get("ok") else 1

    if cmd == "report":
        limit = int(getattr(args, "limit", 20) or 20)
        report = build_ledger_report(runtime_data_dir=rd, limit=limit)
        if as_json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"Live execution ledger — {report['total_entries']} entries total")
            print(f"  Executed: {report['executed_count']}, Failed: {report['failed_count']}")
            for entry in report.get("recent_entries", []):
                print(f"  [{entry.get('status')}] {entry.get('recorded_at')} tool={entry.get('tool')} key={entry.get('idempotency_key')}")
        return 0

    if cmd == "rollback-plan":
        ikey = str(getattr(args, "idempotency_key", "") or "")
        entry = get_ledger_entry(ikey, runtime_data_dir=rd)
        if entry is None:
            result: dict[str, Any] = {"ok": False, "error": f"No ledger entry found for idempotency_key: {ikey}"}
        else:
            rollback = entry.get("rollback_plan") or {}
            result = {
                "ok": True,
                "idempotency_key": ikey,
                "rollback_plan": rollback,
                "tool": entry.get("tool", ""),
                "action_id": entry.get("action_id", ""),
                "status": entry.get("status", ""),
                "note": "Rollback plan is display-only metadata. No automatic rollback is performed.",
            }
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            if result.get("ok"):
                print(f"Rollback plan for key: {ikey}")
                print(f"Tool: {result.get('tool')}, Status: {result.get('status')}")
                print(f"NOTE: {result.get('note')}")
                for k, v in (result.get("rollback_plan") or {}).items():
                    print(f"  {k}: {v}")
            else:
                print(f"ERROR: {result.get('error')}")
        return 0 if result.get("ok") else 1

    return 2


def _run_live_read(args: Any) -> int:
    from runtime.live_read_proof import (
        build_live_read_status,
        run_live_read_proof_pack,
        validate_live_read_boundary,
        write_live_read_proof_report,
    )

    cmd = str(getattr(args, "live_read_command", "") or "")
    profile = str(getattr(args, "profile", "controlled_live_read") or "controlled_live_read")
    rd = str(getattr(args, "runtime_data_dir", DEFAULT_RUNTIME_DATA_DIR) or DEFAULT_RUNTIME_DATA_DIR)
    use_json = bool(getattr(args, "json", False))

    if cmd == "status":
        result = build_live_read_status(profile=profile, runtime_data_dir=rd)
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        print(f"Profile: {result.get('profile', '')}")
        print(f"Credential status: {result.get('credential_status', '')}")
        print(f"Live reads allowed: {result.get('profile_config', {}).get('allow_live_reads', False)}")
        print(f"Live side effects allowed: {result.get('live_side_effects_allowed', False)}")
        print(f"RPA allowed: {result.get('rpa_allowed', False)}")
        print(f"Latest proof available: {result.get('latest_proof_available', False)}")
        if result.get("latest_proof_ok") is not None:
            print(f"Latest proof ok: {result.get('latest_proof_ok')}")
        return 0

    if cmd == "proof":
        no_live = bool(getattr(args, "no_live_probes", False))
        write_report = bool(getattr(args, "write_report", False))
        result = run_live_read_proof_pack(
            profile=profile,
            runtime_data_dir=rd,
            config_dir=str(getattr(args, "config_dir", "") or ""),
            spreadsheet_range=str(getattr(args, "spreadsheet_range", "Sheet1!A1:D10") or "Sheet1!A1:D10"),
            gmail_query=str(getattr(args, "gmail_query", "in:inbox") or "in:inbox"),
            calendar_query=str(getattr(args, "calendar_query", "upcoming") or "upcoming"),
            no_live_probes=no_live,
        )
        if write_report:
            report = write_live_read_proof_report(result, runtime_data_dir=rd)
            result["report_paths"] = report.get("paths", {})
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        status_str = "PASS" if result.get("ok") else "FAIL"
        print(f"Live-read proof: {status_str}")
        print(f"Profile: {result.get('profile', '')}")
        print(f"Live reads attempted: {result.get('live_reads_attempted', False)}")
        print(f"Live side effects performed: {result.get('live_side_effects_performed', False)}")
        print(f"Probes run: {len(result.get('probes', []))}")
        print(f"Side-effect checks: {len(result.get('blocked_side_effect_checks', []))}")
        print(f"RPA blocked: {result.get('rpa_blocked', True)}")
        if result.get("blockers"):
            print(f"Blockers: {result['blockers']}")
        if result.get("warnings"):
            print(f"Warnings: {result['warnings']}")
        if write_report and result.get("report_paths"):
            paths = result["report_paths"]
            print(f"Report JSON: {paths.get('live_read_proof_json', '')}")
            print(f"Report MD: {paths.get('live_read_proof_md', '')}")
        return 0 if result.get("ok") else 1

    if cmd == "blocked-side-effects":
        checks = validate_live_read_boundary(profile=profile)
        blocked_count = sum(1 for c in checks if c.get("status") == "BLOCKED")
        fail_count = sum(1 for c in checks if c.get("status") != "BLOCKED")
        ok = fail_count == 0
        payload = {
            "ok": ok,
            "profile": profile,
            "checks": checks,
            "blocked_count": blocked_count,
            "fail_count": fail_count,
            "live_side_effects_performed": False,
            "rpa_blocked": all(
                c.get("status") == "BLOCKED"
                for c in checks
                if "rpa" in str(c.get("tool", "")).lower()
            ),
        }
        if use_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0 if ok else 1
        print(f"Blocked side-effect checks: {'PASS' if ok else 'FAIL'}")
        print(f"Checks run: {len(checks)}")
        print(f"Confirmed blocked: {blocked_count}")
        for c in checks:
            print(f"  [{c.get('status', '')}] {c.get('tool', '')} — {c.get('reason', '')}")
        return 0 if ok else 1

    print(f"Unknown live-read command: {cmd!r}")
    return 2


def _is_tk_failure(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "tk" in name or "tcl" in name or "no display name" in message or "display" in message and "available" in message


if __name__ == "__main__":
    raise SystemExit(main())
