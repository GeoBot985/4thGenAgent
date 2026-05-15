from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from runtime.manifest_loader import load_manifest as runtime_load_manifest


_TEMPLATES: list[dict] = [
    {
        "template_id": "manual_read_tool",
        "name": "Manual read-only tool manifest",
        "description": (
            "Starts a manifest with one read-only tool step and one output_exists validation. "
            "Use this as the base for any workflow that reads data and produces an output."
        ),
        "risk_level": "low",
        "side_effect": False,
        "sample_inputs": {},
        "expected_smoke_classification": "DRY_RUN_COMPLETED",
    },
    {
        "template_id": "manual_llm_helper",
        "name": "Manual LLM helper manifest",
        "description": (
            "Starts a manifest with one LLM classify/extract step. "
            "Includes a message input, LLM step, output validation, and completion rule."
        ),
        "risk_level": "low",
        "side_effect": False,
        "sample_inputs": {"message": "Where is my order ORD-10042?"},
        "expected_smoke_classification": "DRY_RUN_COMPLETED",
    },
    {
        "template_id": "approval_side_effect",
        "name": "Approval / side-effect starter manifest",
        "description": (
            "Starts a manifest that stages a pending action for approval rather than executing directly. "
            "Live execution is disabled by default. Worker stops at WAITING_FOR_EXECUTE."
        ),
        "risk_level": "medium",
        "side_effect": True,
        "sample_inputs": {},
        "expected_smoke_classification": "WAITING_FOR_EXECUTE_EXPECTED",
    },
    {
        "template_id": "event_driven_stub",
        "name": "Event-driven stub manifest",
        "description": (
            "Starts a manifest with an event trigger. Does not register event routes automatically. "
            "A route snippet is shown after creation so you can register it manually."
        ),
        "risk_level": "low",
        "side_effect": False,
        "sample_inputs": {},
        "expected_smoke_classification": "DRY_RUN_COMPLETED",
    },
]


def list_manifest_templates() -> list[dict]:
    return list(_TEMPLATES)


def manifest_filename_for_id(manifest_id: str) -> str:
    mid = str(manifest_id or "").strip()
    if not mid:
        raise ValueError("manifest_id must not be empty.")
    if ".." in mid or mid.startswith("/") or mid.startswith("\\"):
        raise ValueError(f"manifest_id contains path traversal: {mid!r}")
    safe = re.sub(r"[.\s/\\:]+", "_", mid)
    safe = re.sub(r"[^A-Za-z0-9_\-]", "", safe)
    safe = safe.strip("_")
    if not safe:
        raise ValueError(f"manifest_id produced an empty filename after sanitization: {mid!r}")
    return f"{safe}.manifest.json"


def build_manifest_from_template(
    template_id: str,
    manifest_id: str,
    name: str,
    *,
    description: str = "",
    command: str = "",
    inputs: list[str] | None = None,
    output_alias: str = "",
) -> dict:
    tid = str(template_id or "").strip()
    mid = str(manifest_id or "").strip()
    mname = str(name or "").strip() or mid

    if tid == "manual_read_tool":
        return _build_manual_read_tool(mid, mname, command=command, inputs=inputs, output_alias=output_alias)
    if tid == "manual_llm_helper":
        return _build_manual_llm_helper(mid, mname, command=command, inputs=inputs, output_alias=output_alias)
    if tid == "approval_side_effect":
        return _build_approval_side_effect(mid, mname, command=command, inputs=inputs, output_alias=output_alias)
    if tid == "event_driven_stub":
        return _build_event_driven_stub(mid, mname, command=command, inputs=inputs, output_alias=output_alias)
    raise ValueError(f"Unknown template_id: {tid!r}")


