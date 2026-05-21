# Current Release Status

## Verdict

- NOT_READY

## Verification Date

- 2026-05-21T09:27:55.339475Z

## Commands Run

- pytest
- python scripts/run_golden_demo.py
- python scripts/run_release_verification.py

## Test Summary

- Pytest: see release verifier output
- Commands Run: 44
- Passed Commands: 39
- Failed Commands: 5
- Skipped Checks: 1

## Golden Demo Summary

- Customer: PASS
- Procurement: PASS
- Accounting: PASS
- Approval gate: PASS
- Report artifacts: PASS

## Release Verifier Checks

- imports: PASS
- default_tool_registry: PASS
- optional_rpa_excluded: PASS
- default_scenario_pack: PASS
- golden_demo: PASS
- release_artifacts: PASS
- docs_commands: PASS
- adding_new_tools_doc: PASS
- tool_contract_checklist_doc: PASS

## Known Limitations

- real_ollama_integration_test_missing
- google_sheets_integration_test_missing

## Evidence Files

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