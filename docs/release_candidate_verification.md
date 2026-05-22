# Release Candidate Verification Report

## Verdict

- NOT_READY

## Executive Summary

- Generated At: 2026-05-21T09:27:55.339475Z
- Commands Run: 44
- Passed Commands: 39
- Failed Commands: 5
- Skipped Checks: 1

## Environment

- Python: 3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]
- Platform: Windows-10-10.0.26200-SP0
- CWD: .
- Git Commit: 9f86b219e381abe3aad1ed4c955f8bbe32b450dd
- Git Branch: main

## Architecture Claims Verified

| Claim | Evidence |
|---|---|
| TaskFrame-centered runtime | TaskFrame artifacts, reports, evidence bundle |
| Manifest-driven execution | manifests present; workflow tests pass |
| Generic orchestrator | static scan of runtime/orchestrator.py |
| Domain tools externalized | tool registry and workflow tests |
| Bounded LLM use | LLM command tests and fake-path scan |
| Approval-gated side effects | pending/executed action tests |
| Dry-run execution safety | customer/procurement/accounting dry-run tests |
| Multi-workflow generalization | customer, procurement, accounting, cross-workflow tests |
| Portfolio readiness | README, walkthrough, screenshots, demo script, release verification |

## Test Results

- clean_imports: PASS (0)
- clean_clone_rc_tests: PASS (0)
- full_pytest: FAIL (1)
- smoke_external_event_intake: PASS (0)
- smoke_inspection: PASS (0)
- smoke_inspection_commands: PASS (0)
- core_retry_policy: PASS (0)
- core_retry_tool_failures: PASS (0)
- core_execution_metrics: FAIL (1)
- core_run_ledger: PASS (0)
- customer_lane: FAIL (1)
- procurement_lane: PASS (0)
- accounting_lane: PASS (0)
- cross_workflow_demo: PASS (0)
- golden_demo: PASS (0)
- portfolio_boundary: PASS (0)
- portfolio_docs: PASS (0)
- toolpack_loader_tests: PASS (0)
- toolpack_registry_tests: PASS (0)
- toolpack_cli_tests: PASS (0)
- toolpack_health_tests: PASS (0)
- toolpack_manifest_execution_tests: FAIL (1)
- google_workspace_descriptor_tests: PASS (0)
- google_workspace_auth_tests: PASS (0)
- google_workspace_tool_tests: PASS (0)
- google_workspace_health_tests: PASS (0)
- google_workspace_cli_tests: PASS (0)
- google_workspace_manifest_examples_tests: FAIL (1)
- google_workspace_safety_tests: PASS (0)
- google_workspace_docs_tests: PASS (0)
- builtin_toolpack_migration_tests: PASS (0)
- tool_registry_compat_tests: PASS (0)
- tool_inventory_tests: PASS (0)
- builtin_toolpack_health_tests: PASS (0)
- builtin_toolpack_manifest_compatibility_tests: PASS (0)
- builtin_toolpack_cli_tests: PASS (0)
- builtin_toolpack_docs_tests: PASS (0)
- toolpack_scaffold_tests: PASS (0)
- toolpack_contract_runner_tests: PASS (0)
- toolpack_scaffold_cli_tests: PASS (0)
- toolpack_generated_pack_execution_tests: PASS (0)
- toolpack_governance_tests: PASS (0)
- live_side_effect_contract_tests: PASS (0)
- gmail_send_tests: PASS (0)

## Workflow Verification

- customer: FAIL
- procurement: PASS
- accounting: PASS
- cross_workflow: PASS

## Static Architecture Checks

