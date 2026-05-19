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
TOOL_RESULT_CONTRACT_MD = ROOT / "docs" / "tool_result_contract.md"
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
        "toolpack_contract": "PENDING",
        "google_workspace_toolpack_descriptor": "PENDING",
        "google_workspace_read_only_safety": "PENDING",
        "google_workspace_health_safe": "PENDING",
        "google_workspace_docs": "PENDING",
        "google_workspace_optional_boundary": "PENDING",
        "google_workspace_readonly_pack": "PENDING",
        "toolpack_loader": "PENDING",
        "toolpack_registry_integration": "PENDING",
        "toolpack_cli": "PENDING",
        "external_toolpacks_default_safe": "PENDING",
        "builtin_toolpack_migration": "PENDING",
        "tool_registry_compatibility": "PENDING",
        "tool_inventory": "PENDING",
        "migrated_toolpack_health": "PENDING",
        "default_tool_registry": "PENDING",
        "tool_result_contract": "PENDING",
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
            "safety_verification_pack": "PENDING",
            "live_blocked_evidence_report": "PENDING",
            "default_no_live_side_effects": "PENDING",
            "toolpack_scaffold": "PENDING",
            "toolpack_contract_runner": "PENDING",
            "toolpack_generated_pack_execution": "PENDING",
            "toolpack_governance": "PENDING",
            "toolpack_lifecycle": "PENDING",
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
        ("toolpack_loader_tests", ["python", "-m", "pytest", "tests/test_toolpack_loader.py"]),
        ("toolpack_registry_tests", ["python", "-m", "pytest", "tests/test_toolpack_registry_integration.py"]),
        ("toolpack_cli_tests", ["python", "-m", "pytest", "tests/test_toolpack_cli.py"]),
        ("toolpack_health_tests", ["python", "-m", "pytest", "tests/test_toolpack_health.py"]),
        ("toolpack_manifest_execution_tests", ["python", "-m", "pytest", "tests/test_toolpack_manifest_execution.py"]),
        ("google_workspace_descriptor_tests", ["python", "-m", "pytest", "tests/test_google_workspace_toolpack_descriptor.py"]),
        ("google_workspace_auth_tests", ["python", "-m", "pytest", "tests/test_google_workspace_toolpack_auth.py"]),
        ("google_workspace_tool_tests", ["python", "-m", "pytest", "tests/test_google_workspace_toolpack_tools.py"]),
        ("google_workspace_health_tests", ["python", "-m", "pytest", "tests/test_google_workspace_toolpack_health.py"]),
        ("google_workspace_cli_tests", ["python", "-m", "pytest", "tests/test_google_workspace_toolpack_cli.py"]),
        ("google_workspace_manifest_examples_tests", ["python", "-m", "pytest", "tests/test_google_workspace_toolpack_manifest_examples.py"]),
        ("google_workspace_safety_tests", ["python", "-m", "pytest", "tests/test_google_workspace_toolpack_safety.py"]),
        ("google_workspace_docs_tests", ["python", "-m", "pytest", "tests/test_google_workspace_toolpack_docs.py"]),
        ("builtin_toolpack_migration_tests", ["python", "-m", "pytest", "tests/test_builtin_toolpack_migration.py"]),
        ("tool_registry_compat_tests", ["python", "-m", "pytest", "tests/test_tool_registry_compat.py"]),
        ("tool_inventory_tests", ["python", "-m", "pytest", "tests/test_tool_inventory.py"]),
        ("builtin_toolpack_health_tests", ["python", "-m", "pytest", "tests/test_builtin_toolpack_health.py"]),
        ("builtin_toolpack_manifest_compatibility_tests", ["python", "-m", "pytest", "tests/test_builtin_toolpack_manifest_compatibility.py"]),
        ("builtin_toolpack_cli_tests", ["python", "-m", "pytest", "tests/test_builtin_toolpack_cli.py"]),
        ("builtin_toolpack_docs_tests", ["python", "-m", "pytest", "tests/test_builtin_toolpack_docs.py"]),
        ("toolpack_scaffold_tests", ["python", "-m", "pytest", "tests/test_toolpack_scaffold.py"]),
        ("toolpack_contract_runner_tests", ["python", "-m", "pytest", "tests/test_toolpack_contract_runner.py"]),
        ("toolpack_scaffold_cli_tests", ["python", "-m", "pytest", "tests/test_toolpack_scaffold_cli.py"]),
        ("toolpack_generated_pack_execution_tests", ["python", "-m", "pytest", "tests/test_toolpack_generated_pack_execution.py"]),
        ("toolpack_governance_tests", ["python", "-m", "pytest", "tests/test_toolpack_governance.py", "tests/test_toolpack_governance_report.py", "tests/test_toolpack_governance_cli.py", "tests/test_toolpack_governance_docs.py", "tests/test_toolpack_governance_release_verifier.py"]),
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
        _check_toolpack_contract(),
        _check_google_workspace_toolpack_descriptor(),
        _check_google_workspace_read_only_safety(),
        _check_google_workspace_health_safe(),
        _check_google_workspace_docs(),
        _check_google_workspace_optional_boundary(),
        _check_google_workspace_readonly_pack(),
        _check_toolpack_loader(),
        _check_toolpack_registry_integration(),
        _check_toolpack_cli(),
        _check_external_toolpacks_default_safe(),
        _check_builtin_toolpack_migration(),
        _check_tool_registry_compatibility(),
        _check_tool_inventory(),
        _check_migrated_toolpack_health(),
        _check_default_tool_registry(),
        _check_tool_result_contract(),
        _check_tool_capability_registry(),
        _check_core_tool_health_safe_checks(),
        _check_default_scenario_pack(),
        _check_runtime_contract_docs(),
        _check_runtime_tool_governance(),
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
        _check_manifest_contract_strict(),
        _check_manifest_regression_gallery(),
        _check_public_quickstart_docs(),
        _check_live_safety_docs(),
        _check_live_cli_guardrails(),
        _check_live_execution_default_dry_run(),
        _check_optional_rpa_isolation(),
        _check_config_secrets_hygiene(),
        _check_safety_verification_pack(),
        _check_toolpack_governance(),
        _check_toolpack_lifecycle(),
        _check_event_source_contracts_file(),
        _check_event_source_contracts_valid(),
        _check_event_source_builders_importable(),
        _check_event_source_cli_available(),
        _check_event_source_route_alignment(),
        _check_order_management_manifests_exist(),
        _check_order_management_routes_exist(),
        _check_order_management_scenarios_exist(),
        _check_order_management_tool_registry(),
        _check_order_management_smoke_runs(),
        _check_order_management_approval_dry_run(),
        _check_order_management_docs_exist(),
        _check_supplier_invoice_manifest_exists(),
        _check_supplier_invoice_routes_exist(),
        _check_supplier_invoice_tools_registered(),
        _check_supplier_invoice_scenarios_exist(),
        _check_supplier_invoice_happy_path_smoke(),
        _check_supplier_invoice_exception_path_smoke(),
        _check_supplier_invoice_dry_run_approval(),
        _check_supplier_invoice_report_generation(),
        _check_supplier_invoice_docs_exist(),
        _check_cross_workflow_story_v2(),
        _check_readiness_scorecard_gate(),
    ])
    manifest_health_check = next((check for check in static_checks if check.get("name") == "manifest_catalog_health"), {})
    story_v2_check = next((check for check in static_checks if check.get("name") == "cross_workflow_story_v2"), {})
    scorecard_check = next((check for check in static_checks if check.get("name") == "readiness_scorecard_gate"), {})
    for key in ("json_path", "markdown_path"):
        value = str(manifest_health_check.get(key, "")).strip()
        if value:
            evidence_paths.append(_display_path(Path(value)))
    for key in ("story_markdown_path", "story_html_path", "story_pack_dir", "evidence_manifest_path", "summary_json_path"):
        value = str(story_v2_check.get(key, "")).strip()
        if value:
            evidence_paths.append(_display_path(Path(value)))
    for key in ("json_path", "markdown_path", "html_path"):
        value = str(scorecard_check.get(key, "")).strip()
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
            elif check["name"] == "toolpack_contract":
                release_blockers.append("tool pack contract docs or example pack failed")
            elif check["name"] == "google_workspace_toolpack_descriptor":
                release_blockers.append("google workspace descriptor failed")
            elif check["name"] == "google_workspace_read_only_safety":
                release_blockers.append("google workspace read-only safety failed")
            elif check["name"] == "google_workspace_health_safe":
                release_blockers.append("google workspace health failed")
            elif check["name"] == "google_workspace_docs":
                release_blockers.append("google workspace docs missing")
            elif check["name"] == "google_workspace_optional_boundary":
                release_blockers.append("google workspace optional boundary failed")
            elif check["name"] == "google_workspace_readonly_pack":
                release_blockers.append("google workspace readonly pack failed")
            elif check["name"] == "toolpack_loader":
                release_blockers.append("tool pack loader tests failed")
            elif check["name"] == "toolpack_registry_integration":
                release_blockers.append("tool pack registry integration failed")
            elif check["name"] == "toolpack_cli":
                release_blockers.append("tool pack CLI failed")
            elif check["name"] == "external_toolpacks_default_safe":
                release_blockers.append("external tool pack default safety failed")
            elif check["name"] == "builtin_toolpack_migration":
                release_blockers.append("built-in tool pack migration failed")
            elif check["name"] == "tool_registry_compatibility":
                release_blockers.append("tool registry compatibility failed")
            elif check["name"] == "tool_inventory":
                release_blockers.append("tool inventory failed")
            elif check["name"] == "migrated_toolpack_health":
                release_blockers.append("migrated tool pack health failed")
            elif check["name"] == "default_tool_registry":
                release_blockers.append("default tool registry failed")
            elif check["name"] == "tool_result_contract":
                release_blockers.append("tool result contract failed")
            elif check["name"] == "TOOL_CAPABILITY_REGISTRY":
                release_blockers.append("tool capability registry failed")
            elif check["name"] == "CORE_TOOL_HEALTH_SAFE_CHECKS":
                release_blockers.append("core tool health checks failed")
            elif check["name"] == "default_scenario_pack":
                release_blockers.append("default scenario pack failed")
            elif check["name"] == "runtime_contract_docs":
                release_blockers.append("runtime contract docs failed")
            elif check["name"] == "runtime_tool_governance":
                release_blockers.append("runtime governance enforcement failed")
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
            elif check["name"] == "manifest_contract_strict":
                release_blockers.append("manifest strict contract failed")
            elif check["name"] == "manifest_regression_gallery":
                release_blockers.append("manifest regression gallery failed")
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
            elif check["name"] == "safety_verification_pack":
                release_blockers.append("safety verification pack failed")
            elif check["name"] == "toolpack_governance":
                release_blockers.append("toolpack governance policy check failed")
            elif check["name"] == "toolpack_lifecycle":
                release_blockers.append("tool pack lifecycle check failed")
            elif check["name"] == "order_management_manifests_exist":
                release_blockers.append("order management manifests missing")
            elif check["name"] == "order_management_routes_exist":
                release_blockers.append("order management event routes missing")
            elif check["name"] == "order_management_scenarios_exist":
                release_blockers.append("order management scenarios missing")
            elif check["name"] == "order_management_tool_registry":
                release_blockers.append("order management tool registry incomplete")
            elif check["name"] == "order_management_smoke_runs":
                release_blockers.append("order management tool smoke runs failed")
            elif check["name"] == "order_management_approval_dry_run":
                release_blockers.append("order management approval dry-run safety failed")
            elif check["name"] == "order_management_docs_exist":
                release_blockers.append("order management docs missing")
            elif check["name"] == "supplier_invoice_manifest_exists":
                release_blockers.append("supplier invoice manifest missing")
            elif check["name"] == "supplier_invoice_routes_exist":
                release_blockers.append("supplier invoice routes missing")
            elif check["name"] == "supplier_invoice_tools_registered":
                release_blockers.append("supplier invoice tools missing")
            elif check["name"] == "supplier_invoice_scenarios_exist":
                release_blockers.append("supplier invoice scenarios missing")
            elif check["name"] == "supplier_invoice_happy_path_smoke":
                release_blockers.append("supplier invoice happy path smoke failed")
            elif check["name"] == "supplier_invoice_exception_path_smoke":
                release_blockers.append("supplier invoice exception path smoke failed")
            elif check["name"] == "supplier_invoice_dry_run_approval":
                release_blockers.append("supplier invoice dry-run approval failed")
            elif check["name"] == "supplier_invoice_report_generation":
                release_blockers.append("supplier invoice report generation failed")
            elif check["name"] == "supplier_invoice_docs_exist":
                release_blockers.append("supplier invoice docs missing")
            elif check["name"] == "cross_workflow_story_v2":
                release_blockers.append("cross-workflow story v2 failed")
            elif check["name"] == "readiness_scorecard_gate":
                release_blockers.append("readiness scorecard gate failed")

    for name, blocker in [
        ("toolpack_scaffold_tests", "scaffold tests failed"),
        ("toolpack_contract_runner_tests", "toolpack contract runner tests failed"),
        ("toolpack_scaffold_cli_tests", "toolpack scaffold CLI tests failed"),
        ("toolpack_generated_pack_execution_tests", "toolpack generated pack execution tests failed"),
        ("toolpack_governance_tests", "toolpack governance tests failed"),
        ("toolpack_lifecycle", "tool pack lifecycle check failed"),
    ]:
        cmd = next((c for c in commands if c.get("name") == name), None)
        if cmd and cmd.get("status") != "PASS":
            release_blockers.append(blocker)

    artifact_paths = [
        "README.md",
        "docs/release_artifacts.md",
        "docs/runtime_contracts.md",
        "docs/adding_new_tools.md",
        "docs/tool_contract_checklist.md",
        "docs/toolpack_contract.md",
        "docs/toolpack_authoring_guide.md",
        "docs/toolpack_examples.md",
        "docs/google_workspace_readonly_toolpack.md",
        "docs/google_workspace_setup.md",
        "docs/google_workspace_integration_tests.md",
        "docs/manifest_regression_gallery.md",
        "docs/builtin_toolpack_migration.md",
        "docs/tool_inventory.md",
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
        "config/enabled_toolpacks.json",
        "tool_packs/README.md",
        "tool_packs/demo_echo/toolpack.json",
        "tool_packs/demo_echo/README.md",
        "tool_packs/google_workspace/toolpack.json",
        "tool_packs/google_workspace/tools.py",
        "tool_packs/google_workspace/health.py",
        "tool_packs/google_workspace/auth.py",
        "tool_packs/google_workspace/README.md",
        "tool_packs/google_workspace/examples/smoke_gmail_list_unread.manifest.json",
        "tool_packs/google_workspace/examples/smoke_calendar_search.manifest.json",
        "tool_packs/google_workspace/examples/smoke_sheets_read_range.manifest.json",
        "tool_packs/core_business/toolpack.json",
        "tool_packs/core_memory/toolpack.json",
        "tool_packs/core_llm_micro/toolpack.json",
        "tool_packs/core_reports/toolpack.json",
        "src/tool_registry_compat.py",
        "src/tool_inventory.py",
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
        "docs/safety_verification.md",
        "src/toolpack_scaffold.py",
        "src/toolpack_contract_runner.py",
        "docs/toolpack_scaffold_wizard.md",
        "docs/toolpack_contract_testing.md",
        "src/toolpack_governance.py",
        "docs/toolpack_governance.md",
        "config/toolpack_governance.json",
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
        "toolpack_contract": _status_from_static(static_checks, "toolpack_contract"),
        "google_workspace_toolpack_descriptor": _status_from_static(static_checks, "google_workspace_toolpack_descriptor"),
        "google_workspace_read_only_safety": _status_from_static(static_checks, "google_workspace_read_only_safety"),
        "google_workspace_health_safe": _status_from_static(static_checks, "google_workspace_health_safe"),
        "google_workspace_docs": _status_from_static(static_checks, "google_workspace_docs"),
        "google_workspace_optional_boundary": _status_from_static(static_checks, "google_workspace_optional_boundary"),
        "google_workspace_readonly_pack": _status_from_static(static_checks, "google_workspace_readonly_pack"),
        "toolpack_loader": _status_from_static(static_checks, "toolpack_loader"),
        "toolpack_registry_integration": _status_from_static(static_checks, "toolpack_registry_integration"),
        "toolpack_cli": _status_from_static(static_checks, "toolpack_cli"),
        "external_toolpacks_default_safe": _status_from_static(static_checks, "external_toolpacks_default_safe"),
        "builtin_toolpack_migration": _status_from_static(static_checks, "builtin_toolpack_migration"),
        "tool_registry_compatibility": _status_from_static(static_checks, "tool_registry_compatibility"),
        "tool_inventory": _status_from_static(static_checks, "tool_inventory"),
        "migrated_toolpack_health": _status_from_static(static_checks, "migrated_toolpack_health"),
        "default_tool_registry": _status_from_static(static_checks, "default_tool_registry"),
        "tool_capability_registry": _status_from_static(static_checks, "TOOL_CAPABILITY_REGISTRY"),
        "core_tool_health_safe_checks": _status_from_static(static_checks, "CORE_TOOL_HEALTH_SAFE_CHECKS"),
        "runtime_tool_governance": _status_from_static(static_checks, "runtime_tool_governance"),
        "optional_rpa_excluded": _status_from_static(static_checks, "OPTIONAL_RPA_EXCLUDED_FROM_DEFAULT_RC"),
        "optional_rpa_live_probes_excluded": _status_from_static(static_checks, "OPTIONAL_RPA_LIVE_PROBES_EXCLUDED_FROM_RC"),
        "default_scenario_pack": _status_from_static(static_checks, "default_scenario_pack"),
        "golden_demo": _status_from_commands(commands, "golden_demo"),
        "release_artifacts": "PENDING",
        "docs_commands": _status_from_static(static_checks, "docs_command_alignment"),
        "adding_new_tools_doc": _status_from_static(static_checks, "adding_new_tools_doc"),
        "tool_contract_checklist_doc": _status_from_static(static_checks, "tool_contract_checklist_doc"),
        "manifest_catalog_health": _status_from_static(static_checks, "manifest_catalog_health"),
        "manifest_contract_strict": _status_from_static(static_checks, "manifest_contract_strict"),
        "public_quickstart_docs": _status_from_static(static_checks, "public_quickstart_docs"),
        "optional_rpa_isolation": _status_from_static(static_checks, "optional_rpa_isolation"),
        "config_secrets_hygiene": _status_from_static(static_checks, "config_secrets_hygiene"),
        "safety_verification_pack": _status_from_static(static_checks, "safety_verification_pack"),
        "live_blocked_evidence_report": _status_from_static(static_checks, "safety_verification_pack"),
        "default_no_live_side_effects": _status_from_static(static_checks, "safety_verification_pack"),
        "toolpack_scaffold": _status_from_commands(commands, "toolpack_scaffold_tests"),
        "toolpack_contract_runner": _status_from_commands(commands, "toolpack_contract_runner_tests"),
        "toolpack_generated_pack_execution": _status_from_commands(commands, "toolpack_generated_pack_execution_tests"),
        "toolpack_governance": _status_from_static(static_checks, "toolpack_governance"),
        "cross_workflow_story_v2": _status_from_static(static_checks, "cross_workflow_story_v2"),
        "readiness_scorecard_gate": _status_from_static(static_checks, "readiness_scorecard_gate"),
        "supplier_invoice_manifest_exists": _status_from_static(static_checks, "supplier_invoice_manifest_exists"),
        "supplier_invoice_routes_exist": _status_from_static(static_checks, "supplier_invoice_routes_exist"),
        "supplier_invoice_tools_registered": _status_from_static(static_checks, "supplier_invoice_tools_registered"),
        "supplier_invoice_scenarios_exist": _status_from_static(static_checks, "supplier_invoice_scenarios_exist"),
        "supplier_invoice_happy_path_smoke": _status_from_static(static_checks, "supplier_invoice_happy_path_smoke"),
        "supplier_invoice_exception_path_smoke": _status_from_static(static_checks, "supplier_invoice_exception_path_smoke"),
        "supplier_invoice_dry_run_approval": _status_from_static(static_checks, "supplier_invoice_dry_run_approval"),
        "supplier_invoice_report_generation": _status_from_static(static_checks, "supplier_invoice_report_generation"),
        "supplier_invoice_docs_exist": _status_from_static(static_checks, "supplier_invoice_docs_exist"),
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
        "docs/safety_verification.md",
        "src/toolpack_scaffold.py",
        "src/toolpack_contract_runner.py",
        "docs/toolpack_scaffold_wizard.md",
        "docs/toolpack_contract_testing.md",
        "src/toolpack_governance.py",
        "docs/toolpack_governance.md",
        "config/toolpack_governance.json",
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
        _display_path(ROOT / "docs" / "toolpack_contract.md"),
        _display_path(ROOT / "docs" / "toolpack_authoring_guide.md"),
        _display_path(ROOT / "docs" / "toolpack_examples.md"),
        _display_path(ROOT / "docs" / "builtin_toolpack_migration.md"),
        _display_path(ROOT / "docs" / "tool_inventory.md"),
        _display_path(DEFAULT_DEMO_BOUNDARY_MD),
        _display_path(KNOWN_LIMITATIONS_MD),
        _display_path(RELEASE_STATUS_JSON),
        _display_path(RELEASE_EVIDENCE_JSON),
        _display_path(ROOT / "config" / "enabled_toolpacks.json"),
        _display_path(ROOT / "tool_packs" / "README.md"),
        _display_path(ROOT / "tool_packs" / "demo_echo" / "toolpack.json"),
        _display_path(ROOT / "tool_packs" / "demo_echo" / "README.md"),
        _display_path(ROOT / "tool_packs" / "core_business" / "toolpack.json"),
        _display_path(ROOT / "tool_packs" / "core_memory" / "toolpack.json"),
        _display_path(ROOT / "tool_packs" / "core_llm_micro" / "toolpack.json"),
        _display_path(ROOT / "tool_packs" / "core_reports" / "toolpack.json"),
    ])

    checks["release_artifacts"] = _status_from_artifacts(artifact_checks, [
        "docs/release_artifacts.md",
        "docs/runtime_contracts.md",
        "docs/adding_new_tools.md",
        "docs/tool_contract_checklist.md",
        "docs/toolpack_contract.md",
        "docs/toolpack_authoring_guide.md",
        "docs/toolpack_examples.md",
        "docs/google_workspace_readonly_toolpack.md",
        "docs/google_workspace_setup.md",
        "docs/google_workspace_integration_tests.md",
        "docs/builtin_toolpack_migration.md",
        "docs/tool_inventory.md",
        "docs/default_demo_boundary.md",
        "docs/known_limitations.md",
        "docs/current_release_status.md",
        "docs/release_evidence_pack.md",
        "config/enabled_toolpacks.json",
        "tool_packs/README.md",
        "tool_packs/demo_echo/toolpack.json",
        "tool_packs/demo_echo/README.md",
        "tool_packs/core_business/toolpack.json",
        "tool_packs/core_memory/toolpack.json",
        "tool_packs/core_llm_micro/toolpack.json",
        "tool_packs/core_reports/toolpack.json",
        "scripts/run_golden_demo.py",
        "runtime_data/outputs/reports/golden_demo_report.md",
        "runtime_data/outputs/reports/golden_demo_report.html",
        "runtime_data/outputs/audit/golden_demo_audit.json",
        "runtime_data/audit/release_status_latest.json",
        "runtime_data/audit/release_evidence_pack.json",
        "runtime_data/tool_health/latest_tool_health.json",
    ])
    checks["manifest_regression_gallery"] = _status_from_static(static_checks, "manifest_regression_gallery")

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
        result = next(
            (item for item in snapshot.get("results", []) if isinstance(item, dict) and str(item.get("tool_id", "")) == "rpa_google_messages"),
            None,
        )
        live_rpa = bool(snapshot.get("live_rpa", False))
        ok = capability.core_or_optional == "optional" and capability.rpa_live_probe_required and not live_rpa
        if result is not None and str(result.get("status", "")) in {"live_verified", "failing"}:
            ok = False
        return {
            "name": "OPTIONAL_RPA_LIVE_PROBES_EXCLUDED_FROM_RC",
            "status": "PASS" if ok else "FAIL",
            "tool_present": capability.tool_id,
            "snapshot_tools": sorted(
                str(item.get("tool_id", ""))
                for item in snapshot.get("results", [])
                if isinstance(item, dict)
            ),
            "live_rpa": live_rpa,
            "tool_status": None if result is None else str(result.get("status", "")),
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
        "tool packs",
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
        "toolpack.json",
        "tool pack",
    ]
    missing = [term for term in required_terms if term not in text]
    return {"name": "adding_new_tools_doc", "status": "PASS" if path.is_file() and not missing else "FAIL", "path": str(path), "missing": missing}


