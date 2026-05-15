# Tool Pack Contract

Tool packs are self-contained external bundles that contribute tools to the runtime through configuration rather than core code edits.

## Folder layout

```text
tool_packs/
  demo_echo/
    toolpack.json
    tools.py
    health.py
    README.md
    tests/
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

## Health checks

Tool packs should expose `health.module` and `health.function`, or set `health_supported=false`.

## Manifest usage

Manifests reference registered tool keys only, for example:

```text
[t:echo/echo -> echoed] message="Hello"
```

## Release boundary

Optional/high-risk packs are not automatically added to the default demo or release-candidate path.
