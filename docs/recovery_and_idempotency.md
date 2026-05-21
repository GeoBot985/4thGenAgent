# Recovery And Idempotency

TaskFrame recovery is controlled and dry-run by default.

It is designed for:

- failed TaskFrames
- interrupted or stale TaskFrames
- retryable read failures
- operator-reviewed resume decisions
- duplicate side-effect prevention

It is not designed for autonomous self-healing, live retry, or automatic rollback.

## Recovery States

The recovery assessment classifies a run as one of:

- `retryable`
- `resumable`
- `manual_review_required`
- `blocked`
- `not_recoverable`

### When a run is retryable

A run is retryable when the failed step is safe to retry, no side effect has already been executed, and the retry policy allows the failure class. Read-only external timeouts and dependency failures can be retryable when the manifest policy allows them.

### When a run requires manual review

A run requires manual review when the failure is a validation issue, the runtime store is unhealthy, the manifest cannot be loaded, a side-effect status is unknown, or the retry/resume path cannot be proven safe.

## Idempotency Keys

Every pending action gets a deterministic idempotency key:

```text
<manifest_id>:<frame_id>:<step_id>:<action_type>:<business_ref>
```

That key prevents duplicate side effects when a pending action is retried or resumed.

If the same action was already executed, the runtime blocks the second execution with `DUPLICATE_SIDE_EFFECT_BLOCKED`.

## CLI Commands

Use these commands to inspect and plan recovery:

```bash
taskframe recover assess <frame_id>
taskframe recover retry-step <frame_id> --step <step_id>
taskframe recover resume <frame_id>
```

All three commands default to dry-run behavior. No live retry or live resume is enabled in this spec.

## Why Validation Is Not Auto-Retried

Validation failures indicate the manifest, input data, or business rule set is not acceptable yet. Retrying the same state is usually unhelpful and can hide a real data issue, so validation failures are routed to manual review instead.

## Safety Boundary

Recovery uses the runtime store, monitoring summary, profile safety checks, and idempotency records to decide whether a run is retryable or resumable. That supports controlled pilot readiness, not full production readiness.

## Pilot Readiness Integration

Recovery and idempotency are validated as part of the pilot readiness gate. The gate checks:

- Recovery assessment stub can be generated
- `DUPLICATE_SIDE_EFFECT_BLOCKED` constant is present (idempotency protection)
- Recovery documentation is present

See [pilot_readiness.md](pilot_readiness.md) for the full pilot readiness gate documentation.

## Spec 132 — Live side-effect idempotency contract

Spec 132 extends idempotency enforcement to the live side-effect execution path. Before any live side effect runs, the preflight gate checks:

1. The pending action carries an `idempotency_key` (fails with `IDEMPOTENCY_KEY_REQUIRED` if absent)
2. The same key has not already been used by a different executed action (`DUPLICATE_SIDE_EFFECT_BLOCKED`)
3. The pending action has not already been marked `live_executed: true` (`DUPLICATE_SIDE_EFFECT_BLOCKED`)

These checks run as part of `run_live_side_effect_preflight()` in `runtime/live_side_effect_contract.py`. Recovery dry-run paths are unaffected — they remain dry-run only with the same idempotency key tracking as before.

## Spec 133 — Gmail send idempotency

Spec 133 extends idempotency enforcement to `gmail/send`. Before any live Gmail is sent:

1. The pending action carries an `idempotency_key` — absent key fails with `IDEMPOTENCY_KEY_REQUIRED`
2. The key has not been used by another executed action — duplicate blocked with `DUPLICATE_SIDE_EFFECT_BLOCKED`
3. The pending action has not already been marked `live_executed: true`

These are enforced by the Spec 132 preflight gate in `run_live_side_effect_preflight()`. No Gmail-specific idempotency code is needed — the contract handles it generically.
