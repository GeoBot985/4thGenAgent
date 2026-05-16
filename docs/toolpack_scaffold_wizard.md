# Tool Pack Scaffold Wizard

The scaffold wizard generates a complete tool pack structure from a single CLI command.

---

## Quick start

```bash
taskframe tools scaffold my_crm --namespace crm --tool search_customer --safe-read
taskframe tools validate tool_packs/my_crm/toolpack.json
taskframe tools test tool_packs/my_crm/toolpack.json
taskframe tools examples tool_packs/my_crm/toolpack.json
```

---

## Generated structure

```
tool_packs/my_crm/
  toolpack.json
  __init__.py
  tools.py
  health.py
  README.md
  tests/
    __init__.py
    test_my_crm_contract.py
    test_my_crm_health.py
    test_my_crm_tools.py
  examples/
    smoke_my_crm_search_customer.manifest.json
```

---

## Command reference

### Safe read-only tool

```bash
taskframe tools scaffold my_crm \
  --namespace crm \
  --tool search_customer \
  --safe-read
```

Generated tool defaults:

| Field | Value |
|---|---|
| `side_effect` | `false` |
| `requires_approval` | `false` |
| `allow_live` | `false` |
| `allow_live_side_effect` | `false` |
| `live_guardrail` | `blocked` |

### Side-effect tool

```bash
taskframe tools scaffold my_supplier \
  --namespace supplier \
  --tool send_order \
  --side-effect
```

Generated tool defaults:

| Field | Value |
|---|---|
| `side_effect` | `true` |
| `requires_approval` | `true` |
| `allow_live` | `false` |
| `allow_live_side_effect` | `false` |
| `live_guardrail` | `blocked` |

Side-effect tools always block live execution until explicitly implemented.

### Force overwrite

```bash
taskframe tools scaffold my_crm --force
```

### JSON output

```bash
taskframe tools scaffold my_crm --json
```

---

## Safety rules

The scaffold generator enforces:

- `toolpack_id` must be `snake_case` (lowercase letters, digits, underscores).
- `namespace` must be `snake_case`.
- `tool_name` must be `snake_case`.
- Tool key is always `namespace/tool_name`.
- Side-effect tools require approval and block live execution.
- Generated tools return the standard result shape (`ok`, `type`, `data`, `evidence`, `error`).
- Generated health checks must not call external systems.
- Generated tests must not require network access.
- Generated packs are not automatically inserted into the default scenario pack.
- Existing directories are not overwritten unless `--force` is used.

---

## After scaffolding

1. Replace `tools.py` with real implementation.
2. Replace `health.py` with a real connectivity or config check (no external calls in the scaffold check).
3. Run `taskframe tools validate` to confirm the descriptor is correct.
4. Run `taskframe tools test` to confirm the contract passes.
5. Add to `config/enabled_toolpacks.json` with `allow_optional_toolpacks: true` to enable.

---

## Default tool key format

`namespace/action` — for example `crm/search_customer`, `supplier/send_order`.

---

## Module path

Generated module: `tool_packs.<toolpack_id>.tools`

The scaffold generator sets `module_prefix` to `tool_packs.<toolpack_id>` in the descriptor.

---

## Validation

```bash
taskframe tools validate tool_packs/my_crm/toolpack.json
```

See [docs/toolpack_contract.md](toolpack_contract.md) for the full contract specification.

---

## Contract testing

```bash
taskframe tools test tool_packs/my_crm/toolpack.json
```

See [docs/toolpack_contract_testing.md](toolpack_contract_testing.md) for the full testing guide.
