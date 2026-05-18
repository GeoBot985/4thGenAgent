# Tool Pack Contract

Tool packs are self-contained external bundles that contribute tools to the runtime through configuration rather than core code edits.

Built-in migrated tools use the same descriptor contract. The runtime treats the contract as the normal tool shape, whether the pack is core or external.

## Generating a new pack

Use the scaffold wizard to generate the full structure in one step:

```bash
taskframe tools scaffold my_pack --namespace mypkg --tool run --safe-read
```

See [toolpack_scaffold_wizard.md](toolpack_scaffold_wizard.md) for all options.

## Folder layout

```text
tool_packs/
  demo_echo/
    toolpack.json
    tools.py
    health.py
    README.md
    tests/
      test_demo_echo_contract.py
      test_demo_echo_health.py
      test_demo_echo_tools.py
    examples/
      smoke_demo_echo_echo.manifest.json
```

## `toolpack.json`

Required top-level fields:

- `toolpack_id`
- `name`
- `version`
- `runtime_contract_version`
- `core_or_optional`
- `module_prefix`
- `health`
- `tools`

Each tool declaration must include:

- `tool`
- `namespace`
- `action`
- `module`
- `function`
- `side_effect`
- `requires_approval`
- `allow_live`
- `allow_live_side_effect`
- `live_guardrail`
- `output_type`

## Safety fields

Side-effect tools must require approval.

Live side effects stay blocked by default and must be explicitly declared, validated, and tested.

## Tool Result Contract

Every tool should return a canonical result with `ok`, `type`, `data`, `evidence`, `error`, and runtime `metadata`.

The runtime accepts legacy bridge results during migration, but normalized results must always carry non-empty evidence.

See [tool_result_contract.md](tool_result_contract.md) for the canonical shape and evidence examples.

## Health checks

Tool packs should expose `health.module` and `health.function`, or set `health_supported=false`.

## Manifest usage

Manifests reference registered tool keys only, for example:

```text
[t:echo/echo -> echoed] message="Hello"
```

## Contract test harness

Run the contract test harness against any pack:

```bash
taskframe tools test tool_packs/my_pack/toolpack.json --json
```

Checks run: descriptor valid, import ok, smoke invocation, result shape, safety policy, health check, and manifest smoke. See [toolpack_contract_testing.md](toolpack_contract_testing.md) for the full check table.

## Release boundary

Optional/high-risk packs are not automatically added to the default demo or release-candidate path.