def validate_manifest_candidate(
    manifest: dict,
    manifest_dir: str | Path = "manifests",
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if not isinstance(manifest, dict):
        return False, ["manifest must be a dict."]

    manifest_id = str(manifest.get("manifest_id") or manifest.get("id") or "").strip()
    if not manifest_id:
        errors.append("manifest_id is required.")

    # Filename safety
    if manifest_id:
        try:
            manifest_filename_for_id(manifest_id)
        except ValueError as exc:
            errors.append(str(exc))

    # Catalog uniqueness
    if manifest_id:
        try:
            from src.manifest_workbench import list_manifest_catalog
            catalog = list_manifest_catalog(str(manifest_dir))
            existing_ids = {str(e.get("manifest_id", "")) for e in catalog}
            if manifest_id in existing_ids:
                errors.append(f"Duplicate manifest_id: {manifest_id} already exists in catalog.")
        except Exception as exc:
            errors.append(f"Could not check catalog: {exc}")

    # Top-level contract
    for field in ("name", "version", "trigger", "inputs", "steps", "validations", "completion"):
        if field not in manifest:
            errors.append(f"Missing required top-level field: {field}")

    # Steps
    steps = manifest.get("steps")
    if isinstance(steps, list):
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"Step {idx} is not a dict.")
                continue
            step_id = str(step.get("id") or step.get("step_id") or "").strip()
            if not step_id:
                errors.append(f"Step {idx} is missing an id.")
            command = str(step.get("command") or "").strip()
            if not command:
                errors.append(f"Step {idx} ({step_id or '?'}) is missing a command.")

    # Try loading via runtime
    if not errors:
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".manifest.json", delete=False, encoding="utf-8"
            ) as tmp:
                tmp_path = Path(tmp.name)
                tmp.write(json.dumps(manifest, indent=2, ensure_ascii=False))
            runtime_load_manifest(tmp_path)
        except Exception as exc:
            errors.append(f"Manifest failed runtime validation: {exc}")
        finally:
            if tmp_path and tmp_path.is_file():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    return (len(errors) == 0), errors


def write_manifest_candidate(
    manifest: dict,
    manifest_dir: str | Path = "manifests",
) -> dict:
    manifest_id = str(manifest.get("manifest_id") or manifest.get("id") or "").strip()

    ok, errors = validate_manifest_candidate(manifest, manifest_dir=manifest_dir)
    if not ok:
        return {"ok": False, "manifest_id": manifest_id, "path": "", "errors": errors}

    try:
        filename = manifest_filename_for_id(manifest_id)
    except ValueError as exc:
        return {"ok": False, "manifest_id": manifest_id, "path": "", "errors": [str(exc)]}

    target = Path(manifest_dir) / filename
    if target.exists():
        return {
            "ok": False,
            "manifest_id": manifest_id,
            "path": str(target),
            "errors": [f"File already exists: {target}. Use a different manifest_id."],
        }

    # Atomic write: temp file → validate → rename
    tmp_path: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", suffix=".manifest.json", delete=False,
            dir=target.parent, encoding="utf-8"
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(json.dumps(manifest, indent=2, ensure_ascii=False))
        runtime_load_manifest(tmp_path)
        tmp_path.rename(target)
        tmp_path = None
    except Exception as exc:
        if tmp_path and tmp_path.is_file():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        return {"ok": False, "manifest_id": manifest_id, "path": "", "errors": [str(exc)]}

    return {
        "ok": True,
        "manifest_id": manifest_id,
        "path": str(target),
        "errors": [],
        "message": "Manifest created.",
    }


# ---------------------------------------------------------------------------
# Template builders
# ---------------------------------------------------------------------------

def _build_manual_read_tool(
    manifest_id: str,
    name: str,
    command: str = "",
    inputs: list[str] | None = None,
    output_alias: str = "",
) -> dict:
    alias = _safe_alias(output_alias, "result")
    cmd = command.strip() if command.strip() else f"[t:g/check -> {alias}] max_results=5"
    input_list = _parse_inputs(inputs)
    return {
        "manifest_id": manifest_id,
        "name": name,
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": input_list,
        "steps": [
            {"id": "read_data", "command": cmd},
            {"id": "validate_result_exists", "command": f"[validate:{alias}_exists]"},
        ],
        "validations": [
            {"id": "no_runtime_errors", "type": "no_errors"},
            {
                "id": f"{alias}_exists",
                "type": "output_exists",
                "output": alias,
            },
        ],
        "completion": {
            "success_outputs": [alias],
            "acceptable_empty_outputs": [alias],
        },
        "live_execution": {"enabled": False, "allowed_tools": [], "requires_approval": True},
    }


