# Current Release Status

## Verdict

- READY_WITH_KNOWN_LIMITATIONS

## Verification Date

- 2026-05-19T09:03:05.410825Z

## Commands Run

- pytest
- python scripts/run_golden_demo.py
- python scripts/run_release_verification.py

## Test Summary

- Pytest: 2310 passed, 6 skipped
- Commands Run: 42
- Passed Commands: 42
- Failed Commands: 0
- Skipped Checks: 2

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
- runtime_data\release_verification\cross_workflow_story_v2\run_070ccdff77\demo_packs\cross_workflow_business_demo_v2_9b5193adf624\story_pack\index.md
- runtime_data\release_verification\cross_workflow_story_v2\run_070ccdff77\demo_packs\cross_workflow_business_demo_v2_9b5193adf624\story_pack\index.html
- runtime_data\release_verification\cross_workflow_story_v2\run_070ccdff77\demo_packs\cross_workflow_business_demo_v2_9b5193adf624\story_pack
- runtime_data\release_verification\cross_workflow_story_v2\run_070ccdff77\demo_packs\cross_workflow_business_demo_v2_9b5193adf624\story_pack\evidence_manifest.json
- runtime_data\release_verification\cross_workflow_story_v2\run_070ccdff77\demo_packs\cross_workflow_business_demo_v2_9b5193adf624\story_pack\summary.json
- runtime_data\readiness\readiness_scorecard.json
- runtime_data\readiness\readiness_scorecard.md
- runtime_data\readiness\readiness_scorecard.html
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_3d676a2ca4\portfolio_evidence\portfolio_evidence_pack_v1_20260519T090817_a7892f56\index.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_3d676a2ca4\portfolio_evidence\portfolio_evidence_pack_v1_20260519T090817_a7892f56\index.html
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_3d676a2ca4\portfolio_evidence\portfolio_evidence_pack_v1_20260519T090817_a7892f56\summary.json
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_3d676a2ca4\portfolio_evidence\portfolio_evidence_pack_v1_20260519T090817_a7892f56\architecture.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_3d676a2ca4\portfolio_evidence\portfolio_evidence_pack_v1_20260519T090817_a7892f56\demo_script.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_3d676a2ca4\portfolio_evidence\portfolio_evidence_pack_v1_20260519T090817_a7892f56\tool_inventory.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_3d676a2ca4\portfolio_evidence\portfolio_evidence_pack_v1_20260519T090817_a7892f56\workflow_proof.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_3d676a2ca4\portfolio_evidence\portfolio_evidence_pack_v1_20260519T090817_a7892f56\screenshot_checklist.md
- runtime_data\release_verification\portfolio_evidence_pack_v1\run_3d676a2ca4\portfolio_evidence\portfolio_evidence_pack_v1_20260519T090817_a7892f56
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