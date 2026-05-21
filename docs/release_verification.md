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


## Spec 132 — Live side-effect contract checks

Release verification (Spec 132) confirms:

- `runtime/live_side_effect_contract.py` exists and defines all 10 error codes
- `runtime/live_execution_reports.py` exists with report and audit event writers
- `docs/live_side_effect_execution_contract.md` exists
- Live side effects are disabled by default (policy `enabled: false`)
- `demo`, `release`, and `pilot` profiles block live side effects
- Only the `live` profile can potentially allow live side effects
- Live execution requires `dry_run=False` explicitly
- Live execution requires manifest allowlist
- Live execution requires tool registry allowlist (`allow_live_side_effect`)
- Live execution requires an approved pending action with valid approval record
- Live execution requires a non-empty idempotency key
- Duplicate idempotency key is blocked with `DUPLICATE_SIDE_EFFECT_BLOCKED`
- Guardrail is required (tool with `live_guardrail: blocked` is blocked)
- Typed confirmation `LIVE-EXECUTE` is required
- Live execution attempts produce JSON and Markdown reports
- No default demo workflow performs live side effects

## Spec 133 — Gmail send tool checks

Release verification (Spec 133) confirms:

- `runtime/gmail_send_tool.py` exists with all required symbols
- `docs/live_gmail_send.md` exists
- `gmail/send` is registered in the tool registry with `side_effect=true`, `requires_approval=true`, `allow_live_side_effect=true`, `live_guardrail="gmail_send"`
- Gmail send config defaults: `enabled=false`, `allow_attachments=false`, `max_recipients=5`
- `gmail_send` guardrail is importable from `runtime.live_guardrails`
- `demo`, `dev`, `test`, `release`, and `pilot` profiles block live Gmail sends
- Audit event constants `LIVE_EMAIL_SENT` and `LIVE_EMAIL_SEND_BLOCKED` are defined
- Email body is never included in reports
- Gmail send report files use the `email_send_` prefix