def _check_tool_contract_checklist_doc() -> dict[str, Any]:
    path = TOOL_CONTRACT_CHECKLIST_MD
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    required_terms = ["- [ ]", "tool_registry", "pendingaction", "health check", "live execution", "toolpack.json"]
    missing = [term for term in required_terms if term not in text]
    return {"name": "tool_contract_checklist_doc", "status": "PASS" if path.is_file() and not missing else "FAIL", "path": str(path), "missing": missing}


def _check_toolpack_contract() -> dict[str, Any]:
    required_paths = [
        ROOT / "docs" / "toolpack_contract.md",
        ROOT / "docs" / "toolpack_authoring_guide.md",
        ROOT / "docs" / "toolpack_examples.md",
        ROOT / "tool_packs" / "README.md",
        ROOT / "tool_packs" / "demo_echo" / "toolpack.json",
        ROOT / "tool_packs" / "demo_echo" / "README.md",
        ROOT / "config" / "enabled_toolpacks.json",
    ]
    missing_paths = [str(path.relative_to(ROOT)) for path in required_paths if not path.is_file()]
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8").lower() if (ROOT / "README.md").is_file() else ""
    docs_text = " ".join(
        path.read_text(encoding="utf-8").lower()
        for path in required_paths
        if path.is_file() and path.suffix in {".md", ".json"}
    )
    required_terms = [
        "tool pack",
        "toolpack.json",
        "external tool packs",
        "safety fields",
        "manifest usage",
    ]
    missing_terms = [term for term in required_terms if term not in docs_text and term not in readme_text]
    status = "PASS" if not missing_paths and not missing_terms else "FAIL"
    return {
        "name": "toolpack_contract",
        "status": status,
        "missing_paths": missing_paths,
        "missing_terms": missing_terms,
    }


