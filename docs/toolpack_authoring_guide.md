# Tool Pack Authoring Guide

## 0. Scaffold a new pack

Generate the complete pack structure with a single command:

```bash
taskframe tools scaffold my_pack --namespace mypkg --tool search --safe-read
```

This creates `tool_packs/my_pack/` with `toolpack.json`, `tools.py`, `health.py`, `README.md`, and a full test suite. See [toolpack_scaffold_wizard.md](toolpack_scaffold_wizard.md) for options.

After scaffolding, validate, run contract tests, and record a governance decision before writing any real logic:

```bash
taskframe tools validate tool_packs/my_pack/toolpack.json
taskframe tools test tool_packs/my_pack/toolpack.json
taskframe tools enable my_pack --classification optional --env dev,test --reason "Initial scaffold"
taskframe tools lifecycle tool_packs/my_pack/toolpack.json --env dev --write-report
```

See [toolpack_governance.md](toolpack_governance.md) for the classification and environment reference.

## 1. Start with a safe pack

Use a harmless pack first. The demo echo pack exists to prove the contract without introducing external dependencies or live side effects.

Core built-in tools are also being migrated behind the same contract. The difference is source and release boundary, not descriptor format.

## 2. Keep the pack self-contained

Put pack code, health checks, and README content inside one folder. Do not import browser or cloud dependencies from default runtime imports.

## 3. Declare tool safety explicitly

Side-effect tools must declare:

- `side_effect: true`
- `requires_approval: true`
- `allow_live: true` only when intended
- `allow_live_side_effect: true` only when explicitly permitted and tested

## 4. Validate and contract-test before registering

Use:

```bash
taskframe tools validate tool_packs/demo_echo/toolpack.json
taskframe tools test tool_packs/demo_echo/toolpack.json
```

`taskframe tools test` runs import checks, smoke invocations, result shape validation, and safety policy checks. See [toolpack_contract_testing.md](toolpack_contract_testing.md) for the full check list.

The contract test also enforces non-empty evidence for canonical tool results. If you are authoring a test or scaffold pack, see [tool_result_contract.md](tool_result_contract.md) for the required evidence shape.

## 5. Inspect health

Use:

```bash
taskframe tools health demo_echo
```

## 6. Evaluate lifecycle readiness

Use the lifecycle command to confirm discovery, governance, registry integration, and smoke checks before widening access:

```bash
taskframe tools lifecycle tool_packs/demo_echo/toolpack.json --env dev --write-report
```

The lifecycle report is the operator-facing summary of readiness. It complements validation, contract tests, and health checks instead of replacing them.

## 7. Enable packs through config

Add enabled pack paths to `config/enabled_toolpacks.json`.

Optional packs remain excluded until explicit enablement is provided in configuration.

## 8. Keep manifests registry-driven

Manifests should reference tool keys only. They should never import pack modules directly.

If a tool stages a side effect, return a pending-action result with evidence that records the pending action id and approval requirement.


## Google Workspace and external auth packs

Google Workspace is the first real external tool pack. It uses the same `toolpack.json` contract as other packs, but it is read-only and optional.

When authoring external auth packs, keep the default demo path free of live side effects and make credentials optional for clean-clone validation.
