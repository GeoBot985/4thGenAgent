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
