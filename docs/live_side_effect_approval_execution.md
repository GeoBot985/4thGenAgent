# Live Side-Effect Approval Execution Model

## Purpose

The live side-effect approval execution model (Spec 155) defines the full approval-gate-to-execution lifecycle for controlled live side effects. A live side effect may only execute after: manifest preparation, TaskFrame attachment, operator approval, runtime policy checks, idempotency enforcement, pre-execution validation, post-execution verification, and rollback metadata recording.

---

## v1 Scope

**Only `sheet/write_rows` is executable in v1.**

The following tools remain blocked regardless of profile configuration:

| Tool | Status |
|---|---|
| `gmail/send` | BLOCKED |
| `gmail/draft_send` | BLOCKED |
| `calendar/create` | BLOCKED |
| `calendar/update` | BLOCKED |
| `calendar/delete` | BLOCKED |
| `rpa/run` | BLOCKED |
| `rpa/click` | BLOCKED |
| `rpa/type` | BLOCKED |
| `rpa/navigate` | BLOCKED |

---

## Profile

The `controlled_live_write` profile governs v1 execution:

```json
{
  "profile_id": "controlled_live_write",
  "environment": "pilot",
  "allow_live_reads": true,
  "allow_live_side_effects": true,
  "require_tool_governance": true,
  "require_operator_approval": true,
  "require_typed_confirmation": true,
  "require_idempotency_key": true,
  "require_worker_identity": true,
  "require_rollback_plan": true,
  "executable_tools": ["sheet/write_rows"],
  "blocked_tool_classes": ["rpa", "send", "delete", "mutation"]
}
```

---

## Extended Pending Action Model

Spec 155 extends the pending action with these additional required fields:

| Field | Description |
|---|---|
| `target_ref` | Spreadsheet ID or target resource reference |
| `prepared_payload_hash` | SHA-256 of the prepared payload (must match at execution time) |
| `rollback_plan` | Display-only metadata dict describing how to undo the write |
| `worker_identity` | Identity of the worker process running the execution |

Plus the existing required fields: `idempotency_key`, `business_ref`, `approved_by`, `approved_at`.

---

## Pre-Execution Preflight (15 Checks)

`build_live_side_effect_preflight()` runs 15 checks before any execution:

| # | Check | Error Code |
|---|---|---|
| 1 | Profile is `controlled_live_write` | `PROFILE_NOT_LIVE_WRITE` |
| 2 | Profile allows live side effects | `PROFILE_SIDE_EFFECTS_DISABLED` |
| 3 | Tool is in v1 executable set | `TOOL_NOT_V1_EXECUTABLE` |
| 4 | Tool is not in blocked list | `TOOL_EXPLICITLY_BLOCKED` |
| 5 | Pending action status is APPROVED | `PENDING_ACTION_NOT_APPROVED` |
| 6 | `approved_by` is present | `APPROVAL_IDENTITY_MISSING` |
| 7 | `approved_at` is present | `APPROVAL_TIMESTAMP_MISSING` |
| 8 | `worker_identity` is present | `WORKER_IDENTITY_MISSING` |
| 9 | `idempotency_key` is present | `IDEMPOTENCY_KEY_REQUIRED` |
| 10 | `idempotency_key` not in ledger | `LEDGER_DUPLICATE` |
| 11 | `prepared_payload_hash` is present | `PAYLOAD_HASH_MISSING` |
| 12 | `target_ref` is present | `TARGET_REF_MISSING` |
| 13 | `business_ref` is present | `BUSINESS_REF_MISSING` |
| 14 | `rollback_plan` is non-empty dict | `ROLLBACK_PLAN_MISSING` |
| 15 | Typed confirmation matches (when supplied) | `CONFIRMATION_PHRASE_WRONG` |

---

## Typed Confirmation Phrase

The typed confirmation phrase is frame/action/tool specific:

```
EXECUTE LIVE sheet/write_rows <frame_id> <action_id>
```

This phrase must be typed exactly before live execution proceeds. It is case-sensitive.

---

## Execution Flow

```
1. build_live_side_effect_preflight() — 15 checks
2. If preflight blocked → append BLOCKED ledger entry → return blocked result
3. append_ledger_entry(status=EXECUTING) — in-flight marker
4. Call sheet_write_live_execute() (or dry_run_fallback)
5. append_ledger_entry(status=EXECUTED or FAILED)
6. build_live_execution_audit_event() → append_live_audit_event()
7. build_live_execution_report() → write_live_execution_report()
8. Return execution result
```

---

## Post-Execution Verification

`verify_live_side_effect_result()` performs post-execution checks:

- Execution result `ok` must be True
- Tool in result must match action tool
- Target ref in result must match action target ref
- Execution type must be a known sheet write type
- `rows_written` must be non-negative (if present)

---

## Rollback Plan

The rollback plan is **display-only metadata** in v1. No automatic rollback is performed.

The rollback plan is stored in:
- The ledger entry for the execution
- The execution report

Example rollback plan:
```json
{
  "action": "delete_rows",
  "range": "Sheet1!A2:D5",
  "note": "Delete the written rows to undo the write operation."
}
```

---

## CLI Commands

### Preflight (no execution)

```bash
python -m src.taskframe_cli live-side-effect preflight \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --tool sheet/write_rows \
  --profile controlled_live_write \
  --json
```

### Execute (requires typed confirmation)

```bash
python -m src.taskframe_cli live-side-effect execute \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --tool sheet/write_rows \
  --confirm "EXECUTE LIVE sheet/write_rows <frame_id> <action_id>" \
  --json
```

Use `--dry-run-fallback` for simulation without external API calls:

```bash
python -m src.taskframe_cli live-side-effect execute \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --confirm "EXECUTE LIVE sheet/write_rows <frame_id> <action_id>" \
  --dry-run-fallback \
  --json
```

### Post-Execution Verification

```bash
python -m src.taskframe_cli live-side-effect verify \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --json
```

### Ledger Report

```bash
python -m src.taskframe_cli live-side-effect report --json
```

### Rollback Plan (display only)

```bash
python -m src.taskframe_cli live-side-effect rollback-plan \
  --idempotency-key <key> \
  --json
```

---

## Release Verification

The release verifier includes `live_side_effect_approval_execution_model` as a standard check. It runs without requiring any real Google credentials:

- Validates the execution module exists with all required symbols
- Validates the ledger module with all required symbols
- Validates `controlled_live_write` profile configuration
- Validates CLI has all required commands
- Runs boundary preflight (no external API call)
- Verifies idempotency enforcement
- Confirms no auto-rollback in the module

---

## Safety Statement

> Only `sheet/write_rows` is executable in v1.
> Gmail send, calendar mutations, and RPA are blocked at the tool level.
> No automatic rollback is performed.
> All executions are logged in the JSONL ledger.
> Typed confirmation is required before any live execution.
> No real Google credentials are required for release verification.

---

## See Also

- [live_execution_ledger.md](live_execution_ledger.md) — Ledger storage
- [live_sheet_write_pilot.md](live_sheet_write_pilot.md) — Sheet write pilot
- [governed_live_read_proof.md](governed_live_read_proof.md) — Live read proof