- python_imports: PASS
- packaging_cli: PASS
- manifest_health_cli_strict: PASS
- toolpack_contract: PASS
- google_workspace_toolpack_descriptor: PASS
- google_workspace_read_only_safety: PASS
- google_workspace_health_safe: PASS
- google_workspace_docs: PASS
- google_workspace_optional_boundary: PASS
- google_workspace_readonly_pack: PASS
- toolpack_loader: PASS
- toolpack_registry_integration: PASS
- toolpack_cli: PASS
- external_toolpacks_default_safe: PASS
- builtin_toolpack_migration: PASS
- tool_registry_compatibility: PASS
- tool_inventory: PASS
- migrated_toolpack_health: PASS
- default_tool_registry: PASS
- tool_result_contract: PASS
- TOOL_CAPABILITY_REGISTRY: PASS
- CORE_TOOL_HEALTH_SAFE_CHECKS: PASS
- default_scenario_pack: PASS
- runtime_contract_docs: PASS
- runtime_tool_governance: PASS
- runtime_profiles: PASS
- runtime_store: FAIL
- production_persistence_backend: PASS
- durable_event_queue: PASS
- operational_monitoring: FAIL
- recovery: PASS
- default_demo_boundary_doc: PASS
- known_limitations_doc: PASS
- adding_new_tools_doc: PASS
- tool_contract_checklist_doc: PASS
- orchestrator_pollution: PASS
- fake_llm_paths: PASS
- side_effect_registry: PASS
- OPTIONAL_RPA_EXCLUDED_FROM_DEFAULT_RC: PASS
- OPTIONAL_RPA_LIVE_PROBES_EXCLUDED_FROM_RC: PASS
- release_artifacts_manifest: PASS
- docs_command_alignment: PASS
- generated_manifest_template_quality_gates: PASS
- manifest_catalog_health: PASS
- manifest_contract_strict: PASS
- manifest_regression_gallery: PASS
- public_quickstart_docs: PASS
- live_safety_docs: PASS
- live_cli_guardrails: PASS
- live_execution_default_dry_run: PASS
- optional_rpa_isolation: PASS
- config_secrets_hygiene: PASS
- safety_verification_pack: PASS
- toolpack_governance: PASS
- toolpack_lifecycle: PASS
- portfolio_evidence_pack_v1: PASS
- event_source_contracts_file: PASS
- event_source_contracts_valid: PASS
- event_source_builders_importable: PASS
- event_source_cli_available: PASS
- event_source_route_alignment: PASS
- order_management_manifests_exist: PASS
- order_management_routes_exist: PASS
- order_management_scenarios_exist: PASS
- order_management_tool_registry: PASS
- order_management_smoke_runs: PASS
- order_management_approval_dry_run: PASS
- order_management_docs_exist: PASS
- controlled_live_profile_v0: PASS
- supplier_invoice_manifest_exists: PASS
- supplier_invoice_routes_exist: PASS
- supplier_invoice_tools_registered: PASS
- supplier_invoice_scenarios_exist: PASS
- supplier_invoice_happy_path_smoke: PASS
- supplier_invoice_exception_path_smoke: PASS
- supplier_invoice_dry_run_approval: PASS
- supplier_invoice_report_generation: PASS
- supplier_invoice_docs_exist: PASS
- cross_workflow_story_v2: PASS
- readiness_scorecard_gate: PASS
- pilot_readiness_gate: PASS
- live_side_effect_contract: PASS
- gmail_send_tool: PASS

## Side-Effect Safety Checks

- side_effect_registry: PASS

## LLM Safety Checks

- fake_llm_paths: PASS

## Documentation / Portfolio Asset Checks

