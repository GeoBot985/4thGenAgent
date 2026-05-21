# Claude Code Test Policy

Do not run full release verification unless explicitly requested.

## Developer quick tests

Use this during normal development:

```bash
python tools/run_dev_tests.py
```

This excludes slow, release, integration, and live tests.
Use full release verification only when explicitly required.

Default test command:

```bash
python -m pytest tests -m "not slow and not release and not integration and not live" -q
```

For focused changes, run only the directly relevant test file:

```bash
python -m pytest tests/<test_file>.py -q
```

Do not run these unless explicitly requested:

```bash
python -m pytest
python tools/run_release_candidate_verification.py
python tools/run_release_candidate_verification.py --mode release
```
