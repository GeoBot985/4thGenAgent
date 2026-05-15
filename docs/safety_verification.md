# Safety Verification

TaskFrame Runtime enforces a layered safety model. This document describes the safety claims, how they are verified, and where evidence is recorded.

---

## Safety claims

The safety verification pack checks nine claims that together establish the dry-run default and live-execution safety boundary.

| # | Claim | How verified |
|---|---|---|
| 1 | Default demo produces no live side effects | Demo scenario runs; run report inspected for side-effect actions |
| 2 | Side-effect tools stage pending actions | Tool registry inspected for `requires_approval` on all side-effect tools |
| 3 | Approval is required before execution | Pending action state machine and live-execution guardrail source inspected |
| 4 | Dry-run execution is auditable | Run report and audit artefact presence checked |
| 5 | Live execution is blocked by default | `TASKFRAME_ENABLE_LIVE_EXECUTION` not set in default environment |
| 6 | Manifest policy blocks live execution | Manifests scanned for `live_execution.enabled=true` (zero expected) |
| 7 | Tool policy blocks live side effects | Tool registry inspected for `allow_live_side_effect=False` on all side-effect tools |
| 8 | CLI live-execution guardrails are enforced | `execute-approved --live` path requires env var, flag, and typed confirmation phrase |
| 9 | Optional RPA tools are excluded from the default path | `rpa_google_messages.excluded_from_default_release=True` in tool capability registry |

---

## Running the safety verification pack

```bash
taskframe safety-pack
```

Options:

| Flag | Meaning |
|---|---|
| `--no-demo` | Use static analysis only; skip demo scenario runs |
| `--runtime-data-dir <dir>` | Override runtime data directory (default: `runtime_data`) |
| `--manifest-dir <dir>` | Override manifests directory (default: `manifests`) |
| `--json` | Print full JSON pack to stdout |

---

## Output files

After running `taskframe safety-pack`, the following artefacts are written:

| File | Purpose |
|---|---|
| `runtime_data/safety_verification/safety_verification_pack.json` | Machine-readable full pack |
| `runtime_data/safety_verification/safety_verification_pack.md` | Human-readable summary |
| `runtime_data/safety_verification/live_blocked_evidence.json` | Live-blocked evidence JSON |
| `runtime_data/safety_verification/live_blocked_evidence.md` | Live-blocked evidence Markdown |
| `runtime_data/safety_verification/dry_run_evidence.json` | Dry-run evidence JSON |
| `runtime_data/safety_verification/dry_run_evidence.md` | Dry-run evidence Markdown |
| `docs/safety_verification_pack.md` | Copy of the summary in docs/ |
| `docs/live_blocked_evidence_report.md` | Copy of the live-blocked evidence in docs/ |

---

## Live-blocked evidence report

The live-blocked evidence report (`docs/live_blocked_evidence_report.md`) records six checks:

| Check | What it verifies |
|---|---|
| `runtime_live_disabled` | `TASKFRAME_ENABLE_LIVE_EXECUTION` is not set |
| `manifest_live_disabled` | No manifest has `live_execution.enabled=true` |
| `tool_live_blocked` | All side-effect tools block live execution by policy |
| `pending_action_not_approved` | Unapproved pending actions cannot proceed to execution |
| `wrong_confirmation_blocked` | A wrong typed confirmation phrase blocks live execution |
| `optional_rpa_excluded` | RPA tools are excluded from the default tool path |

---

## Expected result

In the default repository state (no environment overrides, default manifests, default tool registry):

- All 9 claims PASS.
- Live-blocked evidence shows 6 checks PASS.
- The overall status is `PASS`.

If any claim fails, the pack lists it in the `blockers` field and exits non-zero.

---

## Relationship to release verification

`taskframe verify` calls the release verifier, which includes a `safety_verification_pack` check. The release verifier expects:

- `taskframe safety-pack --json` exits 0 with `"ok": true`.
- `docs/safety_verification_pack.md` exists.
- `docs/live_blocked_evidence_report.md` exists.

If the safety pack fails, the release verification verdict is `BLOCKED`.

---

## Architecture note

The safety boundary is enforced at multiple independent layers:

1. **Environment** — `TASKFRAME_ENABLE_LIVE_EXECUTION` must be `1`.
2. **Pending action state** — action must be `APPROVED` before execution proceeds.
3. **Manifest policy** — `live_execution.enabled` must be `true` in the manifest.
4. **Tool policy** — tool spec must have `allow_live=True` and `allow_live_side_effect=True`.
5. **CLI guardrail** — `--live --i-understand-live-side-effects --confirm "<phrase>"` must all match.

All five must be satisfied simultaneously. A failure at any layer blocks live execution without affecting dry-run safety.

See [docs/live_execution_safety.md](live_execution_safety.md) for the full live-execution boundary specification.