- README.md: OK
- docs/release_artifacts.md: OK
- docs/runtime_contracts.md: OK
- docs/adding_new_tools.md: OK
- docs/tool_contract_checklist.md: OK
- docs/toolpack_contract.md: OK
- docs/toolpack_authoring_guide.md: OK
- docs/toolpack_examples.md: OK
- docs/google_workspace_readonly_toolpack.md: OK
- docs/google_workspace_setup.md: OK
- docs/google_workspace_integration_tests.md: OK
- docs/manifest_regression_gallery.md: OK
- docs/builtin_toolpack_migration.md: OK
- docs/tool_inventory.md: OK
- docs/cli_reference.md: OK
- docs/quickstart.md: OK
- docs/index.md: OK
- docs/optional_rpa.md: OK
- docs/default_demo_boundary.md: OK
- docs/known_limitations.md: OK
- docs/current_release_status.md: OK
- docs/release_evidence_pack.md: OK
- scripts/run_release_verification.py: OK
- scripts/run_golden_demo.py: OK
- config/enabled_toolpacks.json: OK
- tool_packs/README.md: OK
- tool_packs/demo_echo/toolpack.json: OK
- tool_packs/demo_echo/README.md: OK
- tool_packs/google_workspace/toolpack.json: OK
- tool_packs/google_workspace/tools.py: OK
- tool_packs/google_workspace/health.py: OK
- tool_packs/google_workspace/auth.py: OK
- tool_packs/google_workspace/README.md: OK
- tool_packs/google_workspace/examples/smoke_gmail_list_unread.manifest.json: OK
- tool_packs/google_workspace/examples/smoke_calendar_search.manifest.json: OK
- tool_packs/google_workspace/examples/smoke_sheets_read_range.manifest.json: OK
- tool_packs/core_business/toolpack.json: OK
- tool_packs/core_memory/toolpack.json: OK
- tool_packs/core_llm_micro/toolpack.json: OK
- tool_packs/core_reports/toolpack.json: OK
- src/tool_registry_compat.py: OK
- src/tool_inventory.py: OK
- runtime/business_context.py: OK
- docs/architecture_overview.md: OK
- docs/demo_walkthrough.md: OK
- docs/demo_script.md: OK
- docs/capture_screenshots.md: OK
- docs/portfolio_summary.md: OK
- docs/release_candidate_verification.md: OK
- docs/release_verification.md: OK
- docs/runtime_store.md: OK
- docs/operational_monitoring.md: OK
- docs/operator_ui.md: OK
- runtime_data/outputs/reports/golden_demo_report.md: OK
- runtime_data/outputs/reports/golden_demo_report.html: OK
- runtime_data/outputs/audit/golden_demo_audit.json: OK
- runtime_data/audit/release_status_latest.json: OK
- runtime_data/audit/release_evidence_pack.json: OK
- runtime_data/tool_health/latest_tool_health.json: OK
- runtime_data/tool_health/reports/report_generator_probe.md: OK
- runtime_data/tool_health/reports/report_generator_probe.html: OK
- docs/screenshots/01_operator_home.png: OK
- docs/screenshots/02_scenario_pack.png: OK
- docs/screenshots/03_taskframe_detail.png: OK
- docs/screenshots/04_step_playback.png: OK
- docs/screenshots/05_pending_approval.png: OK
- docs/screenshots/06_tool_status_panel.png: OK
- docs/screenshots/07_tool_health_details.png: OK
- docs/screenshots/08_report_output.png: OK
- docs/screenshots/09_release_verification.png: OK
- docs/safety_verification.md: OK
- src/toolpack_scaffold.py: OK
- src/toolpack_contract_runner.py: OK
- docs/toolpack_scaffold_wizard.md: OK
- docs/toolpack_contract_testing.md: OK
- src/toolpack_governance.py: OK
- docs/toolpack_governance.md: OK
- config/toolpack_governance.json: OK
- docs/live_gmail_send.md: OK
- runtime/gmail_send_tool.py: OK
- README.md: OK
- docs/release_artifacts.md: OK
- docs/runtime_contracts.md: OK
- docs/adding_new_tools.md: OK
- docs/tool_contract_checklist.md: OK
- docs/cli_reference.md: OK
- docs/quickstart.md: OK
- docs/index.md: OK
- docs/optional_rpa.md: OK
- docs/default_demo_boundary.md: OK
- docs/known_limitations.md: OK
- docs/current_release_status.md: OK
- docs/release_evidence_pack.md: OK
- scripts/run_release_verification.py: OK
- scripts/run_golden_demo.py: OK
- runtime/business_context.py: OK
- docs/architecture_overview.md: OK
- docs/demo_walkthrough.md: OK
- docs/demo_script.md: OK
- docs/capture_screenshots.md: OK
- docs/portfolio_summary.md: OK
- docs/release_candidate_verification.md: OK
- runtime_data/outputs/reports/golden_demo_report.md: OK
- runtime_data/outputs/reports/golden_demo_report.html: OK
- runtime_data/outputs/audit/golden_demo_audit.json: OK
- runtime_data/audit/release_status_latest.json: OK
- runtime_data/audit/release_evidence_pack.json: OK
- runtime_data/tool_health/latest_tool_health.json: OK
- runtime_data/tool_health/reports/report_generator_probe.md: OK
- runtime_data/tool_health/reports/report_generator_probe.html: OK
- docs/screenshots/01_operator_home.png: OK
- docs/screenshots/02_scenario_pack.png: OK
- docs/screenshots/03_taskframe_detail.png: OK
- docs/screenshots/04_step_playback.png: OK
- docs/screenshots/05_pending_approval.png: OK
- docs/screenshots/06_tool_status_panel.png: OK
- docs/screenshots/07_tool_health_details.png: OK
- docs/screenshots/08_report_output.png: OK
- docs/screenshots/09_release_verification.png: OK
- docs/safety_verification.md: OK
- src/toolpack_scaffold.py: OK
- src/toolpack_contract_runner.py: OK
- docs/toolpack_scaffold_wizard.md: OK
- docs/toolpack_contract_testing.md: OK
- src/toolpack_governance.py: OK
- docs/toolpack_governance.md: OK
- config/toolpack_governance.json: OK
- docs/live_side_effect_execution_contract.md: OK
- runtime/live_side_effect_contract.py: OK
- runtime/live_execution_reports.py: OK

## Report and Evidence Artifact Checks

