# Consolidated Docs Bundle

This file inlines the text-based files under `docs/` and lists binary assets separately.
It is intended to be shared with an LLM as a single reference document.

## Inventory

- Text files included: 67
- Binary assets listed: 24
- Source directory: `D:/Projects/4thGenAgent/docs`

## Text Files

### docs/adding_new_tools.md

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


### docs/architecture_diagram.mmd

flowchart TD
    A[Operator UI] --> B[Cross-Workflow Demo Pack]
    A --> C[Event Routes]
    B --> C
    C --> D[Manifests]
    D --> E[TaskFrame]
    E --> F[Generic Orchestrator / State Machine]
    F --> G[Tool Registry]
    F --> H[LLM Adapter]
    F --> I[Validation Layer]
    G --> J[Business Tools]
    G --> K[Google Sheets]
    I --> L[Pending Actions / Approval Gate]
    L --> M[Dry-Run Executor]
    M --> N[Reports / Evidence Bundle]
    N --> O[Runtime Data]
    O --> A

    subgraph Principle["Architecture Principle"]
      P[Business logic lives in manifests + tools]
      Q[Not in the orchestrator]
    end
    D -.-> Principle


### docs/architecture_diagram.svg

<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="980" viewBox="0 0 1800 980" fill="none">
  <defs>
    <style>
      .bg { fill: #f7f8fa; }
      .panel { fill: #ffffff; stroke: #cbd5e1; stroke-width: 2; rx: 18; ry: 18; }
      .title { font: 700 30px Arial, sans-serif; fill: #0f172a; }
      .subtitle { font: 600 18px Arial, sans-serif; fill: #334155; }
      .label { font: 600 22px Arial, sans-serif; fill: #0f172a; }
      .small { font: 500 17px Arial, sans-serif; fill: #334155; }
      .accent { fill: #111827; }
      .node { fill: #ffffff; stroke: #0f172a; stroke-width: 2.5; rx: 16; ry: 16; }
      .tool { fill: #ecfeff; stroke: #0891b2; stroke-width: 2.5; rx: 16; ry: 16; }
      .llm { fill: #fef3c7; stroke: #d97706; stroke-width: 2.5; rx: 16; ry: 16; }
      .approval { fill: #dcfce7; stroke: #16a34a; stroke-width: 2.5; rx: 16; ry: 16; }
      .report { fill: #ede9fe; stroke: #7c3aed; stroke-width: 2.5; rx: 16; ry: 16; }
      .arrow { stroke: #475569; stroke-width: 4; fill: none; marker-end: url(#arrowhead); }
      .dashed { stroke-dasharray: 10 8; }
    </style>
    <marker id="arrowhead" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
      <path d="M 0 0 L 12 6 L 0 12 z" fill="#475569"/>
    </marker>
  </defs>
  <rect class="bg" x="0" y="0" width="1800" height="980"/>
  <text class="title" x="60" y="60">TaskFrame Runtime Architecture</text>
  <text class="subtitle" x="60" y="95">Business logic lives in manifests + tools, not in the orchestrator</text>

  <rect class="panel" x="40" y="140" width="1720" height="760" rx="20" ry="20"/>

  <rect class="node" x="80" y="220" width="230" height="84" rx="16" ry="16"/>
  <text class="label" x="195" y="255" text-anchor="middle">Operator UI</text>
  <text class="small" x="195" y="282" text-anchor="middle">Scenarios and demo packs</text>

  <rect class="node" x="80" y="380" width="230" height="84" rx="16" ry="16"/>
  <text class="label" x="195" y="415" text-anchor="middle">Event Routes</text>
  <text class="small" x="195" y="442" text-anchor="middle">Map triggers to manifests</text>

  <rect class="node" x="370" y="220" width="240" height="84" rx="16" ry="16"/>
  <text class="label" x="490" y="255" text-anchor="middle">Cross-Workflow</text>
  <text class="label" x="490" y="282" text-anchor="middle">Demo Pack</text>

  <rect class="node" x="370" y="380" width="240" height="84" rx="16" ry="16"/>
  <text class="label" x="490" y="415" text-anchor="middle">Manifests</text>
  <text class="small" x="490" y="442" text-anchor="middle">Steps, validations, completion</text>

  <rect class="node" x="670" y="300" width="240" height="120" rx="16" ry="16"/>
  <text class="label" x="790" y="337" text-anchor="middle">TaskFrame</text>
  <text class="small" x="790" y="364" text-anchor="middle">State, outputs, evidence</text>
  <text class="small" x="790" y="390" text-anchor="middle">tool calls, LLM calls, approvals</text>

  <rect class="node" x="980" y="300" width="280" height="120" rx="16" ry="16"/>
  <text class="label" x="1120" y="337" text-anchor="middle">Generic Orchestrator</text>
  <text class="small" x="1120" y="364" text-anchor="middle">State machine only</text>
  <text class="small" x="1120" y="390" text-anchor="middle">No business branches</text>

  <rect class="tool" x="1320" y="180" width="180" height="80" rx="16" ry="16"/>
  <text class="label" x="1410" y="214" text-anchor="middle">Tool Registry</text>
  <text class="small" x="1410" y="240" text-anchor="middle">Deterministic adapters</text>

  <rect class="tool" x="1320" y="290" width="180" height="80" rx="16" ry="16"/>
  <text class="label" x="1410" y="324" text-anchor="middle">Business Tools</text>
  <text class="small" x="1410" y="350" text-anchor="middle">Customer / procurement</text>

  <rect class="llm" x="1320" y="400" width="180" height="80" rx="16" ry="16"/>
  <text class="label" x="1410" y="434" text-anchor="middle">LLM Adapter</text>
  <text class="small" x="1410" y="460" text-anchor="middle">Bounded microtools</text>

  <rect class="tool" x="1320" y="510" width="180" height="80" rx="16" ry="16"/>
  <text class="label" x="1410" y="544" text-anchor="middle">Validation Layer</text>
  <text class="small" x="1410" y="570" text-anchor="middle">Deterministic checks</text>

  <rect class="approval" x="1320" y="620" width="180" height="80" rx="16" ry="16"/>
  <text class="label" x="1410" y="654" text-anchor="middle">Approval Gate</text>
  <text class="small" x="1410" y="680" text-anchor="middle">Pending actions</text>

  <rect class="approval" x="1320" y="730" width="180" height="80" rx="16" ry="16"/>
  <text class="label" x="1410" y="764" text-anchor="middle">Dry-Run Executor</text>
  <text class="small" x="1410" y="790" text-anchor="middle">No live side effects</text>

  <rect class="report" x="980" y="700" width="280" height="96" rx="16" ry="16"/>
  <text class="label" x="1120" y="737" text-anchor="middle">Reports / Evidence</text>
  <text class="small" x="1120" y="764" text-anchor="middle">Markdown, HTML, JSON</text>
  <text class="small" x="1120" y="790" text-anchor="middle">TaskFrame artifacts</text>

  <rect class="node" x="670" y="700" width="240" height="96" rx="16" ry="16"/>
  <text class="label" x="790" y="737" text-anchor="middle">Runtime Data</text>
  <text class="small" x="790" y="764" text-anchor="middle">JSON business data</text>
  <text class="small" x="790" y="790" text-anchor="middle">Run artifacts and seeds</text>

  <rect class="node" x="80" y="740" width="520" height="120" rx="16" ry="16"/>
  <text class="label" x="340" y="778" text-anchor="middle">Google Sheets</text>
  <text class="small" x="340" y="806" text-anchor="middle">Accounting surface: Payments, Orders, CustomerInvoices, Ledger, ReconRuns, ReconExceptions</text>
  <text class="small" x="340" y="834" text-anchor="middle">Data surface, not logic engine</text>

  <line class="arrow" x1="310" y1="262" x2="370" y2="262"/>
  <line class="arrow" x1="310" y1="422" x2="370" y2="422"/>
  <line class="arrow" x1="610" y1="262" x2="670" y2="324"/>
  <line class="arrow" x1="610" y1="422" x2="670" y2="356"/>
  <line class="arrow" x1="910" y1="360" x2="980" y2="360"/>
  <line class="arrow" x1="1260" y1="360" x2="1320" y2="220"/>
  <line class="arrow" x1="1260" y1="360" x2="1320" y2="330"/>
  <line class="arrow" x1="1260" y1="360" x2="1320" y2="440"/>
  <line class="arrow" x1="1260" y1="360" x2="1320" y2="550"/>
  <line class="arrow" x1="1410" y1="600" x2="1410" y2="620"/>
  <line class="arrow" x1="1410" y1="700" x2="1410" y2="730"/>
  <line class="arrow" x1="1320" y1="770" x2="1260" y2="748"/>
  <line class="arrow" x1="980" y1="748" x2="910" y2="748"/>
  <line class="arrow" x1="670" y1="748" x2="600" y2="800"/>
  <line class="arrow dashed" x1="490" y1="740" x2="490" y2="640"/>
  <text class="small" x="1050" y="655" text-anchor="middle">Business logic is in manifests + tools</text>
</svg>


### docs/architecture_overview.md

# Architecture Overview

TaskFrame Runtime is a manifest-driven autonomous business worker runtime for AI-assisted company operations.

The central rule is simple:

- business behavior belongs in manifests and tools
- presentation behavior belongs in `src/`
- runtime execution stays controlled, auditable, and deterministic where it matters

Intent / Event
    ->
Manifest Lookup
    ->
TaskFrame Creation
    ->
Orchestrator / State Machine
    ->
Tools / LLM / Memory
    ->
Validation / Approval Gates
    ->
TaskFrame Finalisation / Audit

| Block | Required explanation |
|---|---|
| Intent / Event | An explicit operator action, scheduled trigger, or external event starts the run. |
| Manifest Lookup | The runtime resolves the request to a manifest that defines allowed steps and validations. |
| TaskFrame Creation | A TaskFrame is created to hold run state, outputs, evidence, validations, and audit trail. |
| Orchestrator / State Machine | The orchestrator executes known manifests and state transitions; it does not invent workflows. |
| Tools / LLM / Memory | Tools are deterministic adapters, the LLM is a bounded helper, and memory stores durable facts separate from TaskFrame outputs. |
| Validation / Acceptance Gate | Deterministic checks decide completion and approval gates control side effects. |
| TaskFrame Finalisation / Audit | The run is closed with a durable audit trail, evidence bundle, and run report. |

## Controlled LLM Use

The LLM is used for bounded tasks such as:

- extraction
- classification
- drafting
- summarisation

It is not allowed to choose arbitrary tools or certify the final outcome.

## Run-Bound Evidence

Reports and evidence are generated from persisted run data, not from the live UI state.

- `runtime/run_report.py` builds run reports and evidence bundles
- `src/demo_story_presenter.py` builds the business-readable Demo view model
- `src/operator_ui.py` renders widgets and calls actions, but does not build business meaning

## Approval Gate

Side effects are staged as pending actions and must pass an approval gate before they can execute. This keeps live sends, writes, and other external actions visible and operator-controlled.

## Order Management Workflow Lane

The order management lane (Spec 110) adds five manifest-driven workflows for
validating new orders, reserving stock, releasing paid orders, detecting delayed
shipments, and updating shipment status. All business logic lives in
`runtime/order_management_tools.py` and the five manifests in `manifests/`.
The orchestrator is unchanged — no order logic was added to it. Side-effect
operations (stock reservation, order release, shipment update) follow the
standard prepare/execute approval pattern: prepare tools stage pending actions;
execute tools run with `dry_run=True` and require operator approval before any
mutation is simulated. See [docs/order_management_workflows.md](order_management_workflows.md).

## Optional RPA Tools

Browser-backed RPA tools are treated as optional, high-risk, live-environment-dependent adapters. They are excluded from default clean-clone release verification because they depend on local browser state, external authentication, and changing web UIs. They can still support operator-triggered live probes in local mode, but they are not part of the default portfolio demo path.

## Boundary Summary

- `runtime/` owns execution, persistence, validation, tool routing, and reporting
- `src/` owns UI presentation and view-model construction
- `tools/` owns CLI utilities and release verification
- `optional_tools/` owns optional integration surfaces
- `bits/` contains a separate FastAPI/RAG prototype path

See [docs/product_boundary.md](product_boundary.md) for the product framing in one place.


### docs/builtin_toolpack_migration.md

# Built-in Tool Pack Migration v1

This document records the first migration step where selected core tools are represented as tool packs while the legacy registry remains as fallback.

## What migrated in v1

- `business/get_order_context`
- `memory/set`
- `q/extract_order_ref`
- `report/generate`

These tools are available through the same `toolpack.json` contract used by external packs.

## Compatibility registry

The runtime merges:

1. migrated core tool packs;
2. enabled external tool packs;
3. legacy fallback registry.

The compatibility registry is intentionally conservative. Migrated tools must not become less safe than the legacy equivalent.

## What stays unchanged

- manifest syntax;
- pending-action approval flow;
- default dry-run behavior;
- optional RPA exclusion;
- live execution guardrails.

Existing manifests keep using the same command strings. No manifest edits are required for this migration step.


### docs/capture_screenshots.md

# Capture Screenshots

These portfolio screenshots are captured from the live operator console and the generated release/report artifacts.

## Start The Console

```powershell
python -m src.operator_ui
```

## Generate The Demo Artifacts First

```powershell
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

## Current Screenshot Set

The current portfolio set is:

- `docs/screenshots/01_operator_home.png`
- `docs/screenshots/02_demo_customer_happy_path.png`
- `docs/screenshots/03_demo_customer_pending_approval.png`
- `docs/screenshots/04_run_report_step_outcomes.png`
- `docs/screenshots/05_demo_customer_failed_validation.png`
- `docs/screenshots/06_report_generation_demo.png`
- `docs/screenshots/07_business_report_visible_path.png`
- `docs/screenshots/08_tool_status_panel.png`
- `docs/screenshots/09_release_verification.png`

## Capture Notes

- Capture the operator UI after the clean demo and tool health state is loaded.
- Use the default portfolio workflows only.
- Show the business-readable Demo View for the customer and report-generation scenarios.
- Include the run report step-outcome view for the audit artifact.
- Do not include ABSA, Google Messages, or any personal/private RPA workflow in the main demo path.
- For report and verification screenshots, capture the generated markdown or artifact viewer output, not live external systems.


### docs/cli_reference.md

# TaskFrame CLI Reference

`taskframe` is the public command-line entry point for the packaged runtime.

## Commands

### `taskframe ui`

Launches the Tkinter operator console.

- `--runtime-data-dir runtime_data`

Exit codes:
- `0` on normal close
- non-zero if the UI cannot start

### `taskframe demo`

Runs one safe operator demo scenario.

The `cross-workflow-v2` subcommand runs the consolidated cross-workflow business story and writes a story pack under `runtime_data/demo_packs/<pack_run_id>/story_pack/`.

- `--scenario <scenario_id>`
- `--runtime-data-dir runtime_data`
- `--reset-dataset`
- `--report`
- `--local-llm`
- `--json`

Exit codes:
- `0` when the scenario completes successfully
- non-zero on scenario failure

### `taskframe readiness`

Builds the 90% readiness scorecard.

- `--runtime-data-dir runtime_data`
- `--strict`
- `--threshold 90`
- `--open-report`
- `--json`

Exit codes:
- `0` when the scorecard passes or when strict mode is off
- non-zero when strict mode fails

### `taskframe portfolio-pack`

Builds the public-facing portfolio evidence pack.

- `--runtime-data-dir runtime_data`
- `--no-story-pack`
- `--no-readiness`
- `--open`
- `--json`

Exit codes:
- `0` when the portfolio evidence pack is generated successfully
- non-zero when pack generation fails

### `taskframe golden-demo`

Runs the golden demo verification.

Exit codes:
- `0` when the golden demo passes
- non-zero when it fails

### `taskframe verify`

Runs release verification.

- `--full`
- `--quick` placeholder; the current implementation runs the full verification set

Exit codes:
- `0` when release verification is `READY` or `READY_WITH_KNOWN_LIMITATIONS`
- non-zero when release verification fails

### `taskframe safety-status`

Prints the current live execution safety summary.

- `--runtime-data-dir runtime_data`
- `--json`

Exit codes:
- `0` on success

### `taskframe pending-actions`

Lists pending actions for the active frame or for a specific frame id.

- `--frame-id <frame_id>`
- `--runtime-data-dir runtime_data`
- `--json`

Exit codes:
- `0` on success, including when no pending actions are present

### `taskframe live-preflight`

Shows why one pending action is blocked, dry-run-only, or ready for typed confirmation.

- `--frame-id <frame_id>`
- `--action-id <action_id>`
- `--runtime-data-dir runtime_data`
- `--manifest-dir manifests`
- `--json`

Exit codes:
- `0` when the action reaches live-ready confirmation mode
- non-zero when live execution is blocked

### `taskframe execute-approved`

Executes an approved pending action in dry-run mode by default.

- `--frame-id <frame_id>`
- `--action-id <action_id>`
- `--runtime-data-dir runtime_data`
- `--manifest-dir manifests`
- `--dry-run`
- `--live`
- `--i-understand-live-side-effects`
- `--confirm "<phrase>"`
- `--json`

Exit codes:
- `0` when the dry-run path succeeds
- `0` when the live path succeeds after all guardrails pass
- non-zero when live execution is blocked or the dry-run path fails

Live execution requires `TASKFRAME_ENABLE_LIVE_EXECUTION=1` and a typed confirmation phrase. `--live` alone is insufficient.

### `taskframe config show`

Prints the active config profile in sanitized form.

Exit codes:
- `0` on success
- non-zero on failure

### `taskframe config paths`

Prints the configuration lookup paths.

Exit codes:
- `0` on success
- non-zero on failure

### `taskframe config init --profile <name>`

Copies an example profile into the user config directory.

Exit codes:
- `0` when initialization succeeds
- non-zero if the file already exists or the example profile cannot be found

### `taskframe manifest-health`

Runs the active manifest catalog health check in report mode by default.

- `--manifest-dir manifests`
- `--runtime-data-dir runtime_data`
- `--no-smoke`
- `--smoke-limit <n>`
- `--strict`
- `--json`

Exit codes:
- report mode: `0` even when failures are found
- strict mode: `0` only when no failures are found

Manifest health modes:

- `taskframe manifest-health` writes the report and exits successfully for operator inspection.
- `taskframe manifest-health --strict --no-smoke` is the release-gate mode and exits non-zero on active catalog failures.
- `taskframe manifest-health --json --no-smoke` prints a compact JSON summary while still writing the report files.

### `taskframe readiness`

Builds the 90% readiness scorecard for the controlled demo/portfolio path.

- `--strict`
- `--threshold <number>`
- `--runtime-data-dir runtime_data`
- `--open-report`
- `--json`

The scorecard writes JSON, Markdown, and HTML reports under `runtime_data/readiness/`.

### `taskframe manifests validate-strict <manifest_path>`

Validates one manifest against the strict contract without running smoke execution.

- `--json`

Exit codes:
- `0` when the manifest passes strict validation
- non-zero when strict validation fails

### `taskframe manifests gallery`

Runs the manifest regression gallery for curated bad, edge-case, and unsafe fixtures.

- `taskframe manifests gallery list`
- `taskframe manifests gallery validate`
- `taskframe manifests gallery run --fixture completion_output_missing`
- `taskframe manifests gallery report`
- `list`
- `validate`
- `run --fixture <fixture_id>`
- `report`
- `--gallery-dir tests/fixtures/manifest_regression_gallery`
- `--runtime-data-dir runtime_data`
- `--no-smoke`
- `--no-autofix`
- `--no-repair-guidance`
- `--json`

Gallery reports are written to `runtime_data/manifest_regression_gallery/`.

### `taskframe version`

Prints the installed runtime version.

Exit codes:
- `0`

### `taskframe tools discover`

Discovers configured tool packs and reports whether they are enabled, valid, and registered.

- `--config-path config/enabled_toolpacks.json`
- `--json`

Exit codes:
- `0` on success

### `taskframe tools list`

Lists registered tools, including any external tool-pack tools that are currently enabled.

- `--config-path config/enabled_toolpacks.json`
- `--json`

Exit codes:
- `0` on success

### `taskframe tools inspect <tool_or_toolpack_id>`

Inspects one built-in tool or one external tool pack.

- `--config-path config/enabled_toolpacks.json`
- `--json`

Exit codes:
- `0` on success
- non-zero when the target cannot be found

### `taskframe tools validate <toolpack_path>`

Validates a tool pack descriptor.

- `--json`

Exit codes:
- `0` when validation passes
- non-zero when validation fails

### `taskframe tools health <toolpack_id>`

Runs the tool pack health check for one pack.

- `--config-path config/enabled_toolpacks.json`
- `--json`

Exit codes:
- `0` when the tool pack is healthy or intentionally disabled
- non-zero when health fails

### `taskframe tools lifecycle <toolpack_path>`

Evaluates the full operator lifecycle for one tool pack and produces a structured readiness report.

- `--env demo|dev|test|release|live`
- `--config-path config/enabled_toolpacks.json`
- `--runtime-data-dir runtime_data`
- `--no-contract` â€” skip contract tests
- `--no-health` â€” skip health checks
- `--no-manifest-smoke` â€” skip example manifest smoke validation
- `--write-report` â€” write JSON and Markdown lifecycle reports
- `--json`

Exit codes:
- `0` when the tool pack is ready or ready with warnings
- non-zero when the pack is invalid, blocked, disabled, or otherwise not ready

### `taskframe tools inventory`

Builds the merged tool inventory report.

- `--runtime-data-dir runtime_data`
- `--json`

Exit codes:
- `0` on success

### `taskframe tools compat-check`

Compares the migrated built-in tool packs with the legacy fallback registry.

- `--json`

Exit codes:
- `0` when compatibility passes
- non-zero when a migrated tool becomes less safe or a required migrated tool is missing

### `taskframe tools scaffold <toolpack_id>`

Generates a new tool pack scaffold.

- `--namespace <namespace>` — tool namespace (defaults to toolpack_id)
- `--tool <action>` — tool action name (defaults to `run`)
- `--safe-read` — generate a safe read-only tool (default)
- `--side-effect` — generate a side-effect tool that requires approval
- `--output-dir tool_packs` — output directory
- `--force` — overwrite existing scaffold
- `--json`

Exit codes:
- `0` when scaffold is created
- non-zero when the pack ID is invalid or the directory exists without `--force`

### `taskframe tools test <toolpack_path>`

Runs contract tests for a tool pack.

- `--runtime-data-dir runtime_data`
- `--no-manifest-smoke` — skip example manifest smoke runs
- `--json`

Exit codes:
- `0` when all contract checks pass
- non-zero when any check fails

Checks: descriptor valid, imports, tool smoke call, result shape, safety policy, health check, manifest smoke.

### `taskframe tools examples <toolpack_path>`

Prints example manifest step commands for each tool in a pack.

- `--json`

Exit codes:
- `0` on success

### `taskframe tools policy [toolpack_id]`

Shows the governance policy for a single tool pack, or all packs if no ID is given.

- `--json`

Exit codes:
- `0` on success

### `taskframe tools enable <toolpack_id>`

Records a governance decision to enable a tool pack in specified environments.

- `--classification <cls>` — required; one of: `core`, `optional`, `experimental`, `high_risk`, `blocked`
- `--env <envs>` — comma-separated environments (default: `dev,test`)
- `--by <name>` — who is enabling the pack (default: `operator`)
- `--reason <text>` — reason for enablement
- `--json`

Exit codes:
- `0` on success
- non-zero if classification or environments are invalid

### `taskframe tools disable <toolpack_id>`

Records a governance decision to disable a tool pack in specified or all environments.

- `--env <envs>` — comma-separated environments to disable (omit to disable in all)
- `--by <name>` — who is disabling the pack
- `--reason <text>` — reason for disabling
- `--json`

Exit codes:
- `0` on success

### `taskframe tools governance-report`

Generates a governance report listing all tool packs by classification and environment, and flags any policy violations.

- `--json`

Exit codes:
- `0` when no violations are found
- non-zero when policy violations exist

### `taskframe runtime profile`

Shows the resolved runtime environment and governance profile used by the tool runner.

- `--json`

### `taskframe runtime governance-check <tool_key>`

Evaluates runtime governance for a tool key such as `customer/read` or `gmail/search`.

- `--env <demo|dev|test|release|live>`
- `--dry-run`
- `--live-requested`
- `--operation <name>`
- `--json`

### `taskframe safety-pack`

Builds the safety verification pack and live-blocked evidence report.

- `--runtime-data-dir runtime_data`
- `--manifest-dir manifests`
- `--no-demo` — use static analysis only, skip demo scenario runs
- `--output-dir <dir>` — override output directory
- `--json`

Exit codes:
- `0` when all safety claims PASS
- non-zero when any claim fails

Output files:
- `runtime_data/safety_verification/safety_verification_pack.json`
- `runtime_data/safety_verification/safety_verification_pack.md`
- `runtime_data/safety_verification/live_blocked_evidence.json`
- `runtime_data/safety_verification/live_blocked_evidence.md`
- `docs/safety_verification_pack.md`
- `docs/live_blocked_evidence_report.md`

---

## Optional RPA commands

### `taskframe rpa status`

Shows optional RPA tool status without running any live probe or browser check.

Prints:

- whether optional RPA is enabled or disabled
- whether Playwright is installed
- the active profile
- whether a live probe has run

Exit codes:
- `0` always

### `taskframe rpa health`

Checks optional RPA tool health. Default behaviour is to report RPA as disabled with no live probe.

- `--enable-rpa` — enable dependency and config checks (Playwright, package, profile)
- `--live-probe` — run a live browser probe (requires `--enable-rpa`)

Exit codes:
- `0` in default (disabled) mode
- `0` with `--enable-rpa` when all dependencies are present
- `1` with `--enable-rpa` when dependencies are missing
- `1` when `--live-probe` is supplied without `--enable-rpa`

Usage:

```bash
taskframe rpa health                               # Disabled (default)
taskframe rpa health --enable-rpa                  # Dependency checks only
taskframe rpa health --enable-rpa --live-probe     # Full live probe (local setup required)
taskframe rpa health --live-probe                  # ERROR: requires --enable-rpa
```

### `taskframe rpa docs`

Prints the path to `docs/optional_rpa.md` and a short summary.

Exit codes:
- `0`


## Google Workspace tool pack

- `taskframe tools discover`
- `taskframe tools list`
- `taskframe tools inspect gmail/list_unread`
- `taskframe tools inspect toolpack:google_workspace`
- `taskframe tools validate tool_packs/google_workspace/toolpack.json`
- `taskframe tools health google_workspace`
- `taskframe tools lifecycle tool_packs/demo_echo/toolpack.json --env dev`

The tool pack is optional and read-only. Default demo paths do not require Google credentials.


### docs/codebase_containment_review.md

# Codebase Containment Review

Scope: `src/`, `runtime/`, `tools/`, `bits/`, `optional_tools/`

Method:
- Reviewed module names, import edges, and runtime/UI/report call paths.
- Ran `ruff` on the scoped folders for `F401` and `F811`.
- Applied only import cleanup and package-export cleanup. No runtime behavior changes were intended.

## Inventory Summary

| Folder | Code files | Notes |
|---|---:|---|
| `runtime/` | 144 | Core engine, persistence, validation, tool registry, report builder, and domain tools |
| `src/` | 34 | Tkinter UI, presenters, scenario/demo orchestration, report launchers |
| `tools/` | 29 | CLI utilities, verification, release docs, and external integration helpers |
| `bits/` | 77 | FastAPI/RAG prototype, app services, and RAG utilities |
| `optional_tools/` | 9 | Optional RPA integration surface for Google Messages ABSA |

## Major Module Purposes

### `src/`

- `src/operator_ui.py`
  - Tkinter shell and all view rendering.
  - Owns widget wiring and callback dispatch.
  - Should remain presentation-only.
- `src/operator_presenter.py`
  - Builds the technical demo view model for Operator mode.
  - Converts snapshot/taskframe state into compact UI-facing text.
- `src/demo_story_presenter.py`
  - Builds the business-readable Demo story model.
  - Owns demo-specific story selection, scenario compatibility, and step labels.
- `src/operator_data.py`
  - Normalizes snapshots, manifests, selected-step details, and footer text.
- `src/operator_playback.py`
  - Builds the playback timeline and per-step selected detail payloads.
- `src/operator_demo_runner.py`
  - Runs demo manifests and demo packs.
  - Bridges selected demo configs to runtime execution.
- `src/operator_scenario_runner.py`
  - Runs named scenarios, post-actions, and scenario validation.
- `src/operator_reports.py`
  - Thin UI helper for operator run reports and report-folder access.
- `src/operator_approval_actions.py`
  - Approve/reject/execute actions for staged pending side effects.
- `src/operator_approval_pack.py`
  - Builds the approval pack view used by the UI and reports.
- `src/operator_artifacts.py`
  - Tracks artifact paths and openable artifact state.
- `src/operator_actions.py`
  - Event helpers for UI-driven demo intake.
- `src/operator_customer_inbox_runner.py`
  - Customer inbox processing and demo message intake helpers.
- `src/operator_cross_workflow_demo.py`
  - Cross-workflow demo packs and run summaries.

### `runtime/`

- `runtime/orchestrator.py`
  - Core manifest execution engine.
  - Creates TaskFrames, runs steps, verifies completion, and executes tools.
- `runtime/tool_runner.py`
  - Tool invocation, dry-run/live handling, pending-action staging, and result normalization.
- `runtime/tool_registry.py`
  - Authoritative registry of tools and their metadata.
- `runtime/tool_capability_registry.py`
  - Capability metadata and setup requirements for tools.
- `runtime/tool_health.py`
  - Health probes and setup/availability checks.
- `runtime/tool_setup.py`
  - Setup guidance and safe setup actions.
- `runtime/manifest_loader.py`
  - Manifest parsing, validation, and catalog loading.
- `runtime/manifest_catalog.py`
  - Event-route mapping and manifest lookup helpers.
- `runtime/event_router.py`
  - Routes events to manifests and input mappings.
- `runtime/event_store.py`
  - Event persistence, deduplication, and ingestion.
- `runtime/taskframe.py`
  - TaskFrame model, state transitions, audit events, and output helpers.
- `runtime/persistence.py`
  - Filesystem persistence paths and JSON read/write helpers.
- `runtime/taskframe_reload.py`
  - Reloads persisted TaskFrames back into runtime objects.
- `runtime/run_report.py`
  - Run report builder and HTML/Markdown renderers for operator and demo reports.
- `runtime/evidence_bundle.py`
  - Evidence bundle generation from persisted run artifacts.
- `runtime/failure_summary.py`
  - Failure summary extraction and presentation data.
- `runtime/run_ledger.py`
  - Run ledger records and summary snapshots.
- `runtime/artifact_index.py`
  - Indexes persisted run artifacts.
- `runtime/artifact_cleanup.py`
  - Safe cleanup policy and cleanup candidate evaluation.
- `runtime/validation.py`
  - Validation rules and manifest validation execution.
- `runtime/conditions.py`
  - Conditional rule evaluation helpers.
- `runtime/completion_gate.py`
  - Completion evaluation and final state transitions.
- `runtime/approval_commands.py`
  - Approval command execution for pending actions.
- `runtime/approval.py`
  - Approval event helpers.
- `runtime/live_execution.py`
  - Live execution guardrails and execution control.
- `runtime/live_guardrails.py`
  - Live-side-effect safety checks.
- `runtime/scenario_validation.py`
  - Scenario result validation and expectations.
- `runtime/retention_policy.py`
  - Retention and cleanup policy rules.
- `runtime/retry_policy.py`
  - Retry classification and backoff policy.
- `runtime/inspection.py`
  - Read-only inspection helpers for persisted runs.
- `runtime/inspection_commands.py`
  - CLI-style wrappers over inspection actions.
- `runtime/memory_store.py`, `runtime/memory_commands.py`
  - In-memory demo/LLM state persistence and command wrappers.
- `runtime/business_data.py`, `runtime/business_store.py`, `runtime/business_context.py`, `runtime/company_store.py`
  - Seed data, business record access, and context assembly.
- `runtime/customer_tools.py`, `runtime/domain_customer_tools.py`, `runtime/order_tools.py`, `runtime/shipment_tools.py`, `runtime/payment_tools.py`, `runtime/procurement_tools.py`, `runtime/reconciliation_tools.py`, `runtime/accounting_tools.py`
  - Domain tool implementations used by the tool registry.
- `runtime/message_tools.py`, `runtime/messages_tools.py`
  - Message validation / read tooling. This is a duplicate-looking surface and should be watched for drift.
- `runtime/llm_tools.py`, `runtime/llm_micro_tools.py`, `runtime/llm_prompts.py`, `runtime/llm_adapter.py`, `runtime/llm_commands.py`, `runtime/llm_config.py`
  - LLM adapter, prompts, micro-tools, and command integration.
- `runtime/test_tools.py`
  - Test tool surface registered in the tool registry.

### `tools/`

- `tools/run_release_candidate_verification.py`
  - Release verification orchestrator and compliance checks.
- `tools/write_current_release_status.py`
  - Generates current release status and evidence-pack docs.
- `tools/workspace_tools.py`
  - Workspace-facing helper CLI surface.
- `tools/google_auth.py`
  - Shared Google auth helpers.
- `tools/gobook_tools.py`
  - GoBook RPA helper surface.
- `tools/whatsapp_*`
  - WhatsApp browser/RPA helpers and message search/send wrappers.
- `tools/*calendar*`, `tools/*sheet*`, `tools/*gmail*`
  - Google Workspace integration helpers.
- `tools/capture_portfolio_screenshots.py`
  - Screenshot capture utility for portfolio evidence.

### `bits/`

- `bits/main.py`
  - Separate FastAPI/RAG prototype application.
  - Not part of the current Tkinter demo/report runtime path.
- `bits/app/services/*`
  - Prompting, ingestion, confidence, response formatting, grounding, and RAG services.
- `bits/rag/*`
  - RAG ingestion/search/OCR/layout utilities and manual experiments.
- `bits/models.py`
  - Pydantic request/response models for the FastAPI prototype.
- `bits/ollama_client.py`
  - Ollama client wrapper for the prototype app.

### `optional_tools/`

- `optional_tools/rpa/google_messages_absa/messages_tools.py`
  - Optional browser-backed Google Messages ABSA integration.
- `optional_tools/rpa/google_messages_absa/health.py`
  - Optional health checks for the ABSA integration.
- `optional_tools/rpa/google_messages_absa/registry.py`
  - Registration metadata for the optional integration.
- `optional_tools/rpa/google_messages_absa/tests/*`
  - Optional integration tests for the ABSA surface.

## Boundary Check

### Runtime boundary

- `runtime/` does not import `tkinter`, `ttk`, or UI widgets.
- Runtime owns execution, persistence, validation, reporting, tool registry, and evidence generation.
- Demo-specific presentation text lives in `src/demo_story_presenter.py`, not in runtime orchestration.
- `runtime/run_report.py` is a report builder only. It renders HTML/Markdown from persisted frame data; it does not drive the UI.

### UI/report boundary

- `src/operator_ui.py` imports `src.demo_story_presenter.build_demo_story` and `runtime.run_report.generate_demo_run_report`.
- The Tkinter file renders widgets and routes button actions.
- Business meaning is derived in presenters/report builders, not inside the widget tree.
- `src/demo_story_presenter.py` is the single place for demo story wording and scenario compatibility checks.
- `runtime/run_report.py` is the single place for run-report model construction and HTML/Markdown rendering.

### Orchestration boundary

- `runtime/orchestrator.py` executes manifests and tool steps.
- It uses manifest metadata and TaskFrame state, not demo-only presentation concepts.
- Scenario selection and user-facing labels are handled above runtime in `src/`.
- Business workflow details remain in manifests and tool registry entries.

## Suspected Dead or Legacy Surfaces

These are not proven dead, but they look legacy, utility-only, or duplication-prone:

- `runtime/message_tools.py`
  - Singular message tool surface that overlaps with `runtime/messages_tools.py`.
  - Keep an eye on this pair for drift or aliasing cleanup.
- `bits/main.py`
  - Separate FastAPI/RAG prototype, not part of the current demo/report flow.
- `bits/rag/manual_test_rag.py`
  - Manual harness only.
- `runtime/test_tools.py`
  - Registry-backed test surface rather than production workflow code.
- `optional_tools/rpa/google_messages_absa/tests/*`
  - Optional integration tests, not core runtime behavior.

## Duplicate Responsibility Areas

- `src/operator_demo_runner.py` and `src/operator_scenario_runner.py`
  - Both turn a selected scenario into a run, but for different entry points.
- `src/operator_presenter.py` and `src/demo_story_presenter.py`
  - Both build view models from runtime state, but one is technical and one is business-readable.
- `runtime/run_report.py` and `src/operator_reports.py`
  - Report generation vs. UI entrypoint for opening reports.
- `runtime/manifest_loader.py` and `runtime/manifest_catalog.py`
  - Closely related manifest loading and routing responsibilities.
- `runtime/message_tools.py` and `runtime/messages_tools.py`
  - Similar naming and adjacent responsibilities; highest drift risk in this review.
- `runtime/tool_registry.py` and `runtime/tool_capability_registry.py`
  - Tool registration and capability metadata should stay aligned.

## Safe Cleanup Performed

- Removed unused imports across the scoped folders.
- Fixed one duplicate import redefinition in `bits/main.py`.
- Kept `runtime/__init__.py` as an explicit re-export surface with `__all__` so the package API stays stable.
- No dead functions were removed because this review did not prove any were unused by tests.

## Verification

Completed successfully after the cleanup:

- `python -m ruff check src runtime tools bits optional_tools --select F401,F811`
- `python -m pytest`
- `python scripts/run_golden_demo.py`
- `python scripts/run_release_verification.py`

## Notes

- The repository has a large surface area, but the runtime/demo/report/UI split is now reasonably contained.
- The highest-risk coupling area remains the message-tool naming overlap and the dual presenter/report path.
- Further simplification should focus on consolidation, not more presentation logic inside `runtime/`.


### docs/common_manifest_authoring_failures.md

# Common Manifest Authoring Failures

## 1. Purpose of the Broken Manifest Gallery

The broken manifest gallery is a permanent regression asset located at `tests/fixtures/broken_manifests/`. It exists to:

- Document common authoring mistakes with concrete, minimal examples.
- Protect the manifest authoring subsystem (Specs 081–084) from silent regressions.
- Give operators a reference for what bad manifests look like and why they fail.
- Verify that auto-fix preview (Spec 084) correctly proposes fixes for fixable issues and correctly refuses to patch unfixable ones.

The gallery is a **test asset**, not a runtime manifest catalog. The broken fixtures are never loaded by the orchestrator or exposed through the workbench selector.

---

## 2. How to Read a Manifest Failure

Every manifest failure produces one or more **findings** through the Repair Guidance system. Each finding has:

| Field | Meaning |
|---|---|
| `id` | Machine-readable finding identifier (e.g. `completion_output_missing`) |
| `severity` | `critical`, `error`, or `warning` |
| `location` | Where in the manifest the problem was found |
| `message` | Plain-English description of the problem |
| `suggested_fix` | How to fix it |
| `example` | Example of the corrected value |

To read a finding programmatically:
```python
from src.manifest_authoring_feedback import explain_manifest_failure

guidance = explain_manifest_failure(manifest=my_manifest)
for finding in guidance["findings"]:
    print(f"[{finding['severity']}] {finding['id']}: {finding['message']}")
    print(f"  Fix: {finding['suggested_fix']}")
```

Auto-Fix Preview then takes the findings and proposes deterministic patches where possible.

---

## 3. Common Failure Types

### 3.1 Completion output missing

**Finding ID:** `completion_output_missing`  
**Severity:** error

The `completion.success_outputs` list contains an alias that no step command produces.

```json
"steps": [
  {"id": "read_data", "command": "[t:g/check -> result] max_results=5"}
],
"completion": {
  "success_outputs": ["reply"]
}
```

`result` is produced but `reply` is expected. The completion can never be satisfied.

**Fix:** Change `reply` to `result` in `completion.success_outputs`.

---

### 3.2 Validation output missing

**Finding ID:** `validation_references_missing_output`  
**Severity:** error

A validation rule (type `output_exists`) references an output alias that no step produces.

```json
"validations": [
  {"id": "reply_exists", "type": "output_exists", "output": "reply"}
]
```

**Fix:** Change the `output` field to match the actual alias produced by the step.

---

### 3.3 Unknown tool

**Finding ID:** `unknown_tool` (from smoke result)  
**Severity:** error

A step command references a tool namespace/action that is not registered in the tool registry. This cannot be detected by static analysis — it only appears after a smoke run.

```json
{"id": "read_data", "command": "[t:x/unknown_tool -> result] max_results=5"}
```

**Fix:** Replace the unregistered tool with a registered one. Check the manifest tool reference for available namespaces.

---

### 3.4 Invalid command

**Finding ID:** `command_parse_error`  
**Severity:** error

A step command does not use the correct `[t:namespace/action -> alias]` or `[q:action -> alias]` format.

```json
{"id": "read_data", "command": "g/check result max_results=5"}
```

**Fix:** Rewrite the command using the correct bracket format.

---

### 3.5 Input used but not declared

**Finding ID:** `input_used_but_not_declared`  
**Severity:** error

A step command references `$inputs.X` but `X` is not listed in the manifest's `inputs` array.

```json
"inputs": [],
"steps": [
  {"id": "read_data", "command": "[t:g/check -> result] query=$inputs.message"}
]
```

**Fix:** Add `"message"` to the `inputs` list.

---

### 3.6 Input declared but not used

**Finding ID:** `input_declared_but_not_used`  
**Severity:** warning

An input is listed in `inputs` but never referenced in any step command.

```json
"inputs": ["message"],
"steps": [
  {"id": "read_data", "command": "[t:g/check -> result] max_results=5"}
]
```

**Fix:** Either remove the unused input or reference it in a step command.

---

### 3.7 Duplicate step ID

**Finding ID:** `duplicate_step_id`  
**Severity:** error

Two or more steps share the same `id`.

```json
"steps": [
  {"id": "read_data", "command": "[t:g/check -> result] max_results=5"},
  {"id": "read_data", "command": "[validate:result_exists]"}
]
```

**Fix:** Rename the duplicate step to a unique ID (e.g. `read_data_2`). If other parts of the manifest reference the duplicate step ID (in `when` conditions, validations, or completion), those references must also be updated manually.

---

### 3.8 Live execution enabled

**Finding ID:** `live_execution_enabled`  
**Severity:** critical

`live_execution.enabled` is set to `true` in an authored or smoke-tested manifest.

```json
"live_execution": {"enabled": true}
```

Live execution bypasses the pending-action approval model. It is blocked by the smoke runner and must not be used in authored manifests.

**Fix:** Set `live_execution.enabled` to `false`. Use `allow_pending_approval: true` and the `approval_side_effect` template for side effects that require explicit approval.

---

### 3.9 Missing output alias

**Finding ID:** `step_missing_output_alias`  
**Severity:** warning

A tool or LLM command (`[t:...]` or `[q:...]`) does not include the `-> alias` output capture segment.

```json
{"id": "read_data", "command": "[t:g/check] max_results=5"}
```

No output alias means the step result is not captured, completion cannot be satisfied, and validation cannot check the output.

**Fix:** Add `-> alias_name` to the command, e.g. `[t:g/check -> result] max_results=5`.

---

### 3.10 Side effect without pending expectation

**Finding ID:** `side_effect_command_without_pending_expectation`  
**Severity:** warning

A step command that appears to stage a side effect (e.g. `[t:wa/send ...]`) is present, but the manifest completion block does not declare `allow_pending_approval: true` or `success_pending_actions`.

**Fix:** Use the `approval_side_effect` template. Add `allow_pending_approval: true`, `success_pending_actions`, and a `pending_action_exists` validation.

---

### 3.11 Malformed JSON

**Finding ID:** `json_parse_error`  
**Severity:** error

The manifest file cannot be parsed as JSON.

**Fix:** Fix the JSON syntax (missing closing brackets, trailing commas, unquoted keys, etc.).

---

## 4. Which Failures Can Be Auto-Fixed

| Failure | Finding ID | Auto-fix? | Condition |
|---|---|---|---|
| Completion output wrong | `completion_output_missing` | Yes | Exactly one step alias exists |
| Validation output wrong | `validation_references_missing_output` | Yes | Exactly one step alias exists |
| Empty completion, no acceptable_empty | `completion_empty_without_acceptable_empty` | Yes | Step aliases exist |
| Input declared but not used | `input_declared_but_not_used` | Yes | Input is a simple string (not object) |
| Input used but not declared | `input_used_but_not_declared` | Yes | Always |
| Live execution enabled | `live_execution_enabled` | Yes | live_execution is a valid dict |
| Duplicate step ID | `duplicate_step_id` | Yes | No external references to the duplicate ID |

---

## 5. Which Failures Must Be Fixed Manually

| Failure | Finding ID | Reason |
|---|---|---|
| Unknown tool | `unknown_tool` | System must not choose a replacement tool |
| Invalid command | `command_parse_error` / `command_invalid` | Intent is ambiguous; system cannot rewrite syntax |
| Missing output alias | `step_missing_output_alias` | System cannot infer the intended alias name |
| Side-effect without pending design | `side_effect_command_without_pending_expectation` | Approval workflow design must be explicit |
| Duplicate step with external refs | `duplicate_step_id` (refs present) | Renaming would break `when` / validation references |
| Malformed JSON | `json_parse_error` | JSON must be fixed before any further analysis |
| Missing required field | `missing_required_top_level_field` | Choice of value requires operator judgement |
| Missing command | `step_missing_command` | System cannot invent a command |
| Invalid manifest ID | `invalid_manifest_id` | Only the operator can name a manifest |
| Runtime load failure | `manifest_load_failed` | Root cause requires analysis |

---

## 6. Why Tool and Command Fixes Are Not Automatic

The manifest system is designed so that **the operator declares which tool to use**. The manifest is the task instruction contract; the orchestrator executes what the manifest says, not what it infers.

Allowing auto-fix to choose a replacement tool would:
- Silently change the behaviour of the task.
- Bypass the operator's explicit tool selection intent.
- Risk using a tool that stages unintended side effects.

Similarly, command syntax carries intent (tool choice, parameters, output alias). The system cannot safely rewrite a broken command without knowing what the operator intended.

These constraints are permanent design rules, not temporary limitations.

---

## 7. Recommended Repair Workflow

For any broken manifest, follow this sequence:

1. **Open in Manifest Workbench** and load the manifest.
2. Click **Validate** to see structural errors.
3. Click **Repair Guidance** to see all static analysis findings with suggested fixes.
4. Click **Auto-Fix Preview** to see which findings have deterministic low-risk proposals.
5. For supported findings:
   - Review the Before/After preview and unified diff.
   - Click **Apply Selected Fix to Editor** to patch the editor buffer.
   - Repeat for remaining fixable findings.
6. For unsupported findings:
   - Read the finding's `suggested_fix` and `example`.
   - Edit the manifest directly in the JSON editor.
7. After all fixes, click **Validate** again to confirm no errors remain.
8. Click **Repair Guidance** to confirm findings are cleared.
9. **Save** the manifest.
10. Click **Smoke test manifest** to confirm end-to-end behaviour.

---

## Gallery Files

The gallery lives at `tests/fixtures/broken_manifests/`. The `gallery_index.json` describes every fixture with expected findings and auto-fix expectations.

| Fixture | Broken Condition |
|---|---|
| `completion_output_missing.manifest.json` | Completion expects wrong alias |
| `validation_output_missing.manifest.json` | Validation checks wrong alias |
| `unknown_tool.manifest.json` | Unregistered tool namespace |
| `invalid_command.manifest.json` | Missing bracket format |
| `input_used_but_not_declared.manifest.json` | $inputs reference without declaration |
| `input_declared_but_not_used.manifest.json` | Declared input never used |
| `duplicate_step_id.manifest.json` | Two steps share same ID |
| `unsafe_live_execution.manifest.json` | live_execution.enabled: true |
| `missing_output_alias.manifest.json` | Tool command without -> alias |
| `side_effect_without_pending_expectation.manifest.json` | Side effect without approval design |
| `malformed_json.manifest.json.txt` | Truncated invalid JSON |


### docs/configuration.md

# Configuration and Secrets

## Overview

TaskFrame uses a safe default configuration for the demo path. You can run the project without Google credentials, browser profiles, Ollama, or live integrations.

Configuration is profile-based. Profiles change where settings are read from; they do not automatically enable live side effects.

## Safe default configuration

The default profile uses:

- fake/deterministic LLM mode
- Google integrations disabled
- RPA disabled
- live execution disabled
- local runtime data paths

This is the right choice for first-time setup and public demos.

## Config profiles

Available profiles:

- `default` — safe local dry-run path
- `dev` — local development profile
- `local-llm` — use local Ollama if available
- `google-live` — enable Google config lookup only
- `rpa-local` — enable local browser/RPA config lookup only

Profiles do not override approval policy or live-execution rules.

## Where config files live

Lookup order:

1. explicit CLI argument
2. `TASKFRAME_CONFIG_DIR`
3. user config directory: `~/.taskframe/`
4. repo examples under `config/examples/`

Runtime data defaults to `runtime_data/` unless `TASKFRAME_RUNTIME_DIR` or a CLI override is supplied.

## Environment variables

Supported variables:

- `TASKFRAME_CONFIG_DIR`
- `TASKFRAME_PROFILE`
- `TASKFRAME_RUNTIME_DIR`
- `TASKFRAME_LLM_PROVIDER`
- `TASKFRAME_OLLAMA_MODEL`
- `TASKFRAME_OLLAMA_BASE_URL`
- `TASKFRAME_ACCOUNTING_SHEET_CONFIG`
- `ENABLE_OPTIONAL_RPA_TOOLS`

CLI arguments win over environment variables.

## Google integration config

Google credentials should live under user-local config, for example:

- `~/.taskframe/google/credentials.json`
- `~/.taskframe/google/google_token.json`

The repository root is not the preferred place for credentials. If legacy files still exist locally, treat them as transitional and keep them out of Git.

## Accounting sheet config

The accounting sheet config should live at:

- `~/.taskframe/accounting_google_sheet.json`

A repository example file is provided at:

- `config/examples/accounting_google_sheet.example.json`

## Optional RPA config

RPA/browser profiles are optional and high-risk. Keep them local and user-specific. Do not commit browser session state or profile directories.

### RPA local profile

The `rpa-local` profile enables optional RPA config lookup. It does not automatically launch browser tools or run live probes.

To use it:

```bash
TASKFRAME_PROFILE=rpa-local taskframe rpa health --enable-rpa
```

Or set it in `~/.taskframe/taskframe.rpa-local.json`.

An example profile is available at `config/examples/taskframe.rpa-local.example.json`.

RPA config must stay in user-local config only:

- browser profile paths
- session directories
- authentication state

**Never commit RPA config, browser session files, or profile directories to the repository.**

## Local Ollama config

For a local LLM profile, use:

- `TASKFRAME_LLM_PROVIDER=ollama`
- `TASKFRAME_OLLAMA_MODEL=<your-model>`
- `TASKFRAME_OLLAMA_BASE_URL=http://127.0.0.1:11434`

The default profile still uses fake/deterministic mode.

## What not to commit

Do not commit:

- credentials
- tokens
- browser profiles
- local config files
- runtime outputs

The repository `.gitignore` excludes the common secret and local-config patterns.

## Troubleshooting

- If `taskframe config show` reports the wrong profile, check `TASKFRAME_PROFILE`.
- If Google checks are failing, confirm the credential files exist under `~/.taskframe/google/`.
- If Ollama is unavailable, switch back to the default fake provider.
- If a local config file is not being read, check `TASKFRAME_CONFIG_DIR`.

Use `taskframe config paths` to inspect the lookup order and active config file path.


### docs/controlled_live_profile.md

# Controlled Live Read Profile

## Purpose
The `controlled_live_read` profile enables governed, read-only access to external services (Gmail, Calendar, Sheets) for demonstration and testing purposes. It does not enable production live automation, live writes, or live side effects.

## What Is Allowed
- Gmail search and read
- Calendar search and read
- Sheets read and get_values
- Google Workspace read-only tool pack

## What Is Blocked
- Gmail send and draft send
- Calendar create, update, delete
- Sheets write, write_rows, update
- RPA browser automation (all rpa/* tools)
- Any tool with side_effect=True

## Governance Requirements
- `require_tool_governance: true` — tool governance must pass before any live read is attempted
- Only tools in the `google_workspace_readonly` tool pack are permitted
- Tool pack must be enabled and pass health check

## Credential Requirements
- Google OAuth credentials must be configured at `~/.taskframe/google/credentials.json`
- Google token must exist at `~/.taskframe/google/google_token.json`
- No credentials are required to run the profile status check

## How to Run Preflight

```bash
taskframe profile controlled-live-status
taskframe profile controlled-live-status --check-tools
taskframe profile controlled-live-status --json
```

From the operator UI: use the "Controlled Live Read Status" button in the Live Safety Panel.

## Safety Guarantees
- `allow_live_side_effects: false` — side effects are unconditionally blocked
- All write/send/delete tool calls return `LIVE_SIDE_EFFECT_BLOCKED`
- RPA tools are blocked regardless of credentials or configuration
- Tool governance is enforced before any live read is attempted

## Known Limitations
- This profile allows governed live reads only. It does not allow production live automation or live side effects.
- Real Google credentials are required to use live read tools.
- The profile does not schedule or automate live reads in the background.


### docs/core_concepts.md

# Core Concepts

## TaskFrame
The TaskFrame is the runtime case file for a single run. It stores inputs, outputs, evidence, validations, tool calls, LLM calls, pending actions, and audit events. It is the source of truth for what happened during execution.

## Manifest
A manifest defines the workflow instructions, allowed steps, validation rules, and completion conditions. It is both the instruction contract and the acceptance contract for a run. The orchestrator executes the manifest; it does not invent new business logic.

## ToolResult
A ToolResult is the structured output returned by a tool adapter. It records what the tool did, what it observed, and any error or status details. ToolResults are designed to be deterministic and easy to audit.

## Pending Action
A pending action is a side effect that has been prepared but not executed. It keeps the operation visible, inspectable, and approval-gated. Pending actions help prevent accidental live writes or sends.

## Approval Gate
The approval gate is the operator control point for side effects. Nothing sensitive should execute until the action is reviewed and approved. This keeps the runtime safe even when a workflow has prepared a live operation.

## Validation Gate
The validation gate decides whether a run is complete. It checks outputs and evidence against the manifest contract and runtime facts. The LLM cannot self-certify completion.

## Bounded LLM Step
A bounded LLM step uses the model for a narrow task such as extraction, drafting, summarisation, or classification. The model does not choose the workflow or bypass validations. Its output is always constrained by the runtime.

## Tool Capability
Tool capability is the metadata that says what a tool is for, whether it is core or optional, what setup it needs, and whether it has side-effect risk. This makes the tool layer visible and explainable in the operator UI.

## Health Check
A health check is a safe read-only probe that verifies whether a tool is usable. Health checks should not send, write, delete, or otherwise mutate external systems. They are used to show readiness without introducing risk.

## Live RPA Probe
A live RPA probe is an operator-triggered browser-backed check for optional RPA tools. It opens the target environment read-only and verifies that the session and surface are usable. It is excluded from clean-clone release verification because it depends on local browser state and authentication.

## Golden Demo
The golden demo is the deterministic portfolio run that exercises the core business workflows. It produces reports, audit artifacts, and release-candidate outputs using only the default demo path. It is the main proof that the runtime works in a clean clone.

## Release Verification
Release verification is the clean-clone check that confirms the repo still runs as intended. It validates the default tool registry, scenario pack, golden demo, release artifacts, and documentation alignment. Known limitations are recorded, but default functionality must still pass.


### docs/current_release_status.md

# Current Release Status

## Verdict

- READY_WITH_KNOWN_LIMITATIONS

## Verification Date

- 2026-05-04T00:00:00Z

## Commands Run

- pytest
- python scripts/run_golden_demo.py
- python scripts/run_release_verification.py

## Test Summary

- Pytest: see release verifier output
- Commands Run: 1
- Passed Commands: 1
- Failed Commands: 0
- Skipped Checks: 0

## Golden Demo Summary

- Customer: PASS
- Procurement: PASS
- Accounting: PASS
- Approval gate: PASS
- Report artifacts: PASS

## Release Verifier Checks

- imports: UNKNOWN
- default_tool_registry: UNKNOWN
- optional_rpa_excluded: UNKNOWN
- default_scenario_pack: UNKNOWN
- golden_demo: UNKNOWN
- release_artifacts: UNKNOWN
- docs_commands: UNKNOWN
- adding_new_tools_doc: UNKNOWN
- tool_contract_checklist_doc: UNKNOWN

## Known Limitations

- example

## Evidence Files

- runtime_data/runs/frame_1/reports/run_report.md
- runtime_data\audit\release_candidate_verification.json
- runtime_data\audit\release_status_latest.json
- runtime_data\audit\release_evidence_pack.json
- docs\release_candidate_verification.md
- docs\release_candidate_evidence_index.md
- docs\current_release_status.md
- docs\release_evidence_pack.md
- docs\known_limitations.md
- docs\adding_new_tools.md
- docs\tool_contract_checklist.md


### docs/default_demo_boundary.md

# Default Demo Boundary

This document freezes what belongs in the default clean-clone RC path and what does not.

## Included in Default RC

- Customer workflow
- Procurement workflow
- Accounting workflow
- Approval gate
- Dry-run execution
- Report generation
- Audit evidence
- Runtime contract inspection

## Excluded From Default RC

- Optional RPA tools
- External tool packs not explicitly enabled for the default path
- Live WhatsApp or Gmail sending
- Live browser automation
- Live execution from the default demo path
- Unbounded LLM tool choice
- Production credentials
- Real customer or supplier data

## Rule

Optional tools may exist in the repo, but they must not be imported or required by the default RC verification path.
The default release candidate remains manifest-driven, TaskFrame-centered, approval-gated, and validation-based.

External tool packs are configuration-driven. Adding a pack does not automatically add it to the default demo or release-candidate path.

Migrated core tool packs are part of the core runtime path and remain compatible with existing manifests.

Adding a tool does not automatically add it to the default RC path.

A new tool is excluded from the default RC path unless:

- it is needed by the golden demo
- it has safe health checks
- it has deterministic tests
- it does not require live credentials for default verification
- it does not enable live side effects by default
- it keeps live execution behind explicit safety guardrails and confirmation


## Google Workspace boundary

The default demo path does not depend on Google Workspace credentials or live Google APIs.

The Google Workspace tool pack may be discoverable and inspectable, but it is not part of the default demo flow.


### docs/demo_script.md

# Demo Script

## Opening

This is TaskFrame Runtime, a manifest-driven autonomous business worker runtime for controlled AI-assisted company operations.

It is not a chatbot controlling tools freely. The workflow is selected through a manifest. Each step writes to a TaskFrame, validations decide whether the worker may continue, and side effects are staged for approval instead of being sent automatically.

## Architecture Explanation

- The manifest defines the allowed workflow path.
- The TaskFrame is the runtime case file and audit source of truth.
- Tools are deterministic adapters, not open-ended agents.
- The LLM handles bounded subtasks such as extraction and drafting.
- Approvals gate side effects before anything can execute.
- Validation determines completion, not model confidence.

## Happy-Path Customer Demo

I will start with the customer status workflow.

I select `Customer Status - Happy Path`, run the demo, and show the Demo View.

The important points are:

- the customer request is visible in plain English
- the worker checklist explains what was checked
- the prepared reply is visible
- the approval decision is explicit
- the run report can be opened from the same screen

The message is drafted, but it is not sent automatically. The runtime waits at the approval gate.

## Failed-Validation Demo

Next I switch to `Customer Status - Missing Customer`.

This shows the safety behavior:

- the worker stops safely
- no customer message is prepared
- no live send occurs
- the report explains why the workflow stopped

That is the control boundary: the runtime does not invent success when validation fails.

## Report / Evidence Demo

Then I move to `Report Generation - Happy Path`.

This demonstrates the reporting layer:

- the business report path is visible
- the run report path is visible
- the report artifact can be opened directly
- the run report shows step outcomes, validations, evidence, and pending actions

This is the clearest example of the product boundary: the runtime produces a business artifact and a run-bound audit artifact for the exact frame.

## Safety Model

- The runtime executes only manifest-defined work.
- The LLM is bounded to helper tasks.
- Side effects are never free-run.
- Validation decides whether a run can continue.
- Reports are derived from persisted run data.

## Closing Pitch

The point of the demo is not that the model can improvise. The point is that the runtime can route work, constrain tools, preserve evidence, and stop before side effects without approval.


### docs/demo_script_cross_workflow_v1.md

# Cross-Workflow Business Automation Demo v1

1. Open the operator console.
2. Select `Cross-Workflow Business Automation Demo v1`.
3. Run the pack.
4. Confirm the three workflows complete in order:
   - Customer support
   - Procurement low-stock reorder
   - Accounting payment reconciliation
5. Review the individual reports and evidence bundles.
6. Review the aggregate cross-workflow report.

Expected proof:
- Same runtime
- Same orchestrator
- Three business domains
- Real LLM in demo mode
- Approval-gated side effects
- Dry-run execution only
- Individual and aggregate reports
- No orchestrator business branches


### docs/demo_story.md

# Cross-Workflow Business Automation Demo v2

## What the Demo Shows

This demo presents one controlled business incident flowing across customer support, procurement, and accounting through the same TaskFrame runtime.

## Business Story

The story is an order fulfilment exception. A customer asks about an order, the runtime prepares a response, the operational context moves into procurement and stock handling, and accounting validates the financial side. The story uses seeded data and deterministic workflow steps.

## Runtime Controls

- Manifest-driven execution
- Bounded LLM assistance
- Deterministic validation
- Approval-gated side effects
- Dry-run execution only
- TaskFrame traceability

## What the LLM Does

The LLM is limited to bounded drafting and narrative assistance. It may help with human-readable summaries, but it does not decide workflow outcomes.

## What the LLM Does Not Do

The LLM does not authorize actions, mutate data, perform live writes, or override validation.

## Approval and Dry-Run Safety

All side effects remain approval-gated. Any executed actions in the demo run in dry-run mode only. No live side effects are performed.

## Evidence Pack Contents

The consolidated story pack includes:

- index.md
- index.html
- summary.json
- evidence_manifest.json
- workflow_timeline.json
- screenshots_checklist.md

## How to Run

Use the operator UI or run:

```bash
python -m src.taskframe_cli demo cross-workflow-v2
```

## Known Limitations

This is not production live automation. It is a controlled portfolio demo using seeded data, approval-staged side effects, and dry-run execution only.


### docs/demo_walkthrough.md

# Demo Walkthrough

## What This Project Demonstrates

TaskFrame Runtime is a manifest-driven autonomous business worker runtime for AI-assisted company operations. It shows how a controlled runtime can route work, execute bounded tools, keep a TaskFrame audit trail, require validation, and gate side effects before they can execute.

## What This Project Is Not

- It is not a chatbot.
- It is not a generic free-form agent demo.
- It is not a personal RPA scraper.
- It is not a demo script without an audit trail.

## Demo Prerequisites

- Python 3.11+
- Local demo fixtures and runtime data already seeded by the repo
- Optional browser-backed RPA is not required for the default demo path

## Run Clean Verification

```powershell
pytest
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

## Open Operator UI

```powershell
python -m src.operator_ui
```

The console is the operator surface for scenario selection, TaskFrame inspection, tool health, approvals, and reports.

## Recommended Demo Path

Follow this sequence for a live walkthrough:

1. Start the operator UI.
2. Select `Customer Status - Happy Path`.
3. Run the demo.
4. Show the business-readable Demo View.
5. Open the run report.
6. Show step outcomes and pending approval.
7. Select `Customer Status - Missing Customer`.
8. Run the failed validation demo.
9. Show safe stop behavior.
10. Select `Report Generation - Happy Path`.
11. Open the business report and run report.
12. End with release verification evidence.

## Demo Lanes

### Customer Status

Purpose:
- Answer a customer about an order status

What to point out:
- the selected scenario
- the TaskFrame ID
- the request card
- the worker checklist
- the decision card
- the run report path

Examples:
- Happy path
- Missing customer
- Wrong customer/order
- Unsupported intent

### Procurement

Purpose:
- Prepare a low-stock reorder for approval

What to point out:
- inventory and supplier data
- the staged procurement action
- the approval checkpoint
- the run report and evidence

Examples:
- Low-stock reorder
- Approval dry run

### Accounting

Purpose:
- Reconcile payments, orders, invoices, and ledger data

What to point out:
- reconciliation inputs
- matched and unmatched records
- exception evidence
- validation results
- staged sheet-write actions

### Report Generation

Purpose:
- Produce a business report and a run-bound audit report

What to point out:
- selected source data
- business report artifact path
- run report path
- evidence bundle path

Explain the two report types:

- Business report: the scenario output generated by the workflow
- Run report: the audit report for the exact frame, including manifest steps, step outcomes, validations, evidence, and pending actions

### Approval Gate

Show the pending-action area and point out:

- the human-readable action summary
- the approval and dry-run controls
- the TaskFrame state
- the audit trail in the runtime trace

Explain that side effects are never free-run. The approval gate is explicit and auditable.

### Tool Health

Open the tool capability panel and point out:

- tool names and categories
- core versus optional tools
- safe health status
- setup instructions
- read-only test controls

Explain that tools are visible and testable, but default verification uses safe probes only.

### Audit / Release Verification

Open the release verification report and point out:

- the clean-clone verifier verdict
- the golden demo result
- the optional RPA exclusion boundary
- the artifact links and runtime report paths

Explain that completion is validation-based, not model-certified.

## Known Limitations

- Live browser-backed RPA probes require local operator setup and are excluded from clean-clone RC verification.
- Live Google Sheets and Ollama availability depend on the local environment.


### docs/event_workflow_demo.md

# Event Workflow Demo

## Purpose
Shows event-driven TaskFrame execution using a demo customer message.

## Command
python scripts/run_event_demo.py

## Expected Result
Workflow ends at WAITING_FOR_EXECUTE with one pending send_customer_message action.

## What This Proves
- External event intake works.
- Event-to-manifest routing works.
- Event payload maps into TaskFrame inputs.
- Manifest execution works.
- Demo business lookup works.
- Draft reply generation works.
- Side effects are gated as pending actions.

## What This Does Not Do
- It does not send real messages.
- It does not use Gmail or WhatsApp.
- It does not use a real database.
- It does not use an LLM.
- It does not run a listener or webhook.


### docs/final_portfolio_walkthrough.md

# Final Portfolio Walkthrough

## 1. One-Minute Overview

TaskFrame Runtime is a manifest-driven autonomous business worker runtime for controlled AI-assisted company operations.

It demonstrates how autonomous workers can follow defined procedures, use tools, validate results, pause for approval, and produce audit-ready evidence without giving the LLM open-ended control.

## 2. What This Project Demonstrates

- Controlled autonomous business work
- Manifest-defined workflows
- TaskFrame audit records
- Deterministic validation
- Approval-gated side effects
- Bounded LLM use
- Run-bound HTML and Markdown reports
- Evidence bundles tied to the exact run

## 3. Architecture in Plain English

1. A demo scenario is selected.
2. The manifest determines the allowed workflow.
3. The orchestrator executes the known steps.
4. Tools read or prepare business data.
5. The LLM is only used where bounded help is useful.
6. Validation decides whether the run can continue.
7. Approval is required before any side effect.
8. The run is written into a TaskFrame and reported back as audit evidence.

## 4. How To Run The Demo

Run the supported verification path:

```powershell
pytest
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

Open the operator UI:

```powershell
python -m src.operator_ui
```

## 5. Recommended Demo Path

Use this exact sequence when presenting the portfolio:

1. Start the operator UI.
2. Select `Customer Status - Happy Path`.
3. Run the demo.
4. Show the business-readable Demo View.
5. Open the run report.
6. Show step outcomes and the pending approval action.
7. Select `Customer Status - Missing Customer`.
8. Run the failed validation demo.
9. Show the safe stop behavior.
10. Select `Report Generation - Happy Path`.
11. Open the business report and the run report.
12. End with release verification evidence.

## 6. What To Click

In Demo view:

- use the demo dropdown to select the scenario
- click `Start demo`
- use `Approve dry run` or `Reject` only when the UI shows a pending approval
- click `Create/open run report` to generate and open the audit report for the active run
- click `Open business report` only when the report-generation scenario exposes a business artifact path

## 7. What To Inspect

For `Customer Status - Happy Path`, inspect:

- the customer request card
- the worker checklist
- the prepared reply
- the approval card
- the run report step outcomes

For `Customer Status - Missing Customer`, inspect:

- the safe-stop headline
- the failure explanation
- the absence of any prepared reply
- the absence of any message being sent

For `Report Generation - Happy Path`, inspect:

- the business report artifact path
- the run report path
- the report step outcomes
- the evidence bundle path

## 8. Where Reports And Evidence Are Stored

Run-bound artifacts are written to:

- `runtime_data/outputs/reports/<frame_id>_run_report.html`
- `runtime_data/outputs/reports/<frame_id>_run_report.md`
- `runtime_data/outputs/evidence/<frame_id>_evidence_bundle.json`

Report-generation scenarios also create a business report artifact path when available.

## 9. What The Demo Proves

- The runtime is not a chatbot.
- The LLM does not choose tools freely.
- The workflow is selected and constrained by the manifest.
- Validation can stop the run safely.
- Side effects wait for approval.
- The system preserves an audit trail that a reviewer can inspect after the demo.

## 10. Known Limitations

- The project is a controlled runtime prototype, not a production deployment.
- Live integrations can be dry-run, fixture-backed, or approval-gated.
- Optional browser-backed RPA tools are excluded from the default clean-clone verification path.
- The demo business dataset is intentionally small and deterministic.

## 11. Suggested Talking Points

- This is controlled autonomous business work, not free-form agent behavior.
- The TaskFrame is the case file for the run.
- Validation decides whether the worker can continue.
- Approval gates prevent silent side effects.
- Reports are bound to the exact run and preserve evidence for review.
- The architecture is designed for auditability, not improvisation.

## Key Evidence Files

- [docs/current_release_status.md](current_release_status.md)
- [docs/release_candidate_verification.md](release_candidate_verification.md)
- [docs/release_candidate_evidence_index.md](release_candidate_evidence_index.md)
- [docs/release_evidence_pack.md](release_evidence_pack.md)
- [runtime_data/outputs/reports/golden_demo_report.html](../runtime_data/outputs/reports/golden_demo_report.html)
- [runtime_data/outputs/audit/golden_demo_audit.json](../runtime_data/outputs/audit/golden_demo_audit.json)

## Report Types

| Report type | Purpose |
|---|---|
| Business report | Output generated by a report-generation workflow |
| Run report | Step-by-step audit report showing manifest steps, step outcomes, validations, evidence, and pending actions |


### docs/google_workspace_integration_tests.md

# Google Workspace Integration Tests

These tests are optional and only run when Google OAuth credentials are configured locally.
They are read-only and do not require write-capable Google scopes.

## Environment

```text
RUN_GOOGLE_WORKSPACE_INTEGRATION=1
GOOGLE_WORKSPACE_TEST_SPREADSHEET_ID=<spreadsheet-id>
GOOGLE_WORKSPACE_TEST_RANGE=Sheet1!A1:B5
```

## What they cover

- `google/auth_status`
- `gmail/list_unread`
- `calendar/list_upcoming`
- `sheets/read_range`

## Safety

The integration tests are read-only. They do not send mail, write sheets, or mutate calendar state.
Live verification is explicit; default validation remains local.


### docs/google_workspace_readonly_toolpack.md

# Google Workspace Read-Only Tool Pack

## Purpose

The Google Workspace tool pack provides optional, read-only Gmail, Calendar, and Sheets tools.
It is designed to be discoverable and inspectable without requiring Google credentials in a clean clone.

## Safety model

- no send, create, update, delete, move, archive, or write operations;
- no raw OAuth tokens in logs, reports, TaskFrames, or health output;
- live reads require explicit configuration and credentials;
- the live probe is manual and never runs during default validation;
- default demo paths remain unchanged.

## Health modes

The pack supports local readiness checks without live API calls by default.
Live verification is optional and only runs when explicitly requested.
Credentials are optional for clean-clone validation, but required for live reads.

## Example tools

- `google/auth_status`
- `gmail/list_unread`
- `gmail/search`
- `gmail/read_metadata`
- `calendar/search`
- `calendar/list_upcoming`
- `sheets/read_range`


### docs/google_workspace_setup.md

# Google Workspace Setup

## OAuth credential files

Store Google credentials in your user config directory, typically `~/.taskframe/google/`.
Use placeholder example files as a starting point and keep real secrets out of the repo.

## Optional dependency install

The pack uses Google client libraries only when you install the Google extra.

```bash
pip install -e ".[google]"
```

## Validate the pack

```bash
python -m src.taskframe_cli tools validate tool_packs/google_workspace/toolpack.json
python -m src.taskframe_cli tools health google_workspace
```

## Safe health checks

Use the default local health path first:

```bash
python -m src.taskframe_cli tools health google_workspace
```

The live probe is manual. It is only appropriate when Google credentials are configured and you explicitly want to verify live read access.

## Optional live-read integration tests

Set the integration flag and provide credentials before running the live-read tests.

## What the pack cannot do

- send Gmail;
- create, update, or delete Calendar events;
- write Sheets data;
- access Drive write operations;
- expose OAuth token contents.

Clean-clone releases do not require Google credentials because the pack stays optional and read-only.


### docs/index.md

# Documentation Index

## Start here

- [README.md](../README.md) — Project overview, quickstart, and safe-by-default summary
- [docs/quickstart.md](quickstart.md) — Step-by-step setup, first demo, and troubleshooting
- [docs/cli_reference.md](cli_reference.md) — All CLI commands with flags and examples
- [docs/demo_walkthrough.md](demo_walkthrough.md) — Guided walkthrough of the demo console

## Architecture

- [docs/architecture_overview.md](architecture_overview.md) — System architecture and design decisions
- [docs/runtime_contracts.md](runtime_contracts.md) — Runtime contracts and invariants
- [docs/default_demo_boundary.md](default_demo_boundary.md) — What is and is not included in the default demo
- [docs/product_boundary.md](product_boundary.md) — Product boundary and architectural framing
- [docs/core_concepts.md](core_concepts.md) — TaskFrame, manifest, orchestrator, approval gates

## Manifests

- [docs/manifest_building_manual.md](manifest_building_manual.md) — How to author manifests
- [docs/manifest_command_reference.md](manifest_command_reference.md) — Command syntax reference
- [docs/manifest_tool_reference.md](manifest_tool_reference.md) — Available tools and namespaces
- [docs/manifest_health_dashboard.md](manifest_health_dashboard.md) — Manifest catalog health dashboard
- [docs/manifest_catalog_health_repair.md](manifest_catalog_health_repair.md) — How to repair manifest catalog issues
- [docs/common_manifest_authoring_failures.md](common_manifest_authoring_failures.md) — Common authoring failures and how to fix them

## Tools

- [docs/adding_new_tools.md](adding_new_tools.md) — How to add a new tool to the registry
- [docs/tool_contract_checklist.md](tool_contract_checklist.md) — Checklist for tool safety and contract compliance

## Release evidence

- [docs/current_release_status.md](current_release_status.md) — Current verified release status
- [docs/release_candidate_verification.md](release_candidate_verification.md) — Release candidate verification report
- [docs/release_evidence_pack.md](release_evidence_pack.md) — Full release evidence pack
- [docs/release_candidate_evidence_index.md](release_candidate_evidence_index.md) — Evidence index for the current release candidate
- [docs/known_limitations.md](known_limitations.md) — Current known limitations

## Portfolio

- [docs/final_portfolio_walkthrough.md](final_portfolio_walkthrough.md) — Complete portfolio walkthrough
- [docs/portfolio_summary.md](portfolio_summary.md) — Portfolio summary for reviewers
- [docs/demo_script.md](demo_script.md) — Demo script for live presentations


### docs/invoiceops_demo_pack.md

# InvoiceOps Demo Pack

This demo pack shows the InvoiceOps manifest running end to end in safe fixture mode.

## Purpose

- Prove the Spec 125 manifest can process invoice inputs without live Google Sheets writes.
- Show the happy path, blocked paths, exception paths, and rollback metadata in one deterministic gallery.
- Provide a readable regression pack for operators and reviewers.

## Scenarios

- `happy_path_matched`
- `wrong_po`
- `missing_po`
- `missing_receipt`
- `duplicate_invoice`
- `supplier_mismatch`
- `price_mismatch`
- `quantity_mismatch`
- `bad_invoice_text`
- `rollback_required_case`

## Expected Business Behaviour

- Happy path invoices match and prepare dry-run writes for the invoice register, match register, and ledger.
- Wrong PO, missing PO, missing receipt, duplicate invoice, supplier mismatch, and quantity mismatch stop safely and route to exception handling.
- Price mismatch produces an exception path with prepared dry-run writes and rollback metadata.
- Bad invoice text fails validation safely before any write preparation.
- Rollback-required cases always include rollback plans on prepared writes.

## Expected Safety Behaviour

- No scenario performs a live Google Sheets write.
- Prepared writes remain metadata only.
- Approval execution is not part of this pack.
- Rollback execution is not part of this pack.

## Evidence Outputs

- Invoice source evidence
- Extraction evidence
- Matching evidence
- Exception evidence
- Prepared write evidence
- Rollback evidence
- Match, exception, ledger, rollback, and evidence bundle reports

## What Is Intentionally Not Live

- Google Sheets writes
- Approval execution
- Rollback execution
- Manifest creation
- UI changes
- HTML/Markdown rendering beyond the report text already produced by the tools

## How To Run

The gallery is exposed as a deterministic Python runner and pytest coverage.

### Pytest

```bash
pytest tests/test_invoiceops_regression_gallery.py -q
```

### Direct runner

```bash
python -c "from runtime.invoiceops_gallery import run_invoiceops_gallery; import json; print(json.dumps(run_invoiceops_gallery(), indent=2))"
```

Gallery outputs are written under `runtime_data/invoiceops_demo_outputs/` when the runner is executed.


### docs/invoiceops_tool_boundary.md

# InvoiceOps Tool Boundary and Data Contracts

## Overview

InvoiceOps is the subsystem responsible for invoice matching, exception handling, and ledger
preparation within the 4thGenAgent runtime. This document defines the tool boundary rules and
all canonical data contracts used across InvoiceOps tools.

## Tool Boundary Rules

1. **InvoiceOps tools return plain dicts** wrapped in the existing `ToolResult` contract from
   `runtime/models.py`. No new result contract is introduced.

2. **Every InvoiceOps result must include all six ToolResult keys**:
   ```json
   {
     "ok": true,
     "type": "invoiceops_type_name",
     "data": {},
     "evidence": {},
     "error": "",
     "metadata": {}
   }
   ```

3. **Validation helpers** (`validate_*_shape`) return `{"ok": bool, "errors": [], "warnings": []}`.
   They never raise on validation failure; callers inspect `ok` and `errors`.

4. **Dry-run by default.** Every `prepared_write` must have `dry_run=True` unless explicitly
   overridden. `requires_approval=True` is always enforced — the validator errors if it is `False`.

5. **No live side effects** in any InvoiceOps contract or validator. Reads, transformations, and
   prepared writes are all deterministic and side-effect-free.

6. **Stdlib-only validators.** No third-party libraries are used in `invoiceops_contracts.py` or
   `invoiceops_constants.py`.

---

## Canonical Data Contracts

All shapes are validated by the corresponding `validate_*_shape` function in
`runtime/invoiceops_contracts.py`. Constants (enum sets, tolerances) live in
`runtime/invoiceops_constants.py`.

### 1. `invoice`

The canonical representation of a supplier invoice.

| Field | Type | Description |
|---|---|---|
| `invoice_id` | string | Unique identifier for this invoice record |
| `supplier_id` | string | Supplier identifier |
| `supplier_name` | string | Supplier display name |
| `invoice_number` | string | Supplier-assigned invoice number |
| `invoice_date` | YYYY-MM-DD | Date on the invoice |
| `po_number` | string | Linked purchase order number |
| `currency` | string | Currency code (e.g. `ZAR`) |
| `subtotal` | float | Pre-tax total |
| `tax_total` | float | Total tax amount |
| `invoice_total` | float | Grand total; must equal `subtotal + tax_total` |
| `line_items` | list[invoice_line] | One or more line items |

**Invoice line item**

| Field | Type |
|---|---|
| `line_no` | int |
| `description` | string |
| `sku` | string |
| `quantity` | float |
| `unit_price` | float |
| `tax_amount` | float |
| `line_total` | float |

Validator warns when `line_total` differs from both `quantity * unit_price` and
`quantity * unit_price + tax_amount` beyond the numeric tolerance (`0.005`).

---

### 2. `purchase_order`

| Field | Type | Enum values |
|---|---|---|
| `po_number` | string | |
| `supplier_id` | string | |
| `supplier_name` | string | |
| `status` | string | `open`, `part_received`, `closed`, `cancelled` |
| `currency` | string | |
| `po_total` | float | |
| `line_items` | list[po_line] | |

**PO line item**: `line_no` (int), `sku`, `description`, `ordered_quantity`, `unit_price`,
`line_total` (all floats except strings).

---

### 3. `goods_receipt`

| Field | Type | Enum values |
|---|---|---|
| `receipt_id` | string | |
| `po_number` | string | |
| `supplier_id` | string | |
| `receipt_date` | YYYY-MM-DD | |
| `status` | string | `received`, `partial`, `cancelled` |
| `line_items` | list[receipt_line] | |

**Receipt line item**: `line_no` (int), `sku`, `description`, `received_quantity` (float).

---

### 4. `supplier`

| Field | Type | Enum values |
|---|---|---|
| `supplier_id` | string | |
| `supplier_name` | string | |
| `status` | string | `active`, `inactive`, `blocked` |
| `vat_number` | string | |
| `payment_terms` | string | |
| `default_currency` | string | |

---

### 5. `match_result`

| Field | Type | Enum values |
|---|---|---|
| `match_id` | string | |
| `invoice_id` | string | |
| `invoice_number` | string | |
| `supplier_id` | string | |
| `po_number` | string | |
| `match_status` | string | `matched`, `exception`, `blocked` |
| `checks` | list[check_item] | |
| `exceptions` | list | |
| `ledger_posting_allowed` | bool | |
| `prepared_write_allowed` | bool | |

**Check item**: `check_id` (string), `status` (`pass`, `fail`, `warn`, `not_applicable`),
`expected`, `actual`, `message` (all strings).

---

### 6. `invoice_exception`

| Field | Type | Enum values |
|---|---|---|
| `exception_id` | string | |
| `exception_type` | string | `wrong_po`, `missing_po`, `missing_receipt`, `duplicate_invoice`, `supplier_mismatch`, `amount_mismatch`, `tax_mismatch`, `quantity_mismatch`, `bad_invoice_input` |
| `severity` | string | `low`, `medium`, `high`, `blocker` |
| `invoice_id` | string | |
| `po_number` | string | |
| `message` | string | |
| `recommended_action` | string | |
| `blocking` | bool | |

---

### 7. `ledger_row`

| Field | Type | Enum / constraints |
|---|---|---|
| `ledger_entry_id` | string | |
| `source_type` | string | must be `supplier_invoice` |
| `source_ref` | string | |
| `supplier_id` | string | |
| `invoice_number` | string | |
| `po_number` | string | |
| `debit_account` | string | |
| `credit_account` | string | |
| `amount` | float | |
| `currency` | string | |
| `status` | string | `prepared`, `posted`, `reversed` |

---

### 8. `prepared_write`

| Field | Type | Constraints |
|---|---|---|
| `prepared_write_id` | string | |
| `target` | string | `invoice_register`, `ledger`, `exception_register`, `match_register` |
| `operation` | string | `append`, `update` |
| `rows` | list | |
| `dry_run` | bool | **must be `True`**; validator warns if `False` |
| `requires_approval` | bool | **must be `True`**; validator errors if `False` |
| `rollback_plan` | dict | must be non-empty for write-like operations |

---

### 9. `rollback_plan`

| Field | Type | Enum values |
|---|---|---|
| `rollback_id` | string | |
| `rollback_type` | string | `delete_appended_rows`, `mark_reversed`, `manual_review_required`, `not_applicable` |
| `target` | string | |
| `source_prepared_write_id` | string | |
| `safe_to_auto_prepare` | bool | |
| `steps` | list[rollback_step] | |
| `reason` | string | |

**Rollback step**: `step_no` (int), `action` (string), `target` (string), `data` (dict).

---

### 10. `invoiceops_report`

| Field | Type |
|---|---|
| `report_id` | string |
| `invoice_id` | string |
| `match_status` | string (`matched`, `exception`, `blocked`) |
| `summary` | string |
| `checks` | list |
| `exceptions` | list |
| `prepared_writes` | list |
| `rollback_plans` | list |
| `evidence` | list |

---

### Evidence reference

Every InvoiceOps object that originated from a source document may carry evidence references.

| Field | Type | Constraints |
|---|---|---|
| `evidence_id` | string | |
| `source_type` | string | `pdf`, `text`, `google_sheet`, `fixture`, `tool_output` |
| `source_ref` | string | Path, URL, or identifier of the source |
| `field_path` | string | Dotted path of the extracted field (e.g. `invoice.invoice_number`) |
| `raw_value` | string | The raw extracted string |
| `confidence` | float | `0.0`–`1.0`; `1.0` for deterministic tools |

---

## Numeric Tolerance

Cross-field arithmetic checks (e.g. `invoice_total = subtotal + tax_total`) use a tolerance of
**`0.005`** (half a cent in ZAR). Differences larger than this generate a warning.

---

## Out of Scope (Spec 116)

The following are **not** implemented in Spec 116:

- Invoice PDF reader / OCR
- RAG ingestion or embedding
- Invoice field extraction
- Google Sheets reads or writes
- Duplicate invoice detection
- PO matching logic
- Goods receipt matching
- Live ledger writes
- Manifest integration
- Scenario gallery


### docs/known_limitations.md

# Known Limitations

The RC demonstrates controlled autonomous business automation in a demo business environment.
It is not presented as production-ready for unsupervised live operations.

## Default RC Limitations
- The clean-clone release-candidate path uses deterministic fixtures and demo data.
- Live side effects stay approval-gated or dry-run only.

## Optional Tooling Limitations
- Optional browser-backed RPA remains outside the default RC path.
- Optional tooling may depend on local browser state or external authentication.

## Live Execution Limitations
- Live execution is disabled by default.
- Live execution requires explicit runtime and manifest policy approval.

## RPA Limitations
- Browser-backed RPA is local-operator-only and not required for clean-clone verification.

## LLM Limitations
- The LLM is bounded to extraction, classification, summarisation, drafting, comparison, and exception explanation.

## Not Production Claims
- This release candidate is not a promise of unsupervised production operation.

## Deferred Work
- Optional live integration profiles.
- Batch and queue orchestration.
- Scheduler UI polish.
- Expanded business scenario packs.

## Verifier Notes
- example


### docs/live_blocked_evidence_report.md

# Live-Blocked Evidence Report

## Verdict

**PASS**

Generated: 2026-05-19T18:39:28.815335Z

## What Was Tested

- Runtime live mode disabled
- Manifest live policy disabled
- Tool live side-effect policy disabled
- Pending action not approved
- Wrong confirmation phrase
- Optional RPA default exclusion

## Evidence Table

| Check | Expected | Actual | Status |
|---|---|---|---|
| runtime_live_disabled | disabled | disabled | PASS |
| manifest_live_disabled | 0 manifests with live_execution.enabled=true | 0 manifests with live_execution.enabled=true | PASS |
| tool_live_blocked | all side-effect tools require approval or have live blocked | all tools compliant | PASS |
| pending_action_not_approved | PENDING_APPROVAL state requires explicit approval before execution | State machine: PENDING_APPROVAL → APPROVED → EXECUTING → EXECUTED | PASS |
| wrong_confirmation_blocked | typed confirmation required for live execution | EXECUTE LIVE <frame_id> <action_id> format required | PASS |
| optional_rpa_excluded | rpa_google_messages excluded_from_default_release=True | excluded | PASS |

## Live Attempt Results

No live side effects were performed.

No live side effects were performed.


### docs/live_execution_safety.md

# Live Execution Safety

TaskFrame defaults to dry-run execution.

Live execution is intentionally hard to trigger. It requires all of the following:

- `TASKFRAME_ENABLE_LIVE_EXECUTION=1`
- an approved pending action
- a TaskFrame in `WAITING_FOR_EXECUTE` or `EXECUTING_PENDING`
- manifest opt-in for live execution
- the manifest allowing the exact tool
- a tool spec that allows live side effects
- a passing live guardrail
- relevant tool health that is not failing
- typed confirmation that exactly matches the generated confirmation phrase

## Default behaviour

The default portfolio demo does not perform live side effects.

Dry-run is the normal path for both the operator UI and the CLI.
Optional RPA remains outside the default path and is governed by its own explicit safety checks.

## CLI guardrails

Use these commands to inspect safety before attempting any execution:

```bash
taskframe safety-status
taskframe pending-actions
taskframe live-preflight --frame-id <frame_id> --action-id <action_id>
taskframe execute-approved --frame-id <frame_id> --action-id <action_id> --dry-run
```

The live form is still guarded:

```bash
taskframe execute-approved \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --live \
  --i-understand-live-side-effects \
  --confirm "EXECUTE LIVE <frame_id> <action_id>"
```

`--live` alone is not sufficient.

## Example live preflight output

```text
Frame: frame_123
Action: pa_456
Tool: sheet/write
Status: LIVE_READY_REQUIRES_CONFIRMATION
Severity: warning
Guardrail: sheet_write | ok=true
Confirmation: EXECUTE LIVE frame_123 pa_456
Safe option: taskframe execute-approved --frame-id frame_123 --action-id pa_456 --dry-run
```

## Dry-run execution

Dry-run execution stays available even when live execution is blocked.

```bash
taskframe execute-approved --frame-id <frame_id> --action-id <action_id> --dry-run
```

## Example blocked output

```text
LIVE EXECUTION BLOCKED
Frame: frame_123
Action: pa_456
Tool: sheet/write
Status: LIVE_BLOCKED

Blockers:
- runtime_live_mode_disabled: TASKFRAME_ENABLE_LIVE_EXECUTION is not enabled.
- tool_not_live_allowed: Tool does not allow live side effects.

Safe option:
taskframe execute-approved --frame-id frame_123 --action-id pa_456 --dry-run
```

## Why this matters

The live boundary is the controlled side-effect edge. It must remain visible, auditable, and difficult to bypass.


### docs/manifest_building_manual.md

# Manifest Building Manual

## 1. Plain-English Overview

A manifest is the instruction file for an autonomous business worker. It tells the runtime what task is allowed, which inputs are required, which steps must run, which tools or LLM micro-actions may be used, what validations must pass, and when the worker must stop for approval. The manifest is not free-form prompting: it is a controlled workflow contract that the runtime executes step by step and records in a TaskFrame.

In simple terms: the manifest is the worker's SOP.

## 2. Manifest Anatomy

Canonical shape:

```json
{
  "manifest_id": "customer.message_status_check",
  "name": "Customer Message Status Check",
  "version": 1,
  "trigger": {
    "type": "manual"
  },
  "inputs": [
    {
      "name": "message",
      "required": true
    },
    {
      "name": "customer_id",
      "required": true
    }
  ],
  "steps": [
    {
      "id": "extract_order_ref",
      "command": "[q:extract_order_ref -> order_ref] text=$inputs.message"
    }
  ],
  "validations": [],
  "completion": {
    "success_outputs": ["order_ref"]
  }
}
```

Field purpose:

| Field | Purpose |
| --- | --- |
| `manifest_id` | Unique ID used by the catalog and runtime |
| `name` | Human-readable name |
| `version` | Integer manifest version |
| `trigger` | Manual, event, or scheduled trigger metadata |
| `inputs` | Required runtime inputs |
| `steps` | Ordered commands the worker may execute |
| `validations` | Rules used to prove the outcome is acceptable |
| `completion` | Required outputs or pending actions for success |

## 3. Command Reference

See also: [manifest_command_reference.md](manifest_command_reference.md)

Command types:

- `[q:action -> output]` LLM / semantic micro-action
- `[t:namespace/action -> output]` Deterministic tool action
- `[validate:rule_id]` Run named validation rule
- `[maintenance:action -> output]` Maintenance/report/artifact command

Examples:

```text
[q:extract_order_ref -> order_ref] text=$inputs.message
[q:classify_customer_message -> category] text=$inputs.message
[q:draft_customer_status_reply -> draft_reply] context=$outputs.order_context
[t:customer/read -> customer] customer_id=$inputs.customer_id
[t:order/read -> order] order_ref=$outputs.order_ref.order_ref
[t:shipment/read -> shipment] order_ref=$outputs.order_ref.order_ref
[t:sheet/read_range -> payments_sheet] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.payments_range
[validate:customer_owns_order]
[validate:reply_matches_facts]
```

For the supplier invoice matching workflow, reference the tool output envelope explicitly when the runtime returns a `ToolResult`. For example, use `$invoice.data.po_ref` and `$match_result.data.match_status` when the step output is a canonical tool result wrapper.

Variable references:

- `$inputs.message`
- `$inputs.customer_id`
- `$outputs.order_ref`
- `$outputs.order_ref.order_ref`
- `$outputs.customer.customer_id`
- `$outputs.order.status`

Rule:

Every step that produces data should write it to an output alias using `-> output_name`.

## 4. Common Workflow Patterns

Read-only workflow

1. Accept inputs
2. Read records
3. Validate facts
4. Produce final output
5. Complete

Approval-gated workflow

1. Accept inputs
2. Read records
3. Build draft action
4. Validate action
5. Stage pending action
6. Stop for approval

Report workflow

1. Read source data
2. Build report model
3. Generate report artifact
4. Generate evidence bundle
5. Complete

Failed validation workflow

1. Input or lookup fails
2. Validation fails
3. Runtime stops
4. No side effect is created
5. Run report explains safe stop

## 5. Validation and Completion Rules

Validations are the difference between a useful autonomous worker and an unsafe chatbot. The LLM may extract or draft, but validation decides whether the result is acceptable.

Validation examples:

```json
{
  "id": "customer_exists",
  "type": "output_field_truthy",
  "output": "customer",
  "field": "customer_id",
  "message": "Customer record must exist."
}
```

```json
{
  "id": "reply_exists",
  "type": "output_exists",
  "output": "draft_reply",
  "message": "Draft reply must be created."
}
```

Completion example:

```json
{
  "success_outputs": ["draft_reply"],
  "success_pending_actions": ["send_customer_message"],
  "allow_pending_approval": true,
  "continue_after_pending": true
}
```

## 6. Side-Effect and Approval Rules

Side-effect classes:

| Type | Examples | Approval |
| --- | --- | --- |
| Read-only | search, read, classify, summarize | No approval |
| Prepare/stage | draft, prepare message, build PO | Usually no live side effect |
| Side effect | send, write, update, delete, submit | Approval required |

Rule:

A manifest must not silently execute side effects. Side-effect steps must create pending actions and stop for approval unless explicitly allowed by live execution policy.

Live execution policy example:

```json
{
  "live_execution": {
    "enabled": false,
    "allowed_tools": [],
    "requires_approval": true
  }
}
```

## 7. How to Test a Manifest in the Workbench

1. Open Manifest Workbench
2. Select a manifest
3. Click Validate manifest
4. Fill generated input fields or paste Raw JSON input override
5. Keep fixture mode enabled for external read tools unless testing live credentials
6. Click Run dry-run test
7. Inspect the Dry-run Execution Panel
8. Select each step in the Step List Panel
9. Review Step result inspector
10. Click Create/open run report

Expected states:

| State | Meaning |
| --- | --- |
| `COMPLETED` | Workflow finished successfully |
| `WAITING_FOR_EXECUTE` | Pending action created and approval required |
| `FAILED_VALIDATION` | Business rule or fixture validation stopped the workflow |
| `FAILED_EXECUTION` | Tool/runtime error stopped execution |

## 8. Worked Examples

Example A - LLM classify message

```json
{
  "manifest_id": "llm.classify_customer_message",
  "name": "LLM Classify Customer Message",
  "version": 1,
  "trigger": {"type": "manual"},
  "inputs": [{"name": "message", "required": true}],
  "steps": [
    {
      "id": "classify_message",
      "command": "[q:classify_customer_message -> category] text=$inputs.message"
    }
  ],
  "validations": [
    {
      "id": "category_exists",
      "type": "output_exists",
      "output": "category",
      "message": "Classification output must exist."
    }
  ],
  "completion": {
    "success_outputs": ["category"]
  }
}
```

Example B - Customer order status

Abbreviated flow:

`extract order ref -> classify -> read customer -> read order -> read shipment -> build context -> draft reply -> validate -> stage message`

Example C - Accounting reconciliation

Abbreviated flow:

`read payment sheet -> read orders sheet -> load records -> reconcile -> prepare recon writes -> stop for approval`

## 9. Frontier LLM Authoring Guide

See also: [manifest_llm_authoring_guide.md](manifest_llm_authoring_guide.md)

When generating a manifest:

1. Do not invent tools.
2. Use only commands listed in the command reference or existing tool registry.
3. Every required input must appear in `inputs`.
4. Every produced value must have an output alias.
5. Later steps must reference prior outputs through `$outputs`.
6. Add validations for required business facts.
7. Add completion rules that match the intended final state.
8. Side effects must be staged and approval-gated.
9. Failed validation must stop safely.
10. Do not rely on chat history. The TaskFrame outputs are the data pipe.

Required output format for LLM-generated manifest:

1. Manifest JSON
2. Test input JSON
3. Expected outcome summary
4. Workbench test checklist

LLM build procedure:

1. Identify task type
2. Identify trigger
3. Define required inputs
4. Select allowed tools or LLM micro-actions
5. Build step sequence
6. Add validations
7. Add completion rules
8. Check side-effect policy
9. Produce test input JSON
10. Predict expected Workbench result

LLM self-check checklist:

- Is every command valid?
- Does every output alias exist before it is referenced?
- Are required inputs complete?
- Does every side effect require approval?
- Can failed lookup or validation stop safely?
- Does completion require the right output or pending action?
- Can this run in dry-run mode?
- Is the manifest specific enough for the runtime and not relying on model judgment?

## 10. Pre-Commit Checklist

Before committing a manifest:

- [ ] Manifest validates in Workbench
- [ ] Required input fields render correctly
- [ ] Dry-run test completes or fails for the expected reason
- [ ] Step outputs are visible
- [ ] Failed paths stop safely
- [ ] Pending actions are approval-gated
- [ ] Run report opens and explains step outcomes
- [ ] No live external dependency is required for default tests
- [ ] No unsupported tool or command is invented

## 11. Saving New Manifests

1. Click New manifest.
2. Edit manifest JSON.
3. Validate manifest.
4. Add test inputs.
5. Run dry-run test.
6. Fix errors.
7. Save manifest.
8. Reload catalog.
9. Re-run from saved manifest.

Warning: Do not save manifests that require live external credentials for default portfolio tests unless fixture mode is available.

---

## 12. Managing the Manifest Catalog

The Manifest Workbench provides catalog management actions in the **Catalog actions** toolbar row.

### Duplicate manifest

1. Select a manifest in the catalog.
2. Click **Duplicate manifest**.
3. A new manifest is created with a `_copy` suffix on the manifest_id and name.
4. If `_copy` already exists, a numeric suffix is added (`_copy_2`, `_copy_3`, …).
5. The duplicate is loaded in the editor automatically.

### Rename manifest

1. Select a manifest in the catalog.
2. Click **Rename manifest**.
3. Enter a new manifest ID and optionally a new name.
4. The manifest file is renamed and the manifest_id is updated atomically.
5. The renamed manifest appears in the catalog; the old ID no longer appears.

### Archive manifest

1. Select a manifest in the catalog.
2. Click **Archive manifest**.
3. Confirm the archive action.
4. The manifest file is moved to `manifests/archive/`.
5. The archived manifest no longer appears in the active catalog.

### Restore archived manifest

1. Click **Restore archived**.
2. Select an archived manifest from the list.
3. The manifest is validated before restore.
4. The file is moved back to `manifests/`.
5. The restored manifest appears in the active catalog.

### Reload catalog

Click **Reload manifest catalog** in the selector row to refresh the catalog list from disk.

> **Warning:** Do not rename or archive manifests that are referenced by demo scenarios unless you also update the scenario configuration. Manifest catalog management changes files, not scenario references.

---

## 13. Creating a New Manifest from a Template

### What the wizard does

The **New manifest from template** button in the Catalog actions row opens a guided wizard that:

1. Lets you choose a starter template.
2. Lets you fill in Manifest ID, Name, inputs, primary command, and output alias.
3. Previews the generated JSON in a scrollable text area.
4. Validates the candidate manifest (catalog uniqueness, runtime loadability, required fields).
5. Writes the manifest atomically to `manifests/` if validation passes.
6. Refreshes the catalog and loads the new manifest into the editor.

### What it does not do

- It does not write LLM-generated manifests.
- It does not register event routes automatically.
- It does not enable live execution.
- It does not edit existing manifests beyond what the editor already supports.
- It does not create finished workflows — generated manifests are starter contracts.

### Available templates

| Template | ID | Side effect | Purpose |
| --- | --- | --- | --- |
| Manual read-only tool manifest | `manual_read_tool` | No | Read data, validate output exists, complete |
| Manual LLM helper manifest | `manual_llm_helper` | No | Classify/extract with LLM step, validate, complete |
| Approval / side-effect starter | `approval_side_effect` | Yes (staged) | Stage a pending action, stop for approval |
| Event-driven stub manifest | `event_driven_stub` | No | Trigger via event; shows route snippet after creation |

### How to choose a template

- For any workflow that reads data without side effects: use `manual_read_tool`.
- For any workflow that uses LLM extraction or classification: use `manual_llm_helper`.
- For any workflow that sends a message, writes data, or submits an action: use `approval_side_effect`.
- For event-triggered workflows: use `event_driven_stub`.

### How to validate before saving

1. Fill in the Manifest ID and other fields.
2. Click **Preview** to generate the JSON.
3. Click **Validate** to run backend validation.
4. If validation passes, the **Create Manifest** button is enabled.
5. Click **Create Manifest** to write and save.

### Where created manifests are saved

All wizard-created manifests are saved in `manifests/` using the safe filename derived from the manifest_id (`customer_status_check.manifest.json`).

### How to register event routes after using the event-driven template

After saving an event-driven manifest, the wizard shows a route snippet. Register it manually in `config/event_routes.json`:

```json
{
  "route_id": "my_event_route",
  "source": "external",
  "event_type": "stub",
  "manifest_id": "example.generated_manifest",
  "input_map": {
    "message": "payload.message"
  }
}
```

> **Warning:** Generated manifests are starter contracts only. You must refine steps, validations, and completion rules before using them in production workflows. The wizard produces a manifest that loads and validates — not a finished SOP.

---

## 14. Smoke-Testing Generated Manifests

### What a smoke test does

A smoke test runs a manifest through the runtime in **dry-run mode** using isolated temporary data directories. No live tools are called, no side effects are produced, no event routes are modified. The smoke runner:

1. Validates manifest shape and required fields.
2. Checks that live execution is disabled.
3. Parses all step commands.
4. Loads the manifest via `runtime_load_manifest`.
5. Checks that all referenced tools are registered.
6. Creates a `TaskFrame` under a temp runtime directory.
7. Runs the orchestrator until it blocks (dry-run mode).
8. Classifies the result and checks it against the expected smoke classification for the template used.

### How to trigger a smoke test from the UI

- **After wizard creation**: The wizard prompts "Run smoke test now?" after successfully saving a manifest. Click **Yes** to run immediately.
- **From the Catalog actions row**: Select a manifest in the catalog list and click **Smoke test manifest**. Results are shown in a dialog.

### Smoke classifications

| Classification | Meaning | Passing? |
| --- | --- | --- |
| `DRY_RUN_COMPLETED` | All steps completed in dry-run mode. | Yes |
| `WAITING_FOR_EXECUTE_EXPECTED` | Manifest reached WAITING_FOR_EXECUTE, which is expected for side-effect/approval templates. | Yes |
| `COMPLETED_NO_DATA_ACCEPTED` | Completed with no data, accepted as empty output. | Yes |
| `LOAD_FAILED` | Manifest failed to load via runtime loader. | No |
| `COMMAND_INVALID` | A step command failed to parse. | No |
| `TOOL_NOT_REGISTERED` | A referenced tool is not in the tool registry. | No |
| `UNEXPECTED_LIVE_SIDE_EFFECT` | `live_execution.enabled` is `true` — blocked by smoke runner. | No |
| `VALIDATION_FAILED` | TaskFrame reached FAILED_VALIDATION state. | No |
| `EXECUTION_FAILED` | TaskFrame reached FAILED_EXECUTION state. | No |
| `TASKFRAME_ERROR` | An exception occurred during orchestration. | No |
| `SHAPE_INVALID` | Manifest is missing required top-level fields. | No |

### Smoke reports

After every smoke run, the runner writes two report files under `runtime_data/generated_manifest_smoke/`:

- `<report_name>.json` — machine-readable result with all check outcomes, classification, errors, and warnings.
- `<report_name>.md` — human-readable Markdown summary with a results table.

The UI displays paths to both files in the result dialog.

### Template quality gates

All four built-in templates are automatically smoke-tested as part of the release verifier (`tools/run_release_candidate_verification.py`). The quality gate:

- Runs all templates using isolated temp directories.
- Checks that each template reaches its declared `expected_smoke_classification`.
- Fails the release check if any template fails.
- Does not write to the production `manifests/` directory.
- Does not modify `config/event_routes.json`.

To run the quality gates manually:

```python
from src.generated_manifest_smoke_runner import run_template_quality_gates
result = run_template_quality_gates(
    runtime_data_dir="runtime_data/generated_manifest_smoke",
    manifest_dir="manifests/_quality_gate_tmp",
)
print(result["status"], result["passed"], "/", result["template_count"])
```

### What smoke tests do not verify

- Smoke tests do not validate business correctness of step logic.
- Smoke tests do not send real messages, read live data, or access external systems.
- A passing smoke test means the manifest is structurally valid and runs without errors in dry-run mode — not that it is production-ready.
- Smoke tests do not replace manual review of step commands, validation rules, and completion conditions.

> **Warning:** Never enable `live_execution.enabled: true` in a generated or wizard-created manifest without explicitly reviewing every step for side effects and adding the appropriate approval rules.

---

## 15. Manifest Authoring Feedback and Repair Guidance

### What repair guidance does

The **Repair Guidance** button in the Catalog actions row runs deterministic static analysis on the current editor JSON and translates validation and smoke-test failures into actionable repair suggestions. It does not rewrite the manifest and does not use an LLM.

Repair guidance:

1. Parses the editor JSON (catches and explains JSON syntax errors).
2. Runs static manifest analysis (structure, commands, inputs, validations, completion, live execution).
3. Incorporates the last validation result if available.
4. Incorporates the last smoke test result if available.
5. Produces a sorted list of findings with severity, location, suggested fix, and example.
6. Writes a JSON and Markdown report to `runtime_data/generated_manifest_smoke/`.

### Finding severities

| Severity | Meaning |
| --- | --- |
| `critical` | Must be resolved before any smoke or live use. Example: live execution enabled. |
| `error` | Will cause validation or smoke test failure. Example: command parse error. |
| `warning` | Non-blocking but likely wrong. Example: declared input not used. |
| `info` | Informational note. Example: event trigger reminder. |

Findings are sorted critical → error → warning → info, then by location.

### Common findings and fixes

| Finding ID | What it means | How to fix |
| --- | --- | --- |
| `live_execution_enabled` | `live_execution.enabled` is `true` | Set to `false`; use pending approvals instead |
| `command_parse_error` | A step command cannot be parsed | Correct command syntax: `[t:namespace/action -> alias]` |
| `unknown_tool` | A step references an unregistered tool | Use a tool from the manifest tool reference |
| `completion_output_missing` | Completion expects an output alias no step writes | Fix the alias to match a step's output, or update a step command |
| `validation_references_missing_output` | A validation references an output alias no step writes | Fix the validation output to match a step alias |
| `input_used_but_not_declared` | A command references `$inputs.X` but `X` is not in inputs | Add `X` to the inputs list |
| `input_declared_but_not_used` | An input is declared but no command references it | Remove it or use it in a step command |
| `missing_required_top_level_field` | A required field is absent | Add the missing field |
| `event_trigger_without_route_note` | Event trigger — route not auto-registered | Register the route manually in `config/event_routes.json` |
| `side_effect_command_without_pending_expectation` | Side-effect command without pending approval setup | Use the approval_side_effect template; add `allow_pending_approval: true` |

### How to use repair guidance from the UI

1. Open or edit a manifest in the Manifest Workbench.
2. Click **Repair Guidance** in the Catalog actions row.
3. The guidance panel shows all findings sorted by severity.
4. Fix each finding in the editor.
5. Click **Validate** or **Smoke test manifest** again to confirm.

### Repair guidance from code

```python
from src.manifest_authoring_feedback import explain_manifest_failure, write_repair_guidance_report

guidance = explain_manifest_failure(
    manifest=my_manifest_dict,
    smoke_result=last_smoke_result,   # optional
)
print(guidance["status"])   # HAS_FINDINGS or NO_FINDINGS
for finding in guidance["findings"]:
    print(f"[{finding['severity']}] {finding['id']}: {finding['message']}")
    print(f"  Fix: {finding['suggested_fix']}")

report = write_repair_guidance_report(guidance, runtime_data_dir="runtime_data")
print(report["markdown_path"])
```

### What repair guidance does not do

- It does not auto-rewrite manifests.
- It does not call an LLM.
- It does not run the manifest — run Smoke test for runtime feedback.
- A passing repair guidance check (NO_FINDINGS) does not guarantee the manifest is production-ready.

---

## 16. Auto-Fix Preview Mode

The Auto-Fix Preview mode (Spec 084) proposes deterministic, low-risk patches for common manifest authoring issues detected by Repair Guidance. It never modifies a manifest silently — every fix requires explicit operator approval.

### What Auto-Fix Preview does

- Reads findings from the Repair Guidance analysis.
- Generates a deterministic patch proposal for each fixable finding.
- Shows a before/after JSON preview and a unified diff for each proposed fix.
- Applies the selected fix to the editor buffer only after operator approval.
- Marks the editor as dirty so the operator must save manually.
- Re-runs validation after apply so remaining issues are visible.
- Writes a JSON and Markdown report to `runtime_data/generated_manifest_smoke/`.

### What Auto-Fix Preview does not do

- It does not modify manifests without explicit operator action.
- It does not use an LLM.
- It does not rewrite entire manifests.
- It does not run smoke tests automatically after applying a fix.
- It does not register event routes.
- It does not select or replace tools automatically.
- It does not fix command syntax errors.

### Supported fixes (low risk, deterministic)

| Finding | Fix |
|---|---|
| `completion_output_missing` | Replace the wrong completion output alias with the single produced step alias. |
| `validation_references_missing_output` | Replace the wrong validation output alias with the single produced step alias. |
| `completion_empty_without_acceptable_empty` | Add `acceptable_empty_outputs` containing step output aliases. |
| `input_declared_but_not_used` | Remove the unused simple-string input entry. |
| `input_used_but_not_declared` | Add the missing input to the `inputs` list (creates the list if absent). |
| `live_execution_enabled` | Set `live_execution.enabled` to `false`. |
| `duplicate_step_id` | Rename the duplicate step ID to `<original>_2` (only when no external references exist). |

### Unsupported fixes (blocked — operator must resolve manually)

The following findings cannot be patched automatically. The system will show a NOT_SUPPORTED proposal explaining why:

- `unknown_tool` — the system cannot choose a replacement tool.
- `command_invalid` / `command_parse_error` — the system cannot rewrite command syntax.
- `side_effect_command_without_pending_expectation` — requires explicit approval wiring.
- `unknown_validation_type` — only registered validation types are safe to use.
- `missing_required_top_level_field` — most structural fields require operator judgement.
- `step_missing_command` — the system cannot invent a command.
- `invalid_manifest_id` — only the operator can name a manifest.
- `manifest_load_failed`, `execution_failed`, `validation_failed`, `completion_failed` — runtime failures require operator analysis.
- `duplicate_step_id` with external references — renaming would break `when` conditions or validation rules.

### How to use Auto-Fix Preview

1. Open the Manifest Workbench and load a manifest.
2. Click **Auto-Fix Preview** (beside Repair Guidance in the catalog row).
3. The modal shows a proposal list on the left and details on the right.
4. Select a proposal. Review the **Summary**, **Patch Operations**, **Diff**, and **Before / After** JSON.
5. If the proposal has status `PROPOSED` and risk `low`, the **Apply Selected Fix to Editor** button is enabled.
6. Click **Apply Selected Fix to Editor** to apply the patch to the editor buffer.
7. A confirmation dialog appears before the fix is applied.
8. After applying, click **Validate** or **Repair Guidance** to check remaining issues.
9. Save the manifest using the normal **Save** action when satisfied.

### Why saving remains explicit

The Auto-Fix Preview applies fixes to the in-memory editor buffer only. The file on disk is not changed until the operator clicks **Save**. This allows the operator to review the patched manifest, run validation, and discard the change if needed — all before committing to disk.

### Recommended workflow after applying a fix

1. Apply the fix to the editor buffer.
2. Run **Validate** to check the patched manifest.
3. Run **Repair Guidance** to see if any findings remain.
4. If satisfied, click **Save** to write the manifest to disk.
5. Run **Smoke test manifest** to confirm end-to-end behaviour.

---

## 17. Broken Manifest Gallery and Regression Pack

A permanent gallery of intentionally broken manifests lives at `tests/fixtures/broken_manifests/`. This is a test asset, not a runtime catalog. The gallery serves three purposes:

1. **Regression protection** — every change to the manifest authoring subsystem must still diagnose, explain, and safely propose fixes for all documented failure patterns.
2. **Living documentation** — the fixtures are the ground truth for what broken manifests look like in practice.
3. **Developer reference** — the gallery index describes expected findings and auto-fix outcomes for each broken pattern.

### What the gallery contains

| Fixture | Broken Condition |
|---|---|
| `completion_output_missing` | Completion expects an alias no step produces |
| `validation_output_missing` | Validation checks an alias no step produces |
| `unknown_tool` | Step references an unregistered tool (smoke-detected only) |
| `invalid_command` | Command missing `[t:namespace/action -> alias]` format |
| `input_used_but_not_declared` | Command uses `$inputs.X` without declaring `X` |
| `input_declared_but_not_used` | Input declared but never referenced in commands |
| `duplicate_step_id` | Two steps share the same ID |
| `unsafe_live_execution` | `live_execution.enabled: true` in authored manifest |
| `missing_output_alias` | Tool command missing `-> alias` segment |
| `side_effect_without_pending_expectation` | Side-effect command without approval design |
| `malformed_json` | File contains truncated invalid JSON (`.txt` extension) |

### Running the regression pack

```text
python -m pytest tests/test_manifest_authoring_regression_gallery.py
```

### Gallery index

The `gallery_index.json` file describes each fixture's expected findings and auto-fix outcomes. Regression tests read this index and assert against actual analysis results. See `docs/common_manifest_authoring_failures.md` for the full reference.

---

## 18. Manifest Health Dashboard

The **Validate All** action in the Manifest Workbench runs a catalog-wide health review across active manifests and opens the **Manifest Health Dashboard**.

### Manifest Catalog Boundary

Only manifests in the active catalog are treated as release/operator manifests. Test, smoke, broken, and internal policy fixtures must live under `tests/fixtures/` and be loaded explicitly by tests. This keeps intentionally unsafe test manifests out of the operator UI and out of release health scope without weakening active-catalog checks.

### Manifest health modes

`taskframe manifest-health` is the non-blocking report mode. It writes the manifest health report and exits successfully so operators can review findings.

`taskframe manifest-health --strict --no-smoke` is the release-gate mode. It exits non-zero when the active manifest catalog has failures.

For one-off validation of a single file, use:

```bash
taskframe manifests validate-strict manifests/customer_status_llm_e2e.manifest.json --json
```

For curated regression coverage, use the manifest regression gallery:

```bash
taskframe manifests gallery list
taskframe manifests gallery validate
taskframe manifests gallery run --fixture completion_output_missing
taskframe manifests gallery report
```

The gallery keeps bad, unsafe, and edge-case manifests in `tests/fixtures/manifest_regression_gallery/` so they stay out of the active catalog while still exercising strict validation, repair guidance, smoke classification, and autofix limits.

The dashboard summarizes total manifests, healthy and warning-only manifests, failed and critical manifests, smoke results, repairable manifests with low-risk auto-fix proposals, and manifests that still require manual correction.

Each row shows the manifest ID, validation result, smoke status, top findings, repairable count, and recommended next action. Selecting a row reveals detailed validation errors, smoke classification, repair findings, auto-fix proposal counts, and report paths.

Use the dashboard to:

1. identify catalog-wide authoring risk before release review;
2. open a selected manifest directly in the editor;
3. jump into **Repair Guidance**, **Auto-Fix Preview**, or **Smoke Test Selected** for focused follow-up;
4. open the generated JSON or Markdown health report from `runtime_data/manifest_health/`.

Important limits:

- `Validate All` does not apply fixes.
- `Validate All` does not save edits.
- Smoke checks remain dry-run only.
- Archived manifests and the broken-manifest regression gallery are excluded from production catalog health.

See [manifest_health_dashboard.md](manifest_health_dashboard.md) for the full operator guide.

---

## Order management manifests (Spec 110)

Five production manifests were added as part of the order management workflow pack.
They demonstrate the prepare/execute pattern for side-effect steps:

| Manifest | Pattern |
|---|---|
| `order.validate_new` | Single tool step, completion on `order_validation` output |
| `order.reserve_stock` | Validate + conditional prepare; completion on `stock_reservation_action` pending action |
| `order.release_paid` | Payment check + conditional prepare; completion on `release_action` pending action |
| `order.detect_delayed` | Single tool step; `acceptable_empty_outputs` allows zero delayed orders |
| `order.update_shipment_status` | Prepare step; completion on `shipment_update_action` pending action |

See [order_management_workflows.md](order_management_workflows.md) for the full reference.

## Reference documents

- [manifest_command_reference.md](manifest_command_reference.md) — Command syntax, variable reference, and examples.
- [manifest_tool_reference.md](manifest_tool_reference.md) — Generated list of all registered tools with arguments, output types, and side-effect metadata.
- [manifest_llm_authoring_guide.md](manifest_llm_authoring_guide.md) — Guide for frontier LLMs generating manifests.
- [manifest_health_dashboard.md](manifest_health_dashboard.md) - Catalog-wide Validate All dashboard and report guide.
- [manifest_catalog_boundary.md](manifest_catalog_boundary.md) - Active vs quarantined test-manifest boundary.


### docs/manifest_catalog_boundary.md

# Manifest Catalog Boundary

## Purpose

The manifest catalog boundary separates release/operator manifests from test-only fixtures. Catalog health is intentionally strict, so manifests that are useful only for tests must not be mixed into the active operator catalog.

## Active Manifest Catalog

`manifests/` contains active operator and demo manifests. Files in this directory are assumed to be:

- release-relevant;
- operator-visible;
- health-checkable;
- safe by default.

Active manifests are included in catalog loading, the operator UI, and release health verification.

## Test and Smoke Manifest Quarantine

Test-only manifests live under `tests/fixtures/`, including smoke and live-policy fixtures under `tests/fixtures/smoke_manifests/`.

These fixtures may intentionally contain dangerous settings, intentional failures, or narrowly targeted runtime behavior used by tests. They are not operator-visible and are not part of release catalog health.

## Why Live-Policy Manifests Are Not Active Manifests

Some live-execution policy tests need manifests with `live_execution.enabled: true`. Those manifests are valuable test inputs, but they are not safe defaults for operators and should not be release catalog entries. Keeping them quarantined preserves test coverage without weakening active-catalog safety rules.

## How Tests Should Load Quarantined Manifests

Tests should load quarantined manifests explicitly by path:

```python
from pathlib import Path
from runtime.manifest_loader import load_manifest

SMOKE_MANIFEST_DIR = Path("tests/fixtures/smoke_manifests")
manifest = load_manifest(SMOKE_MANIFEST_DIR / "smoke_live_sheet_create_allowed.manifest.json")
```

When a test exercises route-based runtime behavior for a quarantined manifest, pass the fixture directory as the test runtime's `manifest_dir`.

## Release Health Rules

Release health scans active manifests only. It must:

- fail on active critical manifests;
- fail on active validation/load failures;
- ignore quarantined smoke/test fixtures because they are not release manifests;
- keep archived manifests out of the active catalog.

## Operator UI Visibility Rules

The operator catalog shows active manifests only. Test, smoke, broken, and internal policy fixtures are not operator catalog entries and should be loaded only by tests that name their fixture paths explicitly.


### docs/manifest_catalog_health_repair.md

﻿# Manifest Catalog Health Repair

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


### docs/manifest_command_reference.md

# Manifest Command Reference

## Command types

`[q:action -> output]`
- LLM / semantic micro-action
- Use for extraction, classification, drafting, summarization, and other bounded language tasks.

`[t:namespace/action -> output]`
- Deterministic tool action
- Use for reads, lookups, structured tool calls, and other runtime-backed operations.

`[validate:rule_id]`
- Run a named validation rule
- Use to prove the result is acceptable before completion or approval.

`[maintenance:action -> output]`
- Maintenance, report, or artifact command
- Use for report generation, evidence packaging, and other maintenance outputs.

## Examples

```text
[q:extract_order_ref -> order_ref] text=$inputs.message
[q:classify_customer_message -> category] text=$inputs.message
[q:draft_customer_status_reply -> draft_reply] context=$outputs.order_context
[t:customer/read -> customer] customer_id=$inputs.customer_id
[t:order/read -> order] order_ref=$outputs.order_ref.order_ref
[t:shipment/read -> shipment] order_ref=$outputs.order_ref.order_ref
[t:sheet/read_range -> payments_sheet] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.payments_range
[validate:customer_owns_order]
[validate:reply_matches_facts]
```

## Variable references

- `$inputs.message`
- `$inputs.customer_id`
- `$outputs.order_ref`
- `$outputs.order_ref.order_ref`
- `$outputs.customer.customer_id`
- `$outputs.order.status`

## Rule

Every step that produces data should write it to an output alias using `-> output_name`.

---

## Tool reference

The detailed list of every registered tool — with required/optional arguments, output types, and side-effect metadata — is generated from the runtime registry:

- [manifest_tool_reference.md](manifest_tool_reference.md)

> **Note:** Do not manually edit `docs/manifest_tool_reference.md`. It is generated by `tools/generate_manifest_tool_reference.py` and will be overwritten. Edit the generator or the registry instead.


### docs/manifest_contract_strict_mode.md

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


### docs/manifest_health_dashboard.md

# Manifest Health Dashboard

## Purpose

The Manifest Health Dashboard gives operators a catalog-wide view of active manifest authoring health. It answers which manifests are healthy, warning-only, failed, critical, smoke-passable, repairable, or blocked before release review.

This is an authoring health feature. It does not change runtime workflow behavior.

## Manifest Catalog Boundary

Only manifests in the active catalog are treated as release/operator manifests. Test, smoke, broken, and internal policy fixtures must live under `tests/fixtures/` and be loaded explicitly by tests. The dashboard intentionally excludes quarantined fixtures and `manifests/archive/`; placing an unsafe manifest in the active catalog should still make catalog health fail.

## Manifest health modes

`taskframe manifest-health` is report mode. It writes the catalog health report and exits successfully so operators can inspect the findings without blocking their workflow.

`taskframe manifest-health --strict --no-smoke` is the release-gate mode. It exits non-zero when the active catalog has failures.

## Health classifications

| Health | Meaning |
|---|---|
| `HEALTHY` | The manifest loads, validates, has no repair findings, and passes smoke when smoke is required. |
| `WARNING` | The manifest loads and validates, has warning-only findings, and smoke passed. |
| `FAILED` | The manifest cannot load, fails validation, fails a smoke check, or has error findings. |
| `CRITICAL` | A high-risk issue exists, such as `live_execution.enabled: true`. |
| `SMOKE_SKIPPED` | The manifest loads and validates, but smoke was intentionally skipped for a documented reason. |

## What Validate All checks

`Validate All` scans the active manifest catalog and, for each manifest:

1. Reads the JSON.
2. Loads it through the runtime manifest loader.
3. Runs deterministic repair guidance.
4. Summarizes available auto-fix proposals without applying them.
5. Runs a dry-run smoke check only when it is safe to do so.
6. Assigns a health classification and recommended next action.
7. Writes JSON and Markdown reports under `runtime_data/manifest_health/`.

Archived manifests under `manifests/archive/` are not included. Broken gallery fixtures under `tests/fixtures/broken_manifests/` are test assets and are not included in production catalog checks.

## What it does not check

- It does not execute live side effects.
- It does not apply auto-fixes.
- It does not save manifest edits.
- It does not replace release verification.
- It does not prove business correctness or production readiness.
- It does not invent new repair rules, manifest types, or runtime behavior.

## How smoke checks are handled

Smoke checks always use dry-run behavior. They are skipped when:

- the manifest cannot load;
- a critical finding is present;
- required sample inputs are missing;
- an event manifest has no sample event/input;
- a configured smoke limit has been reached;
- the manifest is known to require external or live setup.

Skipped smoke is informational unless validation or repair findings are already severe.

## Repairable and manual-fix counts

A manifest is **repairable** when at least one deterministic low-risk auto-fix proposal is available.

A manifest is **manual fix required** when it has error or critical findings and there is no low-risk applyable auto-fix.

The dashboard only summarizes auto-fix availability. It never applies changes in bulk.

## How to read the Markdown report

The Markdown report begins with a summary table for catalog-level counts, followed by one row per manifest:

- **Health** — final classification.
- **Validation** — runtime loader result.
- **Smoke** — pass, fail, or skipped.
- **Repairable** — number of low-risk applyable proposals.
- **Top Findings** — the most important repair findings.
- **Next Action** — the recommended operator action.

Use the JSON report when you need machine-readable evidence or downstream automation.

## Recommended operator workflow

1. Open Manifest Workbench.
2. Click **Validate All**.
3. Review summary cards for failures, repairable manifests, and critical issues.
4. Select a row to inspect the detailed validation, smoke, repair, and auto-fix summary.
5. Use **Open Selected Manifest** to load the manifest into the editor.
6. Use **Repair Guidance**, **Auto-Fix Preview**, or **Smoke Test Selected** for focused follow-up work.
7. Re-run **Validate All** after making fixes.
8. Use the generated JSON/Markdown reports as release evidence.


### docs/manifest_llm_authoring_guide.md

# Frontier LLM Authoring Guide

## Purpose

This guide is written so a frontier LLM can generate or revise manifests without inventing unsupported runtime behavior.

## When generating a manifest

1. Do not invent tools.
2. Use only commands listed in the command reference or existing tool registry.
3. Every required input must appear in `inputs`.
4. Every produced value must have an output alias.
5. Later steps must reference prior outputs through `$outputs`.
6. Add validations for required business facts.
7. Add completion rules that match the intended final state.
8. Side effects must be staged and approval-gated.
9. Failed validation must stop safely.
10. Do not rely on chat history. The TaskFrame outputs are the data pipe.

## Required output format for LLM-generated manifest

Return only:

1. Manifest JSON
2. Test input JSON
3. Expected outcome summary
4. Workbench test checklist

## LLM build procedure

1. Identify task type.
2. Identify trigger.
3. Define required inputs.
4. Select allowed tools or LLM micro-actions.
5. Build step sequence.
6. Add validations.
7. Add completion rules.
8. Check side-effect policy.
9. Produce test input JSON.
10. Predict expected Workbench result.

## LLM self-check checklist

- Is every command valid?
- Does every output alias exist before it is referenced?
- Are required inputs complete?
- Does every side effect require approval?
- Can failed lookup or validation stop safely?
- Does completion require the right output or pending action?
- Can this run in dry-run mode?
- Is the manifest specific enough for the runtime and not relying on model judgment?


### docs/manifest_regression_gallery.md

# Manifest Regression Gallery

The manifest regression gallery is the curated fixture suite for keeping manifest parsing, strict validation, repair guidance, smoke classification, and autofix behavior stable as the runtime evolves.

## Purpose

- preserve known bad, edge-case, and unsafe manifests as regression fixtures
- verify strict validation stays aligned with current runtime behavior
- classify smoke failures consistently
- document which manifest issues are autofixable and which are not

## Fixture categories

- valid
- structural
- command
- inputs
- validations
- completion
- side_effects
- events
- llm
- governance

## Index schema

Each fixture entry declares:

- `id`
- `path`
- `category`
- `description`
- `expected_findings`
- `expected_severity`
- `expected_strict_status`
- `expected_autofix`

Optional fields may include smoke classification, repair guidance text checks, and notes.

## Running the gallery

```bash
python -m src.taskframe_cli manifests gallery list
python -m src.taskframe_cli manifests gallery validate
python -m src.taskframe_cli manifests gallery run --fixture completion_output_missing
python -m src.taskframe_cli manifests gallery report
```

Reports are written to:

- `runtime_data/manifest_regression_gallery/gallery_report.json`
- `runtime_data/manifest_regression_gallery/gallery_report.md`

## How it works

For each fixture the gallery:

1. loads the manifest
2. runs strict contract validation
3. collects repair guidance
4. optionally runs smoke classification
5. checks autofix expectations
6. records the result in JSON and Markdown reports

Strict validation failures are release-gated. Repair guidance is informational. Autofix is intentionally limited; unknown tools, unsafe live execution, and malformed JSON are not blindly rewritten.

## Adding a fixture

1. add the manifest under `tests/fixtures/manifest_regression_gallery/`
2. add an entry to `gallery_index.json`
3. choose the narrowest category that matches the failure mode
4. set expectations to the actual strict, smoke, and autofix behavior

## Release verification

The release verifier runs the full gallery and blocks release if fixture expectations drift, the index is invalid, or the report cannot be generated.


### docs/manifest_tool_reference.md

# Manifest Tool Reference

> **This file is generated from the runtime tool registry.**
> Do not edit it manually. To update, run:
> ```
> python tools/generate_manifest_tool_reference.py
> ```
> See [manifest_command_reference.md](manifest_command_reference.md) for command syntax.

---

## acct/build_recon_sheet_rows

| Field | Value |
|---|---|
| Namespace | acct |
| Action | build_recon_sheet_rows |
| Side effect | false |
| Requires approval | false |
| Output type | `recon_sheet_rows` |

### Command form

```text
[t:acct/build_recon_sheet_rows -> output_name] reconciliation_result=$inputs.reconciliation_result exception_summary=$inputs.exception_summary
```

### Required arguments

- `reconciliation_result` (str)
- `exception_summary` (str)

### Optional arguments

- `frame_id` (str)

---
## acct/load_invoices

| Field | Value |
|---|---|
| Namespace | acct |
| Action | load_invoices |
| Side effect | false |
| Requires approval | false |
| Output type | `accounting_invoices` |

### Command form

```text
[t:acct/load_invoices -> output_name] sheet_rows=$inputs.sheet_rows
```

### Required arguments

- `sheet_rows` (str)

---
## acct/load_ledger

| Field | Value |
|---|---|
| Namespace | acct |
| Action | load_ledger |
| Side effect | false |
| Requires approval | false |
| Output type | `accounting_ledger` |

### Command form

```text
[t:acct/load_ledger -> output_name] sheet_rows=$inputs.sheet_rows
```

### Required arguments

- `sheet_rows` (str)

---
## acct/load_orders

| Field | Value |
|---|---|
| Namespace | acct |
| Action | load_orders |
| Side effect | false |
| Requires approval | false |
| Output type | `accounting_orders` |

### Command form

```text
[t:acct/load_orders -> output_name] sheet_rows=$inputs.sheet_rows
```

### Required arguments

- `sheet_rows` (str)

---
## acct/load_payments

| Field | Value |
|---|---|
| Namespace | acct |
| Action | load_payments |
| Side effect | false |
| Requires approval | false |
| Output type | `accounting_payments` |

### Command form

```text
[t:acct/load_payments -> output_name] sheet_rows=$inputs.sheet_rows
```

### Required arguments

- `sheet_rows` (str)

---
## business/get_order_context

| Field | Value |
|---|---|
| Namespace | business |
| Action | get_order_context |
| Side effect | false |
| Requires approval | false |
| Output type | `business_order_context` |

### Command form

```text
[t:business/get_order_context -> output_name] order_id=$inputs.order_id
```

### Required arguments

- `order_id` (str)

### Optional arguments

- `runtime_root` (str)

---
## cal/create

| Field | Value |
|---|---|
| Namespace | cal |
| Action | create |
| Side effect | true |
| Requires approval | true |
| Output type | `calendar_create_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:cal/create -> output_name] title=$inputs.title start=$inputs.start end=$inputs.end
```

### Required arguments

- `title` (str)
- `start` (str)
- `end` (str)

### Optional arguments

- `description` (str)
- `location` (str)

---
## cal/next

| Field | Value |
|---|---|
| Namespace | cal |
| Action | next |
| Side effect | false |
| Requires approval | false |
| Output type | `calendar_event_list` |

### Command form

```text
[t:cal/next -> output_name]
```

### Optional arguments

- `max_results` (int)

---
## cal/remove

| Field | Value |
|---|---|
| Namespace | cal |
| Action | remove |
| Side effect | true |
| Requires approval | true |
| Output type | `calendar_remove_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:cal/remove -> output_name] event_id=$inputs.event_id
```

### Required arguments

- `event_id` (str)

---
## cal/search

| Field | Value |
|---|---|
| Namespace | cal |
| Action | search |
| Side effect | false |
| Requires approval | false |
| Output type | `calendar_event_list` |

### Command form

```text
[t:cal/search -> output_name]
```

### Optional arguments

- `query` (str)
- `days` (int)
- `time_min` (str)
- `time_max` (str)
- `max_results` (int)

---
## customer/build_status_context

| Field | Value |
|---|---|
| Namespace | customer |
| Action | build_status_context |
| Side effect | false |
| Requires approval | false |
| Output type | `status_context` |

### Command form

```text
[t:customer/build_status_context -> output_name] customer=$inputs.customer order=$inputs.order shipment=$inputs.shipment
```

### Required arguments

- `customer` (str)
- `order` (str)
- `shipment` (str)

---
## customer/extract_order_ref

| Field | Value |
|---|---|
| Namespace | customer |
| Action | extract_order_ref |
| Side effect | false |
| Requires approval | false |
| Output type | `order_ref_result` |

### Command form

```text
[t:customer/extract_order_ref -> output_name] message=$inputs.message
```

### Required arguments

- `message` (str)

---
## customer/order_context

| Field | Value |
|---|---|
| Namespace | customer |
| Action | order_context |
| Side effect | false |
| Requires approval | false |
| Output type | `order_context_result` |

### Command form

```text
[t:customer/order_context -> output_name] customer_id=$inputs.customer_id order_ref=$inputs.order_ref
```

### Required arguments

- `customer_id` (str)
- `order_ref` (str)

---
## customer/prepare_message_action

| Field | Value |
|---|---|
| Namespace | customer |
| Action | prepare_message_action |
| Side effect | true |
| Requires approval | true |
| Output type | `customer_message_action` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:customer/prepare_message_action -> output_name] customer=$inputs.customer channel=$inputs.channel message=$inputs.message
```

### Required arguments

- `customer` (str)
- `channel` (str)
- `message` (str)

---
## customer/read

| Field | Value |
|---|---|
| Namespace | customer |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `customer_read_result` |

### Command form

```text
[t:customer/read -> output_name] customer_id=$inputs.customer_id
```

### Required arguments

- `customer_id` (str)

---
## customer/search

| Field | Value |
|---|---|
| Namespace | customer |
| Action | search |
| Side effect | false |
| Requires approval | false |
| Output type | `customer_list` |

### Command form

```text
[t:customer/search -> output_name]
```

### Optional arguments

- `customer_id` (str)
- `name` (str)
- `status` (str)

---
## customer/validate_owns_order

| Field | Value |
|---|---|
| Namespace | customer |
| Action | validate_owns_order |
| Side effect | false |
| Requires approval | false |
| Output type | `ownership_check` |

### Command form

```text
[t:customer/validate_owns_order -> output_name] customer=$inputs.customer order=$inputs.order
```

### Required arguments

- `customer` (str)
- `order` (str)

---
## customer/validate_status_reply

| Field | Value |
|---|---|
| Namespace | customer |
| Action | validate_status_reply |
| Side effect | false |
| Requires approval | false |
| Output type | `reply_validation` |

### Command form

```text
[t:customer/validate_status_reply -> output_name] reply=$inputs.reply order=$inputs.order shipment=$inputs.shipment
```

### Required arguments

- `reply` (str)
- `order` (str)
- `shipment` (str)

---
## file/exists

| Field | Value |
|---|---|
| Namespace | file |
| Action | exists |
| Side effect | false |
| Requires approval | false |
| Output type | `file_exists_result` |

### Command form

```text
[t:file/exists -> output_name] path=$inputs.path
```

### Required arguments

- `path` (str)

### Optional arguments

- `runtime_root` (str)

---
## file/list

| Field | Value |
|---|---|
| Namespace | file |
| Action | list |
| Side effect | false |
| Requires approval | false |
| Output type | `file_list_result` |

### Command form

```text
[t:file/list -> output_name]
```

### Optional arguments

- `path` (str)
- `runtime_root` (str)

---
## file/read_json

| Field | Value |
|---|---|
| Namespace | file |
| Action | read_json |
| Side effect | false |
| Requires approval | false |
| Output type | `file_read_json_result` |

### Command form

```text
[t:file/read_json -> output_name] path=$inputs.path
```

### Required arguments

- `path` (str)

### Optional arguments

- `runtime_root` (str)

---
## file/write_json

| Field | Value |
|---|---|
| Namespace | file |
| Action | write_json |
| Side effect | true |
| Requires approval | true |
| Output type | `file_write_json_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:file/write_json -> output_name] path=$inputs.path data=$inputs.data
```

### Required arguments

- `path` (str)
- `data` (str)

### Optional arguments

- `runtime_root` (str)

---
## g/check

| Field | Value |
|---|---|
| Namespace | g |
| Action | check |
| Side effect | false |
| Requires approval | false |
| Output type | `gmail_check_result` |

### Command form

```text
[t:g/check -> output_name]
```

### Optional arguments

- `max_results` (int)

---
## g/send

| Field | Value |
|---|---|
| Namespace | g |
| Action | send |
| Side effect | true |
| Requires approval | true |
| Output type | `gmail_send_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:g/send -> output_name] to=$inputs.to subject=$inputs.subject body=$inputs.body
```

### Required arguments

- `to` (str)
- `subject` (str)
- `body` (str)

---
## gb/book

| Field | Value |
|---|---|
| Namespace | gb |
| Action | book |
| Side effect | true |
| Requires approval | true |
| Output type | `gobook_booking_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:gb/book -> output_name] date=$inputs.date time_value=$inputs.time_value court=$inputs.court
```

### Required arguments

- `date` (str)
- `time_value` (str)
- `court` (str)

### Optional arguments

- `confirm` (bool)
- `slowmo` (int)

---
## gb/cancel

| Field | Value |
|---|---|
| Namespace | gb |
| Action | cancel |
| Side effect | true |
| Requires approval | true |
| Output type | `gobook_cancel_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:gb/cancel -> output_name] date=$inputs.date time_value=$inputs.time_value court=$inputs.court
```

### Required arguments

- `date` (str)
- `time_value` (str)
- `court` (str)

### Optional arguments

- `confirm` (bool)
- `slowmo` (int)

---
## gb/list

| Field | Value |
|---|---|
| Namespace | gb |
| Action | list |
| Side effect | false |
| Requires approval | false |
| Output type | `gobook_booking_list` |

### Command form

```text
[t:gb/list -> output_name]
```

### Optional arguments

- `slowmo` (int)

---
## gb/open_courts

| Field | Value |
|---|---|
| Namespace | gb |
| Action | open_courts |
| Side effect | false |
| Requires approval | false |
| Output type | `gobook_open_court_list` |

### Command form

```text
[t:gb/open_courts -> output_name] date=$inputs.date start=$inputs.start end=$inputs.end
```

### Required arguments

- `date` (str)
- `start` (str)
- `end` (str)

### Optional arguments

- `slowmo` (int)

---
## inventory/filter_reorder_candidates

| Field | Value |
|---|---|
| Namespace | inventory |
| Action | filter_reorder_candidates |
| Side effect | false |
| Requires approval | false |
| Output type | `reorder_candidates` |

### Command form

```text
[t:inventory/filter_reorder_candidates -> output_name] items=$inputs.items
```

### Required arguments

- `items` (str)

---
## inventory/read

| Field | Value |
|---|---|
| Namespace | inventory |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `inventory_record` |

### Command form

```text
[t:inventory/read -> output_name] sku=$inputs.sku
```

### Required arguments

- `sku` (str)

---
## inventory/search_low_stock

| Field | Value |
|---|---|
| Namespace | inventory |
| Action | search_low_stock |
| Side effect | false |
| Requires approval | false |
| Output type | `low_stock_result` |

### Command form

```text
[t:inventory/search_low_stock -> output_name]
```

---
## memory/set

| Field | Value |
|---|---|
| Namespace | memory |
| Action | set |
| Side effect | true |
| Requires approval | true |
| Output type | `memory_set_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:memory/set -> output_name] key=$inputs.key value=$inputs.value
```

### Required arguments

- `key` (str)
- `value` (str)

### Optional arguments

- `runtime_root` (str)

---
## message/validate_customer_status_reply

| Field | Value |
|---|---|
| Namespace | message |
| Action | validate_customer_status_reply |
| Side effect | false |
| Requires approval | false |
| Output type | `reply_validation` |

### Command form

```text
[t:message/validate_customer_status_reply -> output_name] draft_reply=$inputs.draft_reply order_context=$inputs.order_context
```

### Required arguments

- `draft_reply` (str)
- `order_context` (str)

---
## message/validate_supplier_reorder_message

| Field | Value |
|---|---|
| Namespace | message |
| Action | validate_supplier_reorder_message |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_message_validation` |

### Command form

```text
[t:message/validate_supplier_reorder_message -> output_name] supplier_message=$inputs.supplier_message draft_po=$inputs.draft_po
```

### Required arguments

- `supplier_message` (str)
- `draft_po` (str)

---
## messages/read_recent

| Field | Value |
|---|---|
| Namespace | messages |
| Action | read_recent |
| Side effect | false |
| Requires approval | false |
| Output type | `messages_read_recent_result` |

### Command form

```text
[t:messages/read_recent -> output_name] thread_name=$inputs.thread_name
```

### Required arguments

- `thread_name` (str)

### Optional arguments

- `limit` (int)
- `runtime_root` (str)
- `slowmo` (int)
- `keep_open` (bool)
- `browser_user_data_dir` (str)
- `browser_profile_dir` (str)
- `browser_cdp_url` (str)

---
## order/check_payment_status

| Field | Value |
|---|---|
| Namespace | order |
| Action | check_payment_status |
| Side effect | false |
| Requires approval | false |
| Output type | `order_payment_status_result` |

### Command form

```text
[t:order/check_payment_status -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

### Optional arguments

- `runtime_root` (str)

---
## order/detect_delayed_orders

| Field | Value |
|---|---|
| Namespace | order |
| Action | detect_delayed_orders |
| Side effect | false |
| Requires approval | false |
| Output type | `delayed_orders_result` |

### Command form

```text
[t:order/detect_delayed_orders -> output_name]
```

### Optional arguments

- `days_overdue` (int)
- `runtime_root` (str)

---
## order/execute_release_paid_order

| Field | Value |
|---|---|
| Namespace | order |
| Action | execute_release_paid_order |
| Side effect | true |
| Requires approval | true |
| Output type | `order_release_execution_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/execute_release_paid_order -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

### Optional arguments

- `dry_run` (bool)
- `runtime_root` (str)

---
## order/execute_shipment_status_update

| Field | Value |
|---|---|
| Namespace | order |
| Action | execute_shipment_status_update |
| Side effect | true |
| Requires approval | true |
| Output type | `shipment_update_execution_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/execute_shipment_status_update -> output_name] order_ref=$inputs.order_ref shipment_status=$inputs.shipment_status
```

### Required arguments

- `order_ref` (str)
- `shipment_status` (str)

### Optional arguments

- `tracking_ref` (str)
- `dry_run` (bool)
- `runtime_root` (str)

---
## order/execute_stock_reservation

| Field | Value |
|---|---|
| Namespace | order |
| Action | execute_stock_reservation |
| Side effect | true |
| Requires approval | true |
| Output type | `stock_reservation_execution_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/execute_stock_reservation -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

### Optional arguments

- `reservation_lines` (str)
- `dry_run` (bool)
- `runtime_root` (str)

---
## order/extract_ref_from_text

| Field | Value |
|---|---|
| Namespace | order |
| Action | extract_ref_from_text |
| Side effect | false |
| Requires approval | false |
| Output type | `order_ref_lookup` |

### Command form

```text
[t:order/extract_ref_from_text -> output_name] text=$inputs.text
```

### Required arguments

- `text` (str)

---
## order/items_list

| Field | Value |
|---|---|
| Namespace | order |
| Action | items_list |
| Side effect | false |
| Requires approval | false |
| Output type | `order_item_list` |

### Command form

```text
[t:order/items_list -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

---
## order/prepare_release_paid_order

| Field | Value |
|---|---|
| Namespace | order |
| Action | prepare_release_paid_order |
| Side effect | true |
| Requires approval | true |
| Output type | `order_release_prepare_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/prepare_release_paid_order -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

### Optional arguments

- `runtime_root` (str)

---
## order/prepare_shipment_status_update

| Field | Value |
|---|---|
| Namespace | order |
| Action | prepare_shipment_status_update |
| Side effect | true |
| Requires approval | true |
| Output type | `shipment_update_prepare_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/prepare_shipment_status_update -> output_name] order_ref=$inputs.order_ref shipment_status=$inputs.shipment_status
```

### Required arguments

- `order_ref` (str)
- `shipment_status` (str)

### Optional arguments

- `tracking_ref` (str)
- `runtime_root` (str)

---
## order/prepare_stock_reservation

| Field | Value |
|---|---|
| Namespace | order |
| Action | prepare_stock_reservation |
| Side effect | true |
| Requires approval | true |
| Output type | `stock_reservation_prepare_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/prepare_stock_reservation -> output_name] order_ref=$inputs.order_ref items=$inputs.items
```

### Required arguments

- `order_ref` (str)
- `items` (str)

### Optional arguments

- `runtime_root` (str)

---
## order/read

| Field | Value |
|---|---|
| Namespace | order |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `order_read_result` |

### Command form

```text
[t:order/read -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

---
## order/search

| Field | Value |
|---|---|
| Namespace | order |
| Action | search |
| Side effect | false |
| Requires approval | false |
| Output type | `order_list` |

### Command form

```text
[t:order/search -> output_name]
```

### Optional arguments

- `customer_id` (str)
- `order_ref` (str)
- `status` (str)

---
## order/validate_new

| Field | Value |
|---|---|
| Namespace | order |
| Action | validate_new |
| Side effect | false |
| Requires approval | false |
| Output type | `order_validation_result` |

### Command form

```text
[t:order/validate_new -> output_name] customer_id=$inputs.customer_id items=$inputs.items
```

### Required arguments

- `customer_id` (str)
- `items` (str)

### Optional arguments

- `runtime_root` (str)

---
## order_context/build

| Field | Value |
|---|---|
| Namespace | order_context |
| Action | build |
| Side effect | false |
| Requires approval | false |
| Output type | `order_context_build_result` |

### Command form

```text
[t:order_context/build -> output_name] customer=$inputs.customer order=$inputs.order shipment=$inputs.shipment
```

### Required arguments

- `customer` (str)
- `order` (str)
- `shipment` (str)

### Optional arguments

- `payment` (str)

---
## payment/read_by_order

| Field | Value |
|---|---|
| Namespace | payment |
| Action | read_by_order |
| Side effect | false |
| Requires approval | false |
| Output type | `payment_record` |

### Command form

```text
[t:payment/read_by_order -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

---
## po/build_draft

| Field | Value |
|---|---|
| Namespace | po |
| Action | build_draft |
| Side effect | false |
| Requires approval | false |
| Output type | `draft_po` |

### Command form

```text
[t:po/build_draft -> output_name] supplier=$inputs.supplier candidates=$inputs.candidates
```

### Required arguments

- `supplier` (str)
- `candidates` (str)

---
## po/check_duplicate_open

| Field | Value |
|---|---|
| Namespace | po |
| Action | check_duplicate_open |
| Side effect | false |
| Requires approval | false |
| Output type | `duplicate_po_check` |

### Command form

```text
[t:po/check_duplicate_open -> output_name] candidates=$inputs.candidates
```

### Required arguments

- `candidates` (str)

---
## po/read

| Field | Value |
|---|---|
| Namespace | po |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `purchase_order_result` |

### Command form

```text
[t:po/read -> output_name] po_ref=$inputs.po_ref
```

### Required arguments

- `po_ref` (str)

### Optional arguments

- `runtime_root` (str)

---
## po/validate_draft

| Field | Value |
|---|---|
| Namespace | po |
| Action | validate_draft |
| Side effect | false |
| Requires approval | false |
| Output type | `po_validation` |

### Command form

```text
[t:po/validate_draft -> output_name] draft_po=$inputs.draft_po
```

### Required arguments

- `draft_po` (str)

---
## purchase_order/search_open_by_sku

| Field | Value |
|---|---|
| Namespace | purchase_order |
| Action | search_open_by_sku |
| Side effect | false |
| Requires approval | false |
| Output type | `purchase_order_list` |

### Command form

```text
[t:purchase_order/search_open_by_sku -> output_name] sku=$inputs.sku
```

### Required arguments

- `sku` (str)

---
## q/extract_order_ref

| Field | Value |
|---|---|
| Namespace | q |
| Action | extract_order_ref |
| Side effect | false |
| Requires approval | false |
| Output type | `order_ref_result` |

### Command form

```text
[t:q/extract_order_ref -> output_name] text=$inputs.text
```

### Required arguments

- `text` (str)

---
## receipt/read_by_po

| Field | Value |
|---|---|
| Namespace | receipt |
| Action | read_by_po |
| Side effect | false |
| Requires approval | false |
| Output type | `goods_receipt_result` |

### Command form

```text
[t:receipt/read_by_po -> output_name] po_ref=$inputs.po_ref
```

### Required arguments

- `po_ref` (str)

### Optional arguments

- `runtime_root` (str)

---
## recon/match_payments

| Field | Value |
|---|---|
| Namespace | recon |
| Action | match_payments |
| Side effect | false |
| Requires approval | false |
| Output type | `reconciliation_result` |

### Command form

```text
[t:recon/match_payments -> output_name] payments=$inputs.payments orders=$inputs.orders invoices=$inputs.invoices ledger_entries=$inputs.ledger_entries
```

### Required arguments

- `payments` (str)
- `orders` (str)
- `invoices` (str)
- `ledger_entries` (str)

---
## recon/validate_result

| Field | Value |
|---|---|
| Namespace | recon |
| Action | validate_result |
| Side effect | false |
| Requires approval | false |
| Output type | `reconciliation_validation` |

### Command form

```text
[t:recon/validate_result -> output_name] reconciliation_result=$inputs.reconciliation_result
```

### Required arguments

- `reconciliation_result` (str)

---
## report/generate

| Field | Value |
|---|---|
| Namespace | report |
| Action | generate |
| Side effect | false |
| Requires approval | false |
| Output type | `report_result` |

### Command form

```text
[t:report/generate -> output_name] frame_id=$inputs.frame_id
```

### Required arguments

- `frame_id` (str)

### Optional arguments

- `runtime_data_dir` (str)

---
## sheet/create

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | create |
| Side effect | true |
| Requires approval | true |
| Output type | `sheet_create_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:sheet/create -> output_name] title=$inputs.title
```

### Required arguments

- `title` (str)

---
## sheet/prepare_write_rows

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | prepare_write_rows |
| Side effect | true |
| Requires approval | true |
| Output type | `sheet_write_rows_pending` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:sheet/prepare_write_rows -> output_name] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.range_name rows=$inputs.rows
```

### Required arguments

- `spreadsheet_id` (str)
- `range_name` (str)
- `rows` (str)

### Optional arguments

- `mode` (str)

---
## sheet/read

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `sheet_rows` |

### Command form

```text
[t:sheet/read -> output_name] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.range_name
```

### Required arguments

- `spreadsheet_id` (str)
- `range_name` (str)

---
## sheet/read_range

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | read_range |
| Side effect | false |
| Requires approval | false |
| Output type | `sheet_read_range_result` |

### Command form

```text
[t:sheet/read_range -> output_name] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.range_name
```

### Required arguments

- `spreadsheet_id` (str)
- `range_name` (str)

---
## sheet/write

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | write |
| Side effect | true |
| Requires approval | true |
| Output type | `sheet_write_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:sheet/write -> output_name] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.range_name values_json=$inputs.values_json
```

### Required arguments

- `spreadsheet_id` (str)
- `range_name` (str)
- `values_json` (str)

### Optional arguments

- `mode` (str)

---
## sheet/write_rows

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | write_rows |
| Side effect | true |
| Requires approval | true |
| Output type | `sheet_write_rows_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:sheet/write_rows -> output_name] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.range_name rows=$inputs.rows
```

### Required arguments

- `spreadsheet_id` (str)
- `range_name` (str)
- `rows` (str)

### Optional arguments

- `mode` (str)
- `dry_run` (str)

---
## shipment/read

| Field | Value |
|---|---|
| Namespace | shipment |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `shipment_read_result` |

### Command form

```text
[t:shipment/read -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

---
## supplier/prepare_message_action

| Field | Value |
|---|---|
| Namespace | supplier |
| Action | prepare_message_action |
| Side effect | true |
| Requires approval | true |
| Output type | `supplier_message_pending_action` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:supplier/prepare_message_action -> output_name] supplier=$inputs.supplier draft_po=$inputs.draft_po message=$inputs.message
```

### Required arguments

- `supplier` (str)
- `draft_po` (str)
- `message` (str)

---
## supplier/read

| Field | Value |
|---|---|
| Namespace | supplier |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_record` |

### Command form

```text
[t:supplier/read -> output_name] supplier_id=$inputs.supplier_id
```

### Required arguments

- `supplier_id` (str)

---
## supplier/search_active

| Field | Value |
|---|---|
| Namespace | supplier |
| Action | search_active |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_list` |

### Command form

```text
[t:supplier/search_active -> output_name]
```

---
## supplier/select_for_sku

| Field | Value |
|---|---|
| Namespace | supplier |
| Action | select_for_sku |
| Side effect | false |
| Requires approval | false |
| Output type | `selected_supplier` |

### Command form

```text
[t:supplier/select_for_sku -> output_name] candidates=$inputs.candidates
```

### Required arguments

- `candidates` (str)

---
## supplier/send_message

| Field | Value |
|---|---|
| Namespace | supplier |
| Action | send_message |
| Side effect | true |
| Requires approval | true |
| Output type | `supplier_send_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:supplier/send_message -> output_name] to=$inputs.to subject=$inputs.subject body=$inputs.body
```

### Required arguments

- `to` (str)
- `subject` (str)
- `body` (str)

### Optional arguments

- `draft_po` (str)
- `dry_run` (str)
- `runtime_root` (str)

---
## supplier_invoice/build_exception_report

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | build_exception_report |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_invoice_exception_report_result` |

### Command form

```text
[t:supplier_invoice/build_exception_report -> output_name] invoice=$inputs.invoice purchase_order=$inputs.purchase_order receipts=$inputs.receipts match_result=$inputs.match_result
```

### Required arguments

- `invoice` (str)
- `purchase_order` (str)
- `receipts` (str)
- `match_result` (str)

### Optional arguments

- `exception_summary` (str)
- `runtime_root` (str)

---
## supplier_invoice/check_duplicate

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | check_duplicate |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_invoice_duplicate_check_result` |

### Command form

```text
[t:supplier_invoice/check_duplicate -> output_name] supplier_id=$inputs.supplier_id supplier_invoice_number=$inputs.supplier_invoice_number
```

### Required arguments

- `supplier_id` (str)
- `supplier_invoice_number` (str)

### Optional arguments

- `invoice_ref` (str)
- `runtime_root` (str)

---
## supplier_invoice/execute_ledger_write

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | execute_ledger_write |
| Side effect | true |
| Requires approval | true |
| Output type | `supplier_invoice_ledger_write_execution_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:supplier_invoice/execute_ledger_write -> output_name] ledger_rows=$inputs.ledger_rows
```

### Required arguments

- `ledger_rows` (str)

### Optional arguments

- `dry_run` (str)
- `runtime_root` (str)

---
## supplier_invoice/match_three_way

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | match_three_way |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_invoice_match_result` |

### Command form

```text
[t:supplier_invoice/match_three_way -> output_name] invoice=$inputs.invoice purchase_order=$inputs.purchase_order receipts=$inputs.receipts
```

### Required arguments

- `invoice` (str)
- `purchase_order` (str)
- `receipts` (str)

### Optional arguments

- `tolerance_amount` (float)
- `tolerance_percent` (float)
- `runtime_root` (str)

---
## supplier_invoice/prepare_ledger_write

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | prepare_ledger_write |
| Side effect | true |
| Requires approval | true |
| Output type | `supplier_invoice_ledger_write_prepare_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:supplier_invoice/prepare_ledger_write -> output_name] invoice=$inputs.invoice match_result=$inputs.match_result
```

### Required arguments

- `invoice` (str)
- `match_result` (str)

### Optional arguments

- `runtime_root` (str)

---
## supplier_invoice/prepare_match_run_write

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | prepare_match_run_write |
| Side effect | true |
| Requires approval | true |
| Output type | `supplier_invoice_match_write_prepare_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:supplier_invoice/prepare_match_run_write -> output_name] match_result=$inputs.match_result
```

### Required arguments

- `match_result` (str)

### Optional arguments

- `runtime_root` (str)

---
## supplier_invoice/read

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_invoice_result` |

### Command form

```text
[t:supplier_invoice/read -> output_name] invoice_ref=$inputs.invoice_ref
```

### Required arguments

- `invoice_ref` (str)

### Optional arguments

- `runtime_root` (str)

---
## test/echo

| Field | Value |
|---|---|
| Namespace | test |
| Action | echo |
| Side effect | false |
| Requires approval | false |
| Output type | `test_echo_result` |

### Command form

```text
[t:test/echo -> output_name]
```

### Optional arguments

- `message` (str)
- `event_id` (str)

---
## wa/read

| Field | Value |
|---|---|
| Namespace | wa |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `whatsapp_messages` |

### Command form

```text
[t:wa/read -> output_name] chat=$inputs.chat
```

### Required arguments

- `chat` (str)

### Optional arguments

- `limit` (int)

---
## wa/search

| Field | Value |
|---|---|
| Namespace | wa |
| Action | search |
| Side effect | false |
| Requires approval | false |
| Output type | `whatsapp_search_result` |

### Command form

```text
[t:wa/search -> output_name] chat=$inputs.chat
```

### Required arguments

- `chat` (str)

---
## wa/send

| Field | Value |
|---|---|
| Namespace | wa |
| Action | send |
| Side effect | true |
| Requires approval | true |
| Output type | `whatsapp_send_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:wa/send -> output_name] chat=$inputs.chat
```

### Required arguments

- `chat` (str)

### Optional arguments

- `message` (str)
- `file_path` (str)
- `caption` (str)
- `kind` (str)

---


### docs/operator_console.md

# Operator Console

The console is organized around a compact Demo Mode.

## Demo Mode

Demo Mode keeps the next action visible at the top of the screen:

- Demo selector
- Run selected demo
- Approve & execute dry run
- Reject
- Generate evidence for this run
- Open evidence for this run
- Start over

The main area uses a compact split layout:

- horizontal demo flow
- current run status strip
- ready-to-run summary or run result
- approval and evidence state

Long request text, progress lists, business results, and evidence notes now scroll inside their own panels instead of clipping.

The demo catalog opens in a modal dialog instead of expanding the page.

## Operator Mode

Operator Mode keeps approval-oriented controls and business summaries visible.

## Inspector Mode

Inspector Mode exposes the technical runtime details:

- TaskFrame
- manifest
- trace
- validations
- pending actions
- reports
- tool health


### docs/optional_rpa.md

# Optional RPA Tools

## Overview

TaskFrame Runtime includes optional browser-backed RPA tooling, specifically for Google Messages automation experiments.

These tools are **excluded from the default demo and release path**. They exist to demonstrate future automation reach, not as a default capability.

---

## Why RPA is optional

Browser-backed automation depends on:

- a local Playwright installation;
- a local browser profile;
- an authenticated and manually paired browser session;
- local machine state that changes between sessions.

These dependencies cannot be installed or configured automatically and are not safe to assume in a shared or unfamiliar environment.

---

## Safety warning

Optional RPA tools may interact with local browser sessions and authenticated web applications.

They are excluded from the default demo and release path.

**Do not enable RPA tools against sensitive accounts unless you understand the browser profile, authentication, and data exposure risks.**

If a browser session is configured with access to personal or business accounts, an RPA probe may read or interact with that account's messages.

---

## What is excluded from the default path

The following are **not** required for or included in the default demo:

- `pip install playwright` — not in default dependencies
- browser profile setup — not part of default installation
- `taskframe demo` — does not use RPA tools
- `taskframe ui` — shows RPA capability status as `disabled_optional`, does not run live probes
- `taskframe verify` — does not run RPA live probes
- `python -m pytest` — default tests do not require Playwright
- `taskframe golden-demo` — does not include RPA scenarios

---

## Dependencies

To install optional RPA dependencies:

```bash
pip install -e ".[rpa]"
playwright install
```

This installs Playwright and its browser binaries. It is **not** part of the default install.

---

## Configuration

RPA configuration must remain **user-local**. Do not commit browser profiles, session files, or tokens to the repository.

Recommended config location: `~/.taskframe/`

The recommended profile for RPA work is `rpa-local`. See `docs/configuration.md` for details.

Environment variable to enable optional RPA:

```bash
ENABLE_OPTIONAL_RPA_TOOLS=true
```

Or set the profile explicitly:

```bash
TASKFRAME_PROFILE=rpa-local
```

---

## Browser profile risks

- Browser profiles may include authenticated sessions for personal accounts.
- An RPA live probe may read or send messages if the browser is paired.
- Do not use browser profiles that contain sensitive business or personal communications unless you are operating in a controlled local environment.
- Never share browser profile directories or include them in the repository.

---

## Live probe behaviour

A live probe explicitly runs the RPA tool against a local browser session.

To run a live probe via CLI:

```bash
taskframe rpa health --enable-rpa --live-probe
```

`--live-probe` requires `--enable-rpa`. Running `--live-probe` without `--enable-rpa` will fail with a clear error.

Live probes are **never** run automatically during:

- `taskframe demo`
- `taskframe verify`
- `python -m pytest`
- `taskframe golden-demo`

---

## Troubleshooting

| Problem | Suggested fix |
|---|---|
| `playwright not found` | Run `pip install -e ".[rpa]" && playwright install` |
| `rpa health` shows `disabled` | Set `ENABLE_OPTIONAL_RPA_TOOLS=true` or use `--enable-rpa` flag |
| Browser not paired | Manually pair Google Messages in the Playwright browser (`playwright open`) |
| Live probe fails auth | Re-authenticate the browser session manually |
| `taskframe rpa health --live-probe` fails | Add `--enable-rpa` flag: `taskframe rpa health --enable-rpa --live-probe` |

---

## Recommended use

Optional RPA tools are recommended only for:

- local developer experiments in a controlled environment;
- demonstrating future automation reach in a prepared lab setup;
- validating a specific RPA workflow that has been explicitly designed and approved.

They are **not** recommended for:

- default portfolio demonstrations;
- production or staging environments;
- machines shared with other users;
- accounts with access to sensitive business messages.

---

## CLI reference

```bash
taskframe rpa status              # Show optional RPA status (no probe)
taskframe rpa health              # Default: show RPA health as disabled
taskframe rpa health --enable-rpa # Run dependency and config checks
taskframe rpa health --enable-rpa --live-probe  # Run live browser probe
taskframe rpa docs                # Print this documentation path
```

See `docs/cli_reference.md` for full CLI documentation.


### docs/order_management_workflows.md

# Order Management Workflow Pack v1

Spec 110 adds a first-class order management workflow lane to TaskFrame.
All business logic lives in manifest steps and domain tools — none touches
the orchestrator.

---

## Workflows

| Manifest ID | Trigger event | Purpose |
|---|---|---|
| `order.validate_new` | `operator.order_validate_new` | Validate a new order: customer exists, items in stock, totals correct |
| `order.reserve_stock` | `operator.order_reserve_stock` | Prepare a stock reservation and stage it for operator approval |
| `order.release_paid` | `operator.order_release_paid` | Check payment status and stage a paid-order release for approval |
| `order.detect_delayed` | `operator.order_detect_delayed` | Detect orders whose estimated delivery date has passed |
| `order.update_shipment_status` | `operator.order_update_shipment_status` | Prepare a shipment status update and stage it for approval |

---

## Domain Tools (`runtime/order_management_tools.py`)

All tools follow the [tool result contract](tool_result_contract.md): every function
returns a dict with at least `ok: bool`. Side-effect tools are `dry_run=True` by
default and never write to production stores in the demo environment.

| Tool key | Side effect | Requires approval | Description |
|---|---|---|---|
| `order/validate_new` | No | No | Validate customer, items, and stock levels |
| `order/prepare_stock_reservation` | No | No | Stage a pending reservation action |
| `order/execute_stock_reservation` | Yes | Yes | Execute stock reservation (dry-run only) |
| `order/check_payment_status` | No | No | Look up payment records for an order |
| `order/prepare_release_paid_order` | No | No | Stage a pending release action if payment matched |
| `order/execute_release_paid_order` | Yes | Yes | Execute order release (dry-run only) |
| `order/detect_delayed_orders` | No | No | Scan shipments for overdue estimated delivery dates |
| `order/prepare_shipment_status_update` | No | No | Stage a pending shipment status action |
| `order/execute_shipment_status_update` | Yes | Yes | Execute shipment status update (dry-run only) |

### Prepare / Execute pattern

Side-effect operations use a two-step pattern:

1. **Prepare tool** — reads current state, validates inputs, returns a
   `pending_action` dict with `action_type`, `tool`, and `evidence`.
   Recorded in the run context as a pending action with `status=PENDING_APPROVAL`.
2. **Operator approval** — the operator reviews the pending action in the UI.
3. **Execute tool** — called with `dry_run=True` (the demo default); simulates
   the mutation and returns `before_*` / `after_*` evidence without writing to
   the business store.

This matches the same pending-action contract used by all other side-effect tools
in the runtime.

---

## Event Routes

Routes are defined in `config/event_routes.json` under `routes`:

```json
{ "route_id": "operator.order_validate_new",
  "source": "operator_scenario_pack",
  "event_type": "manual.order_validate_new",
  "manifest_id": "order.validate_new" }
```

Five routes are registered (one per workflow). All use
`source: "operator_scenario_pack"` so they appear in the operator UI scenario
browser and route alignment checks pass.

---

## Operator Scenarios

Ten scenarios are registered under the `order_management` category in
`src/operator_scenarios.py`:

| Scenario ID | Description |
|---|---|
| `order_validate_new_valid` | Validate a new order with sufficient stock |
| `order_validate_new_insufficient_stock` | Validate a new order where stock is zero |
| `order_reserve_stock` | Prepare stock reservation for a valid order |
| `order_release_paid` | Release an order whose payment is matched |
| `order_release_unpaid` | Attempt release for an order with no payment |
| `order_detect_delayed` | Detect delayed orders (returns at least one) |
| `order_update_shipment_status` | Update a shipment to shipped status |
| `order_reserve_stock_approve` | Approve and dry-run execute a stock reservation |
| `order_update_shipment_approve` | Approve and dry-run execute a shipment update |
| `order_check_payment_status` | Check payment status for an order |

---

## Business Dataset

Six test orders are seeded by `runtime/business_data.py`:

| Order ref | Customer | Status | Purpose |
|---|---|---|---|
| `ORD-10050` | CUST-1001 | pending_validation | Valid order, SKU-DESK-01 in stock |
| `ORD-10051` | CUST-1001 | pending_validation | Invalid order, SKU-CHAIR-01 zero stock |
| `ORD-10052` | CUST-1002 | awaiting_release | Payment matched (PAY-10052) |
| `ORD-10053` | CUST-1003 | awaiting_release | No payment — should block release |
| `ORD-10054` | CUST-1004 | released | SHIP-9010, estimated_delivery 2026-04-08 (delayed) |
| `ORD-10055` | CUST-1004 | released | SHIP-9011 packed, ready for status update |

---

## Running the Tests

```bash
# Spec 110 tests only
pytest tests/test_order_management_*.py -q

# Full suite
pytest -q
```

---

## Architectural Constraints

- No order management business logic may be added to the orchestrator
  (`runtime/orchestrator.py`).
- All reads go through `runtime/business_store.py`.
- Execute tools are blocked from live writes: `allow_live=False` in the
  tool registry; `dry_run=True` default in every execute function.
- Pending actions follow the standard approval contract defined in
  `docs/runtime_contracts.md`.


### docs/portfolio_evidence_pack.md

# Portfolio Evidence Pack

## Purpose

The portfolio evidence pack presents TaskFrame as a controlled business automation runtime in a form that is suitable for demos, GitHub, interviews, stakeholder review, and portfolio presentation.

This portfolio pack is evidence for a controlled demo system. It must not be represented as proof of production readiness.

## What It Contains

- An architecture summary
- A demo script
- Workflow proof
- Tool inventory
- Readiness status links
- Screenshot checklist
- Known limitations
- Optional links to the latest story pack and readiness scorecard

## How to Generate It

```powershell
taskframe portfolio-pack
```

Useful options:

- `--json`
- `--open`
- `--no-story-pack`
- `--no-readiness`

## How to Use It in a Demo

Open `index.html` first. It gives a reviewer-facing summary of the runtime, the workflows, the tools, and the current readiness posture.

Then walk through:

1. `architecture.md`
2. `demo_script.md`
3. `workflow_proof.md`
4. `tool_inventory.md`
5. `known_limitations.md`

If the latest story pack and readiness scorecard exist, use them as supporting evidence.

## How It Links to Story and Readiness Evidence

The pack links:

- the latest cross-workflow story pack from Spec 112, when available
- the latest readiness scorecard from Spec 113, when available

These links are optional. The portfolio pack remains valid even when one or both are unavailable, provided it states that clearly.

## Limitations

- This pack documents a controlled portfolio/demo runtime, not production live automation.
- Live side effects are blocked or approval-staged.
- Some workflows use seeded demo data.
- External systems may require credentials.
- RPA is not part of the default release path.
- Production deployment would require security, monitoring, tenancy, and operational hardening.


### docs/portfolio_summary.md

# Portfolio Summary

## Problem Statement

Most AI demos show that a model can talk about work. This project shows a controlled runtime that can actually perform bounded business work inside explicit procedures, validation gates, and approval checkpoints.

## Architecture Summary

TaskFrame Runtime is a manifest-driven autonomous business worker runtime for AI-assisted company operations.

The architecture is deliberately controlled:

- manifests define the allowed workflow
- the orchestrator executes known paths instead of inventing new ones
- TaskFrame records run state, outputs, evidence, validations, and approvals
- tools perform deterministic business actions
- the LLM is bounded to extraction, classification, drafting, and summarisation
- approval gates sit in front of side effects
- run-bound reports and evidence are generated for each demo run

## Core Design Principles

- Manifest-driven execution, not open-ended prompting
- TaskFrame-centered auditability
- Deterministic validation, not model-certified success
- Approval-gated side effects
- Bounded LLM usage
- Run-bound evidence for every scenario
- Optional integrations stay outside the default verification path

## Major Features

- Customer status workflows
- Procurement workflows
- Accounting workflows
- Report generation workflows
- Business-readable Demo View
- Run report HTML and Markdown outputs
- Evidence bundle generation
- Cross-workflow demo story packs
- 90% readiness scorecard reporting
- Public-facing portfolio evidence packs
- Tool health and inspection surfaces
- Clean-clone release verification

## Workflow Examples

- Customer status: answer a customer about an order, validate ownership, draft a reply, and stage approval before any send
- Procurement: detect low stock, prepare a reorder draft, and stage approval before any supplier action
- Accounting: reconcile business records, explain exceptions, and preserve evidence for review
- Report generation: build a business report and a run report for the exact TaskFrame
- Cross-workflow demo story: connect customer support, procurement, and accounting into one reviewer-facing evidence pack
- Readiness scorecard: measure controlled portfolio/demo readiness across the seven major project areas
- Portfolio evidence pack: consolidate the architecture summary, demo script, workflow proof, tool inventory, readiness links, and known limitations into one public-facing artifact

## Evidence And Reporting Model

Two report types are central to the portfolio:

| Report | Purpose |
|---|---|
| Business report | Output generated by a report-generation workflow |
| Run report | Audit-style report showing manifest steps, step outcomes, validations, evidence, and pending actions |

The runtime also produces a TaskFrame audit record and an evidence bundle for each run.
The cross-workflow demo v2 adds one consolidated story pack that links the individual workflow reports and evidence bundles into a single executive-facing artifact set.
The readiness scorecard adds a machine-readable gate that makes the portfolio/demo readiness target measurable.
The portfolio evidence pack adds a public-facing packaging layer so the runtime can be reviewed as a coherent portfolio artifact without claiming production readiness.

## Portfolio Evidence Pack

Run:

```powershell
taskframe portfolio-pack
```

The generated pack links the latest story pack and readiness scorecard when they exist, and it always states the repository limitations clearly.

## Safety And Approval Model

- No silent side effects
- No arbitrary LLM tool control
- No success claim without validation
- No live send until approval
- No default dependence on optional browser-backed integrations

## Current Release Status

Current baseline:

- Verdict: `READY_WITH_KNOWN_LIMITATIONS`
- `pytest`: `1392 passed, 2 skipped`
- Golden demo: `READY`
- Release verification: `17 passed, 0 failed`
- Release blockers: none

Verification commands for the clean release-candidate verification path:

```powershell
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

The clean release-candidate verification path is deterministic, fixture-backed, and intended for the portfolio path.

## Known Limitations

- `real_ollama_integration_test_missing`
- `google_sheets_integration_test_missing`

These are acceptable for the default portfolio path because the supported verification flow is deterministic and fixture-backed.

## Why It Is Portfolio-Relevant

This repository demonstrates a practical, inspectable architecture for controlled autonomous work:

- business workflows are explicit and repeatable
- the runtime is auditable end to end
- validation determines the outcome
- approval gates control side effects
- the UI and reports are business-readable

That makes it a strong portfolio artifact for productized automation, not a chatbot demo.

## Supporting References

- [Final Portfolio Walkthrough](final_portfolio_walkthrough.md)
- [Product Boundary](product_boundary.md)
- [Demo Walkthrough](demo_walkthrough.md)
- [Demo Script](demo_script.md)
- [Current Release Status](current_release_status.md)


### docs/product_boundary.md

# Product Boundary

## Positioning

This repository is a manifest-driven autonomous business worker runtime prototype.

It demonstrates:

- TaskFrame audit records
- approval gates
- deterministic validation
- bounded LLM use
- deterministic tool execution
- run-bound evidence reports

It is not positioned as a chatbot, a generic AI assistant, or a loose demo script.

## Scope Map

| Area | In scope |
|---|---|
| Runtime | Manifest execution, validation, TaskFrame state, tool calls, and evidence capture |
| Demo company | Mock business workflows and seeded demo data |
| UI | Operator, Demo, and Inspector presentation |
| Reports | Run-bound HTML and Markdown evidence |
| Optional integrations | RPA and live external tools outside the default RC path |

## What It Is

- Controlled autonomous business work
- Workflow execution defined by manifests
- Runtime state and audit trail captured in TaskFrame
- Deterministic business validation and approval checkpoints
- Business-readable demo stories and run reports

## What It Is Not

- An open-ended chatbot
- A free-form agent that picks arbitrary tools
- A silent side-effect executor
- A model-certified success system
- A pure RPA bot
- Production-ready unsupervised operation
- Live external automation by default
- Arbitrary LLM tool control
- Use of real customer or supplier data by default

## Architecture Boundary

| Layer | Responsibility |
|---|---|
| `runtime/` | Execute manifests, validate outcomes, persist state, and generate run reports |
| `src/` | Build UI-friendly and demo-friendly view models and render the Tkinter console |
| `tools/` | Provide CLI utilities, verification, and operator support |
| `optional_tools/` | Hold optional integration surfaces that are excluded from the default verification path |
| `bits/` | Contain a separate FastAPI/RAG prototype path |

## Demo And Report Boundary

- `src/demo_story_presenter.py` turns runtime state into a business-readable demo story.
- `runtime/run_report.py` turns persisted run data into an audit-style report and evidence bundle.
- `src/operator_ui.py` renders those models and dispatches actions; it does not invent business meaning.

## Why This Matters

The design shows how AI-assisted workers can operate inside business controls:

- defined procedures
- allowed tools
- validation gates
- approval checkpoints
- evidence trails

That is the product boundary this repository is meant to communicate.


### docs/quickstart.md

# Quickstart Guide

## Purpose

This guide walks you through cloning, installing, and running TaskFrame Runtime for the first time. The full path takes under 5 minutes on a clean machine with Python 3.11+.

---

## Requirements

- Python 3.11 or later
- Git
- A terminal (PowerShell on Windows, bash/zsh on Linux/macOS)
- No Google account, Playwright, Ollama, or browser setup required for the default demo
- The quickstart uses the safe default configuration and does not require live credentials or browser profiles

---

## Windows setup

```powershell
git clone <repo-url>
cd <repo-folder>
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

Verify the install:

```powershell
taskframe version
```

---

## Linux / macOS setup

```bash
git clone <repo-url>
cd <repo-folder>
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify the install:

```bash
taskframe version
```

---

## Run your first demo

```bash
taskframe demo
```

This runs a safe dry-run business scenario. Expected output includes:

- the scenario name
- the final TaskFrame state
- the frame ID
- the report path (if a report was generated)

No live email, message, or sheet write is performed.

---

## Open the UI

```bash
taskframe ui
```

This opens the Operator Demo Console (Tkinter). The normal demo path is:

```
Select demo → Start demo → Review result → Approve dry-run action → Open report
```

If the UI does not open, see the Troubleshooting section below.

---

## Run verification

```bash
taskframe verify
```

This runs the release verification script. It checks:

- imports
- CLI packaging
- manifest health
- tool registry
- scenario pack
- golden demo
- release artifacts

Results are written to `runtime_data/audit/release_candidate_verification.json` and `docs/release_candidate_verification.md`.

---

## Understand dry-run safety

The default install and demo path are dry-run safe.

By default:

- no live emails are sent;
- no live Google Sheets are written;
- no live calendar events are created;
- no browser/RPA tools are launched;
- no live WhatsApp or Google Messages actions are performed;
- LLM calls use the deterministic fake path unless explicitly configured otherwise.

Side-effecting actions (such as sending a customer message) are staged as **pending actions**. They are shown in the UI and the run report, but they are not executed unless an operator explicitly approves live execution — which is disabled in the default demo path.

---

## Optional integrations

The default demo does not require any of these. Install them only if you need live tool integrations.

### Google tools

```bash
pip install -e ".[google]"
```

Required for: Gmail, Google Sheets, Google Calendar tools.

### RPA tools

```bash
pip install -e ".[rpa]"
playwright install
```

Required for: browser-backed automation (Google Messages, WhatsApp Web). Requires local browser profiles and manual authentication. Excluded from the default demo path.

### Development tools

```bash
pip install -e ".[dev]"
python -m pytest
```

Installs test dependencies and runs the full test suite.

---

## Troubleshooting

| Problem | Suggested fix |
|---|---|
| `taskframe` command not found | Ensure the virtual environment is active and `pip install -e .` completed successfully. |
| Tkinter UI does not open | Use `taskframe demo` (CLI) first. Ensure Python was installed with Tkinter support. On Linux, install `python3-tk` via your package manager. |
| Manifest health reports failures | Run `taskframe manifest-health --strict --no-smoke` to see the exact failures. Check the generated manifest health report. |
| Google dependencies missing | Install `pip install -e ".[google]"` only if you are using Google tools. Not needed for the default demo. |
| Playwright missing | Install `pip install -e ".[rpa]"` and run `playwright install` only if using RPA tools. |
| Ollama unavailable | The default demo uses the deterministic fake LLM path. Ollama is optional and not required for `taskframe demo` or `taskframe verify`. |
| Tests fail on import | Ensure the virtual environment is active and `pip install -e ".[dev]"` completed. |


### docs/readiness_scorecard.md

# 90% Readiness Scorecard

## Purpose

This scorecard measures controlled portfolio/demo readiness across the repository. It does not certify production deployment readiness.

## Areas Assessed

- Core Architecture
- Manifest Runtime
- Event Routing
- Business Workflows
- Tooling
- Release Verification
- Production Readiness

## Scoring Rules

- PASS check: full points
- WARN check: half points
- FAIL check: zero points
- NOT_ASSESSED: zero points

Area scores are calculated from weighted checks. The overall score is the average of the seven area scores.

## Release Gate Behaviour

The release gate fails if any area scores below the configured threshold. In strict mode, WARN, FAIL, and NOT_ASSESSED areas are blocking.

## How to Run

```bash
python -m src.taskframe_cli readiness --strict
python -m src.taskframe_cli readiness --json
python -m src.taskframe_cli readiness --strict --open-report
```

## How to Interpret Results

- Overall score should be at or above 90 for the controlled release gate.
- Blocking areas indicate which project areas still need work.
- Report paths point to the generated JSON, Markdown, and HTML artifacts under `runtime_data/readiness/`.

## Known Limitations

This scorecard measures controlled demo and portfolio readiness. It does not certify production deployment readiness.


### docs/release_artifacts.md

# Release Artifacts

This repository uses a deterministic golden demo to produce RC artifacts in `runtime_data/outputs/`.

| Artifact | Path | Created By | Purpose | Required |
|---|---|---|---|---|
| Golden demo summary report | `runtime_data/outputs/reports/golden_demo_report.md` | `scripts/run_golden_demo.py` | Operator-facing release-candidate summary | Yes |
| Golden demo summary HTML | `runtime_data/outputs/reports/golden_demo_report.html` | `scripts/run_golden_demo.py` | Browser-friendly summary view | Yes |
| Golden demo audit JSON | `runtime_data/outputs/audit/golden_demo_audit.json` | `scripts/run_golden_demo.py` | Machine-readable verdict and workflow checks | Yes |
| Customer workflow report | `runtime_data/outputs/reports/customer_workflow_report.md` | `scripts/run_golden_demo.py` | Customer lane evidence | Yes |
| Customer workflow HTML | `runtime_data/outputs/reports/customer_workflow_report.html` | `scripts/run_golden_demo.py` | Browser-friendly customer lane evidence | Yes |
| Customer workflow audit JSON | `runtime_data/outputs/audit/customer_workflow_audit.json` | `scripts/run_golden_demo.py` | Customer lane structured audit trail | Yes |
| Procurement workflow report | `runtime_data/outputs/reports/procurement_workflow_report.md` | `scripts/run_golden_demo.py` | Procurement lane evidence | Yes |
| Procurement workflow HTML | `runtime_data/outputs/reports/procurement_workflow_report.html` | `scripts/run_golden_demo.py` | Browser-friendly procurement lane evidence | Yes |
| Procurement workflow audit JSON | `runtime_data/outputs/audit/procurement_workflow_audit.json` | `scripts/run_golden_demo.py` | Procurement lane structured audit trail | Yes |
| Accounting workflow report | `runtime_data/outputs/reports/accounting_workflow_report.md` | `scripts/run_golden_demo.py` | Accounting lane evidence | Yes |
| Accounting workflow HTML | `runtime_data/outputs/reports/accounting_workflow_report.html` | `scripts/run_golden_demo.py` | Browser-friendly accounting lane evidence | Yes |
| Accounting workflow audit JSON | `runtime_data/outputs/audit/accounting_workflow_audit.json` | `scripts/run_golden_demo.py` | Accounting lane structured audit trail | Yes |


## Order management workflow pack artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Order management doc | `docs/order_management_workflows.md` | Workflow descriptions, tool table, dataset reference |
| Order validate_new manifest | `manifests/order.validate_new.manifest.json` | Manifest for new order validation |
| Order reserve_stock manifest | `manifests/order.reserve_stock.manifest.json` | Manifest for stock reservation |
| Order release_paid manifest | `manifests/order.release_paid.manifest.json` | Manifest for releasing a paid order |
| Order detect_delayed manifest | `manifests/order.detect_delayed.manifest.json` | Manifest for delayed order detection |
| Order update_shipment_status manifest | `manifests/order.update_shipment_status.manifest.json` | Manifest for shipment status updates |

## Google Workspace tool pack artifacts

The release evidence set includes the Google Workspace read-only tool pack descriptor, safety scan, setup guide, and integration-test documentation.

## Cross-workflow demo story pack artifacts

The portfolio demo v2 now produces a consolidated story pack under `runtime_data/demo_packs/<pack_run_id>/story_pack/`.

| Artifact | Path | Purpose |
|---|---|---|
| Story index Markdown | `runtime_data/demo_packs/<pack_run_id>/story_pack/index.md` | Reviewer-facing narrative summary |
| Story index HTML | `runtime_data/demo_packs/<pack_run_id>/story_pack/index.html` | Browser-friendly evidence pack |
| Story summary JSON | `runtime_data/demo_packs/<pack_run_id>/story_pack/summary.json` | Machine-readable story summary |
| Story evidence manifest | `runtime_data/demo_packs/<pack_run_id>/story_pack/evidence_manifest.json` | Linked artifact inventory |
| Workflow timeline | `runtime_data/demo_packs/<pack_run_id>/story_pack/workflow_timeline.json` | Lane-by-lane execution trace |
| Screenshot checklist | `runtime_data/demo_packs/<pack_run_id>/story_pack/screenshots_checklist.md` | Portfolio capture checklist |

## Readiness scorecard artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Readiness scorecard JSON | `runtime_data/readiness/readiness_scorecard.json` | Machine-readable 90% readiness scorecard |
| Readiness scorecard Markdown | `runtime_data/readiness/readiness_scorecard.md` | Reviewer-facing readiness summary |
| Readiness scorecard HTML | `runtime_data/readiness/readiness_scorecard.html` | Browser-friendly readiness view |

## Portfolio evidence pack artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Portfolio pack index Markdown | `runtime_data/portfolio_evidence/<pack_run_id>/index.md` | Public-facing portfolio evidence overview |
| Portfolio pack index HTML | `runtime_data/portfolio_evidence/<pack_run_id>/index.html` | Browser-friendly portfolio evidence overview |
| Portfolio pack summary JSON | `runtime_data/portfolio_evidence/<pack_run_id>/summary.json` | Machine-readable pack summary |
| Architecture summary | `runtime_data/portfolio_evidence/<pack_run_id>/architecture.md` | Architecture explanation for reviewers |
| Demo script | `runtime_data/portfolio_evidence/<pack_run_id>/demo_script.md` | Suggested walkthrough for demos and interviews |
| Tool inventory | `runtime_data/portfolio_evidence/<pack_run_id>/tool_inventory.md` | Tool capability registry summary |
| Workflow proof | `runtime_data/portfolio_evidence/<pack_run_id>/workflow_proof.md` | Workflow evidence and latest-state summary |
| Screenshot checklist | `runtime_data/portfolio_evidence/<pack_run_id>/screenshot_checklist.md` | Review capture checklist |
| Known limitations | `runtime_data/portfolio_evidence/<pack_run_id>/known_limitations.md` | Controlled-demo limitation statement |


### docs/release_candidate_evidence_index.md

# Release Candidate Evidence Index

- Verification JSON: `runtime_data\audit\release_candidate_verification.json`
- Verification Report: `docs\release_candidate_verification.md`
- Known Limitations: `docs\known_limitations.md`
- Current Release Status: `docs\current_release_status.md`
- Release Evidence Pack: `docs\release_evidence_pack.md`
- Runtime Contracts: `docs\runtime_contracts.md`
- Tool Onboarding Guide: `docs\adding_new_tools.md`
- Tool Contract Checklist: `docs\tool_contract_checklist.md`
- Default Demo Boundary: `docs\default_demo_boundary.md`
- README: `README.md`
- Architecture Overview: `docs\architecture_overview.md`
- Architecture Diagram: `docs\architecture_diagram.svg`
- Demo Walkthrough: `docs\demo_walkthrough.md`
- Demo Script: `docs\demo_script.md`
- Portfolio Summary: `docs\portfolio_summary.md`
- Capture Screenshots: `docs\capture_screenshots.md`
- Screenshot Folder: `docs\screenshots`

## Runtime Reports
- runtime_data/runs/frame_1/reports/run_report.md


### docs/release_candidate_verification.md

# Release Candidate Verification Report

## Verdict

- READY_WITH_KNOWN_LIMITATIONS

## Executive Summary

- Generated At: 2026-05-04T00:00:00Z
- Commands Run: 1
- Passed Commands: 1
- Failed Commands: 0
- Skipped Checks: 0

## Environment

- Python: test
- Platform: test
- CWD: test
- Git Commit: abc
- Git Branch: main

## Architecture Claims Verified

| Claim | Evidence |
|---|---|
| TaskFrame-centered runtime | TaskFrame artifacts, reports, evidence bundle |
| Manifest-driven execution | manifests present; workflow tests pass |
| Generic orchestrator | static scan of runtime/orchestrator.py |
| Domain tools externalized | tool registry and workflow tests |
| Bounded LLM use | LLM command tests and fake-path scan |
| Approval-gated side effects | pending/executed action tests |
| Dry-run execution safety | customer/procurement/accounting dry-run tests |
| Multi-workflow generalization | customer, procurement, accounting, cross-workflow tests |
| Portfolio readiness | README, walkthrough, screenshots, demo script, release verification |

## Test Results

- full_pytest: PASS (0)

## Workflow Verification

- customer: PASS

## Static Architecture Checks

- orchestrator_pollution: PASS

## Side-Effect Safety Checks

- side_effect_registry: UNKNOWN

## LLM Safety Checks

- fake_llm_paths: UNKNOWN

## Documentation / Portfolio Asset Checks

- README.md: OK

## Report and Evidence Artifact Checks

- runtime_data/runs/frame_1/reports/run_report.md

## Known Limitations

- example

## Release Blockers

- None

## Evidence Index

- Verification JSON: `runtime_data\audit\release_candidate_verification.json`
- Verification Report: `docs\release_candidate_verification.md`
- Evidence Index: `docs\release_candidate_evidence_index.md`
- Current Release Status: `docs\current_release_status.md`
- Release Evidence Pack: `docs\release_evidence_pack.md`
- Runtime Contracts: `docs\runtime_contracts.md`
- Default Demo Boundary: `docs\default_demo_boundary.md`
- Known Limitations: `docs\known_limitations.md`

## Final Recommendation

The project is READY_WITH_KNOWN_LIMITATIONS.


### docs/release_evidence_pack.md

# Release Evidence Pack

## What Was Verified

- The clean-clone release-candidate path
- The default tool registry and tool capability registry
- The tool onboarding guide and tool contract checklist
- The default scenario pack
- The golden demo workflows
- The contract and boundary documentation
- The optional RPA exclusion boundary

## Where Verifier Outputs Are Stored

- Release verifier JSON: `runtime_data\audit\release_candidate_verification.json`
- Current release status JSON: `runtime_data\audit\release_status_latest.json`
- Release evidence pack JSON: `runtime_data\audit\release_evidence_pack.json`
- Release verifier markdown: `docs\release_candidate_verification.md`
- Current release status markdown: `docs\current_release_status.md`
- Release evidence pack markdown: `docs\release_evidence_pack.md`

## Where Golden Demo Outputs Are Stored

- Golden demo report: `runtime_data\outputs\reports\golden_demo_report.md`
- Golden demo HTML: `runtime_data\outputs\reports\golden_demo_report.html`
- Golden demo audit JSON: `runtime_data\outputs\audit\golden_demo_audit.json`

## Where Report Artifacts Are Stored

- Release artifacts document: `docs\release_artifacts.md`
- Runtime contract doc: `docs\runtime_contracts.md`
- Tool onboarding guide: `docs\adding_new_tools.md`
- Tool contract checklist: `docs\tool_contract_checklist.md`
- Default demo boundary doc: `docs\default_demo_boundary.md`
- Known limitations doc: `docs\known_limitations.md`

## How To Reproduce

```powershell
pytest
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

## Deliberately Excluded From Default RC

- Optional browser-backed RPA tools
- Live WhatsApp/Gmail sending
- Live browser automation
- Unbounded LLM tool choice
- Production credentials
- Real customer and supplier data

## Notes

- Golden demo verdict: READY
- Known limitations count: 1


### docs/runtime_contracts.md

# Runtime Contracts

This document freezes the core runtime shapes that future specs must respect.

## TaskFrame Contract

The canonical TaskFrame is the runtime case file for a single execution. It carries the trigger, parsed inputs, step execution state, outputs, evidence, pending actions, executed actions, validation records, errors, tool calls, LLM calls, audit events, and completion outcome.

### Required Fields

| Field | Purpose | Required | Notes |
|---|---|---|---|
| `frame_id` | Unique runtime task identifier | Yes | Used for reload, approval, and audit |
| `manifest_id` | Selected manifest | Yes | Must not change during a run |
| `state` | Current lifecycle state | Yes | Must be one of the approved runtime states |
| `outputs` | Runtime output pipe | Yes | Later steps read from here |
| `pending_actions` | Staged side effects | Yes | Must require approval |
| `executed_actions` | Approved executed side effects | Yes | Dry-run or live execution record |
| `audit` | Ordered event trail | Yes | Must record significant transitions |

### Canonical Structure

```json
{
  "frame_id": "",
  "manifest_id": "",
  "state": "",
  "trigger": {},
  "raw_input": "",
  "inputs": {},
  "steps": [],
  "current_step_id": "",
  "step_results": [],
  "outputs": {},
  "evidence": [],
  "pending_actions": [],
  "executed_actions": [],
  "validations": [],
  "errors": [],
  "tool_calls": [],
  "llm_calls": [],
  "audit": [],
  "completion_gate_result": {},
  "final_response": ""
}
```

The repo stores step runtime data in `steps`, outputs in `outputs`, evidence in `evidence`, and terminal runtime data in `completion_gate_result` and `final_response`.
Any `step_results` wording in reports should be treated as a derived view over the persisted step runtime data.

### Approved Lifecycle States

`CREATED`, `VALIDATING`, `READY`, `RUNNING`, `WAITING_FOR_INPUT`, `WAITING_FOR_EXECUTE`, `EXECUTING_PENDING`, `VERIFYING`, `COMPLETED`, `COMPLETED_NO_DATA`, `FAILED_VALIDATION`, `FAILED_EXECUTION`, `FAILED_COMPLETION`, `CANCELLED`, `EXPIRED`

## Manifest Contract

A manifest is the instruction plus validation contract for a workflow. No manifest means no execution.

### Required Fields

`manifest_id`, `name`, `version`, `trigger`, `inputs`, `steps`, `validations`, `completion`, `live_execution`

### Step Shape

Each manifest step uses:

`id`, `command`, `when`, `retry`, `timeout_seconds`

### Completion Shape

```json
{
  "success_outputs": ["draft_reply"],
  "success_pending_actions": ["sent_reply"],
  "allow_pending_approval": true,
  "acceptable_empty_outputs": ["unread_mail"]
}
```

The orchestrator executes the manifest; it does not invent new business logic.

## Event Route Contract

Event routes bind an explicit event to a manifest. Events do not execute directly.

### Required Fields

`route_id`, `source`, `event_type`, `manifest_id`, `input_map`, `enabled`

### Rule

Events resolve to manifests. Manifests create TaskFrames. TaskFrames drive execution.

## ToolResult Contract

Tools return structured results. The orchestrator records tool calls, and the LLM does not execute tools directly.

### Standard Shape

`ok`, `type`, `data`, `evidence`, `error`, `metadata`, `raw`

The result must be machine-readable and audit-friendly. The runtime stores tool call records separately from tool outputs.

## Tool Contract

Tools are deterministic capability adapters.

A tool must be registered, health-checkable, and callable only through manifest-defined steps. Tool calls are recorded in `TaskFrame.tool_calls`.

Side-effect tools must stage `PendingAction` records before execution. Live side effects require approval, manifest allowlist, tool allowlist, runtime live mode, and guardrail success.

See [Adding New Tools](adding_new_tools.md) for the onboarding flow and [Tool Contract Checklist](tool_contract_checklist.md) for the copy/paste checklist used in future specs.

## PendingAction Contract

Pending actions stage side effects before execution.

### Standard Shape

`action_id`, `step_id`, `tool`, `namespace`, `action`, `action_type`, `output_alias`, `args`, `body`, `status`, `side_effect`, `requires_approval`, `created_at`, `approved_by`, `approved_at`, `approval_reason`, `rejected_by`, `rejected_at`, `rejection_reason`, `executed_at`, `dry_run`, `live`, `live_side_effect`, `guardrail`, `result_type`, `last_error`

### Approved Statuses

`PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `EXECUTING`, `EXECUTED`, `FAILED`

Side effects must be staged before execution. Approval changes PendingAction status. Execution changes PendingAction status and writes `executed_actions`.

## LLM Call Contract

The LLM is a bounded helper, not a controller.

### Allowed Roles

`extract`, `classify`, `summarise`, `draft`, `compare`, `explain exception`

### Forbidden Roles

`choose arbitrary tools`, `invent workflow`, `self-certify completion`, `execute side effects`, `override manifest scope`, `silently change task scope`

### Record Shape

The repo records LLM calls with fields such as `step_id`, `action`, `prompt`, `system`, `raw_output`, `parsed_output`, `ok`, `error`, `provider`, `model`, and `timestamp`. In spec language these correspond to the raw and parsed response fields. Some adapters also include `error_type`, `args`, `result_type`, and `output_alias`.

## Live Execution Policy Contract

Live execution requires all of the following:

- `runtime_live_mode` must be true
- `ToolRunner` must not be in dry-run mode
- the TaskFrame must be in an executable approval state
- the PendingAction must be `APPROVED`
- the manifest must allow the tool
- the tool registry must allow live side effects
- the guardrail must pass
- the audit trail must record policy and guardrail checks

Default RC must not execute live side effects.


### docs/runtime_tool_governance.md

# Runtime Tool Governance

Runtime governance is the execution-time policy layer that sits between tool discovery and tool invocation.

Discovery tells the operator that a tool exists.
Governance decides whether that tool may execute in the current runtime environment.

## Runtime environment model

Supported environments:

- `demo`
- `dev`
- `test`
- `release`
- `live`

Resolution order:

1. explicit runtime engine / tool runner argument
2. `TASKFRAME_ENV`
3. `config/runtime_profile.json`
4. fallback to `demo`

## Decision model

The runtime evaluates each tool call and returns one of:

- `ALLOW`
- `WARN`
- `BLOCK`

Blocked calls fail safely with a canonical `ToolResult` and a TaskFrame audit event.

## What is checked

Governance is checked before:

- normal tool execution
- pending action staging
- pending action execution
- live health probes
- external toolpack execution

## Core rules

- Built-in core tools are allowed in `demo` unless another safety gate fails.
- Optional packs must be explicitly enabled for the environment.
- Blocked packs stay blocked in every environment.
- High-risk and experimental packs are blocked in safe-release environments.
- Live side effects require both approval and a runtime policy that allows them.

## Pending actions

Pending actions carry governance metadata so the runtime can re-check policy before execution.

If policy changes after staging, execution fails safely instead of silently proceeding.

## Health probes

Health probes are not exempt from governance.

Live probes are only allowed when the pack is enabled and the runtime policy permits them.

Optional RPA probes remain excluded from the default release-candidate path.

## Troubleshooting blocked tools

When a tool is blocked:

1. check the runtime environment
2. check the pack governance policy
3. check whether the pack is enabled for that environment
4. check whether the call requests live side effects
5. inspect the TaskFrame audit record

Discovery is not execution permission. A discovered tool can still be blocked by runtime governance.


### docs/safety_verification.md

# Safety Verification

TaskFrame Runtime enforces a layered safety model. This document describes the safety claims, how they are verified, and where evidence is recorded.

---

## Safety claims

The safety verification pack checks nine claims that together establish the dry-run default and live-execution safety boundary.

| # | Claim | How verified |
|---|---|---|
| 1 | Default demo produces no live side effects | Demo scenario runs; run report inspected for side-effect actions |
| 2 | Side-effect tools stage pending actions | Tool registry inspected for `requires_approval` on all side-effect tools |
| 3 | Approval is required before execution | Pending action state machine and live-execution guardrail source inspected |
| 4 | Dry-run execution is auditable | Run report and audit artefact presence checked |
| 5 | Live execution is blocked by default | `TASKFRAME_ENABLE_LIVE_EXECUTION` not set in default environment |
| 6 | Manifest policy blocks live execution | Manifests scanned for `live_execution.enabled=true` (zero expected) |
| 7 | Tool policy blocks live side effects | Tool registry inspected for `allow_live_side_effect=False` on all side-effect tools |
| 8 | CLI live-execution guardrails are enforced | `execute-approved --live` path requires env var, flag, and typed confirmation phrase |
| 9 | Optional RPA tools are excluded from the default path | `rpa_google_messages.excluded_from_default_release=True` in tool capability registry |

---

## Running the safety verification pack

```bash
taskframe safety-pack
```

Options:

| Flag | Meaning |
|---|---|
| `--no-demo` | Use static analysis only; skip demo scenario runs |
| `--runtime-data-dir <dir>` | Override runtime data directory (default: `runtime_data`) |
| `--manifest-dir <dir>` | Override manifests directory (default: `manifests`) |
| `--json` | Print full JSON pack to stdout |

---

## Output files

After running `taskframe safety-pack`, the following artefacts are written:

| File | Purpose |
|---|---|
| `runtime_data/safety_verification/safety_verification_pack.json` | Machine-readable full pack |
| `runtime_data/safety_verification/safety_verification_pack.md` | Human-readable summary |
| `runtime_data/safety_verification/live_blocked_evidence.json` | Live-blocked evidence JSON |
| `runtime_data/safety_verification/live_blocked_evidence.md` | Live-blocked evidence Markdown |
| `runtime_data/safety_verification/dry_run_evidence.json` | Dry-run evidence JSON |
| `runtime_data/safety_verification/dry_run_evidence.md` | Dry-run evidence Markdown |
| `docs/safety_verification_pack.md` | Copy of the summary in docs/ |
| `docs/live_blocked_evidence_report.md` | Copy of the live-blocked evidence in docs/ |

---

## Live-blocked evidence report

The live-blocked evidence report (`docs/live_blocked_evidence_report.md`) records six checks:

| Check | What it verifies |
|---|---|
| `runtime_live_disabled` | `TASKFRAME_ENABLE_LIVE_EXECUTION` is not set |
| `manifest_live_disabled` | No manifest has `live_execution.enabled=true` |
| `tool_live_blocked` | All side-effect tools block live execution by policy |
| `pending_action_not_approved` | Unapproved pending actions cannot proceed to execution |
| `wrong_confirmation_blocked` | A wrong typed confirmation phrase blocks live execution |
| `optional_rpa_excluded` | RPA tools are excluded from the default tool path |

---

## Expected result

In the default repository state (no environment overrides, default manifests, default tool registry):

- All 9 claims PASS.
- Live-blocked evidence shows 6 checks PASS.
- The overall status is `PASS`.

If any claim fails, the pack lists it in the `blockers` field and exits non-zero.

---

## Relationship to release verification

`taskframe verify` calls the release verifier, which includes a `safety_verification_pack` check. The release verifier expects:

- `taskframe safety-pack --json` exits 0 with `"ok": true`.
- `docs/safety_verification_pack.md` exists.
- `docs/live_blocked_evidence_report.md` exists.

If the safety pack fails, the release verification verdict is `BLOCKED`.

---

## Architecture note

The safety boundary is enforced at multiple independent layers:

1. **Environment** — `TASKFRAME_ENABLE_LIVE_EXECUTION` must be `1`.
2. **Pending action state** — action must be `APPROVED` before execution proceeds.
3. **Manifest policy** — `live_execution.enabled` must be `true` in the manifest.
4. **Tool policy** — tool spec must have `allow_live=True` and `allow_live_side_effect=True`.
5. **CLI guardrail** — `--live --i-understand-live-side-effects --confirm "<phrase>"` must all match.

All five must be satisfied simultaneously. A failure at any layer blocks live execution without affecting dry-run safety.

See [docs/live_execution_safety.md](live_execution_safety.md) for the full live-execution boundary specification.


### docs/safety_verification_pack.md

# Safety Verification Pack

## Verdict

**PASS**

Generated: 2026-05-19T18:39:28.718331Z

## Summary

- Claims checked: 9
- Claims passed: 9
- Claims failed: 0

## Claims

| Claim | Status | Evidence |
|---|---|---|
| default_demo_no_live_side_effects | PASS | Runtime default_mode='dry_run', live_execution_env_enabled=False. Default demo cannot perform live side effects. |
| side_effects_stage_pending_actions | PASS | Tool registry has 24 side-effect tool(s), 24 require approval. Side effects must be staged as pending actions. |
| approval_required_before_execution | PASS | Pending action state machine: PENDING_APPROVAL → APPROVED → EXECUTING → EXECUTED. Live execution blocked unless action i |
| dry_run_execution_auditable | PASS | Golden demo audit exists with verdict='READY'. Dry-run execution is auditable. |
| live_execution_blocked_by_default | PASS | TASKFRAME_ENABLE_LIVE_EXECUTION not set. default_mode='dry_run'. Live execution is blocked by default. |
| manifest_policy_blocks_live_execution | PASS | All 60 manifest(s) have live_execution.enabled=false or unset. Manifest policy blocks live execution. |
| tool_policy_blocks_live_side_effects | PASS | 24 side-effect tool(s) all have live side-effects blocked or require approval. Tool policy enforces the safety boundary. |
| cli_live_guardrails_enforced | PASS | TASKFRAME_ENABLE_LIVE_EXECUTION not set. CLI has live guardrails (--i-understand-live-side-effects, --confirm): True. |
| optional_rpa_excluded_from_default_path | PASS | rpa_google_messages: core_or_optional=optional, excluded_from_default_release=True, rpa_live_probe_required=True. Option |

## Safety Statement

The default portfolio demo is dry-run only. It stages side effects as pending actions
and proves that live execution is blocked unless explicit runtime, manifest, tool,
approval, guardrail, and confirmation checks pass.

No live side effects were performed.


### docs/screenshots/.gitkeep



### docs/spec_054_legacy_customer_failures.md

# Spec 054 Legacy Customer Failures

## Event Workflow Demo Pack

- `tests/test_event_workflow_demo_pack.py::EventWorkflowDemoPackTests::test_demo_does_not_execute_pending_action`
  - Reason: legacy demo runner hit an outdated customer path without test-only LLM injection.
  - Legacy path used: `src/operator_demo_runner.py` selection `customer_message_status_check`.
  - Replacement/current path: tool-driven customer workflow with pytest-gated fake LLM adapter.
  - Decision: migrate.

- `tests/test_event_workflow_demo_pack.py::EventWorkflowDemoPackTests::test_demo_runner_completes_successfully`
  - Reason: same legacy demo path.
  - Legacy path used: `src/operator_demo_runner.py` selection `customer_message_status_check`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.

- `tests/test_event_workflow_demo_pack.py::EventWorkflowDemoPackTests::test_taskframe_state_and_pending_action_remain`
  - Reason: same legacy demo path.
  - Legacy path used: `src/operator_demo_runner.py` selection `customer_message_status_check`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.

## LLM Manifest Execution

- `tests/test_llm_manifest_execution.py::LLMManifestExecutionTests::test_llm_customer_status_reply_manifest_completes_with_fake_adapter`
  - Reason: `llm.customer_status_reply` still referenced an obsolete `customer/order_context` argument shape.
  - Legacy path used: `manifests/llm_customer_status_reply.manifest.json`.
  - Replacement/current path: tool-driven customer lookups plus current order context build.
  - Decision: migrate.

## Customer Workflow

- `tests/test_customer_message_workflow.py::CustomerMessageWorkflowTests::test_missing_order_id_fails_validation`
  - Reason: legacy customer workflow resolved through outdated manifest shape.
  - Legacy path used: `customer.message_status_check`.
  - Replacement/current path: current tool-driven manifest with deterministic order ref extraction.
  - Decision: migrate.

- `tests/test_customer_message_workflow.py::CustomerMessageWorkflowTests::test_unknown_order_fails_validation`
  - Reason: same legacy path.
  - Legacy path used: `customer.message_status_check`.
  - Replacement/current path: current tool-driven manifest.
  - Decision: migrate.

- `tests/test_customer_message_workflow.py::CustomerMessageWorkflowTests::test_workflow_creates_draft_and_pending_action`
  - Reason: same legacy path.
  - Legacy path used: `customer.message_status_check`.
  - Replacement/current path: current tool-driven manifest.
  - Decision: migrate.

- `tests/test_customer_message_workflow.py::CustomerMessageWorkflowTests::test_wrong_customer_fails_validation`
  - Reason: same legacy path.
  - Legacy path used: `customer.message_status_check`.
  - Replacement/current path: current tool-driven manifest.
  - Decision: migrate.

## Negative Customer Scenarios

- `tests/test_negative_customer_status_scenarios.py::NegativeCustomerStatusScenarioTests::test_unsupported_intent_fails_before_order_status_reply`
  - Reason: legacy negative customer flow still used old demo/manifest shape.
  - Legacy path used: `customer.message_status_check`.
  - Replacement/current path: current tool-driven manifest with validation-based failure.
  - Decision: migrate.

## Operator Demo Execution

- `tests/test_operator_demo_execution.py::OperatorDemoExecutionTests::test_demo_run_reaches_pending_approval`
  - Reason: demo runner was not aligned with the current customer workflow path.
  - Legacy path used: `src/operator_demo_runner.py`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.

- `tests/test_operator_demo_execution.py::OperatorDemoExecutionTests::test_demo_runner_executes_customer_status_demo_dry_run`
  - Reason: same legacy demo path.
  - Legacy path used: `src/operator_demo_runner.py`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.

- `tests/test_operator_demo_execution.py::OperatorDemoExecutionTests::test_snapshot_after_demo_run_preserves_pending_action_state`
  - Reason: same legacy demo path.
  - Legacy path used: `src/operator_demo_runner.py`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.

- `tests/test_operator_demo_execution.py::OperatorDemoExecutionTests::test_staged_whatsapp_demo_returns_pending_action_pack`
  - Reason: same legacy demo path.
  - Legacy path used: `src/operator_demo_runner.py`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.


### docs/supplier_invoice_matching_workflow.md

# Supplier Invoice Matching Workflow

This workflow implements a deterministic three-way match between:

- supplier invoice
- purchase order
- goods receipt

It is designed for accounting operations where invoices must be checked before any ledger posting is staged.

## Flow

1. Read the invoice.
2. Read the purchase order.
3. Read receipts for the PO.
4. Check for duplicate invoice number.
5. Run deterministic three-way matching.
6. Draft a bounded exception summary with the LLM helper.
7. Build the exception report.
8. Stage match-run write rows.
9. Stage ledger rows only when the invoice matches.

## Tool set

- `supplier_invoice/read`
- `po/read`
- `receipt/read_by_po`
- `supplier_invoice/check_duplicate`
- `supplier_invoice/match_three_way`
- `draft_supplier_invoice_exception_summary`
- `supplier_invoice/build_exception_report`
- `supplier_invoice/prepare_match_run_write`
- `supplier_invoice/prepare_ledger_write`
- `supplier_invoice/execute_ledger_write`

## Exception codes

Common deterministic exception codes include:

- `PO_NOT_FOUND`
- `RECEIPT_NOT_FOUND`
- `SUPPLIER_MISMATCH`
- `UNKNOWN_SKU`
- `QUANTITY_MISMATCH`
- `RECEIPT_MISMATCH`
- `PRICE_MISMATCH`
- `LINE_TOTAL_MISMATCH`
- `TAX_MISMATCH`
- `TOTAL_MISMATCH`
- `DUPLICATE_INVOICE`

## Approval and dry-run behaviour

- Match-run and ledger writes are approval-gated.
- No live writes are performed.
- Dry-run execution stages pending actions and produces an evidence bundle.
- Exception invoices stage the match-run write but do not stage ledger posting.

## Evidence expectations

The report bundle should include:

- invoice record
- purchase order record
- receipt record(s)
- duplicate check
- deterministic match result
- exception report
- staged pending actions
- dry-run approval/execution output

## Known limitation

This workflow is intentionally dry-run only. It does not post to a live ledger.


### docs/tool_contract_checklist.md

# Tool Contract Checklist

## Tool identity

- [ ] Tool has a clear namespace/action.
- [ ] Tool performs one capability.
- [ ] Tool name does not imply broader orchestration than it performs.

## Risk classification

- [ ] Tool is classified as read-only, transform, prepare, side-effect, live side-effect, or optional/high-risk.
- [ ] Side-effect classification is conservative.
- [ ] Optional/RPA status is explicitly stated.

## Implementation

- [ ] Tool function accepts explicit arguments.
- [ ] Tool function does not mutate TaskFrame directly.
- [ ] Tool function does not call orchestrator.
- [ ] Tool function does not select other tools.
- [ ] Tool function returns structured data.

## Registry

- [ ] Tool is registered in `TOOL_REGISTRY`.
- [ ] If the tool is external, it is described by `toolpack.json` and enabled through configuration.
- [ ] If the tool is a migrated built-in tool, it is also represented by a core tool pack and covered by the compatibility registry.
- [ ] `required_args` are complete.
- [ ] `optional_args` are complete.
- [ ] `arg_types` are defined where coercion is needed.
- [ ] `output_type` is specific.
- [ ] `side_effect` is correct.
- [ ] `requires_approval` is correct.
- [ ] Live flags are correct.

## Capability status

- [ ] Tool has capability registry metadata.
- [ ] Tool has category.
- [ ] Tool has core or optional flag.
- [ ] Tool has auth requirement.
- [ ] Tool has limitations.
- [ ] Tool appears in operator tool status.

## Health and setup

- [ ] Tool has a safe health check.
- [ ] Health check avoids live side effects.
- [ ] Health check returns structured status.
- [ ] Setup instructions exist.
- [ ] Safe setup does not mutate external systems.

## Manifest use

- [ ] Tool is used only through manifest steps.
- [ ] Manifest command uses explicit output alias.
- [ ] Required prior outputs are validated.
- [ ] Completion contract matches tool behavior.
- [ ] Side-effect tools create `PendingAction` records.

## Live execution

- [ ] Live execution is blocked by default.
- [ ] Live side effect has explicit guardrail if enabled.
- [ ] Manifest allowlist is required for live execution.
- [ ] Approval is required before execution.
- [ ] Tests cover blocked live execution.

## Scaffold and contract test harness

- [ ] Pack was generated with `taskframe tools scaffold` or follows the same layout.
- [ ] `taskframe tools validate` exits 0 with no errors.
- [ ] `taskframe tools test` exits 0 with `ok: true` and `status: PASS`.
- [ ] Generated contract tests in `tests/test_{id}_contract.py` pass.
- [ ] Generated health tests in `tests/test_{id}_health.py` pass.
- [ ] Generated tool tests in `tests/test_{id}_tools.py` pass.
- [ ] Example manifest in `examples/` validates in manifest smoke check.

## Tests

- [ ] Registry test added.
- [ ] Argument validation test added.
- [ ] Dry-run test added.
- [ ] Side-effect staging test added if relevant.
- [ ] Health check test added.
- [ ] Setup instruction test added.
- [ ] Optional boundary test added if optional.
- [ ] Release verifier impact considered.

## Documentation

- [ ] Tool is documented.
- [ ] Operator setup notes are documented.
- [ ] Known limitations are documented.
- [ ] Default RC inclusion or exclusion is documented.


## Google Workspace read-only checklist

- `toolpack.json` exists and validates.
- All tools are `side_effect: false`.
- All tools are `requires_approval: false`.
- All tools are `allow_live_side_effect: false`.
- No executable `.py` file contains write/send/delete API calls.


### docs/tool_inventory.md

# Tool Inventory Report

Generated: 2026-05-19T18:59:39Z

Report JSON: runtime_data/tool_inventory/tool_inventory.json
Report Markdown: runtime_data/tool_inventory/tool_inventory.md

## Summary

| Metric | Count |
|---|---:|
| Total tools | 113 |
| Migrated tool-pack tools | 4 |
| Legacy fallback tools | 109 |
| External enabled tools | 0 |
| Total tool packs | 2 |
| Optional disabled tools | 10 |
| Side-effect tools | 24 |
| Live side-effect allowed | 0 |

## Tools

| Tool | Source | Pack | Side Effect | Requires Approval | Live Side Effect | Output Type |
|---|---|---|---:|---:|---:|---|
| acct/build_recon_sheet_rows | legacy_fallback |  | no | no | no | recon_sheet_rows |
| acct/load_invoices | legacy_fallback |  | no | no | no | accounting_invoices |
| acct/load_ledger | legacy_fallback |  | no | no | no | accounting_ledger |
| acct/load_orders | legacy_fallback |  | no | no | no | accounting_orders |
| acct/load_payments | legacy_fallback |  | no | no | no | accounting_payments |
| business/get_order_context | migrated_toolpack | core_business | no | no | no | business_order_context |
| cal/create | legacy_fallback |  | yes | yes | no | calendar_create_result |
| cal/next | legacy_fallback |  | no | no | no | calendar_event_list |
| cal/remove | legacy_fallback |  | yes | yes | no | calendar_remove_result |
| cal/search | legacy_fallback |  | no | no | no | calendar_event_list |
| customer/build_status_context | legacy_fallback |  | no | no | no | status_context |
| customer/extract_order_ref | legacy_fallback |  | no | no | no | order_ref_result |
| customer/order_context | legacy_fallback |  | no | no | no | order_context_result |
| customer/prepare_message_action | legacy_fallback |  | yes | yes | no | customer_message_action |
| customer/read | legacy_fallback |  | no | no | no | customer_read_result |
| customer/search | legacy_fallback |  | no | no | no | customer_list |
| customer/validate_owns_order | legacy_fallback |  | no | no | no | ownership_check |
| customer/validate_status_reply | legacy_fallback |  | no | no | no | reply_validation |
| file/exists | legacy_fallback |  | no | no | no | file_exists_result |
| file/list | legacy_fallback |  | no | no | no | file_list_result |
| file/read_json | legacy_fallback |  | no | no | no | file_read_json_result |
| file/write_json | legacy_fallback |  | yes | yes | no | file_write_json_result |
| g/check | legacy_fallback |  | no | no | no | gmail_check_result |
| g/send | legacy_fallback |  | yes | yes | no | gmail_send_result |
| gb/book | legacy_fallback |  | yes | yes | no | gobook_booking_result |
| gb/cancel | legacy_fallback |  | yes | yes | no | gobook_cancel_result |
| gb/list | legacy_fallback |  | no | no | no | gobook_booking_list |
| gb/open_courts | legacy_fallback |  | no | no | no | gobook_open_court_list |
| inventory/filter_reorder_candidates | legacy_fallback |  | no | no | no | reorder_candidates |
| inventory/read | legacy_fallback |  | no | no | no | inventory_record |
| inventory/search_low_stock | legacy_fallback |  | no | no | no | low_stock_result |
| invoiceops/build_evidence_bundle | legacy_fallback |  | no | no | no | invoiceops_report |
| invoiceops/build_exception_action_plan | legacy_fallback |  | no | no | no | invoiceops_exception_action_plan |
| invoiceops/build_exception_report | legacy_fallback |  | no | no | no | invoiceops_report |
| invoiceops/build_ledger_posting_summary | legacy_fallback |  | no | no | no | invoiceops_report |
| invoiceops/build_match_report | legacy_fallback |  | no | no | no | invoiceops_report |
| invoiceops/build_rollback_summary | legacy_fallback |  | no | no | no | invoiceops_report |
| invoiceops/check_duplicate_invoice | legacy_fallback |  | no | no | no | invoiceops_match_check |
| invoiceops/check_tax | legacy_fallback |  | no | no | no | invoiceops_match_check |
| invoiceops/check_totals | legacy_fallback |  | no | no | no | invoiceops_match_check |
| invoiceops/classify_exceptions | legacy_fallback |  | no | no | no | invoiceops_exception_classification |
| invoiceops/extract_invoice_fields | legacy_fallback |  | no | no | no | invoiceops_invoice |
| invoiceops/lookup_goods_receipt | legacy_fallback |  | no | no | no | invoiceops_match_check |
| invoiceops/lookup_purchase_order | legacy_fallback |  | no | no | no | invoiceops_match_check |
| invoiceops/match_three_way | legacy_fallback |  | no | no | no | invoiceops_match_result |
| invoiceops/prepare_exception_register_write | legacy_fallback |  | no | no | no | invoiceops_prepared_write |
| invoiceops/prepare_invoice_register_write | legacy_fallback |  | no | no | no | invoiceops_prepared_write |
| invoiceops/prepare_ledger_write | legacy_fallback |  | no | no | no | invoiceops_prepared_write |
| invoiceops/prepare_match_register_write | legacy_fallback |  | no | no | no | invoiceops_prepared_write |
| invoiceops/prepare_rollback_plan | legacy_fallback |  | no | no | no | invoiceops_rollback_plan |
| invoiceops/read_exception_register | legacy_fallback |  | no | no | no | invoiceops_sheet_rows |
| invoiceops/read_invoice_file | legacy_fallback |  | no | no | no | invoiceops_raw_invoice_text |
| invoiceops/read_invoice_register | legacy_fallback |  | no | no | no | invoiceops_sheet_rows |
| invoiceops/read_ledger | legacy_fallback |  | no | no | no | invoiceops_sheet_rows |
| invoiceops/read_po_register | legacy_fallback |  | no | no | no | invoiceops_sheet_rows |
| invoiceops/read_receipt_register | legacy_fallback |  | no | no | no | invoiceops_sheet_rows |
| invoiceops/read_supplier_master | legacy_fallback |  | no | no | no | invoiceops_sheet_rows |
| invoiceops/search_po_fallback | legacy_fallback |  | no | no | no | invoiceops_fallback_result |
| invoiceops/search_receipt_fallback | legacy_fallback |  | no | no | no | invoiceops_fallback_result |
| invoiceops/search_supplier_fallback | legacy_fallback |  | no | no | no | invoiceops_fallback_result |
| invoiceops/validate_invoice_fields | legacy_fallback |  | no | no | no | invoiceops_invoice_validation |
| memory/set | migrated_toolpack | core_memory | yes | yes | no | memory_set_result |
| message/validate_customer_status_reply | legacy_fallback |  | no | no | no | reply_validation |
| message/validate_supplier_reorder_message | legacy_fallback |  | no | no | no | supplier_message_validation |
| messages/read_recent | legacy_fallback |  | no | no | no | messages_read_recent_result |
| order/check_payment_status | legacy_fallback |  | no | no | no | order_payment_status_result |
| order/detect_delayed_orders | legacy_fallback |  | no | no | no | delayed_orders_result |
| order/execute_release_paid_order | legacy_fallback |  | yes | yes | no | order_release_execution_result |
| order/execute_shipment_status_update | legacy_fallback |  | yes | yes | no | shipment_update_execution_result |
| order/execute_stock_reservation | legacy_fallback |  | yes | yes | no | stock_reservation_execution_result |
| order/extract_ref_from_text | legacy_fallback |  | no | no | no | order_ref_lookup |
| order/items_list | legacy_fallback |  | no | no | no | order_item_list |
| order/prepare_release_paid_order | legacy_fallback |  | yes | yes | no | order_release_prepare_result |
| order/prepare_shipment_status_update | legacy_fallback |  | yes | yes | no | shipment_update_prepare_result |
| order/prepare_stock_reservation | legacy_fallback |  | yes | yes | no | stock_reservation_prepare_result |
| order/read | legacy_fallback |  | no | no | no | order_read_result |
| order/search | legacy_fallback |  | no | no | no | order_list |
| order/validate_new | legacy_fallback |  | no | no | no | order_validation_result |
| order_context/build | legacy_fallback |  | no | no | no | order_context_build_result |
| payment/read_by_order | legacy_fallback |  | no | no | no | payment_record |
| po/build_draft | legacy_fallback |  | no | no | no | draft_po |
| po/check_duplicate_open | legacy_fallback |  | no | no | no | duplicate_po_check |
| po/read | legacy_fallback |  | no | no | no | purchase_order_result |
| po/validate_draft | legacy_fallback |  | no | no | no | po_validation |
| purchase_order/search_open_by_sku | legacy_fallback |  | no | no | no | purchase_order_list |
| q/extract_order_ref | migrated_toolpack | core_llm_micro | no | no | no | order_ref_result |
| receipt/read_by_po | legacy_fallback |  | no | no | no | goods_receipt_result |
| recon/match_payments | legacy_fallback |  | no | no | no | reconciliation_result |
| recon/validate_result | legacy_fallback |  | no | no | no | reconciliation_validation |
| report/generate | migrated_toolpack | core_reports | no | no | no | report_result |
| sheet/create | legacy_fallback |  | yes | yes | yes | sheet_create_result |
| sheet/prepare_write_rows | legacy_fallback |  | yes | yes | no | sheet_write_rows_pending |
| sheet/read | legacy_fallback |  | no | no | no | sheet_rows |
| sheet/read_range | legacy_fallback |  | no | no | no | sheet_read_range_result |
| sheet/write | legacy_fallback |  | yes | yes | yes | sheet_write_result |
| sheet/write_rows | legacy_fallback |  | yes | yes | yes | sheet_write_rows_result |
| shipment/read | legacy_fallback |  | no | no | no | shipment_read_result |
| supplier/prepare_message_action | legacy_fallback |  | yes | yes | no | supplier_message_pending_action |
| supplier/read | legacy_fallback |  | no | no | no | supplier_record |
| supplier/search_active | legacy_fallback |  | no | no | no | supplier_list |
| supplier/select_for_sku | legacy_fallback |  | no | no | no | selected_supplier |
| supplier/send_message | legacy_fallback |  | yes | yes | no | supplier_send_result |
| supplier_invoice/build_exception_report | legacy_fallback |  | no | no | no | supplier_invoice_exception_report_result |
| supplier_invoice/check_duplicate | legacy_fallback |  | no | no | no | supplier_invoice_duplicate_check_result |
| supplier_invoice/execute_ledger_write | legacy_fallback |  | yes | yes | no | supplier_invoice_ledger_write_execution_result |
| supplier_invoice/match_three_way | legacy_fallback |  | no | no | no | supplier_invoice_match_result |
| supplier_invoice/prepare_ledger_write | legacy_fallback |  | yes | yes | no | supplier_invoice_ledger_write_prepare_result |
| supplier_invoice/prepare_match_run_write | legacy_fallback |  | yes | yes | no | supplier_invoice_match_write_prepare_result |
| supplier_invoice/read | legacy_fallback |  | no | no | no | supplier_invoice_result |
| test/echo | legacy_fallback |  | no | no | no | test_echo_result |
| wa/read | legacy_fallback |  | no | no | no | whatsapp_messages |
| wa/search | legacy_fallback |  | no | no | no | whatsapp_search_result |
| wa/send | legacy_fallback |  | yes | yes | no | whatsapp_send_result |

## Tool Packs

| Tool Pack | Status | Environments | Classification | Tool Count | Last Check | Lifecycle Report |
|---|---|---|---|---:|---|---|
| demo_echo | UNTESTED | demo, dev, test | optional | 3 | 2026-05-19T18:59:39Z | runtime_data/toolpacks/lifecycle/demo_echo_lifecycle.md |
| google_workspace | UNTESTED | dev, test | optional | 7 | 2026-05-19T18:59:39Z | runtime_data/toolpacks/lifecycle/google_workspace_lifecycle.md |


### docs/tool_result_contract.md

# Tool Result Contract

Every executed tool call should normalize to a canonical runtime result:

This document defines the canonical result shape used inside the runtime.

```json
{
  "ok": true,
  "type": "example_result",
  "data": {},
  "evidence": {
    "tool": "namespace/action",
    "mode": "dry_run",
    "source": "builtin",
    "operation": "read",
    "input_refs": [],
    "output_ref": "example_output"
  },
  "error": "",
  "metadata": {
    "tool": "namespace/action",
    "source": "builtin",
    "mode": "dry_run"
  }
}
```

## Evidence Shape

Evidence is a dictionary, not a list. The minimum fields are:

- `tool`
- `mode`
- `source`
- `operation`
- `input_refs`
- `output_ref`

Safe additions for read-only tools include values such as `query` and `record_count`.

For staged side effects, evidence should include values such as `pending_action_id`, `requires_approval`, and `live_executed`.

For failures, evidence should include `failure_stage` and a safe error code, not secrets or raw credentials.

## Examples

Read-only example:

```json
{
  "ok": true,
  "type": "sheets_range_values",
  "data": {"rows": [["A1"]], "row_count": 1},
  "evidence": {
    "tool": "sheet/read",
    "mode": "dry_run",
    "source": "builtin",
    "operation": "read",
    "input_refs": ["spreadsheet_id=demo"],
    "output_ref": "sheet_rows",
    "record_count": 1
  },
  "error": "",
  "metadata": {"tool": "sheet/read", "mode": "dry_run", "source": "builtin"}
}
```

Staged side-effect example:

```json
{
  "ok": true,
  "type": "pending_action",
  "data": {"action_id": "pa_123"},
  "evidence": {
    "tool": "wa/send",
    "mode": "dry_run",
    "source": "builtin",
    "operation": "prepare",
    "input_refs": ["chat=Cornelia"],
    "output_ref": "sent_msg",
    "pending_action_id": "pa_123",
    "requires_approval": true,
    "live_executed": false
  },
  "error": "",
  "metadata": {"tool": "wa/send", "mode": "dry_run", "source": "builtin"}
}
```

Failure example:

```json
{
  "ok": false,
  "type": "sheet_rows",
  "data": {},
  "evidence": {
    "tool": "sheet/read",
    "mode": "dry_run",
    "source": "builtin",
    "operation": "read",
    "input_refs": ["spreadsheet_id=demo"],
    "output_ref": "sheet_rows",
    "failure_stage": "auth_check",
    "safe_error_code": "GOOGLE_AUTH_NOT_CONFIGURED"
  },
  "error": "GOOGLE_AUTH_NOT_CONFIGURED",
  "metadata": {"tool": "sheet/read", "mode": "dry_run", "source": "builtin"}
}
```

## Redaction Rules

- Do not place tokens, credentials, or raw secrets in evidence.
- Do not store full personal message bodies in evidence.
- Prefer IDs, counts, aliases, and safe summaries.

## TaskFrame Audit

The runtime writes tool calls into the TaskFrame with the tool key, result type, ok/error state, input summary, dry-run/live mode, source, and an evidence reference.

The contract runner and release verifier both use this contract as a release gate.


### docs/toolpack_authoring_guide.md

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


### docs/toolpack_contract.md

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


### docs/toolpack_contract_testing.md

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


### docs/toolpack_examples.md

# Tool Pack Examples

## Safe demo pack

The repository includes `tool_packs/demo_echo/` as a safe example.

It provides:

- `echo/echo`
- `echo/summarize_args`
- `echo/fail`

## Example manifest step

```text
[t:echo/echo -> echoed] message="Hello"
```

## Example discovery output

```text
taskframe tools discover
Tool pack discovery:
Enabled count: 1
Registered tool count: 0
```

## Example validation output

```text
taskframe tools validate tool_packs/demo_echo/toolpack.json
Status: PASS
```


## Google Workspace examples

The Google Workspace tool pack includes example manifests for Gmail unread checks, Calendar search, and Sheets range reads under `tool_packs/google_workspace/examples/`.

These examples are read-only and are intended for explicit validation or integration testing only.


### docs/toolpack_governance.md

# Tool Pack Governance + Environment Enablement Policy

Every tool pack that runs in the TaskFrame runtime must have a recorded governance decision. This document defines the classification system, environment profiles, and CLI commands for managing tool pack policy.

## Why Governance

Without explicit governance:

- A developer enables an optional pack
- A manifest starts using it
- The demo or release path accidentally depends on it
- High-risk or experimental behavior leaks into default runtime

The governance model ensures that only approved, classified packs can run in restricted environments (demo, release, live).
Runtime enforcement now consumes this policy directly, so governance is not just a CLI/reporting concern.

## Tool Pack Classifications

| Classification | Meaning | Default environments |
|---|---|---|
| `core` | Built-in packs — part of the default runtime | All (demo, dev, test, release, live) |
| `optional` | External or integration packs — safe, but not core | dev, test only by default |
| `experimental` | Packs under active development | dev only |
| `high_risk` | Live side effects, RPA, or dangerous operations | None — must be explicitly enabled per-env |
| `blocked` | Explicitly disabled — may not run anywhere | None |

When in doubt, classify higher risk. It is easy to promote; it is harder to contain a mis-classified pack.

## Environment Profiles

| Environment | Purpose | Restricted? |
|---|---|---|
| `demo` | Safe operator demo — shown to stakeholders | Yes — core and explicitly approved optional only |
| `dev` | Local development | No — all safe classifications allowed |
| `test` | CI and automated testing | No — core and optional allowed |
| `release` | Release candidate verification | Yes — core only by default |
| `live` | Production execution | Yes — core and explicitly approved optional only |

`demo` and `release` are the most restricted environments. `high_risk` and `experimental` packs are never allowed in `demo` or `release` unless a governance violation is explicitly accepted and recorded.

At runtime, discovery does not imply execution permission. The tool runner must evaluate governance before execution, staging, pending-action approval, and live health probes.

## Governance Config

Governance decisions are recorded in `config/toolpack_governance.json`. Each entry records:

- `toolpack_id` — the pack being governed
- `classification` — one of the classifications above
- `enabled_environments` — environments where this pack is active
- `enabled_by` — who recorded the decision
- `enabled_at` — ISO timestamp of the decision
- `reason` — human-readable justification

Example entry:

```json
{
  "toolpack_id": "google_workspace",
  "classification": "optional",
  "enabled_environments": ["dev", "test"],
  "enabled_by": "operator",
  "enabled_at": "2026-05-16T00:00:00+00:00",
  "reason": "Auth not verified for demo/release yet."
}
```

## CLI Reference

### Show policy

```bash
# All packs
taskframe tools policy --json

# One pack
taskframe tools policy google_workspace --json
```

### Enable a pack

```bash
taskframe tools enable my_pack \
  --classification optional \
  --env dev,test \
  --by operator \
  --reason "Safe integration, no live side effects"
```

### Disable a pack

```bash
# Disable in specific environments
taskframe tools disable my_pack --env release,live

# Disable everywhere
taskframe tools disable my_pack --reason "Quarantined — pending security review"
```

### Governance report

```bash
taskframe tools governance-report --json
taskframe tools governance-report
```

The report shows packs by classification and environment, and flags any policy violations. The release verifier runs this check automatically.

## Policy Violations

The following conditions are treated as violations:

- A `high_risk` or `experimental` pack is enabled in `demo` or `release`
- A `blocked` pack has any enabled environments
- A pack in `demo` or `release` is classified `high_risk`, `experimental`, or `blocked`

Violations cause `taskframe tools governance-report` to exit non-zero and fail the release verifier.

## Release Verifier Integration

The release verifier runs `validate_governance_for_release()` which checks:

1. `governance_config_exists` — `config/toolpack_governance.json` is present
2. `no_policy_violations` — no classification/environment conflicts
3. `demo_env_safe` — no unsafe packs in the demo environment
4. `release_env_safe` — no unsafe packs in the release environment

Any failure blocks the release candidate.

## Seeding a New Pack

After scaffolding a new pack, record its governance decision before committing:

```bash
taskframe tools scaffold my_pack --namespace mypkg --tool run --safe-read
taskframe tools enable my_pack --classification optional --env dev,test --reason "Initial scaffold"
taskframe tools governance-report
```

See [toolpack_scaffold_wizard.md](toolpack_scaffold_wizard.md) and [toolpack_contract_testing.md](toolpack_contract_testing.md) for the complete authoring workflow.


### docs/toolpack_lifecycle.md

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


### docs/toolpack_scaffold_wizard.md

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


## Binary Assets

The following files are present in `docs/` but are binary or image assets, so their raw bytes are not inlined here.

| File | Size (bytes) |
|---|---:|
| `docs/screenshots/01_operator_home.png` | 23781 |
| `docs/screenshots/02_demo_customer_happy_path.png` | 36349 |
| `docs/screenshots/02_scenario_pack.png` | 28387 |
| `docs/screenshots/03_demo_customer_pending_approval.png` | 37145 |
| `docs/screenshots/03_taskframe_detail.png` | 200784 |
| `docs/screenshots/04_run_report_step_outcomes.png` | 58134 |
| `docs/screenshots/04_step_playback.png` | 202066 |
| `docs/screenshots/05_demo_customer_failed_validation.png` | 37833 |
| `docs/screenshots/05_pending_approval.png` | 203369 |
| `docs/screenshots/06_report_generation_demo.png` | 39375 |
| `docs/screenshots/06_tool_status_panel.png` | 184593 |
| `docs/screenshots/07_business_report_visible_path.png` | 41916 |
| `docs/screenshots/07_tool_health_details.png` | 190317 |
| `docs/screenshots/08_report_output.png` | 45089 |
| `docs/screenshots/08_tool_status_panel.png` | 35900 |
| `docs/screenshots/09_release_verification.png` | 81948 |
| `docs/screenshots/accounting_workflow_completed.png` | 23591 |
| `docs/screenshots/architecture_diagram.png` | 13600 |
| `docs/screenshots/cross_workflow_demo_completed.png` | 19278 |
| `docs/screenshots/customer_workflow_completed.png` | 23043 |
| `docs/screenshots/operator_ui_main.png` | 16667 |
| `docs/screenshots/pending_approval_view.png` | 13791 |
| `docs/screenshots/procurement_workflow_completed.png` | 24151 |
| `docs/screenshots/report_example.png` | 17001 |
