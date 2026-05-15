from __future__ import annotations

import copy
import difflib
import hashlib
import json
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Status / risk constants
# ---------------------------------------------------------------------------

_STATUS_ORDER = {"PROPOSED": 0, "NOT_SUPPORTED": 1, "APPLIED": 2, "FAILED": 3}

_FIX_TITLES: dict[str, str] = {
    "completion_output_missing": "Align completion output with existing step output",
    "validation_output_missing": "Align validation output with existing step output",
    "validation_references_missing_output": "Align validation output with existing step output",
    "completion_empty_without_acceptable_empty": "Add missing acceptable empty outputs",
    "input_declared_but_not_used": "Remove unused declared input",
    "input_used_but_not_declared": "Add missing declared input",
    "live_execution_enabled": "Disable live execution",
    "duplicate_step_id": "Rename duplicate step ID",
}

# Finding IDs that can never be auto-patched safely
_ALWAYS_UNSUPPORTED: frozenset[str] = frozenset({
    "unknown_tool",
    "command_invalid",
    "command_parse_error",
    "side_effect_command_without_pending_expectation",
    "unknown_validation_type",
    "missing_required_top_level_field",
    "step_missing_command",
    "invalid_manifest_id",
    "manifest_load_failed",
    "execution_failed",
    "validation_failed",
    "completion_failed",
    "shape_invalid",
    "missing_or_empty_steps",
    "json_parse_error",
    "duplicate_manifest_id",
    "event_trigger_without_route_note",
    "preflight_failed",
    "sample_inputs_missing",
    "taskframe_error",
    "live_side_effect_blocked",
    "unexpected_pending_action",
    "step_missing_output_alias",
})

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def propose_manifest_fixes(
    manifest: dict,
    guidance: dict | None = None,
) -> dict:
    """Analyse guidance findings and return deterministic low-risk fix proposals."""
    if not isinstance(manifest, dict):
        return _no_fixes_result("", "Manifest is not a dict.")

    if guidance is None:
        from src.manifest_authoring_feedback import explain_manifest_failure
        guidance = explain_manifest_failure(manifest=manifest)

    manifest_id = str(manifest.get("manifest_id") or manifest.get("id") or "")
    findings = guidance.get("findings") or []

    if not findings:
        return _no_fixes_result(manifest_id)

    proposals: list[dict] = []
    for finding in findings:
        proposal = _generate_proposal(manifest, finding)
        if proposal is not None:
            proposals.append(proposal)

    proposals = _sort_proposals(proposals)

    supported = [p for p in proposals if p["status"] == "PROPOSED"]
    unsupported = [p for p in proposals if p["status"] != "PROPOSED"]

    status = "HAS_PROPOSALS" if proposals else "NO_SUPPORTED_FIXES"
    warnings: list[str] = [] if supported else ["No deterministic low-risk fixes are available."]

    return {
        "ok": True,
        "status": status,
        "manifest_id": manifest_id,
        "proposal_count": len(proposals),
        "supported_count": len(supported),
        "unsupported_count": len(unsupported),
        "proposals": proposals,
        "warnings": warnings,
    }


def apply_manifest_fix_preview(
    manifest: dict,
    proposal: dict,
) -> dict:
    """Apply proposal patches to an in-memory copy. Does NOT mutate the original manifest."""
    patches = proposal.get("patches") or []
    try:
        patched = _apply_patches(manifest, patches)
    except Exception as exc:
        return {"ok": False, "status": "PREVIEW_FAILED", "error": str(exc)}

    before_json = json.dumps(manifest, indent=2, ensure_ascii=False)
    after_json = json.dumps(patched, indent=2, ensure_ascii=False)
    diff = list(difflib.unified_diff(
        before_json.splitlines(),
        after_json.splitlines(),
        fromfile="before",
        tofile="after",
        lineterm="",
    ))
    return {
        "ok": True,
        "status": "PREVIEW_READY",
        "manifest": patched,
        "before_json": before_json,
        "after_json": after_json,
        "patches": patches,
        "diff": diff,
    }


