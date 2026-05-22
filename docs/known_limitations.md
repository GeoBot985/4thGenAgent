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

## Event Source Limitations (Spec 139)
- No long-running polling daemon yet; polling is triggered explicitly via CLI.
- No push webhooks yet.
- Gmail live-read requires manual OAuth token setup (`~/.taskframe/gmail_token.json`).
- Calendar and Google Sheets polling are not yet implemented.
- Polling history redacts message bodies by default.
- Gmail live-read source is disabled by default and must be explicitly enabled.

## Worker Supervisor Limitations (Spec 140)
- No Windows service or Linux systemd integration; worker must be run manually via CLI.
- No parallel workers; single-threaded, single-process only.
- No distributed locking; one `runtime_data_dir` per local worker.
- No indefinite loop mode; bounded by `max_cycles` and `max_runtime_seconds`.
- Worker operational state (lock, heartbeat, cycle history) is always filesystem-based.
- SQLite tables for worker operational data are planned but not implemented in v1.
- Live side-effect execution is not available; always dry-run.

## Deferred Work
- Optional live integration profiles.
- Batch and queue orchestration.
- Scheduler UI polish.
- Expanded business scenario packs.
- Event source polling daemon → replaced by bounded worker loop (Spec 140).
- Gmail send/mutate operations (intentionally out of scope).
- Windows service / systemd integration for worker supervisor.
- Distributed locking for multi-host worker deployments.

## Verifier Notes
- real_ollama_integration_test_missing
- google_sheets_integration_test_missing