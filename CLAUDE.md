# Claude Code Test Policy

Do not run the full test suite locally.

Do not use:

```bash
python -m pytest
```

Use bounded validation instead:

```bash
python tools/run_bounded_validation.py quick
python tools/run_bounded_validation.py local
```

Full pytest is reserved for overnight/full CI only.

For backend work, remember that the production API now has an auth boundary. Use bearer tokens or the explicit dev bypass only in local development, and do not treat backend auth as a replacement for runtime live-execution guardrails.

## Developer quick tests

Use this during normal development:

```bash
python tools/run_bounded_validation.py quick
```

Use this for staged local validation:

```bash
python tools/run_bounded_validation.py local
```

Use full release verification only when explicitly required:

```bash
python scripts/run_release_verification.py
```
