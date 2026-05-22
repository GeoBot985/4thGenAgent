# Testing Strategy

TaskFrame uses bounded validation groups for local work. Plain `python -m pytest` is reserved for overnight or explicit full-CI runs.

The CLI mirrors the same boundary:

```powershell
taskframe validate quick
taskframe validate local
```

## Local Commands

```powershell
python tools/run_bounded_validation.py quick
python tools/run_bounded_validation.py backend
python tools/run_bounded_validation.py manifest
python tools/run_bounded_validation.py toolpack
python tools/run_bounded_validation.py runtime
python tools/run_bounded_validation.py reports
python tools/run_bounded_validation.py local
```

## CI / Overnight

```powershell
python tools/run_bounded_validation.py ci
python tools/run_bounded_validation.py local
```

## Policy

- Use the bounded runner for local validation.
- Keep groups separated into subprocesses.
- Keep per-group timeouts in place.
- Reserve full-suite pytest for explicit CI or overnight validation only.