def _check_tool_result_contract() -> dict[str, Any]:
    try:
        from runtime.manifest_loader import load_manifest
        from runtime.taskframe import create_taskframe
        from runtime.tool_registry import build_tool_registry
        from runtime.tool_runner import ToolRunner
        from src.toolpack_contract_runner import run_toolpack_contract_tests, validate_tool_result_shape
        from src.toolpack_loader import discover_toolpacks

        registry = build_tool_registry(include_external=True)
        missing_output_type = [key for key, spec in registry.items() if not str(spec.get("output_type", "")).strip()]

        empty_evidence_rejected = not validate_tool_result_shape(
            {"ok": True, "type": "tool_result_contract_test", "data": {}, "evidence": {}, "error": ""},
            "tool_result_contract_test",
        )["ok"]
        failed_result_requires_error = not validate_tool_result_shape(
            {"ok": False, "type": "tool_result_contract_test", "data": {}, "evidence": {"tool": "tool", "mode": "dry_run", "source": "builtin", "operation": "validation", "input_refs": [], "output_ref": "tool_result_contract_test"}, "error": ""},
            "tool_result_contract_test",
        )["ok"]

        demo_pack_result = run_toolpack_contract_tests(ROOT / "tool_packs" / "demo_echo" / "toolpack.json", include_manifest_smoke=False)
        discovery = discover_toolpacks(include_disabled=False)
        active_override_packs = [
            str(item.get("toolpack_id", ""))
            for item in discovery.get("toolpacks", [])
            if bool(item.get("enabled", False)) and bool(item.get("allow_empty_evidence_for_contract_test", False))
        ]

        smoke_manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        smoke_frame = create_taskframe(smoke_manifest)
        smoke_frame.state = "RUNNING"
        smoke_step_result = ToolRunner(dry_run=True).run_step(smoke_frame, smoke_frame.steps[0])
        smoke_tool_call = smoke_frame.tool_calls[-1] if smoke_frame.tool_calls else {}
        smoke_ok = (
            bool(smoke_step_result.ok)
            and isinstance(smoke_step_result.evidence, dict)
            and bool(smoke_step_result.evidence)
            and bool(smoke_tool_call.get("evidence_ref", ""))
            and bool(smoke_tool_call.get("mode", ""))
            and bool(smoke_tool_call.get("source", ""))
        )

        pending_manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        pending_frame = create_taskframe(pending_manifest)
        pending_frame.state = "RUNNING"
        staged = ToolRunner(dry_run=True).run_step(pending_frame, pending_frame.steps[0])
        pending_result = {"ok": False, "evidence": {}, "tool_call": {}}
        if bool(staged.ok) and pending_frame.pending_actions:
            pending_action = pending_frame.pending_actions[0]
            pending_action["status"] = "APPROVED"
            pending_result_obj = ToolRunner(dry_run=True).execute_pending_action(pending_frame, pending_action)
            pending_tool_call = pending_frame.tool_calls[-1] if pending_frame.tool_calls else {}
            pending_result = {
                "ok": bool(pending_result_obj.ok),
                "evidence": pending_result_obj.evidence,
                "tool_call": pending_tool_call,
            }

        pending_ok = bool(pending_result["ok"]) and isinstance(pending_result["evidence"], dict) and bool(pending_result["evidence"]) and bool(pending_result["tool_call"].get("evidence_ref", ""))
        docs_text = TOOL_RESULT_CONTRACT_MD.read_text(encoding="utf-8").lower() if TOOL_RESULT_CONTRACT_MD.is_file() else ""
        docs_ok = TOOL_RESULT_CONTRACT_MD.is_file() and all(
            term in docs_text
            for term in (
                "canonical result shape",
                "evidence shape",
                "secrets",
                "taskframe",
                "pending_action_id",
                "failure",
            )
        )

        ok = (
            not missing_output_type
            and empty_evidence_rejected
            and failed_result_requires_error
            and bool(demo_pack_result.get("ok", False))
            and not active_override_packs
            and smoke_ok
            and pending_ok
            and docs_ok
        )
        return {
            "name": "tool_result_contract",
            "status": "PASS" if ok else "FAIL",
            "missing_output_type": missing_output_type,
            "empty_evidence_rejected": empty_evidence_rejected,
            "failed_result_requires_error": failed_result_requires_error,
            "demo_pack_result": demo_pack_result,
            "active_override_packs": active_override_packs,
            "smoke_result": {
                "ok": bool(smoke_step_result.ok),
                "evidence": smoke_step_result.evidence,
                "tool_call": smoke_tool_call,
            },
            "pending_result": pending_result,
            "docs_ok": docs_ok,
        }
    except Exception as exc:
        return {"name": "tool_result_contract", "status": "FAIL", "error": str(exc)}


