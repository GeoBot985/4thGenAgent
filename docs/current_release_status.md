# Current Release Status

## Verdict

- READY_WITH_KNOWN_LIMITATIONS

## Verification Date

- 2026-05-15T19:28:56.799690Z

## Commands Run

- pytest
- python scripts/run_golden_demo.py
- python scripts/run_release_verification.py

## Test Summary

- Pytest: 1723 passed, 1 skipped
- Commands Run: 17
- Passed Commands: 17
- Failed Commands: 0
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
- docs\default_demo_boundary.md
- docs\known_limitations.md
- runtime_data\audit\release_status_latest.json
- runtime_data\audit\release_evidence_pack.json