def apply_manifest_fix_to_file(
    manifest_path: str | Path,
    proposal: dict,
    *,
    approved: bool,
) -> dict:
    """Apply a proposal to the manifest file on disk after operator approval."""
    if not approved:
        return {
            "ok": False,
            "status": "APPROVAL_REQUIRED",
            "error": "Operator approval is required before applying an auto-fix.",
        }

    if proposal.get("status") != "PROPOSED":
        return {"ok": False, "status": "BLOCKED", "error": "Only PROPOSED fixes may be applied."}

    if proposal.get("risk") != "low":
        return {"ok": False, "status": "BLOCKED", "error": "Only low-risk fixes may be applied."}

    path = Path(manifest_path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "status": "LOAD_FAILED", "error": f"Could not read manifest file: {exc}"}

    # Verify old_values still match current file content
    patches = proposal.get("patches") or []
    for patch in patches:
        if patch.get("op") in ("replace", "remove") and "old_value" in patch:
            try:
                current_val = _get_by_path(manifest, patch["path"])
            except Exception as exc:
                return {
                    "ok": False,
                    "status": "STALE",
                    "error": f"Path {patch['path']!r} not found in file: {exc}",
                }
            if current_val != patch["old_value"]:
                return {
                    "ok": False,
                    "status": "STALE",
                    "error": (
                        f"Manifest has changed since proposal was generated. "
                        f"old_value mismatch at {patch['path']}: "
                        f"expected {patch['old_value']!r}, found {current_val!r}."
                    ),
                }

    try:
        patched = _apply_patches(manifest, patches)
    except Exception as exc:
        return {"ok": False, "status": "FAILED", "error": f"Patch application failed: {exc}"}

    # Validate patched manifest
    validation = _validate_patched_manifest(patched)

    # Atomic write: write to .tmp then replace
    tmp_path = path.with_suffix(".autofix_tmp")
    try:
        tmp_path.write_text(json.dumps(patched, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(path)
    except Exception as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return {"ok": False, "status": "WRITE_FAILED", "error": f"Could not write manifest file: {exc}"}

    manifest_id = str(patched.get("manifest_id") or "")
    return {
        "ok": True,
        "status": "APPLIED",
        "manifest_id": manifest_id,
        "path": str(path),
        "validation": validation,
    }


def write_autofix_report(
    result: dict,
    *,
    runtime_data_dir: str | Path = "runtime_data",
    report_name: str = "manifest_autofix_report",
) -> dict:
    """Write the autofix proposal result as JSON and Markdown reports."""
    out_dir = Path(runtime_data_dir) / "generated_manifest_smoke"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "json_path": "", "markdown_path": ""}

    json_path = out_dir / f"{report_name}.json"
    md_path = out_dir / f"{report_name}.md"

    try:
        json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": str(exc), "json_path": "", "markdown_path": ""}

    try:
        md_path.write_text(_build_autofix_markdown(result), encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": str(exc), "json_path": str(json_path), "markdown_path": ""}

    return {"ok": True, "json_path": str(json_path), "markdown_path": str(md_path)}


# ---------------------------------------------------------------------------
# Internal: proposal routing
# ---------------------------------------------------------------------------


def _generate_proposal(manifest: dict, finding: dict) -> dict | None:
    finding_id = finding.get("id", "")

    if finding_id == "completion_output_missing":
        return _fix_completion_output_mismatch(manifest, finding)
    if finding_id in ("validation_output_missing", "validation_references_missing_output"):
        return _fix_validation_output_mismatch(manifest, finding)
    if finding_id == "completion_empty_without_acceptable_empty":
        return _fix_completion_empty_without_acceptable_empty(manifest, finding)
    if finding_id == "input_declared_but_not_used":
        return _fix_remove_unused_input(manifest, finding)
    if finding_id == "input_used_but_not_declared":
        return _fix_add_missing_input(manifest, finding)
    if finding_id == "live_execution_enabled":
        return _fix_disable_live_execution(manifest, finding)
    if finding_id == "duplicate_step_id":
        return _fix_duplicate_step_id(manifest, finding)
    if finding_id in _ALWAYS_UNSUPPORTED:
        return _not_supported_proposal(
            finding,
            f"The system cannot safely patch '{finding_id}' automatically.",
        )
    # Unknown finding — return unsupported
    return _not_supported_proposal(finding, f"No automatic fix available for '{finding_id}'.")


# ---------------------------------------------------------------------------
# Internal: fix generators
# ---------------------------------------------------------------------------


def _fix_completion_output_mismatch(manifest: dict, finding: dict) -> dict:
    loc = finding.get("location", "")
    cidx_m = re.search(r"\[(\d+)\]", loc)
    if not cidx_m:
        return _not_supported_proposal(finding, "Could not determine completion output index from location.")

    cidx = int(cidx_m.group(1))
    completion = manifest.get("completion") or {}
    success_outputs = completion.get("success_outputs") or []
    if cidx >= len(success_outputs):
        return _not_supported_proposal(finding, f"Completion success_outputs[{cidx}] does not exist.")

    old_alias = str(success_outputs[cidx])
    step_aliases = _collect_step_aliases(manifest)

    if len(step_aliases) != 1:
        return _not_supported_proposal(
            finding,
            "Multiple possible output aliases exist. Operator must choose manually.",
        )

    new_alias = step_aliases[0]
    patch = {
        "op": "replace",
        "path": f"/completion/success_outputs/{cidx}",
        "old_value": old_alias,
        "new_value": new_alias,
    }
    return _make_proposal(finding, [patch], manifest)


def _fix_validation_output_mismatch(manifest: dict, finding: dict) -> dict:
    loc = finding.get("location", "")
    vidx_m = re.search(r"\[(\d+)\]", loc)
    if not vidx_m:
        return _not_supported_proposal(finding, "Could not determine validation index from location.")

    vidx = int(vidx_m.group(1))
    validations = manifest.get("validations") or []
    if vidx >= len(validations):
        return _not_supported_proposal(finding, f"validations[{vidx}] does not exist.")

    val = validations[vidx]
    if not isinstance(val, dict):
        return _not_supported_proposal(finding, "Validation entry is not a dict.")

    old_output = str(val.get("output") or "")
    step_aliases = _collect_step_aliases(manifest)

    if len(step_aliases) != 1:
        return _not_supported_proposal(
            finding,
            "Multiple possible output aliases exist. Operator must choose manually.",
        )

    new_output = step_aliases[0]
    patch = {
        "op": "replace",
        "path": f"/validations/{vidx}/output",
        "old_value": old_output,
        "new_value": new_output,
    }
    return _make_proposal(finding, [patch], manifest)


def _fix_completion_empty_without_acceptable_empty(manifest: dict, finding: dict) -> dict:
    step_aliases = _collect_step_aliases(manifest)
    if not step_aliases:
        return _not_supported_proposal(
            finding, "No step output aliases found. Add outputs to steps first."
        )

    completion = manifest.get("completion") or {}
    existing_acceptable = completion.get("acceptable_empty_outputs")

    patches: list[dict] = []
    if existing_acceptable is None:
        patches.append({
            "op": "add",
            "path": "/completion/acceptable_empty_outputs",
            "new_value": list(step_aliases),
        })
    else:
        existing_set = set(existing_acceptable) if isinstance(existing_acceptable, list) else set()
        missing = [a for a in step_aliases if a not in existing_set]
        if not missing:
            return _not_supported_proposal(
                finding, "All step aliases already appear in acceptable_empty_outputs."
            )
        for alias in missing:
            patches.append({
                "op": "add",
                "path": "/completion/acceptable_empty_outputs/-",
                "new_value": alias,
            })

    return _make_proposal(finding, patches, manifest)


def _fix_remove_unused_input(manifest: dict, finding: dict) -> dict:
    msg = finding.get("message", "")
    m = re.search(r"Input '([^']+)'", msg)
    if not m:
        return _not_supported_proposal(finding, "Could not determine input name from finding message.")

    input_name = m.group(1)
    inputs = manifest.get("inputs") or []

    try:
        idx = next(
            i for i, item in enumerate(inputs)
            if (isinstance(item, str) and item == input_name)
            or (isinstance(item, dict) and item.get("name") == input_name)
        )
    except StopIteration:
        return _not_supported_proposal(finding, f"Input '{input_name}' not found in inputs list.")

    entry = inputs[idx]
    if not isinstance(entry, str):
        return _not_supported_proposal(
            finding, "Input entry is not a simple string. Operator must remove manually."
        )

    patch = {"op": "remove", "path": f"/inputs/{idx}", "old_value": input_name}
    return _make_proposal(finding, [patch], manifest)


def _fix_add_missing_input(manifest: dict, finding: dict) -> dict:
    msg = finding.get("message", "")
    m = re.search(r"\$inputs\.(\w+)", msg)
    if not m:
        return _not_supported_proposal(finding, "Could not determine input name from finding message.")

    input_name = m.group(1)
    inputs = manifest.get("inputs")

    patches: list[dict] = []
    if inputs is None:
        patches.append({"op": "add", "path": "/inputs", "new_value": []})
    patches.append({"op": "add", "path": "/inputs/-", "new_value": input_name})
    return _make_proposal(finding, patches, manifest)


def _fix_disable_live_execution(manifest: dict, finding: dict) -> dict:
    live = manifest.get("live_execution")
    if not isinstance(live, dict):
        return _not_supported_proposal(
            finding, "live_execution field is malformed or missing."
        )

    patch = {
        "op": "replace",
        "path": "/live_execution/enabled",
        "old_value": True,
        "new_value": False,
    }
    return _make_proposal(finding, [patch], manifest)


def _fix_duplicate_step_id(manifest: dict, finding: dict) -> dict:
    loc = finding.get("location", "")
    idx_m = re.search(r"\[(\d+)\]", loc)
    if not idx_m:
        return _not_supported_proposal(finding, "Could not determine step index from location.")

    idx = int(idx_m.group(1))
    steps = manifest.get("steps") or []
    if idx >= len(steps):
        return _not_supported_proposal(finding, f"steps[{idx}] does not exist.")

    step = steps[idx]
    if not isinstance(step, dict):
        return _not_supported_proposal(finding, "Step is not a dict.")

    id_key = "id" if "id" in step else "step_id"
    old_id = str(step.get(id_key) or "")
    if not old_id:
        return _not_supported_proposal(finding, "Step has no id to rename.")

    # Check for references to old_id elsewhere in the manifest
    if _step_id_has_external_references(manifest, old_id, step_idx=idx):
        return _not_supported_proposal(
            finding,
            f"Step ID '{old_id}' is referenced elsewhere in the manifest. Update references manually.",
        )

    # Build a new unique ID
    existing_ids = {
        str(s.get("id") or s.get("step_id") or "")
        for i, s in enumerate(steps)
        if isinstance(s, dict) and i != idx
    }
    new_id = f"{old_id}_2"
    suffix = 2
    while new_id in existing_ids:
        suffix += 1
        new_id = f"{old_id}_{suffix}"

    patch = {
        "op": "replace",
        "path": f"/steps/{idx}/{id_key}",
        "old_value": old_id,
        "new_value": new_id,
    }
    return _make_proposal(finding, [patch], manifest)


# ---------------------------------------------------------------------------
# Internal: proposal builders
# ---------------------------------------------------------------------------


def _make_proposal(finding: dict, patches: list[dict], manifest: dict) -> dict:
    finding_id = finding.get("id", "unknown")
    fix_id = _make_fix_id(finding_id, patches)

    try:
        patched = _apply_patches(manifest, patches)
    except Exception as exc:
        return _not_supported_proposal(finding, f"Patch preview failed: {exc}")

    before_json = json.dumps(manifest, indent=2, ensure_ascii=False)
    after_json = json.dumps(patched, indent=2, ensure_ascii=False)
    diff = list(difflib.unified_diff(
        before_json.splitlines(),
        after_json.splitlines(),
        fromfile="before",
        tofile="after",
        lineterm="",
    ))

    return {
        "fix_id": fix_id,
        "finding_id": finding_id,
        "title": _FIX_TITLES.get(finding_id, f"Fix {finding_id.replace('_', ' ')}"),
        "severity": finding.get("severity", "error"),
        "risk": "low",
        "confidence": "high",
        "status": "PROPOSED",
        "location": finding.get("location", ""),
        "summary": finding.get("message", ""),
        "patches": patches,
        "before_preview": before_json,
        "after_preview": after_json,
        "diff": diff,
        "warnings": [],
        "requires_operator_approval": True,
    }


def _not_supported_proposal(finding: dict, reason: str) -> dict:
    finding_id = finding.get("id", "unknown")
    return {
        "fix_id": f"unsupported_{finding_id}",
        "finding_id": finding_id,
        "title": f"Unsupported automatic fix: {finding_id.replace('_', ' ')}",
        "severity": finding.get("severity", "error"),
        "risk": "blocked",
        "confidence": "n/a",
        "status": "NOT_SUPPORTED",
        "location": finding.get("location", ""),
        "summary": finding.get("message", ""),
        "patches": [],
        "before_preview": "",
        "after_preview": "",
        "diff": [],
        "warnings": [reason],
        "requires_operator_approval": True,
    }


def _no_fixes_result(manifest_id: str, warning: str = "") -> dict:
    return {
        "ok": True,
        "status": "NO_SUPPORTED_FIXES",
        "manifest_id": manifest_id,
        "proposal_count": 0,
        "supported_count": 0,
        "unsupported_count": 0,
        "proposals": [],
        "warnings": [warning] if warning else ["No deterministic low-risk fixes are available."],
    }


def _sort_proposals(proposals: list[dict]) -> list[dict]:
    return sorted(
        proposals,
        key=lambda p: (
            _STATUS_ORDER.get(p.get("status", "NOT_SUPPORTED"), 99),
            p.get("finding_id", ""),
            p.get("fix_id", ""),
        ),
    )


def _make_fix_id(finding_id: str, patches: list[dict]) -> str:
    patch_bytes = json.dumps(patches, sort_keys=True).encode()
    h = hashlib.md5(patch_bytes).hexdigest()[:6]
    return f"fix_{finding_id}_{h}"


# ---------------------------------------------------------------------------
# Internal: patch engine
# ---------------------------------------------------------------------------


def _apply_patches(manifest: dict, patches: list[dict]) -> dict:
    result = copy.deepcopy(manifest)
    for patch in patches:
        op = patch["op"]
        path = patch["path"]
        if op in ("replace", "remove") and "old_value" in patch:
            current = _get_by_path(result, path)
            if current != patch["old_value"]:
                raise ValueError(
                    f"old_value mismatch at {path!r}: "
                    f"expected {patch['old_value']!r}, found {current!r}"
                )
        _set_by_path(result, path, patch.get("new_value"), op=op)
    return result


def _get_by_path(obj, path: str):
    parts = [p for p in path.split("/") if p]
    cur = obj
    for p in parts:
        if isinstance(cur, list):
            cur = cur[int(p)]
        elif isinstance(cur, dict):
            if p not in cur:
                raise KeyError(f"Key {p!r} not found in dict")
            cur = cur[p]
        else:
            raise ValueError(f"Cannot navigate through {type(cur).__name__} at segment {p!r}")
    return cur


def _set_by_path(obj, path: str, value, op: str = "replace") -> None:
    parts = [p for p in path.split("/") if p]
    if not parts:
        raise ValueError("Empty path")

    cur = obj
    for p in parts[:-1]:
        if isinstance(cur, list):
            cur = cur[int(p)]
        elif isinstance(cur, dict):
            cur = cur[p]
        else:
            raise ValueError(f"Cannot navigate through {type(cur).__name__}")

    last = parts[-1]
    if op == "replace":
        if isinstance(cur, list):
            cur[int(last)] = value
        elif isinstance(cur, dict):
            cur[last] = value
        else:
            raise ValueError("Cannot replace on non-container")
    elif op == "add":
        if isinstance(cur, list):
            if last == "-":
                cur.append(value)
            else:
                cur.insert(int(last), value)
        elif isinstance(cur, dict):
            cur[last] = value
        else:
            raise ValueError("Cannot add to non-container")
    elif op == "remove":
        if isinstance(cur, list):
            del cur[int(last)]
        elif isinstance(cur, dict):
            del cur[last]
        else:
            raise ValueError("Cannot remove from non-container")
    else:
        raise ValueError(f"Unknown patch op: {op!r}")


# ---------------------------------------------------------------------------
# Internal: manifest helpers
# ---------------------------------------------------------------------------


def _collect_step_aliases(manifest: dict) -> list[str]:
    steps = manifest.get("steps") or []
    aliases: list[str] = []
    seen: set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            continue
        cmd = str(step.get("command") or "").strip()
        if not cmd:
            continue
        alias = _extract_alias_from_command(cmd)
        if alias and alias not in seen:
            aliases.append(alias)
            seen.add(alias)
    return aliases


def _extract_alias_from_command(command: str) -> str | None:
    try:
        from runtime.command_parser import parse_command
        parsed = parse_command(command)
        return parsed.output_alias if parsed.output_alias else None
    except Exception:
        pass
    # Fallback: regex for [... -> alias] pattern
    m = re.search(r"->\s*(\w+)", command)
    if m:
        return m.group(1)
    return None


def _step_id_has_external_references(
    manifest: dict,
    step_id: str,
    *,
    step_idx: int,
) -> bool:
    steps = manifest.get("steps") or []
    for i, step in enumerate(steps):
        if i == step_idx or not isinstance(step, dict):
            continue
        when = str(step.get("when") or "")
        if step_id in when:
            return True

    validations = manifest.get("validations") or []
    for val in validations:
        if isinstance(val, dict):
            val_str = json.dumps(val)
            if step_id in val_str:
                return True

    completion = manifest.get("completion") or {}
    if isinstance(completion, dict):
        if step_id in json.dumps(completion):
            return True

    return False


def _validate_patched_manifest(patched: dict) -> dict:
    try:
        from src.manifest_authoring_feedback import analyze_manifest_static
        findings = analyze_manifest_static(patched)
        errors = [
            f["message"]
            for f in findings
            if f.get("severity") in ("critical", "error")
        ]
        return {"ok": len(errors) == 0, "errors": errors}
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)]}