- runtime_data\manifest_health\manifest_health_report.json
- runtime_data\manifest_health\manifest_health_report.md
- runtime_data\release_verification\cross_workflow_story_v2\run_15e506114d\demo_packs\cross_workflow_business_demo_v2_7693e2f318f7\story_pack\index.md
- runtime_data\release_verification\cross_workflow_story_v2\run_15e506114d\demo_packs\cross_workflow_business_demo_v2_7693e2f318f7\story_pack\index.html
- runtime_data\release_verification\cross_workflow_story_v2\run_15e506114d\demo_packs\cross_workflow_business_demo_v2_7693e2f318f7\story_pack
- runtime_data\release_verification\cross_workflow_story_v2\run_15e506114d\demo_packs\cross_workflow_business_demo_v2_7693e2f318f7\story_pack\evidence_manifest.json
- runtime_data\release_verification\cross_workflow_story_v2\run_15e506114d\demo_packs\cross_workflow_business_demo_v2_7693e2f318f7\story_pack\summary.json
- runtime_data\readiness\readiness_scorecard.json
- runtime_data\readiness\readiness_scorecard.md
- runtime_data\readiness\readiness_scorecard.html
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_87adda713b\portfolio_evidence\portfolio_evidence_pack_v1_20260521T093444_f6e886a3\index.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_87adda713b\portfolio_evidence\portfolio_evidence_pack_v1_20260521T093444_f6e886a3\index.html
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_87adda713b\portfolio_evidence\portfolio_evidence_pack_v1_20260521T093444_f6e886a3\summary.json
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_87adda713b\portfolio_evidence\portfolio_evidence_pack_v1_20260521T093444_f6e886a3\architecture.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_87adda713b\portfolio_evidence\portfolio_evidence_pack_v1_20260521T093444_f6e886a3\demo_script.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_87adda713b\portfolio_evidence\portfolio_evidence_pack_v1_20260521T093444_f6e886a3\tool_inventory.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_87adda713b\portfolio_evidence\portfolio_evidence_pack_v1_20260521T093444_f6e886a3\workflow_proof.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_87adda713b\portfolio_evidence\portfolio_evidence_pack_v1_20260521T093444_f6e886a3\screenshot_checklist.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_87adda713b\portfolio_evidence\portfolio_evidence_pack_v1_20260521T093444_f6e886a3
- runtime_data\pilot_readiness\2026-05-21T09-34-46-367482Z
- runtime_data\outputs\reports\golden_demo_report.md
- runtime_data\outputs\reports\golden_demo_report.html
- runtime_data\outputs\audit\golden_demo_audit.json
- runtime_data\audit\release_candidate_verification.json
- docs\release_candidate_verification.md
- docs\release_candidate_evidence_index.md
- docs\current_release_status.md
- docs\release_evidence_pack.md
- docs\runtime_contracts.md
- docs\adding_new_tools.md
- docs\tool_contract_checklist.md
- docs\toolpack_contract.md
- docs\toolpack_authoring_guide.md
- docs\toolpack_examples.md
- docs\builtin_toolpack_migration.md
- docs\tool_inventory.md
- docs\default_demo_boundary.md
- docs\known_limitations.md
- runtime_data\audit\release_status_latest.json
- runtime_data\audit\release_evidence_pack.json
- config\enabled_toolpacks.json
- tool_packs\README.md
- tool_packs\demo_echo\toolpack.json
- tool_packs\demo_echo\README.md
- tool_packs\core_business\toolpack.json
- tool_packs\core_memory\toolpack.json
- tool_packs\core_llm_micro\toolpack.json
- tool_packs\core_reports\toolpack.json

## Known Limitations

- real_ollama_integration_test_missing
- google_sheets_integration_test_missing

## Release Blockers

- full_pytest failed
- core_execution_metrics failed
- customer_lane failed
- toolpack_manifest_execution_tests failed
- google_workspace_manifest_examples_tests failed
- runtime store validation failed
- operational monitoring validation failed

## Evidence Index

- Verification JSON: `runtime_data\audit\release_candidate_verification.json`
- Verification Report: `docs\release_candidate_verification.md`
- External Event Source Polling: `docs\external_event_source_polling.md`
- Evidence Index: `docs\release_candidate_evidence_index.md`
- Current Release Status: `docs\current_release_status.md`
- Release Evidence Pack: `docs\release_evidence_pack.md`
- Runtime Contracts: `docs\runtime_contracts.md`
- Default Demo Boundary: `docs\default_demo_boundary.md`
- Known Limitations: `docs\known_limitations.md`

## Final Recommendation

The project is NOT_READY.