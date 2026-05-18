# Adding New Tools

This guide defines the standard path for onboarding a new tool into the runtime without breaking the architecture.

Tools are deterministic capability adapters.
Tools do not control workflows or choose other tools.
Manifests decide when tools are used.
TaskFrames record all tool activity.
Side effects are staged and approved.
Live execution is blocked by default.

## Tool Onboarding Overview

**For external tool packs**, use the scaffold wizard as the starting point:

```bash
taskframe tools scaffold my_pack --namespace mypkg --tool run --safe-read
taskframe tools validate tool_packs/my_pack/toolpack.json
taskframe tools test tool_packs/my_pack/toolpack.json
```

See [toolpack_scaffold_wizard.md](toolpack_scaffold_wizard.md) and [toolpack_contract_testing.md](toolpack_contract_testing.md).

**For built-in tools**, follow the full onboarding sequence:

1. Classify the tool
2. Implement the tool function
3. Register the tool
4. Add capability metadata
5. Add health check
6. Add setup instructions
7. Add guardrail if live side effect is possible
8. Add manifest usage
9. Add tests
10. Confirm tool appears in operator status
11. Confirm release verifier boundary
12. Run a lifecycle evaluation and record the report

## Tool Classification

| Class | Description | Examples | Default execution |
|---|---|---|---|
| Read-only | Reads data only | search, read, list, check | Can run immediately |
| Transform | Converts or formats input | parse, normalise, summarise | Can run immediately |
| Prepare or stage | Prepares a future side effect | draft, prepare, stage | Creates pending output or action |
| Side-effect | Changes external state | send, create, update, delete | Must stage pending action |
| Live side-effect | Executes a real side effect | send real email, write real sheet | Requires approval and live gate |
| Optional or high-risk | RPA or fragile external automation | browser automation | Excluded from default RC |

When in doubt, classify the tool as higher risk.

## Tool Implementation Rules

A tool function must:

- accept explicit arguments only
- perform one clear action
- avoid hidden global state where practical
- return a structured result
- not mutate TaskFrame directly
- not call the orchestrator
- not call the LLM
- not select other tools
- not silently execute side effects

Preferred return shape:

```json
{
  "ok": true,
  "data": {},
  "error": "",
  "evidence": {
    "tool": "namespace/action",
    "mode": "dry_run",
    "source": "builtin",
    "operation": "read",
    "input_refs": [],
    "output_ref": "output_alias"
  }
}
```

Tool functions perform capability work. The runtime records the tool call. The manifest decides why the tool is called.

See [tool_result_contract.md](tool_result_contract.md) for the canonical runtime result shape and the redaction rules that apply to evidence.

## Tool Registry

Built-in tools remain registered in `TOOL_REGISTRY`.

External tools should be packaged as tool packs and enabled through configuration.

Selected built-in tools are being migrated behind the same tool-pack contract. The compatibility registry keeps old manifests working while the migration proceeds.

Example tool pack descriptor:

```json
{
  "toolpack_id": "demo_echo",
  "name": "Demo Echo Tool Pack",
  "module_prefix": "tool_packs.demo_echo",
  "tools": []
}
```

Register a new built-in tool in `TOOL_REGISTRY` only when the tool truly belongs in the core runtime.

```json
{
  "namespace/action": {
    "namespace": "namespace",
    "action": "action",
    "module": "runtime.some_tool_module",
    "function": "function_name",
    "side_effect": false,
    "requires_approval": false,
    "allow_live": true,
    "allow_live_side_effect": false,
    "live_guardrail": "blocked",
    "output_type": "some_result_type",
    "required_args": [],
    "optional_args": [],
    "arg_types": {}
  }
}
```

| Field | Required | Meaning |
|---|---|---|
| `namespace` | Yes | Tool namespace used in command syntax |
| `action` | Yes | Tool action name |
| `module` | Yes | Python module path |
| `function` | Yes | Function to call |
| `side_effect` | Yes | Whether the tool changes state |
| `requires_approval` | Yes | Whether pending approval is required |
| `allow_live` | Yes | Whether read-only live execution is allowed |
| `allow_live_side_effect` | Yes | Whether approved live side effect is possible |
| `live_guardrail` | Yes | Guardrail name or `blocked` |
| `output_type` | Yes | Result type recorded in TaskFrame |
| `required_args` | Yes | Required arguments |
| `optional_args` | Yes | Optional arguments |
| `arg_types` | Yes | Coercion rules |

Command syntax example:

```text
[t:customer/read -> customer] customer_id=$inputs.customer_id
```

## Argument Contract

- Required args must be present.
- Optional args may be omitted.
- `arg_types` should be used for deterministic coercion.
- Tool functions should not parse raw command text directly.

Example:

```json
{
  "arg_types": {
    "limit": "int",
    "dry_run": "bool"
  }
}
```

Argument resolution belongs to the runtime. Business parsing belongs in explicit parser or extractor tools, or in bounded LLM steps.

## Capability Registry

Every visible tool must have capability metadata.