# ---------------------------------------------------------------------------
# Internal: report builder
# ---------------------------------------------------------------------------


def _build_autofix_markdown(result: dict) -> str:
    status = result.get("status", "UNKNOWN")
    manifest_id = result.get("manifest_id", "unknown")
    proposals = result.get("proposals") or []
    warnings = result.get("warnings") or []

    lines = [
        "# Manifest Auto-Fix Preview Report",
        "",
        f"Status: {status}  ",
        f"Manifest: {manifest_id}",
        "",
        "## Proposal Summary",
        "",
        "| Status | Risk | Finding | Title |",
        "|---|---|---|---|",
    ]

    for p in proposals:
        pstatus = p.get("status", "")
        risk = p.get("risk", "")
        fid = p.get("finding_id", "")
        title = p.get("title", "")
        lines.append(f"| {pstatus} | {risk} | {fid} | {title} |")

    lines.append("")

    proposed = [p for p in proposals if p.get("status") == "PROPOSED"]
    if proposed:
        first = proposed[0]
        patches = first.get("patches") or []
        lines += [
            "## Proposed Patch",
            "",
            "```json",
            json.dumps(patches, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
        diff = first.get("diff") or []
        if diff:
            lines += ["## Diff", "", "```diff"]
            lines.extend(diff)
            lines.append("```")
            lines.append("")

    if warnings:
        lines += ["## Warnings", ""]
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)
