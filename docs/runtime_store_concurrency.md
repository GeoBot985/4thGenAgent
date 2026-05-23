# Runtime Store Concurrency

The runtime store is file-based. As more backend, UI, scheduler, and worker code touches the same TaskFrame artifacts, we need explicit protection against stale reads and concurrent writes.

This spec adds two controls:

1. Per-artifact lock files under `runtime_data/locks/`.
2. Optimistic version checks on mutable JSON artifacts.

## Why file locking exists

JSON artifacts under `runtime_data/` can be updated by multiple processes. Without a lock, two writers can read the same version and overwrite each other. Lock files let the runtime serialize a single mutable write per artifact key.

## How optimistic versions work

Mutable artifacts carry:

- `schema_version`
- `runtime_version`
- `updated_at`

Every successful mutation increments `runtime_version` and refreshes `updated_at`. Writers can pass an `expected_version`; if the artifact has moved on, the write is rejected with `VERSION_CONFLICT`.

## Approval conflict behavior

Approval and rejection paths require the latest version of the frame or approval artifact. If two requests race:

- one succeeds
- one returns a conflict

Already-finalized actions are rejected deterministically instead of being re-applied.

## Stale UI/API update handling

Clients should treat `VERSION_CONFLICT` as a reload signal. Load the current artifact again, re-read the current state, and resubmit only if the action is still valid.

## Limitations

This spec improves controlled pilot safety for a file-based runtime store. It does not provide database-grade transactional guarantees, distributed locking, multi-node clustering, or full production persistence.

Known limits:

- locks are local to the filesystem
- recovery is TTL-based, not consensus-based
- concurrent processes still depend on the filesystem honoring atomic rename and exclusive create semantics

## Migration path

This is a hardening layer, not a replacement for a database. If the runtime later moves to a persistent store with transactional writes, the same version fields and conflict handling can carry forward with less operational risk.