def _check_google_workspace_toolpack_descriptor() -> dict[str, Any]:
    required_paths = [
        ROOT / "tool_packs" / "google_workspace" / "toolpack.json",
        ROOT / "tool_packs" / "google_workspace" / "README.md",
        ROOT / "tool_packs" / "google_workspace" / "auth.py",
        ROOT / "tool_packs" / "google_workspace" / "tools.py",
        ROOT / "tool_packs" / "google_workspace" / "health.py",
    ]
    missing_paths = [str(path.relative_to(ROOT)) for path in required_paths if not path.is_file()]
    if missing_paths:
        return {"name": "google_workspace_toolpack_descriptor", "status": "FAIL", "missing_paths": missing_paths}
    try:
        from src.toolpack_loader import load_toolpack_descriptor, validate_toolpack_descriptor

        descriptor = load_toolpack_descriptor(ROOT / "tool_packs" / "google_workspace" / "toolpack.json")
        validation = validate_toolpack_descriptor(descriptor, base_path=ROOT / "tool_packs" / "google_workspace")
        ok = bool(validation.get("ok", False)) and int(validation.get("tool_count", 0) or 0) == 7
        return {
            "name": "google_workspace_toolpack_descriptor",
            "status": "PASS" if ok else "FAIL",
            "validation": validation,
        }
    except Exception as exc:
        return {"name": "google_workspace_toolpack_descriptor", "status": "FAIL", "error": str(exc)}


def _check_google_workspace_read_only_safety() -> dict[str, Any]:
    try:
        from src.google_workspace_safety_scan import scan_google_workspace_pack_for_forbidden_calls

        descriptor = json.loads((ROOT / "tool_packs" / "google_workspace" / "toolpack.json").read_text(encoding="utf-8"))
        side_effect_tools = [item.get("tool", "") for item in descriptor.get("tools", []) if isinstance(item, dict) and (item.get("side_effect") or item.get("allow_live_side_effect"))]
        scan = scan_google_workspace_pack_for_forbidden_calls(ROOT / "tool_packs" / "google_workspace")
        ok = not side_effect_tools and scan.get("ok", False)
        return {
            "name": "google_workspace_read_only_safety",
            "status": "PASS" if ok else "FAIL",
            "side_effect_tools": side_effect_tools,
            "scan": scan,
        }
    except Exception as exc:
        return {"name": "google_workspace_read_only_safety", "status": "FAIL", "error": str(exc)}


def _check_google_workspace_health_safe() -> dict[str, Any]:
    try:
        from src.toolpack_loader import check_toolpack_health

        result = check_toolpack_health("google_workspace", config_path=ROOT / "config" / "enabled_toolpacks.json", live=False)
        ok = result.get("status") in {"ready", "needs_auth", "missing_dependency"} and not bool(result.get("live_checked", False))
        return {
            "name": "google_workspace_health_safe",
            "status": "PASS" if ok else "FAIL",
            "health": result,
        }
    except Exception as exc:
        return {"name": "google_workspace_health_safe", "status": "FAIL", "error": str(exc)}


