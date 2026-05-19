# Release Evidence Pack

## What Was Verified

- The clean-clone release-candidate path
- The default tool registry and tool capability registry
- The tool onboarding guide and tool contract checklist
- The default scenario pack
- The golden demo workflows
- The contract and boundary documentation
- The optional RPA exclusion boundary

## Where Verifier Outputs Are Stored

- Release verifier JSON: `runtime_data\audit\release_candidate_verification.json`
- Current release status JSON: `runtime_data\audit\release_status_latest.json`
- Release evidence pack JSON: `runtime_data\audit\release_evidence_pack.json`
- Release verifier markdown: `docs\release_candidate_verification.md`
- Current release status markdown: `docs\current_release_status.md`
- Release evidence pack markdown: `docs\release_evidence_pack.md`

## Where Golden Demo Outputs Are Stored

- Golden demo report: `runtime_data\outputs\reports\golden_demo_report.md`
- Golden demo HTML: `runtime_data\outputs\reports\golden_demo_report.html`
- Golden demo audit JSON: `runtime_data\outputs\audit\golden_demo_audit.json`

## Where Report Artifacts Are Stored

- Release artifacts document: `docs\release_artifacts.md`
- Runtime contract doc: `docs\runtime_contracts.md`
- Tool onboarding guide: `docs\adding_new_tools.md`
- Tool contract checklist: `docs\tool_contract_checklist.md`
- Default demo boundary doc: `docs\default_demo_boundary.md`
- Known limitations doc: `docs\known_limitations.md`

## How To Reproduce

```powershell
pytest
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

## Deliberately Excluded From Default RC

- Optional browser-backed RPA tools
- Live WhatsApp/Gmail sending
- Live browser automation
- Unbounded LLM tool choice
- Production credentials
- Real customer and supplier data

## Notes

- Golden demo verdict: READY
- Known limitations count: 2