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