def _check_google_workspace_docs() -> dict[str, Any]:
    required_paths = [
        ROOT / "docs" / "google_workspace_readonly_toolpack.md",
        ROOT / "docs" / "google_workspace_setup.md",
        ROOT / "docs" / "google_workspace_integration_tests.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.is_file()]
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8").lower() if (ROOT / "README.md").is_file() else ""
    docs_text = " ".join(path.read_text(encoding="utf-8").lower() for path in required_paths if path.is_file())
    required_terms = ["google workspace", "read-only", "oauth", "integration tests", "tool pack"]
    missing_terms = [term for term in required_terms if term not in docs_text and term not in readme_text]
    ok = not missing and not missing_terms
    return {
        "name": "google_workspace_docs",
        "status": "PASS" if ok else "FAIL",
        "missing_paths": missing,
        "missing_terms": missing_terms,
    }


def _check_google_workspace_optional_boundary() -> dict[str, Any]:
    try:
        from runtime.tool_registry import build_tool_registry
        from src.toolpack_loader import build_external_tool_registry, discover_toolpacks

        discovery = discover_toolpacks(include_disabled=True)
        pack = next((item for item in discovery.get("toolpacks", []) if str(item.get("toolpack_id", "")) == "google_workspace"), None)
        external_registry = build_external_tool_registry()
        registry = build_tool_registry(include_external=True)
        ok = bool(pack) and not external_registry and "gmail/list_unread" not in registry
        return {
            "name": "google_workspace_optional_boundary",
            "status": "PASS" if ok else "FAIL",
            "discovered": bool(pack),
            "external_registry_count": len(external_registry),
            "registry_contains_google": "gmail/list_unread" in registry,
        }
    except Exception as exc:
        return {"name": "google_workspace_optional_boundary", "status": "FAIL", "error": str(exc)}


def _check_google_workspace_readonly_pack() -> dict[str, Any]:
    missing: list[str] = []
    toolpack_dir = ROOT / "tool_packs" / "google_workspace"
    descriptor_path = toolpack_dir / "toolpack.json"
    tool_paths = [
        toolpack_dir / "toolpack.json",
        toolpack_dir / "tools.py",
        toolpack_dir / "health.py",
        toolpack_dir / "auth.py",
        toolpack_dir / "README.md",
        toolpack_dir / "examples" / "smoke_gmail_list_unread.manifest.json",
        toolpack_dir / "examples" / "smoke_calendar_search.manifest.json",
        toolpack_dir / "examples" / "smoke_sheets_read_range.manifest.json",
        ROOT / "docs" / "google_workspace_readonly_toolpack.md",
        ROOT / "docs" / "google_workspace_setup.md",
        ROOT / "docs" / "google_workspace_integration_tests.md",
    ]
    missing.extend(str(path.relative_to(ROOT)) for path in tool_paths if not path.is_file())
    if missing:
        return {"name": "google_workspace_readonly_pack", "status": "FAIL", "missing_paths": missing}

    try:
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        tools = [item for item in descriptor.get("tools", []) if isinstance(item, dict)]
        required_tools = {
            "google/auth_status",
            "gmail/list_unread",
            "gmail/search",
            "gmail/read_metadata",
            "calendar/search",
            "calendar/list_upcoming",
            "sheets/read_range",
        }
        read_only_ok = all(
            item.get("side_effect") is False
            and item.get("requires_approval") is False
            and item.get("allow_live") is True
            and item.get("allow_live_side_effect") is False
            and item.get("live_guardrail") == "read_only_google_workspace"
            for item in tools
        )
        descriptor_ok = (
            descriptor.get("toolpack_id") == "google_workspace"
            and descriptor.get("risk_class") == "read_only_external_api"
            and descriptor.get("health_supported") is True
            and len(tools) == 7
            and {str(item.get("tool", "")) for item in tools} == required_tools
            and read_only_ok
        )

        from src.toolpack_loader import load_toolpack_descriptor, validate_toolpack_descriptor
        from src.toolpack_lifecycle import evaluate_toolpack_lifecycle, write_lifecycle_report
        from src.toolpack_loader import check_toolpack_health

        validation = validate_toolpack_descriptor(load_toolpack_descriptor(descriptor_path), base_path=toolpack_dir)
        health = check_toolpack_health("google_workspace", config_path=ROOT / "config" / "enabled_toolpacks.json", live=False)
        lifecycle = evaluate_toolpack_lifecycle(
            descriptor_path,
            environment="dev",
            config_path=ROOT / "config" / "enabled_toolpacks.json",
            runtime_data_dir=ROOT / "runtime_data",
        )

        lifecycle_status = str(lifecycle.get("status", "")).strip()
        lifecycle_ok = lifecycle_status in {"READY", "READY_WITH_WARNINGS", "GOVERNANCE_REQUIRED", "DISABLED", "UNTESTED"}
        health_ok = bool(health.get("health_supported", False)) and str(health.get("status", "")).strip() in {"ready", "needs_auth", "missing_dependency", "live_verified", "failing"}

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            runtime_data_dir = Path(tmp) / "runtime_data"
            runtime_data_dir.mkdir(parents=True, exist_ok=True)
            written = write_lifecycle_report(lifecycle, runtime_data_dir=runtime_data_dir)
            report_written = Path(written.get("json_path", "")).is_file() and Path(written.get("markdown_path", "")).is_file()

        pyproject = ROOT / "pyproject.toml"
        google_extra_optional = False
        default_install_optional = False
        if pyproject.is_file():
            project = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            optional_deps = dict(project.get("project", {}).get("optional-dependencies", {}))
            google_extra = optional_deps.get("google", [])
            google_extra_optional = isinstance(google_extra, list) and any("google-api-python-client" in str(item) for item in google_extra)
            default_deps = project.get("project", {}).get("dependencies", [])
            default_install_optional = all("google-api-python-client" not in str(item) for item in default_deps)

        auth_result = None
        try:
            from tool_packs.google_workspace import auth

            dependency_state = auth.google_dependency_state()
            auth_files = auth.google_auth_files()
            auth_result = {
                "dependencies_ok": bool(dependency_state.get("ok")),
                "credentials_file_present": bool(auth_files.get("credentials_file_present")),
                "token_file_present": bool(auth_files.get("token_file_present")),
            }
        except Exception as exc:
            auth_result = {"error": str(exc)}

        if auth_result and auth_result.get("dependencies_ok") and (auth_result.get("credentials_file_present") or auth_result.get("token_file_present")):
            expected_ready = lifecycle_status == "READY"
        else:
            expected_ready = lifecycle_status in {"GOVERNANCE_REQUIRED", "DISABLED", "READY_WITH_WARNINGS", "UNTESTED"}

        ok = (
            descriptor_ok
            and validation.get("ok", False)
            and health_ok
            and lifecycle_ok
            and report_written
            and google_extra_optional
            and default_install_optional
            and expected_ready
        )
        return {
            "name": "google_workspace_readonly_pack",
            "status": "PASS" if ok else "FAIL",
            "descriptor_ok": descriptor_ok,
            "validation": validation,
            "health": health,
            "lifecycle": lifecycle,
            "report_written": report_written,
            "google_extra_optional": google_extra_optional,
            "default_install_optional": default_install_optional,
            "auth_result": auth_result,
        }
    except Exception as exc:
        return {"name": "google_workspace_readonly_pack", "status": "FAIL", "error": str(exc)}


def _check_toolpack_loader() -> dict[str, Any]:
    result = run_command("toolpack_loader_tests", ["python", "-m", "pytest", "tests/test_toolpack_loader.py"], timeout_seconds=180)
    return {
        "name": "toolpack_loader",
        "status": result["status"],
        "command": result["command"],
        "returncode": result["returncode"],
        "stdout_tail": result["stdout_tail"],
        "stderr_tail": result["stderr_tail"],
    }


def _check_toolpack_registry_integration() -> dict[str, Any]:
    result = run_command("toolpack_registry_tests", ["python", "-m", "pytest", "tests/test_toolpack_registry_integration.py"], timeout_seconds=180)
    return {
        "name": "toolpack_registry_integration",
        "status": result["status"],
        "command": result["command"],
        "returncode": result["returncode"],
        "stdout_tail": result["stdout_tail"],
        "stderr_tail": result["stderr_tail"],
    }


def _check_toolpack_cli() -> dict[str, Any]:
    commands = [
        run_command("toolpack_cli_discover", ["python", "-m", "src.taskframe_cli", "tools", "discover"], timeout_seconds=180),
        run_command("toolpack_cli_list", ["python", "-m", "src.taskframe_cli", "tools", "list"], timeout_seconds=180),
        run_command("toolpack_cli_validate", ["python", "-m", "src.taskframe_cli", "tools", "validate", "tool_packs/demo_echo/toolpack.json"], timeout_seconds=180),
        run_command("toolpack_cli_health", ["python", "-m", "src.taskframe_cli", "tools", "health", "demo_echo"], timeout_seconds=180),
        run_command("toolpack_cli_inventory", ["python", "-m", "src.taskframe_cli", "tools", "inventory"], timeout_seconds=180),
        run_command("toolpack_cli_compat_check", ["python", "-m", "src.taskframe_cli", "tools", "compat-check"], timeout_seconds=180),
    ]
    ok = all(item["status"] == "PASS" for item in commands)
    return {
        "name": "toolpack_cli",
        "status": "PASS" if ok else "FAIL",
        "commands": commands,
        "command_failures": [item["name"] for item in commands if item["status"] != "PASS"],
    }


def _check_external_toolpacks_default_safe() -> dict[str, Any]:
    try:
        from runtime.tool_registry import build_tool_registry
        from src.toolpack_loader import build_external_tool_registry, discover_toolpacks

        builtin_only = build_tool_registry(include_external=False)
        full_registry = build_tool_registry(include_external=True)
        external_registry = build_external_tool_registry()
        discovery = discover_toolpacks(include_disabled=True)
        has_demo_echo = any(str(item.get("toolpack_id", "")) == "demo_echo" for item in discovery.get("toolpacks", []))
        ok = (
            "echo/echo" not in builtin_only
            and "echo/echo" not in full_registry
            and not external_registry
            and has_demo_echo
        )
        return {
            "name": "external_toolpacks_default_safe",
            "status": "PASS" if ok else "FAIL",
            "builtin_count": len(builtin_only),
            "full_count": len(full_registry),
            "external_count": len(external_registry),
            "discovered_demo_echo": has_demo_echo,
        }
    except Exception as exc:
        return {"name": "external_toolpacks_default_safe", "status": "FAIL", "error": str(exc)}


def _check_builtin_toolpack_migration() -> dict[str, Any]:
    required_paths = [
        ROOT / "tool_packs" / "core_business" / "toolpack.json",
        ROOT / "tool_packs" / "core_memory" / "toolpack.json",
        ROOT / "tool_packs" / "core_llm_micro" / "toolpack.json",
        ROOT / "tool_packs" / "core_reports" / "toolpack.json",
        ROOT / "src" / "tool_registry_compat.py",
        ROOT / "src" / "tool_inventory.py",
        ROOT / "docs" / "builtin_toolpack_migration.md",
        ROOT / "docs" / "tool_inventory.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.is_file()]
    return {
        "name": "builtin_toolpack_migration",
        "status": "PASS" if not missing else "FAIL",
        "missing_paths": missing,
    }


def _check_tool_registry_compatibility() -> dict[str, Any]:
    try:
        from runtime.tool_registry import BUILTIN_LEGACY_TOOL_REGISTRY
        from src.tool_registry_compat import build_compatibility_registry, compare_legacy_and_toolpack_registry

        migrated_registry = build_compatibility_registry()
        comparison = compare_legacy_and_toolpack_registry(BUILTIN_LEGACY_TOOL_REGISTRY, migrated_registry)
        return {
            "name": "tool_registry_compatibility",
            "status": "PASS" if comparison.get("ok", False) else "FAIL",
            "summary": {
                "migrated_toolpack_tools": len(migrated_registry),
                "legacy_fallback_tools": len(BUILTIN_LEGACY_TOOL_REGISTRY),
                "new_tools": len(comparison.get("new_tools", [])),
                "changed_tools": len(comparison.get("changed_tools", [])),
                "missing_tools": len(comparison.get("missing_tools", [])),
            },
            "comparison": comparison,
        }
    except Exception as exc:
        return {"name": "tool_registry_compatibility", "status": "FAIL", "error": str(exc)}


def _check_tool_inventory() -> dict[str, Any]:
    try:
        from src.tool_inventory import build_tool_inventory_report

        report = build_tool_inventory_report(runtime_data_dir=ROOT / "runtime_data")
        ok = bool(report.get("ok", False))
        return {
            "name": "tool_inventory",
            "status": "PASS" if ok else "FAIL",
            "summary": report.get("summary", {}),
            "json_path": report.get("json_path", ""),
            "markdown_path": report.get("markdown_path", ""),
            "docs_path": report.get("docs_path", ""),
        }
    except Exception as exc:
        return {"name": "tool_inventory", "status": "FAIL", "error": str(exc)}


def _check_migrated_toolpack_health() -> dict[str, Any]:
    try:
        from runtime.tool_health import check_all_tool_health, check_tool_health

        results = check_all_tool_health(include_optional=False, live_rpa=False)
        ids = {item.tool_id for item in results}
        required_ids = {"toolpack:core_business", "toolpack:core_memory", "toolpack:core_llm_micro", "toolpack:core_reports"}
        single = check_tool_health("toolpack:core_business", live=False)
        ok = required_ids.issubset(ids) and bool(single.ok)
        return {
            "name": "migrated_toolpack_health",
            "status": "PASS" if ok else "FAIL",
            "required_ids": sorted(required_ids),
            "observed_ids": sorted(required_ids.intersection(ids)),
            "single_health": single.to_dict() if hasattr(single, "to_dict") else {},
        }
    except Exception as exc:
        return {"name": "migrated_toolpack_health", "status": "FAIL", "error": str(exc)}


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


def _check_manifest_contract_strict() -> dict[str, Any]:
    try:
        from src.manifest_health import run_manifest_health_check, write_manifest_health_report
    except Exception as exc:
        return {"name": "manifest_contract_strict", "status": "FAIL", "error": str(exc)}

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        runtime_data_dir = Path(tmp) / "runtime_data"
        runtime_data_dir.mkdir(parents=True, exist_ok=True)
        result = run_manifest_health_check(
            manifest_dir=ROOT / "manifests",
            runtime_data_dir=runtime_data_dir,
            include_smoke=False,
            strict_contract=True,
        )
        report = write_manifest_health_report(result, runtime_data_dir=runtime_data_dir, report_name="manifest_health_strict_report")

    summary = result.get("summary") if isinstance(result, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    strict_failed = int(summary.get("strict_failed", 0) or 0)
    strict_warnings = int(summary.get("strict_warnings", 0) or 0)
    report_ok = bool(report.get("ok"))
    ok = bool(result.get("ok")) and report_ok and strict_failed == 0
    return {
        "name": "manifest_contract_strict",
        "status": "PASS" if ok else "FAIL",
        "health_status": result.get("status", "UNKNOWN"),
        "summary": summary,
        "report_ok": report_ok,
        "strict_failed": strict_failed,
        "strict_warnings": strict_warnings,
        "json_path": str(report.get("json_path", "")),
        "markdown_path": str(report.get("markdown_path", "")),
        "error": str(report.get("error", "")),
    }


def _check_manifest_regression_gallery() -> dict[str, Any]:
    try:
        from src.manifest_regression_gallery import (
            run_gallery,
            validate_gallery_index,
            write_gallery_report,
        )
    except Exception as exc:
        return {"name": "manifest_regression_gallery", "status": "FAIL", "error": str(exc)}

    gallery_dir = ROOT / "tests" / "fixtures" / "manifest_regression_gallery"
    validation = validate_gallery_index(gallery_dir)
    if not validation.get("ok", False):
        return {
            "name": "manifest_regression_gallery",
            "status": "FAIL",
            "gallery_dir": _display_path(gallery_dir),
            "validation": validation,
        }

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        runtime_data_dir = Path(tmp) / "runtime_data"
        runtime_data_dir.mkdir(parents=True, exist_ok=True)
        result = run_gallery(
            gallery_dir=gallery_dir,
            runtime_data_dir=runtime_data_dir,
            strict=True,
            smoke=True,
            repair_guidance=True,
            autofix=True,
        )
        report = write_gallery_report(result, runtime_data_dir=runtime_data_dir)

    ok = bool(result.get("ok")) and bool(report.get("ok")) and result.get("failed", 0) == 0
    return {
        "name": "manifest_regression_gallery",
        "status": "PASS" if ok else "FAIL",
        "gallery_dir": _display_path(gallery_dir),
        "validation": validation,
        "result": {
            "ok": result.get("ok", False),
            "status": result.get("status", "UNKNOWN"),
            "total_fixtures": result.get("total_fixtures", 0),
            "passed": result.get("passed", 0),
            "failed": result.get("failed", 0),
        },
        "report_ok": bool(report.get("ok")),
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


def _check_safety_verification_pack() -> dict[str, Any]:
    missing: list[str] = []

    if not (ROOT / "docs" / "safety_verification.md").is_file():
        missing.append("docs/safety_verification.md")

    cli_ref = ROOT / "docs" / "cli_reference.md"
    if cli_ref.is_file():
        if "safety-pack" not in cli_ref.read_text(encoding="utf-8"):
            missing.append("cli_reference:safety-pack")
    else:
        missing.append("docs/cli_reference.md")

    result = run_command(
        "safety_pack_no_demo",
        ["python", "-m", "src.taskframe_cli", "safety-pack", "--no-demo", "--json"],
        timeout_seconds=120,
    )
    if result["returncode"] != 0:
        missing.append("safety_pack_command_failed")
    else:
        try:
            import json as _json
            data = _json.loads(result["stdout"])
            if not data.get("ok"):
                missing.append("safety_pack_ok_not_true")
            if len(data.get("claims", [])) != 9:
                missing.append(f"safety_pack_expected_9_claims_got_{len(data.get('claims', []))}")
        except Exception as exc:
            missing.append(f"safety_pack_json_parse_error:{exc}")

    return {
        "name": "safety_verification_pack",
        "status": "PASS" if not missing else "FAIL",
        "missing": missing,
    }


def _check_toolpack_governance() -> dict[str, Any]:
    missing: list[str] = []

    gov_config = ROOT / "config" / "toolpack_governance.json"
    if not gov_config.is_file():
        missing.append("config/toolpack_governance.json")

    gov_doc = ROOT / "docs" / "toolpack_governance.md"
    if not gov_doc.is_file():
        missing.append("docs/toolpack_governance.md")
    else:
        text = gov_doc.read_text(encoding="utf-8")
        for required in ("core", "optional", "experimental", "high_risk", "blocked",
                         "demo", "release", "tools policy", "tools enable", "tools disable"):
            if required not in text:
                missing.append(f"governance_doc_missing:{required}")

    cli_ref = ROOT / "docs" / "cli_reference.md"
    if cli_ref.is_file():
        cli_text = cli_ref.read_text(encoding="utf-8")
        for cmd in ("tools policy", "tools enable", "tools disable", "tools governance-report"):
            if cmd not in cli_text:
                missing.append(f"cli_reference_missing:{cmd}")
    else:
        missing.append("docs/cli_reference.md")

    try:
        from src.toolpack_governance import validate_governance_for_release
        result = validate_governance_for_release()
        if not result.get("ok"):
            missing.extend(result.get("errors", [f"governance_release_validation_failed"]))
    except Exception as exc:
        missing.append(f"governance_import_error:{exc}")

    return {
        "name": "toolpack_governance",
        "status": "PASS" if not missing else "FAIL",
        "missing": missing,
    }


def _check_runtime_tool_governance() -> dict[str, Any]:
    missing: list[str] = []
    profile_path = ROOT / "config" / "runtime_profile.json"
    doc_path = ROOT / "docs" / "runtime_tool_governance.md"
    cli_ref = ROOT / "docs" / "cli_reference.md"
    if not profile_path.is_file():
        missing.append("config/runtime_profile.json")
        profile = {"environment": "demo", "governance_enforced": True, "allow_unknown_toolpack_in_dev": False, "allow_high_risk_live_override": False}
    else:
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"name": "runtime_tool_governance", "status": "FAIL", "error": f"runtime profile parse failed: {exc}"}

    if not doc_path.is_file():
        missing.append("docs/runtime_tool_governance.md")
    if not cli_ref.is_file():
        missing.append("docs/cli_reference.md")
    else:
        cli_text = cli_ref.read_text(encoding="utf-8").lower()
        for required in ("taskframe runtime profile", "taskframe runtime governance-check"):
            if required not in cli_text:
                missing.append(f"cli_reference_missing:{required}")

    from runtime.runtime_environment import resolve_runtime_environment
    from runtime.tool_governance import evaluate_tool_governance
    from runtime.tool_health import check_all_tool_health

    if str(profile.get("environment", "demo")).strip().lower() != "demo":
        missing.append("default_environment_not_demo")
    if not bool(profile.get("governance_enforced", False)):
        missing.append("governance_enforcement_disabled")

    core_result = evaluate_tool_governance(
        "core/read",
        {
            "source": "builtin",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "",
            "toolpack_classification": "core",
        },
        environment="demo",
        dry_run=True,
        live_requested=False,
        operation="execute",
    )
    if not core_result.get("ok", False):
        missing.append("core_tool_blocked_in_demo")

    google_release_result = evaluate_tool_governance(
        "gmail/search",
        {
            "source": "external_toolpack",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "google_workspace",
            "toolpack_classification": "optional",
        },
        environment="release",
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    if google_release_result.get("ok", False):
        missing.append("google_workspace_live_allowed_in_release")

    high_risk_result = evaluate_tool_governance(
        "messages/extract_absa_transactions",
        {
            "source": "external_toolpack",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "messages",
            "toolpack_classification": "high_risk",
        },
        environment="demo",
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    if high_risk_result.get("ok", False):
        missing.append("high_risk_demo_allowed")
    high_risk_release_result = evaluate_tool_governance(
        "messages/extract_absa_transactions",
        {
            "source": "external_toolpack",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "allow_live_side_effect": False,
            "toolpack_id": "messages",
            "toolpack_classification": "high_risk",
        },
        environment="release",
        dry_run=False,
        live_requested=True,
        operation="execute",
    )
    if high_risk_release_result.get("ok", False):
        missing.append("high_risk_release_allowed")

    pending_allow = evaluate_tool_governance(
        "sheet/prepare_write_rows",
        {
            "source": "builtin",
            "side_effect": True,
            "requires_approval": True,
            "allow_live": False,
            "allow_live_side_effect": False,
            "toolpack_id": "",
            "toolpack_classification": "core",
        },
        environment="dev",
        dry_run=True,
        live_requested=False,
        operation="execute_pending_action",
    )
    pending_block = evaluate_tool_governance(
        "sheet/prepare_write_rows",
        {
            "source": "builtin",
            "side_effect": True,
            "requires_approval": True,
            "allow_live": False,
            "allow_live_side_effect": False,
            "toolpack_id": "",
            "toolpack_classification": "core",
        },
        environment="dev",
        dry_run=False,
        live_requested=True,
        operation="execute_pending_action",
    )
    if not pending_allow.get("ok", False):
        missing.append("dry_run_pending_action_blocked")
    if pending_block.get("ok", False):
        missing.append("live_pending_action_allowed")

    health_results = check_all_tool_health(include_optional=True, live_rpa=False)
    rpa_health = next((item for item in health_results if item.tool_id == "rpa_google_messages"), None)
    if not rpa_health or rpa_health.status != "disabled_optional":
        missing.append("optional_rpa_live_probe_not_excluded")

    try:
        resolved_env = resolve_runtime_environment()
    except Exception as exc:
        missing.append(f"runtime_environment_resolution_failed:{exc}")
        resolved_env = "demo"
    if resolved_env != "demo":
        missing.append(f"resolved_environment_not_demo:{resolved_env}")

    return {
        "name": "runtime_tool_governance",
        "status": "PASS" if not missing else "FAIL",
        "profile": profile,
        "core_result": core_result,
        "google_release_result": google_release_result,
        "high_risk_result": high_risk_result,
        "high_risk_release_result": high_risk_release_result,
        "pending_allow": pending_allow,
        "pending_block": pending_block,
        "rpa_health": rpa_health.to_dict() if rpa_health else None,
        "resolved_environment": resolved_env,
        "missing": missing,
    }


def _check_toolpack_lifecycle() -> dict[str, Any]:
    missing: list[str] = []

    lifecycle_module = ROOT / "src" / "toolpack_lifecycle.py"
    if not lifecycle_module.is_file():
        missing.append("src/toolpack_lifecycle.py")

    lifecycle_doc = ROOT / "docs" / "toolpack_lifecycle.md"
    if not lifecycle_doc.is_file():
        missing.append("docs/toolpack_lifecycle.md")
    else:
        doc_text = lifecycle_doc.read_text(encoding="utf-8").lower()
        for required in (
            "lifecycle stages",
            "lifecycle statuses",
            "governance",
            "contract test",
            "health check",
            "enablement",
            "evidence",
        ):
            if required not in doc_text:
                missing.append(f"lifecycle_doc_missing:{required}")

    cli_ref = ROOT / "docs" / "cli_reference.md"
    if not cli_ref.is_file():
        missing.append("docs/cli_reference.md")
    else:
        cli_text = cli_ref.read_text(encoding="utf-8").lower()
        if "taskframe tools lifecycle" not in cli_text:
            missing.append("cli_reference_missing:taskframe tools lifecycle")

    try:
        from src.toolpack_lifecycle import evaluate_toolpack_lifecycle, write_lifecycle_report
        from src.toolpack_governance import get_all_policies

        demo_result = evaluate_toolpack_lifecycle(
            ROOT / "tool_packs" / "demo_echo" / "toolpack.json",
            environment="dev",
            config_path=ROOT / "config" / "enabled_toolpacks.json",
            runtime_data_dir=ROOT / "runtime_data",
        )
        demo_ok = bool(demo_result.get("ok", False)) and demo_result.get("status") in {"READY", "READY_WITH_WARNINGS"}

        core_ids = ["core_business", "core_memory", "core_llm_micro", "core_reports"]
        core_demo_results = [
            evaluate_toolpack_lifecycle(
                ROOT / "tool_packs" / pack_id / "toolpack.json",
                environment="demo",
                config_path=ROOT / "config" / "enabled_toolpacks.json",
                runtime_data_dir=ROOT / "runtime_data",
            )
            for pack_id in core_ids
        ]
        core_release_results = [
            evaluate_toolpack_lifecycle(
                ROOT / "tool_packs" / pack_id / "toolpack.json",
                environment="release",
                config_path=ROOT / "config" / "enabled_toolpacks.json",
                runtime_data_dir=ROOT / "runtime_data",
            )
            for pack_id in core_ids
        ]
        core_ok = all(bool(item.get("ok", False)) and item.get("status") in {"READY", "READY_WITH_WARNINGS"} for item in core_demo_results + core_release_results)

        policies = get_all_policies()
        high_risk_ids = sorted(
            {
                str(entry.get("toolpack_id", "")).strip()
                for entry in policies
                if str(entry.get("classification", "")).strip() == "high_risk"
            }
        )
        high_risk_failures: list[str] = []
        for pack_id in high_risk_ids:
            pack_path = ROOT / "tool_packs" / pack_id / "toolpack.json"
            if not pack_path.is_file():
                continue
            for env in ("demo", "release"):
                lifecycle = evaluate_toolpack_lifecycle(
                    pack_path,
                    environment=env,
                    config_path=ROOT / "config" / "enabled_toolpacks.json",
                    runtime_data_dir=ROOT / "runtime_data",
                )
                if lifecycle.get("status") in {"READY", "READY_WITH_WARNINGS"}:
                    high_risk_failures.append(f"{pack_id}:{env}")

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            runtime_data_dir = Path(tmp) / "runtime_data"
            runtime_data_dir.mkdir(parents=True, exist_ok=True)
            write_result = write_lifecycle_report(demo_result, runtime_data_dir=runtime_data_dir)
            report_written = Path(write_result.get("json_path", "")).is_file() and Path(write_result.get("markdown_path", "")).is_file()

        cli_result = run_command(
            "toolpack_lifecycle_cli",
            [
                "python",
                "-m",
                "src.taskframe_cli",
                "tools",
                "lifecycle",
                "tool_packs/demo_echo/toolpack.json",
                "--env",
                "dev",
                "--json",
            ],
            timeout_seconds=180,
        )
        cli_ok = cli_result["status"] == "PASS"
        cli_payload_ok = False
        if cli_ok:
            try:
                payload = json.loads(cli_result["stdout"])
                cli_payload_ok = payload.get("ok", False) and payload.get("status") in {"READY", "READY_WITH_WARNINGS"}
            except Exception:
                cli_payload_ok = False

        ok = demo_ok and core_ok and not high_risk_failures and report_written and cli_ok and cli_payload_ok and not missing
        return {
            "name": "toolpack_lifecycle",
            "status": "PASS" if ok else "FAIL",
            "demo_result": demo_result,
            "core_demo_results": core_demo_results,
            "core_release_results": core_release_results,
            "high_risk_ids": high_risk_ids,
            "high_risk_failures": high_risk_failures,
            "cli": cli_result,
            "report_written": report_written,
            "missing": missing,
        }
    except Exception as exc:
        return {"name": "toolpack_lifecycle", "status": "FAIL", "error": str(exc), "missing": missing}


def _check_event_source_contracts_file() -> dict[str, Any]:
    path = ROOT / "config" / "event_source_contracts.json"
    if not path.is_file():
        return {"name": "event_source_contracts_file", "status": "FAIL", "error": "config/event_source_contracts.json not found."}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        contracts = data.get("contracts", []) if isinstance(data, dict) else []
        return {"name": "event_source_contracts_file", "status": "PASS" if len(contracts) >= 8 else "FAIL", "count": len(contracts)}
    except Exception as exc:
        return {"name": "event_source_contracts_file", "status": "FAIL", "error": str(exc)}


def _check_event_source_contracts_valid() -> dict[str, Any]:
    try:
        from runtime.event_source_registry import validate_all_event_source_contracts

        result = validate_all_event_source_contracts()
        return {"name": "event_source_contracts_valid", "status": "PASS" if result.get("ok") else "FAIL", "count": result.get("count", 0), "missing": result.get("missing_builtin_sources", [])}
    except Exception as exc:
        return {"name": "event_source_contracts_valid", "status": "FAIL", "error": str(exc)}


def _check_event_source_builders_importable() -> dict[str, Any]:
    try:
        from runtime.event_source_builders import (
            build_operator_event, build_schedule_event, build_customer_inbox_event,
            build_gmail_event, build_calendar_event, build_sheet_event,
            build_rpa_event, build_system_event,
        )
        return {"name": "event_source_builders_importable", "status": "PASS"}
    except Exception as exc:
        return {"name": "event_source_builders_importable", "status": "FAIL", "error": str(exc)}


def _check_event_source_cli_available() -> dict[str, Any]:
    try:
        from src.taskframe_cli import build_parser

        parser = build_parser()
        argv = ["event-sources", "list", "--json"]
        args = parser.parse_args(argv)
        return {"name": "event_source_cli_available", "status": "PASS" if args.command == "event-sources" else "FAIL"}
    except Exception as exc:
        return {"name": "event_source_cli_available", "status": "FAIL", "error": str(exc)}


def _check_event_source_route_alignment() -> dict[str, Any]:
    try:
        from runtime.event_source_route_alignment import validate_event_source_route_alignment

        result = validate_event_source_route_alignment()
        return {"name": "event_source_route_alignment", "status": "PASS" if result.get("ok") else "FAIL", "route_count": result.get("route_count", 0), "mismatches": len(result.get("mismatches", []))}
    except Exception as exc:
        return {"name": "event_source_route_alignment", "status": "FAIL", "error": str(exc)}


def _check_order_management_manifests_exist() -> dict[str, Any]:
    required = [
        "manifests/order.validate_new.manifest.json",
        "manifests/order.reserve_stock.manifest.json",
        "manifests/order.release_paid.manifest.json",
        "manifests/order.detect_delayed.manifest.json",
        "manifests/order.update_shipment_status.manifest.json",
    ]
    missing = [p for p in required if not (ROOT / p).is_file()]
    return {"name": "order_management_manifests_exist", "status": "PASS" if not missing else "FAIL", "missing": missing, "count": len(required) - len(missing)}


def _check_order_management_routes_exist() -> dict[str, Any]:
    path = ROOT / "config" / "event_routes.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        routes = data.get("routes", data) if isinstance(data, dict) else data
        order_routes = [r for r in routes if isinstance(r, dict) and str(r.get("route_id", "")).startswith("operator.order_")]
        return {"name": "order_management_routes_exist", "status": "PASS" if len(order_routes) >= 5 else "FAIL", "count": len(order_routes)}
    except Exception as exc:
        return {"name": "order_management_routes_exist", "status": "FAIL", "error": str(exc)}


def _check_order_management_scenarios_exist() -> dict[str, Any]:
    try:
        from src.operator_scenarios import SCENARIO_CATEGORIES, list_scenarios

        has_category = "order_management" in SCENARIO_CATEGORIES
        order_scenarios = list_scenarios(category="order_management")
        return {"name": "order_management_scenarios_exist", "status": "PASS" if has_category and len(order_scenarios) >= 5 else "FAIL", "has_category": has_category, "count": len(order_scenarios)}
    except Exception as exc:
        return {"name": "order_management_scenarios_exist", "status": "FAIL", "error": str(exc)}


def _check_order_management_tool_registry() -> dict[str, Any]:
    try:
        from runtime.tool_registry import TOOL_REGISTRY

        order_tools = [k for k in TOOL_REGISTRY if k.startswith("order/")]
        return {"name": "order_management_tool_registry", "status": "PASS" if len(order_tools) >= 9 else "FAIL", "count": len(order_tools), "tools": order_tools}
    except Exception as exc:
        return {"name": "order_management_tool_registry", "status": "FAIL", "error": str(exc)}


def _check_order_management_smoke_runs() -> dict[str, Any]:
    try:
        from runtime.order_management_tools import (
            order_validate_new, order_check_payment_status, order_detect_delayed_orders,
        )

        val = order_validate_new(customer_id="CUST-1001", items=[{"sku": "SKU-DESK-01", "quantity": 1}])
        pay = order_check_payment_status(order_ref="ORD-10042")
        delayed = order_detect_delayed_orders(days_overdue=1)
        ok = (
            isinstance(val, dict) and "ok" in val
            and isinstance(pay, dict) and "ok" in pay
            and isinstance(delayed, dict) and "delayed_orders" in delayed
        )
        return {"name": "order_management_smoke_runs", "status": "PASS" if ok else "FAIL"}
    except Exception as exc:
        return {"name": "order_management_smoke_runs", "status": "FAIL", "error": str(exc)}


def _check_order_management_approval_dry_run() -> dict[str, Any]:
    try:
        from runtime.order_management_tools import order_execute_stock_reservation

        result = order_execute_stock_reservation(order_ref="ORD-10050", reservation_lines=[], dry_run=True)
        is_dry = result.get("dry_run") is True
        return {"name": "order_management_approval_dry_run", "status": "PASS" if is_dry else "FAIL", "dry_run": result.get("dry_run")}
    except Exception as exc:
        return {"name": "order_management_approval_dry_run", "status": "FAIL", "error": str(exc)}


def _check_order_management_docs_exist() -> dict[str, Any]:
    path = ROOT / "docs" / "order_management_workflows.md"
    return {"name": "order_management_docs_exist", "status": "PASS" if path.is_file() else "FAIL", "path": str(path)}


def _check_supplier_invoice_manifest_exists() -> dict[str, Any]:
    path = ROOT / "manifests" / "supplier_invoice_match.manifest.json"
    return {"name": "supplier_invoice_manifest_exists", "status": "PASS" if path.is_file() else "FAIL", "path": str(path)}


def _check_supplier_invoice_routes_exist() -> dict[str, Any]:
    routes_path = ROOT / "config" / "event_routes.json"
    try:
        routes = json.loads(routes_path.read_text(encoding="utf-8")) if routes_path.is_file() else {}
    except Exception:
        routes = {}
    route_items = routes.get("routes", []) if isinstance(routes, dict) else []
    found = any(
        isinstance(route, dict)
        and route.get("route_id") == "operator.supplier_invoice_match"
        and route.get("manifest_id") == "supplier_invoice.match_to_po_receipt"
        for route in route_items
    )
    return {"name": "supplier_invoice_routes_exist", "status": "PASS" if found else "FAIL", "path": str(routes_path)}


def _check_supplier_invoice_tools_registered() -> dict[str, Any]:
    try:
        from runtime.tool_registry import TOOL_REGISTRY

        required = [
            "supplier_invoice/read",
            "po/read",
            "receipt/read_by_po",
            "supplier_invoice/check_duplicate",
            "supplier_invoice/match_three_way",
            "supplier_invoice/prepare_match_run_write",
            "supplier_invoice/prepare_ledger_write",
            "supplier_invoice/execute_ledger_write",
            "supplier_invoice/build_exception_report",
        ]
        missing = [tool for tool in required if tool not in TOOL_REGISTRY]
        return {
            "name": "supplier_invoice_tools_registered",
            "status": "PASS" if not missing else "FAIL",
            "count": len(required) - len(missing),
            "missing": missing,
        }
    except Exception as exc:
        return {"name": "supplier_invoice_tools_registered", "status": "FAIL", "error": str(exc)}


def _check_supplier_invoice_scenarios_exist() -> dict[str, Any]:
    try:
        from src.operator_scenarios import list_scenarios

        required = {
            "supplier_invoice_match_happy_path",
            "supplier_invoice_match_price_exception",
            "supplier_invoice_match_quantity_exception",
            "supplier_invoice_match_missing_receipt",
            "supplier_invoice_match_missing_po",
            "supplier_invoice_match_duplicate_invoice",
            "supplier_invoice_match_approve_execute_dry_run",
            "supplier_invoice_match_report_generation",
        }
        scenarios = list_scenarios(category="accounting", include_test_only=False)
        ids = {str(item.get("id", "")) for item in scenarios}
        missing = sorted(required - ids)
        return {
            "name": "supplier_invoice_scenarios_exist",
            "status": "PASS" if not missing else "FAIL",
            "count": len(required) - len(missing),
            "missing": missing,
        }
    except Exception as exc:
        return {"name": "supplier_invoice_scenarios_exist", "status": "FAIL", "error": str(exc)}


def _run_supplier_invoice_scenario(scenario_id: str, *, generate_report: bool = False) -> dict[str, Any]:
    from src.operator_scenario_runner import run_scenario

    return run_scenario(
        scenario_id,
        runtime_data_dir=str(ROOT / "runtime_data"),
        reset_dataset=False,
        generate_report=generate_report,
        allow_test_fake_llm=True,
    )


def _output_data(outputs: dict[str, Any], key: str) -> dict[str, Any]:
    value = outputs.get(key, {})
    if isinstance(value, dict):
        data = value.get("data", {})
        return data if isinstance(data, dict) else {}
    return {}


def _check_supplier_invoice_happy_path_smoke() -> dict[str, Any]:
    try:
        result = _run_supplier_invoice_scenario("supplier_invoice_match_happy_path")
        outputs = result.get("snapshot", {}).get("outputs", {}) if isinstance(result, dict) else {}
        ok = (
            result.get("ok") is True
            and result.get("state") == "WAITING_FOR_EXECUTE"
            and _output_data(outputs, "match_result").get("match_status") == "matched"
        )
        return {"name": "supplier_invoice_happy_path_smoke", "status": "PASS" if ok else "FAIL"}
    except Exception as exc:
        return {"name": "supplier_invoice_happy_path_smoke", "status": "FAIL", "error": str(exc)}


def _check_supplier_invoice_exception_path_smoke() -> dict[str, Any]:
    try:
        result = _run_supplier_invoice_scenario("supplier_invoice_match_price_exception")
        outputs = result.get("snapshot", {}).get("outputs", {})
        match_result = _output_data(outputs, "match_result")
        ok = (
            result.get("ok") is True
            and result.get("state") == "WAITING_FOR_EXECUTE"
            and match_result.get("match_status") == "exception"
            and _output_data(outputs, "exception_report").get("match_status") == "exception"
        )
        return {"name": "supplier_invoice_exception_path_smoke", "status": "PASS" if ok else "FAIL"}
    except Exception as exc:
        return {"name": "supplier_invoice_exception_path_smoke", "status": "FAIL", "error": str(exc)}


def _check_supplier_invoice_dry_run_approval() -> dict[str, Any]:
    try:
        result = _run_supplier_invoice_scenario("supplier_invoice_match_approve_execute_dry_run")
        snapshot = result.get("snapshot", {})
        ok = (
            result.get("ok") is True
            and result.get("state") == "COMPLETED"
            and len(snapshot.get("executed_actions", [])) == 2
            and any(item.get("tool") == "supplier_invoice/execute_ledger_write" for item in snapshot.get("executed_actions", []))
        )
        return {"name": "supplier_invoice_dry_run_approval", "status": "PASS" if ok else "FAIL"}
    except Exception as exc:
        return {"name": "supplier_invoice_dry_run_approval", "status": "FAIL", "error": str(exc)}


def _check_supplier_invoice_report_generation() -> dict[str, Any]:
    try:
        result = _run_supplier_invoice_scenario("supplier_invoice_match_report_generation", generate_report=True)
        report = result.get("report_result", {}) if isinstance(result, dict) else {}
        ok = (
            result.get("ok") is True
            and report.get("ok") is True
            and Path(str(report.get("markdown_path", ""))).is_file()
            and Path(str(report.get("html_path", ""))).is_file()
            and Path(str(report.get("evidence_bundle_path", ""))).is_file()
        )
        return {"name": "supplier_invoice_report_generation", "status": "PASS" if ok else "FAIL", "report": report}
    except Exception as exc:
        return {"name": "supplier_invoice_report_generation", "status": "FAIL", "error": str(exc)}


def _check_supplier_invoice_docs_exist() -> dict[str, Any]:
    required = [
        ROOT / "docs" / "supplier_invoice_matching_workflow.md",
        ROOT / "docs" / "manifest_building_manual.md",
        ROOT / "docs" / "release_candidate_verification.md",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    return {"name": "supplier_invoice_docs_exist", "status": "PASS" if not missing else "FAIL", "missing": missing}


def _check_cross_workflow_story_v2() -> dict[str, Any]:
    try:
        from src.demo_story_pack import build_cross_workflow_story_pack
        from src.operator_cross_workflow_demo import get_demo_pack, run_cross_workflow_demo_pack
    except Exception as exc:
        return {"name": "cross_workflow_story_v2", "status": "FAIL", "error": str(exc)}

    from uuid import uuid4

    try:
        pack = get_demo_pack("cross_workflow_business_demo_v2")
        if pack.get("id") != "cross_workflow_business_demo_v2":
            return {"name": "cross_workflow_story_v2", "status": "FAIL", "error": "v2 pack not registered"}
        verification_root = ROOT / "runtime_data" / "release_verification" / "cross_workflow_story_v2"
        verification_root.mkdir(parents=True, exist_ok=True)
        tmp = verification_root / f"run_{uuid4().hex[:10]}"
        tmp.mkdir(parents=True, exist_ok=True)
        result = run_cross_workflow_demo_pack(
            pack_id="cross_workflow_business_demo_v2",
            runtime_data_dir=str(tmp),
            reset_dataset=True,
            generate_reports=True,
            use_real_llm=False,
            allow_test_fake_llm=True,
            skip_llm_preflight=True,
        )
        story = result.get("story_pack_result", {}) if isinstance(result, dict) else {}
        story_dir = Path(str(story.get("story_pack_dir", "")))
        index_md = Path(str(story.get("index_markdown_path", "")))
        index_html = Path(str(story.get("index_html_path", "")))
        evidence_manifest_path = Path(str(story.get("evidence_manifest_path", "")))
        summary_json_path = Path(str(story.get("summary_json_path", "")))
        if not result.get("ok"):
            return {
                "name": "cross_workflow_story_v2",
                "status": "FAIL",
                "pack_id": result.get("pack_id", ""),
                "pack_run_id": result.get("pack_run_id", ""),
                "error": result.get("error", ""),
            }
        if not story.get("ok"):
            return {
                "name": "cross_workflow_story_v2",
                "status": "FAIL",
                "pack_id": result.get("pack_id", ""),
                "pack_run_id": result.get("pack_run_id", ""),
                "error": "Story pack builder failed.",
            }
        if not (story_dir.is_dir() and index_md.is_file() and index_html.is_file() and evidence_manifest_path.is_file() and summary_json_path.is_file()):
            return {
                "name": "cross_workflow_story_v2",
                "status": "FAIL",
                "pack_id": result.get("pack_id", ""),
                "pack_run_id": result.get("pack_run_id", ""),
                "error": "Missing story pack artifacts.",
            }
        manifest_data = json.loads(evidence_manifest_path.read_text(encoding="utf-8"))
        artifacts = manifest_data.get("artifacts", []) if isinstance(manifest_data, dict) else []
        evidence_ok = isinstance(artifacts, list) and all(
            isinstance(item, dict) and Path(str(item.get("path", ""))).is_file() and item.get("exists") is True
            for item in artifacts
        )
        if not evidence_ok:
            return {
                "name": "cross_workflow_story_v2",
                "status": "FAIL",
                "pack_id": result.get("pack_id", ""),
                "pack_run_id": result.get("pack_run_id", ""),
                "error": "Invalid evidence manifest.",
            }
        return {
            "name": "cross_workflow_story_v2",
            "status": "PASS",
            "pack_id": result.get("pack_id", ""),
            "pack_run_id": result.get("pack_run_id", ""),
            "story_pack_dir": str(story_dir),
            "story_markdown_path": str(index_md),
            "story_html_path": str(index_html),
            "evidence_manifest_path": str(evidence_manifest_path),
            "summary_json_path": str(summary_json_path),
        }
    except Exception as exc:
        return {"name": "cross_workflow_story_v2", "status": "FAIL", "error": str(exc)}


def _check_readiness_scorecard_gate() -> dict[str, Any]:
    try:
        from src.readiness_scorecard import build_readiness_scorecard
    except Exception as exc:
        return {"name": "readiness_scorecard_gate", "status": "FAIL", "error": str(exc)}

    try:
        result = build_readiness_scorecard(runtime_data_dir=ROOT / "runtime_data", strict=True, threshold=90)
        report_paths = result.get("report_paths", {}) if isinstance(result, dict) else {}
        json_path = Path(str(report_paths.get("json_path", "")))
        markdown_path = Path(str(report_paths.get("markdown_path", "")))
        html_path = Path(str(report_paths.get("html_path", "")))
        areas = result.get("areas", {}) if isinstance(result, dict) else {}
        area_scores_ok = isinstance(areas, dict) and len(areas) == 7 and all(
            isinstance(area, dict) and float(area.get("score", 0.0)) >= 90 for area in areas.values()
        )
        ok = (
            bool(result.get("ok"))
            and result.get("status") == "PASS"
            and area_scores_ok
            and not result.get("blocking_areas")
            and json_path.is_file()
            and markdown_path.is_file()
            and html_path.is_file()
        )
        return {
            "name": "readiness_scorecard_gate",
            "status": "PASS" if ok else "FAIL",
            "overall_score": result.get("overall_score", 0),
            "blocking_areas": result.get("blocking_areas", []),
            "json_path": str(json_path) if json_path.is_file() else "",
            "markdown_path": str(markdown_path) if markdown_path.is_file() else "",
            "html_path": str(html_path) if html_path.is_file() else "",
        }
    except Exception as exc:
        return {"name": "readiness_scorecard_gate", "status": "FAIL", "error": str(exc)}


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
