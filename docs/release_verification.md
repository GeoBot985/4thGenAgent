# Release Verification

`taskframe verify` runs the repository release-verification script and writes JSON and Markdown evidence under `runtime_data/audit/` and `docs/`.

The verification gate checks the default safety posture, runtime profiles, runtime store discipline, operational monitoring, demo workflows, documentation coverage, and the release artifacts required for the controlled portfolio path.

Runtime store checks include:

- runtime store docs
- runtime-store CLI commands
- validation on a seeded demo runtime
- backup archive creation
- restore `--validate-only`
- corrupted artifact detection
- dry-run retention planning

Operational monitoring checks include:

- monitoring docs
- monitoring CLI commands
- failed, pending, stuck, and blocked run classification
- tool-health aggregation
- JSON, Markdown, and HTML report generation

Recovery and idempotency checks include:

- recovery docs
- recovery CLI commands
- retryable versus manual-review classification
- duplicate side-effect blocking
- recovery report generation
- dry-run-only recovery commands

Pilot readiness checks include:

- pilot readiness scorecard (80% threshold)
- mandatory safety checks (profile, side-effect blocking, store, monitoring, recovery, docs)
- pilot evidence pack generation (all required files)
- live-read preflight results
- side-effect blocking evidence
- known limitations register

Verification is not a claim of production readiness. It is a controlled release-readiness gate for the current demo and pilot posture.

See [pilot_readiness.md](pilot_readiness.md) for the difference between demo readiness, pilot readiness, and production readiness.
