# Worker Soak Testing

This document describes the bounded soak harness added in Spec 152.
The soak runner is intended for service-style verification, not for unattended live execution.

## Command

```powershell
taskframe worker soak --profile service --cycles 20 --sleep-seconds 0.1 --json
```

Useful options:

- `--profile`
- `--cycles`
- `--sleep-seconds`
- `--max-runtime-seconds`
- `--queue-limit`
- `--runtime-data-dir`
- `--fail-fast`
- `--json`
- `--write-report`

## Behavior

- Bounded by cycle count and maximum runtime.
- Runs dry-run by default.
- Calls service preflight first when `--profile service` is used.
- Refuses to enable live side effects.
- Does not import optional RPA.
- Writes JSON and Markdown soak reports under `runtime_data/worker/reports/`.

## Output

The soak result includes:

- requested and completed cycle counts
- failed and no-work counts
- duration and max cycle duration
- classification counts
- stale-lock status
- live-side-effect status
- report paths

## When To Use It

Use soak testing after the worker supervisor is otherwise healthy and before any later production-hardening work.
It is useful for proving that repeated bounded cycles do not create duplicate workers, stale-lock deadlocks, or silent cycle failures.

## What It Does Not Do

- It does not enable live side effects.
- It does not install a service wrapper.
- It does not add distributed worker leasing.
- It does not replace later soak, observability, or production deployment specs.