def _build_manual_llm_helper(
    manifest_id: str,
    name: str,
    command: str = "",
    inputs: list[str] | None = None,
    output_alias: str = "",
) -> dict:
    alias = _safe_alias(output_alias, "category")
    input_list = _parse_inputs(inputs) or ["message"]
    msg_ref = "$inputs.message" if "message" in input_list else f"$inputs.{input_list[0]}"
    cmd = command.strip() if command.strip() else (
        f"[q:classify_customer_message -> {alias}] text={msg_ref}"
    )
    return {
        "manifest_id": manifest_id,
        "name": name,
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": input_list,
        "steps": [
            {"id": "llm_step", "command": cmd},
        ],
        "validations": [
            {"id": "no_runtime_errors", "type": "no_errors"},
            {"id": "llm_step_completed", "type": "step_completed", "step": "llm_step"},
            {
                "id": f"{alias}_output_exists",
                "type": "output_exists",
                "output": alias,
            },
        ],
        "completion": {
            "success_outputs": [alias],
        },
        "live_execution": {"enabled": False, "allowed_tools": [], "requires_approval": True},
    }


def _build_approval_side_effect(
    manifest_id: str,
    name: str,
    command: str = "",
    inputs: list[str] | None = None,
    output_alias: str = "",
) -> dict:
    alias = _safe_alias(output_alias, "sent_msg")
    input_list = _parse_inputs(inputs)
    cmd = command.strip() if command.strip() else (
        f'[t:wa/send -> {alias}] chat="Recipient"; message="Your message here"'
    )
    return {
        "manifest_id": manifest_id,
        "name": name,
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": input_list,
        "steps": [
            {"id": "stage_action", "command": cmd},
        ],
        "validations": [
            {"id": "no_runtime_errors", "type": "no_errors"},
            {"id": "stage_action_step_staged", "type": "step_staged", "step": "stage_action"},
            {
                "id": f"{alias}_pending_action_created",
                "type": "pending_action_exists",
                "tool": "wa/send",
                "output": alias,
            },
        ],
        "completion": {
            "success_pending_actions": [alias],
            "success_executed_actions": [alias],
            "success_outputs": [alias],
            "allow_pending_approval": True,
        },
        "live_execution": {"enabled": False, "allowed_tools": [], "requires_approval": True},
    }


def _build_event_driven_stub(
    manifest_id: str,
    name: str,
    command: str = "",
    inputs: list[str] | None = None,
    output_alias: str = "",
) -> dict:
    alias = _safe_alias(output_alias, "result")
    input_list = _parse_inputs(inputs)
    cmd = command.strip() if command.strip() else (
        f"[t:g/check -> {alias}] max_results=5"
    )
    return {
        "manifest_id": manifest_id,
        "name": name,
        "version": 1,
        "trigger": {"type": "event"},
        "inputs": input_list,
        "steps": [
            {"id": "handle_event", "command": cmd},
        ],
        "validations": [
            {"id": "no_runtime_errors", "type": "no_errors"},
            {
                "id": f"{alias}_exists",
                "type": "output_exists",
                "output": alias,
            },
        ],
        "completion": {
            "success_outputs": [alias],
            "acceptable_empty_outputs": [alias],
        },
        "live_execution": {"enabled": False, "allowed_tools": [], "requires_approval": True},
    }


# ---------------------------------------------------------------------------
# Event route snippet helper
# ---------------------------------------------------------------------------

def build_event_route_snippet(manifest: dict) -> str:
    manifest_id = str(manifest.get("manifest_id") or "")
    inputs = manifest.get("inputs") or []
    input_map: dict[str, str] = {}
    if isinstance(inputs, list):
        for inp in inputs:
            inp_name = str(inp).strip()
            if inp_name:
                input_map[inp_name] = f"payload.{inp_name}"
    route = {
        "route_id": manifest_id.replace(".", "_"),
        "source": "external",
        "event_type": "stub",
        "manifest_id": manifest_id,
        "input_map": input_map,
    }
    return json.dumps(route, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_alias(alias: str, default: str) -> str:
    a = re.sub(r"[^A-Za-z0-9_]", "_", str(alias or "").strip())
    a = a.strip("_")
    return a if a else default


def _parse_inputs(inputs: list[str] | None) -> list[str]:
    if not inputs:
        return []
    result = []
    for item in inputs:
        for part in str(item).split(","):
            part = part.strip()
            if part:
                result.append(part)
    return result
