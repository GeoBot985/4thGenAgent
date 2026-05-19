# Known Limitations

The RC demonstrates controlled autonomous business automation in a demo business environment.
It is not presented as production-ready for unsupervised live operations.

## Default RC Limitations
- The clean-clone release-candidate path uses deterministic fixtures and demo data.
- Live side effects stay approval-gated or dry-run only.

## Optional Tooling Limitations
- Optional browser-backed RPA remains outside the default RC path.
- Optional tooling may depend on local browser state or external authentication.

## Live Execution Limitations
- Live execution is disabled by default.
- Live execution requires explicit runtime and manifest policy approval.

## RPA Limitations
- Browser-backed RPA is local-operator-only and not required for clean-clone verification.

## LLM Limitations
- The LLM is bounded to extraction, classification, summarisation, drafting, comparison, and exception explanation.

## Not Production Claims
- This release candidate is not a promise of unsupervised production operation.

## Deferred Work
- Optional live integration profiles.
- Batch and queue orchestration.
- Scheduler UI polish.
- Expanded business scenario packs.

## Verifier Notes
- example