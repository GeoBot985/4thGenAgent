# Manifest Catalog Health Repair

## Classification decisions

- `ACTIVE_FIX_REQUIRED`
  - `customer.message_status_check`
  - `event.mock_ping`
  - Action taken: fixed the custom-event validation step commands so the active catalog no longer reports command-parse failures.

- `TEST_FIXTURE_LEAKAGE`
  - `smoke.llm_summarize`
  - `smoke.llm_extract`
  - `smoke.llm_classify`
  - `smoke.llm_draft`
  - `smoke.memory_set`
  - `smoke.memory_get`
  - `smoke.memory_get_missing`
  - `smoke.validate_step_fail_fast`
  - Action taken: moved these manifests into `tests/fixtures/smoke_manifests/` and updated tests to load them explicitly.

- `UNSAFE_SMOKE_MANIFEST`
  - None remaining in the active catalog after quarantine.

- `STALE_MANIFEST`
  - None identified in this repair pass.

- `CATALOG_RULE_FALSE_POSITIVE`
  - None identified in this repair pass.

## Result

The active manifest catalog is expected to remain release-relevant, while test-only and smoke-only manifests are quarantined under `tests/fixtures/`.
