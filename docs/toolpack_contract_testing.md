# Tool Pack Contract Testing

The contract test harness verifies that an external tool pack meets the runtime contract before it can be registered or shipped.

---

## Running contract tests

```bash
taskframe tools test tool_packs/my_crm/toolpack.json
```

With JSON output:

```bash
taskframe tools test tool_packs/my_crm/toolpack.json --json
```

Skip manifest smoke:

```bash
taskframe tools test tool_packs/my_crm/toolpack.json --no-manifest-smoke
```

---

## What is checked

The contract test harness runs seven checks:

| Check | What it verifies |
|---|---|
| `descriptor_valid` | The `toolpack.json` is valid against the runtime contract |
| `import_ok` | The tool module and function can be imported |
| `smoke_ok` | The tool function can be called with generated smoke args |
| `result_shape_ok` | The return value has the required keys: `ok`, `type`, `data`, `evidence`, `error` |
| `safety_ok` | Side-effect tools require approval; live side effects are blocked |
| `health_check` | The health function returns `ok: true` without calling external systems |
| `manifest_smoke` | Example manifests in `examples/` have valid structure |

---

## Result shape

All tool functions must return a dict with these keys:

| Key | Type | Meaning |
|---|---|---|
| `ok` | `bool` | Whether the call succeeded |
| `type` | `str` | Output type identifier (e.g., `crm_search_customer_result`) |
| `data` | `dict` | Structured output data |
| `evidence` | `dict` or `list` | Audit trail |
| `error` | `str` | Error message (empty on success) |

---

## Smoke argument generation

The harness generates smoke arguments from `arg_types` in the descriptor:

| Type | Smoke value |
|---|---|
| `str` | `"TEST"` |
| `int` | `1` |
| `float` | `1.0` |
| `bool` | `False` |
| `dict` | `{}` |
| `list` | `[]` |

If a required argument has an unknown type, the contract test fails with `UNKNOWN_ARG_TYPE`.

---

## Safety policy checks

The harness enforces these safety rules:

- Side-effect tools (`side_effect: true`) must have `requires_approval: true`.
- Scaffolded tools must not have `allow_live_side_effect: true`.

A tool that fails the safety check fails the contract.

---

## Expected output

```
Tool pack: my_crm
  descriptor_valid: PASS
  health_check: PASS
  manifest_smoke: PASS
  crm/search_customer: import=PASS smoke=PASS shape=PASS safety=PASS
```

Exit code `0` when all checks pass, non-zero when any check fails.

---

## Generated contract tests

The scaffold wizard generates contract tests in `tests/test_<id>_contract.py`. These tests use the contract runner and are designed to pass without network access.

Run them directly:

```bash
python -m pytest tool_packs/my_crm/tests/test_my_crm_contract.py
```

---

## Relationship to descriptor validation

`taskframe tools validate` checks the descriptor structure only. `taskframe tools test` also imports, calls, and validates the result shape of each tool function. Always run `test` before enabling a pack in production.

---

## Programmatic use

```python
from src.toolpack_contract_runner import run_toolpack_contract_tests

result = run_toolpack_contract_tests("tool_packs/my_crm/toolpack.json")
assert result["ok"] is True
```

See [docs/toolpack_scaffold_wizard.md](toolpack_scaffold_wizard.md) for the scaffold guide.
