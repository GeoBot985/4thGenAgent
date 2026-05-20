# Runtime Store

The runtime store is the durable file-based record of TaskFrame execution, evidence, and operational metadata. It is designed to be inspectable and recoverable without adding a database yet.

## Layout

The canonical runtime store layout is:

```text
runtime_data/
  taskframes/
  reports/
  approval_packs/
  evidence/
  tool_health/
  indexes/
  backups/
  cleanup/
  migrations/
```

The store also continues to carry legacy run folders under `runtime_data/runs/` while the migration path is still in progress.

## Artifact Types

- `taskframes/` holds TaskFrame JSON records.
- `reports/` holds run reports and related summaries.
- `approval_packs/` holds approval pack records.
- `evidence/` holds evidence bundles and evidence pack records.
- `tool_health/` holds the latest tool health snapshots.
- `indexes/` holds rebuildable indexes.
- `backups/` holds exported zip backups and backup manifests.
- `cleanup/` holds cleanup and retention-plan reports.
- `migrations/` holds migration markers or audit trails.

Each major artifact type should carry a stable path, a schema or version field where practical, created/updated timestamps, and a source frame or run reference.

## Validation

Use:

```bash
taskframe runtime-store check
taskframe runtime-store index
```

Validation checks for:

- required folders
- loadable TaskFrame JSON
- valid manifest references
- valid TaskFrame state
- approval packs that reference real TaskFrames
- evidence bundles whose referenced files exist
- reports that point at real runs
- rebuildable indexes
- corrupted JSON files

Validation reports corrupted paths and orphaned artifacts instead of crashing the full scan.

## Backup And Restore

Back up the runtime store with:

```bash
taskframe runtime-store backup
```

The backup is written under `runtime_data/backups/taskframe_backup_<timestamp>.zip` and includes the backup manifest, TaskFrames, reports, approval packs, evidence, indexes, tool health snapshots, and related runtime metadata.

Restore validation is safe by default:

```bash
taskframe runtime-store restore --backup <path> --target <path> --validate-only
```

Restore validation:

- rejects path traversal
- rejects malformed archives
- validates the restored runtime store
- writes a restore report into the target folder

It never overwrites active `runtime_data`.

## Retention

Retention is dry-run only in this spec:

```bash
taskframe runtime-store retention-plan
taskframe runtime-store cleanup --dry-run
```

Default retention policy:

```json
{
  "keep_completed_days": 30,
  "keep_failed_days": 90,
  "keep_pending_days": 365,
  "keep_approval_packs_days": 365,
  "keep_evidence_packs_days": 365,
  "delete_only_derived_artifacts": true,
  "protect_live_data": true,
  "protect_pending_actions": true
}
```

Only derived artifacts are candidates for cleanup. Pending actions and live-related records are protected so audit evidence is not removed accidentally.

## Demo Versus Pilot Records

Demo artifacts are safe, deterministic evidence for portfolio and development work. Pilot operational records may include controlled live reads and more sensitive evidence, but still do not allow live writes, sends, deletes, or other side effects in this spec.

That separation is deliberate:

- demo data is for portfolio and smoke workflows
- pilot data is for controlled live-read verification
- live side effects remain disabled

## Safe To Delete

Usually safe to delete:

- derived reports that can be regenerated
- rebuildable indexes
- temporary cleanup metadata
- stale backup archives after review

Do not delete without review:

- pending actions
- live-related evidence
- approval packs still awaiting execution or confirmation
- anything referenced by an evidence bundle

If a file cannot be loaded, it should be reported as a validation issue rather than deleted automatically.

## Monitoring Integration

The runtime store feeds the operational monitoring index and dashboard. Monitoring reuses the runtime-store validation summary, so corrupted artifacts, orphaned records, and rebuildability issues are visible without changing task execution.

Operational monitoring is read-only. It does not add automatic retry, recovery, or destructive cleanup.

## Recovery Integration

Recovery assessments and reports are written under `runtime_data/recovery/`.

Those reports record:

- the TaskFrame state
- the failed or current step
- pending actions
- executed actions
- retry attempts
- side-effect risk
- idempotency keys

Recovery is dry-run by default and does not overwrite active runtime data. It exists to support controlled recovery review, not automatic repair.

## Pilot Readiness Integration

The runtime store is validated as part of the pilot readiness gate. The gate checks:

- Required folder layout is present
- JSON artifacts are loadable
- Backup directory is resolvable
- Backup manifest is present in the store contract

See [pilot_readiness.md](pilot_readiness.md) for the full pilot readiness gate documentation.
