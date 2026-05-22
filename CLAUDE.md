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
