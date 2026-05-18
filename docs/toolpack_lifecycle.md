# Tool Pack Lifecycle

This document defines the operator lifecycle for external and migrated tool packs.

The lifecycle is intentionally conservative:

- discovery must succeed before anything else
- descriptor validation must pass before execution checks
- contract tests must pass before enablement
- health checks must be safe and non-destructive
- governance decides whether a pack may be used in a given environment
- registry integration confirms the runtime can actually expose the pack

## Lifecycle stages

The lifecycle evaluator runs the following stages in order:

1. `discovered`
2. `descriptor_valid`
3. `contract_test`
4. `health_check`
5. `governance_policy`
6. `enabled_for_environment`
7. `registry_integration`
8. `example_manifest_smoke`

The CLI entrypoint is:

```bash
taskframe tools lifecycle tool_packs/demo_echo/toolpack.json --env dev --write-report
```

## Lifecycle statuses

The final lifecycle status uses one of these values:

| Status | Meaning |
|---|---|
| `UNKNOWN` | Descriptor could not be discovered or read |
| `DISCOVERED` | Descriptor was found and parsed |
| `INVALID` | Descriptor, contract, health, registry, or example smoke failed |
| `UNTESTED` | The pack is valid but one or more optional lifecycle checks were skipped |
| `GOVERNANCE_REQUIRED` | The pack is valid but not enabled for the requested environment |
| `DISABLED` | The pack is explicitly disabled in configuration or blocked by enablement state |
| `READY` | The pack is valid, tested, healthy, governed, enabled, and registered |
| `READY_WITH_WARNINGS` | The pack is usable, but non-blocking warnings remain |
| `BLOCKED` | The pack is unsafe or policy-blocked for the requested environment |

## Validation vs contract test vs health check vs enablement

These are separate checks:

- **Descriptor validation** checks structure: required fields, tool declarations, module imports, and health metadata.
- **Contract testing** executes smoke calls and verifies canonical result shape and safety constraints.
- **Health checks** run a safe, read-only operational probe.
- **Enablement** checks whether the pack is actually enabled for the requested environment.

Do not treat any one of these as sufficient on its own.

## Governance interaction

Governance answers a different question from validation:

- validation asks whether the pack is structurally sound
- governance asks whether the pack is allowed in this environment

If no governance policy exists:

- `demo`, `release`, and `live` are blocked
- `dev` and `test` are marked `GOVERNANCE_REQUIRED`

High-risk or explicitly blocked packs must not become lifecycle-ready in restricted environments.

## Safe default behavior

The lifecycle path must not introduce live side effects.

The default behavior is:

- no live tool execution
- no destructive actions
- no credential exposure in evidence
- no automatic registration into restricted environments

If a pack is only partially ready, the report should explain why and suggest the next action.

## Onboarding a new tool pack

Recommended sequence:

1. scaffold the pack
2. validate the descriptor
3. run contract tests
4. run health checks
5. record governance
6. evaluate lifecycle
7. write the lifecycle report
8. register or enable the pack only when the lifecycle outcome supports it

Example:

```bash
taskframe tools validate tool_packs/my_pack/toolpack.json
taskframe tools test tool_packs/my_pack/toolpack.json
taskframe tools lifecycle tool_packs/my_pack/toolpack.json --env dev --write-report
```

## Disabling or blocking a pack

A pack should be disabled when it should not be available in an environment even though it may still be structurally valid.

A pack should be blocked when it is unsafe, policy-restricted, or not appropriate for the requested environment.

Use governance configuration for explicit environment control. Do not rely on manifest authors to enforce policy.

## Lifecycle evidence

Lifecycle reports are written to:

```text
runtime_data/toolpacks/lifecycle/<toolpack_id>_lifecycle.json
runtime_data/toolpacks/lifecycle/<toolpack_id>_lifecycle.md
```

The report captures:

- stage outcomes
- warnings and errors
- recommended next action
- the environment that was evaluated
- the runtime summary for the pack

Evidence stored in lifecycle reports must not include credentials, secrets, raw tokens, or full personal message bodies.

## Example outcome

```json
{
  "ok": true,
  "toolpack_id": "demo_echo",
  "environment": "dev",
  "status": "READY"
}
```

That outcome means the pack is ready for use in the requested environment, subject to the normal runtime approval rules for any side-effecting tools.
