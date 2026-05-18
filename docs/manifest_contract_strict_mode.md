# Manifest Contract Strict Mode v1

Strict mode is the release-gate view of manifests. It checks the canonical manifest contract after normalizing known legacy aliases.

## Canonical shape

```json
{
  "manifest_id": "customer.status_llm_e2e",
  "name": "Customer Status LLM E2E",
  "version": "1.0.0",
  "trigger": {
    "type": "manual"
  },
  "inputs": {
    "required": ["customer_id", "message"],
    "optional": []
  },
  "steps": [],
  "validations": [],
  "completion": {},
  "side_effect_policy": {}
}
```

## Legacy aliases

Strict mode still normalizes these fields:

- `id` → `manifest_id`
- `trigger_type` → `trigger.type`
- `step_id` → `steps[].id`
- `required_outputs` → `completion.success_outputs`
- `required_pending_actions` → `completion.success_pending_actions`
- `required_executed_actions` → `completion.success_executed_actions`

When a legacy field is normalized, strict mode records a warning.

## What strict mode checks

- required top-level fields
- step ids, kinds, and output aliases
- input declarations versus references
- validation references
- completion consistency
- side-effect policy consistency
- event route coverage
- tool registry coverage
- live execution flags in active manifests

## Practical guidance

- Use canonical fields in new manifests.
- Keep approval-gated side effects staged through pending actions.
- Do not enable live execution in active or release manifests.
- Keep test-only fixtures out of the active catalog.

## CLI

Validate one manifest:

```bash
taskframe manifests validate-strict manifests/customer_status_llm_e2e.manifest.json --json
```

Check the active catalog:

```bash
taskframe manifest-health --strict --no-smoke
```

## Troubleshooting

| Finding | Meaning | Fix |
|---|---|---|
| `missing_version` | Canonical manifest has no version | Add `version` |
| `unknown_tool` | Tool step is not registered | Register the tool or fix the command |
| `route_missing_required_input_mapping` | Event route does not cover required inputs | Update `config/event_routes.json` |
| `live_execution_enabled` | Active manifest enables live execution | Disable live execution |
| `side_effect_without_pending_completion` | Side effects are not approval-gated | Add pending-action completion rules |

