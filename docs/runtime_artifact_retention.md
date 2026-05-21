# Runtime Artifact Retention

This document explains the runtime artifact management layer.

## What Are Runtime Artifacts?

The system generates significant state during operation:
- `runs/`: Execution traces and summaries for individual frames.
- `reports/`: Approvals, execution packs, evidence bundles.
- `release_verification/`: Release checks.
- `manifest_health_reports/` / `tool_health/`: Health validations.
- `workbench/`: Sandbox previews.
- `tmp/` / `.cache/`: Temporary processing files.

## Why Are They Retained?

Artifacts are essential for:
- Auditing live side-effects.
- Idempotency when recovering failed steps.
- Approval workflow resumption.
- Regression gallery reporting.

## What is Protected?

By default, the cleanup process is non-destructive and highly protective. The following artifacts are **never** deleted during normal cleanup:
- Any artifact modified within the last 14 days.
- Any failed runs.
- Runs containing executed or pending actions.
- Runs containing a live side-effect execution.
- Any file with an unrecognized or `unknown` artifact group.
- Core operational release logs (unless older than 30 days).

## Inspecting Artifact Status

You can review the artifact storage at any time:

```bash
python src/taskframe_cli.py artifacts status
```

This returns total items, sizes, delete candidates, and largest groups.

## Dry-Run Cleanup

You can generate a retention plan without deleting anything:

```bash
python src/taskframe_cli.py artifacts plan-cleanup
```

## Executing Cleanup

Artifacts are never deleted automatically on startup. Deletion must be executed manually and explicitly.

```bash
python src/taskframe_cli.py artifacts cleanup --confirm
```

If `--confirm` is missing, the cleanup command will refuse to execute and exit with code 1.