| Field | Meaning |
|---|---|
| `tool_id` | Stable tool identifier |
| `display_name` | Operator-facing name |
| `description` | Short capability description |
| `category` | Tool category such as business, database, LLM, memory, reporting, or RPA |
| `is_core` | Whether the tool belongs in the default runtime path |
| `side_effect_level` | Read-only, prepare, approval-required, or high-risk |
| `auth_required` | Whether credentials are needed |
| `setup_available` | Whether setup guidance exists |
| `setup_action` | Operator setup action name |
| `rpa_live_probe_required` | Whether a real live probe is required |
| `limitations` | Known operational limits |

Example:

```python
ToolCapability(
    tool_id="google_sheets",
    display_name="Google Sheets",
    description="Reads and writes spreadsheet data.",
    category="external_api",
    is_core=True,
    side_effect_level="write",
    auth_required=True,
    setup_available=True,
    setup_action="show_google_sheets_setup",
    rpa_live_probe_required=False,
    limitations=["Requires OAuth credentials."],
)
```

If a tool is not in the capability registry, the operator cannot properly assess its readiness.

External tool packs must also provide `toolpack.json`, a README, and a safe health check.

Before a new pack is considered operational, run:

```bash
taskframe tools lifecycle tool_packs/my_pack/toolpack.json --env dev --write-report
```

The lifecycle report captures discovery, descriptor validation, contract tests, health checks, governance policy, enablement, registry integration, and example manifest smoke checks in one auditable artifact.

## Tool Health

Every tool should have a safe health status path.

Minimum statuses:

- `ready`
- `not_run`
- `needs_auth`
- `missing_dependency`
- `misconfigured`
- `disabled_optional`
- `live_probe_required`
- `failing`
- `unknown`

Health checks must:

- avoid live side effects
- avoid destructive operations
- return structured `ToolHealthResult`
- record a useful message
- record a recommended action where relevant
- persist into the latest tool health snapshot

Safe health check examples:

| Tool | Safe health check |
|---|---|
| Business database | Load and validate local fixtures |
| Memory store | Check or create local store |
| Report generator | Generate a harmless probe report |
| Gmail | Check credentials or token presence |
| Sheets | Check credentials or config presence |
| Ollama | Check local endpoint or model availability |
| RPA | Report setup or live-probe-required unless explicitly live-tested |

## Tool Setup

Setup instructions belong in `runtime/tool_setup.py`.

Each tool should return:

```json
{
  "tool_id": "...",
  "display_name": "...",
  "summary": "...",
  "operator_action_required": true,
  "steps": []
}
```

Rules:

- Safe setup may create local folders or seed local fixtures.
- Safe setup may not send messages, write external systems, or run live browser automation.
- External auth setup should explain manual steps.
- RPA setup should remain manual unless explicitly approved in a later spec.

## Live Side-Effect Guardrails

A guardrail is required when `allow_live_side_effect = True`.

Live side effects are blocked by default.
Live guardrails are required for any tool that can touch external state.

Live side-effect execution requires:

- `runtime_live_mode == True`
- `ToolRunner.dry_run == False`
- the TaskFrame is in an executable approval state
- the `PendingAction` is `APPROVED`
- the manifest `live_execution.enabled` is `True`
- the manifest allowlist includes the tool
- the registry allowlist includes live side effects
- the guardrail returns `ok == True`
- the audit trail records policy and guardrail checks

New tools must use `live_guardrail = "blocked"` unless a specific guardrail is implemented and tested.

## Manifest Usage

Registering a tool does not make it part of a workflow.

A tool becomes executable only through a manifest step:

```json
{
  "id": "read_customer",
  "command": "[t:customer/read -> customer] customer_id=$inputs.customer_id"
}
```

For side-effect tools:

```json
{
  "id": "prepare_customer_reply",
  "command": "[t:customer/prepare_message_action -> sent_reply] customer=$customer; message=$draft_reply"
}
```

The manifest must define completion correctly:

```json
{
  "completion": {
    "success_pending_actions": ["sent_reply"],
    "allow_pending_approval": true
  }
}
```

Side-effect manifests should complete in `WAITING_FOR_EXECUTE` unless approval or execution is part of the explicit scenario.

## Optional Tools

Optional tools may exist in the repo.

- Optional tools must not be imported by the default runtime path.
- Optional tools must not be required by default tests.
- Optional tools must not be required by the golden demo.
- Optional RPA tools must remain outside the default RC path.

## RPA

RPA tools are optional, high-risk, and live-environment-dependent.

- Mark them optional in the capability registry.
- Require a live probe for meaningful verification.
- Keep setup instructions explicit and manual.
- Do not run live RPA during safe health checks.
- Do not include live RPA in default release verification except as an exclusion boundary check.

## Tests

Every new tool should add tests for:

- registry wiring
- argument validation
- dry-run behavior
- side-effect staging, if relevant
- health check behavior
- setup instruction visibility
- optional boundary handling, if optional
- release verifier impact
