# Worker Hardening

This document defines the worker-supervisor hardening boundary introduced in Spec 152.
It hardens the existing local worker loop without enabling live side effects or optional browser automation.

## What It Covers

- `taskframe worker status --json`
- `taskframe worker health --json`
- `taskframe worker clear-stale-lock`
- bounded cycle classification and recovery recommendations
- worker hardening and soak evidence under `runtime_data/worker/reports/`

## Status Output

`taskframe worker status --json` now includes a `hardening` payload with:

- `ok`
- `classification`
- `anomalies`
- `recommendations`

The status payload also keeps the existing worker fields such as worker ID, PID, lock ID, heartbeat timestamps, cycle count, and last cycle summary.

## Health Output

`taskframe worker health --json` now includes:

- `soak_ready`
- `service_ready`
- `hardening_checks`
- `blockers`
- `warnings`

Health still checks persistence, queue, scheduler, event sources, and stale-lock state.
Service mode additionally requires service preflight and worker identity.

## Cycle Classification

Worker cycles are classified as one of:

- `OK`
- `NO_WORK`
- `PARTIAL_FAILURE`
- `FAILED_RECOVERABLE`
- `FAILED_MANUAL_REVIEW`
- `FAILED_POLICY_BLOCKED`
- `FAILED_STALE_LOCK`
- `FAILED_TIMEOUT`

The classification is used by the hardening report and by the soak harness to summarize repeated runs.

## Stale Lock Recovery

`taskframe worker clear-stale-lock` only clears a stale lock.
It refuses to force-clear a live lock, which keeps duplicate-worker recovery safe.

If the lock is stale, clear it explicitly and then rerun the worker.
If the lock is live, stop the running worker before starting a new one.

## Safety Boundary

Worker hardening improves evidence and recovery behavior, but it does not enable live writes, live sends, or optional RPA.
The default worker path remains dry-run oriented and bounded.
