# Customer custom tool packs

Place this customer's **custom** tool packs here, one directory per pack:

```
tool_packs/<pack_id>/
  toolpack.json   descriptor (id, version, tools, health, core_or_optional)
  tools.py        tool implementations
  health.py       check_health()
  README.md
```

Scaffold and validate with the engine's tooling — do not hand-roll:

- `docs/toolpack_scaffold_wizard.md` — generate the skeleton
- `docs/toolpack_contract.md` / `toolpack_contract_testing.md` — contract gate
- `docs/toolpack_governance.md` / `toolpack_lifecycle.md` — governance

Then register the pack in `../config/enabled_toolpacks.json` with a path relative to the
config dir, e.g.:

```json
{
  "enabled_toolpacks": [
    "tool_packs/core_business/toolpack.json",
    "../tool_packs/acme_billing/toolpack.json"
  ]
}
```

Built-in `core_*` packs are referenced relative to the app root (`tool_packs/...`); custom
bundle packs are referenced relative to the config dir (`../tool_packs/...`).

> Custom packs are NOT a Python import path inside the core image. The bundle is mounted at
> `/bundle`, so reference packs by file path as above; the loader resolves and validates the
> descriptor from disk.
