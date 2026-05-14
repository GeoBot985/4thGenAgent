from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from runtime.errors import ManifestLoadError, ManifestValidationError
from runtime.failure_summary import classify_workbench_failure as _classify_workbench_failure
from runtime.manifest_loader import load_manifest as runtime_load_manifest
from runtime.orchestrator import Orchestrator
from runtime.persistence import get_frame_dir, load_taskframe_dict, save_taskframe, write_json_atomic
from runtime.taskframe import to_dict as taskframe_to_dict
from runtime.taskframe_reload import taskframe_from_dict
from runtime.google_sheet_tools import use_sheet_fixture_mode

from src.operator_data import collect_step_errors, collect_step_evidence, collect_step_outputs, collect_step_validations, find_manifest_step, find_runtime_step
from src.operator_reports import generate_report_for_frame, open_report_html


MANIFEST_DIRS = ("manifests", "config/manifests")


def new_manifest_template() -> dict:
    return {
        "manifest_id": "example.new_manifest",
        "name": "New Manifest",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [],
        "validations": [],
        "completion": {"success_outputs": []},
        "live_execution": {"enabled": False, "allowed_tools": [], "requires_approval": True},
    }


def manifest_filename_for_id(manifest_id: str) -> str:
    safe = _string(manifest_id).strip().replace(".", "_")
    safe = safe.replace("/", "_").replace("\\", "_")
    return f"{safe}.manifest.json" if safe else "manifest.manifest.json"


def validate_manifest_json_text(text: str) -> dict:
    raw_text = str(text or "")
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return {"ok": False, "manifest_id": "", "path": "", "validated": False, "error": f"Invalid JSON: {exc.msg}"}
    if not isinstance(raw, dict):
        return {"ok": False, "manifest_id": "", "path": "", "validated": False, "error": "Manifest root must be a JSON object."}
    tmp_path = Path()
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".manifest.json", delete=False, encoding="utf-8") as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(json.dumps(raw, indent=2, ensure_ascii=False))
        manifest = runtime_load_manifest(tmp_path)
        summary = build_manifest_summary(manifest)
        return {
            "ok": True,
            "manifest_id": summary.get("manifest_id", ""),
            "path": "",
            "validated": True,
            "error": "",
            "manifest": _manifest_to_dict(manifest),
            "summary": summary,
        }
    except Exception as exc:
        return {"ok": False, "manifest_id": _string(raw.get("manifest_id") or raw.get("id")), "path": "", "validated": False, "error": str(exc)}
    finally:
        if tmp_path and tmp_path.is_file():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def save_manifest_json_text(
    text: str,
    target_path: str | None = None,
    manifest_dir: str = "manifests",
    allow_overwrite: bool = False,
) -> dict:
    validation = validate_manifest_json_text(text)
    if not validation.get("ok"):
        return {
            "ok": False,
            "manifest_id": "",
            "path": "",
            "validated": False,
            "error": validation.get("error", "Manifest validation failed."),
        }

    manifest = validation.get("manifest", {})
    manifest_id = _string(manifest.get("manifest_id") if isinstance(manifest, dict) else "")
    if not manifest_id:
        return {"ok": False, "manifest_id": "", "path": "", "validated": False, "error": "manifest_id is required."}

    if target_path:
        target = Path(target_path)
        if target.suffix not in {".json", ".manifest.json"} and not str(target).endswith(".manifest.json"):
            return {
                "ok": False,
                "manifest_id": manifest_id,
                "path": str(target),
                "validated": True,
                "error": "Target file must end with .json or .manifest.json.",
            }
    else:
        target = Path(manifest_dir) / manifest_filename_for_id(manifest_id)

    target_parent = target.parent
    target_parent.mkdir(parents=True, exist_ok=True)

    catalog = list_manifest_catalog(manifest_dir)
    for entry in catalog:
        if _string(entry.get("manifest_id")) != manifest_id:
            continue
        existing_path = Path(str(entry.get("path", ""))).resolve()
        target_resolved = target.resolve()
        if existing_path != target_resolved:
            return {
                "ok": False,
                "manifest_id": manifest_id,
                "path": str(target),
                "validated": True,
                "error": f"A manifest with this ID already exists at {existing_path}. Use Save As or change manifest_id.",
            }
        if existing_path == target_resolved and not allow_overwrite:
            return {
                "ok": False,
                "manifest_id": manifest_id,
                "path": str(target),
                "validated": True,
                "error": f"Manifest file already exists: {target}. Overwrite is blocked unless explicitly allowed.",
            }

    if target.exists() and not allow_overwrite:
        return {
            "ok": False,
            "manifest_id": manifest_id,
            "path": str(target),
            "validated": True,
            "error": f"Manifest file already exists: {target}. Overwrite is blocked unless explicitly allowed.",
        }

    try:
        write_json_atomic(target, manifest)
        return {"ok": True, "manifest_id": manifest_id, "path": str(target), "validated": True, "error": ""}
    except Exception as exc:
        return {"ok": False, "manifest_id": manifest_id, "path": str(target), "validated": True, "error": str(exc)}


def list_manifest_catalog(manifest_dir: str = "manifests") -> list[dict]:
    entries: list[dict] = []
    seen_paths: set[str] = set()
    for base_dir in _candidate_manifest_dirs(manifest_dir):
        base_path = Path(base_dir)
        if not base_path.is_dir():
            continue
        for path in sorted(base_path.glob("*.json")):
            resolved = str(path.resolve())
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            entry = _catalog_entry_for_path(path)
            if entry is not None:
                entries.append(entry)
    entries.sort(key=lambda item: (str(item.get("manifest_id", "")), str(item.get("name", "")), str(item.get("path", ""))))
    return entries


def load_manifest_for_workbench(path_or_id: str) -> dict:
    target = str(path_or_id or "").strip()
    if not target:
        return _failure_result("", "Manifest path or manifest_id is required.")

    try:
        manifest_record = _load_manifest_record(target)
        manifest = manifest_record["manifest"]
        summary = build_manifest_summary(manifest)
        step_rows = build_manifest_step_rows(manifest)
        validation = validate_manifest_for_workbench(target)
        return {
            "ok": True,
            "path": manifest_record["path"],
            "manifest_id": summary.get("manifest_id", ""),
            "manifest": _manifest_to_dict(manifest),
            "summary": summary,
            "step_rows": step_rows,
            "validation": validation,
            "error": "",
        }
    except Exception as exc:
        return _failure_result(target, str(exc))


def validate_manifest_for_workbench(path_or_id: str) -> dict:
    target = str(path_or_id or "").strip()
    if not target:
        return _failure_result("", "Manifest path or manifest_id is required.")

    try:
        manifest_record = _load_manifest_record(target)
        manifest = manifest_record["manifest"]
        summary = build_manifest_summary(manifest)
        return {
            "ok": True,
            "path": manifest_record["path"],
            "manifest_id": summary.get("manifest_id", ""),
            "summary": summary,
            "errors": [],
            "error": "",
        }
    except Exception as exc:
        return _failure_result(target, str(exc))


def build_manifest_summary(manifest: Any) -> dict:
    data = _manifest_to_dict(manifest)
    required_inputs = _required_inputs(data)
    steps = _list_value(data.get("steps"))
    validations = _list_value(data.get("validations"))
    completion = _dict_value(data.get("completion"))
    return {
        "manifest_id": _string(data.get("manifest_id") or data.get("id")),
        "name": _string(data.get("name")),
        "version": data.get("version", ""),
        "trigger": _trigger_text(data.get("trigger") if isinstance(data.get("trigger"), dict) else data.get("trigger_type")),
        "required_inputs": required_inputs,
        "step_count": len(steps),
        "validation_count": len(validations),
        "completion_rules": completion,
        "live_execution_policy": _dict_value(data.get("live_execution")),
        "side_effect": bool(data.get("side_effect", False)),
        "raw": data,
    }


def build_manifest_step_rows(manifest: Any) -> list[dict]:
    data = _manifest_to_dict(manifest)
    rows: list[dict] = []
    for index, item in enumerate(_list_value(data.get("steps")), start=1):
        if not isinstance(item, dict):
            continue
        command = _string(item.get("command"))
        rows.append(
            {
                "#": index,
                "step_id": _string(item.get("step_id") or item.get("id")),
                "command": command,
                "kind": _string(item.get("kind")),
                "output_alias": _string(item.get("output_alias") or item.get("output")),
                "when_condition": _compact_json(item.get("when")),
                "retry_policy": _compact_json(item.get("retry") or item.get("retry_policy")),
                "timeout": item.get("timeout_seconds", ""),
                "raw": dict(item),
            }
        )
    return rows


def create_test_frame(manifest_id: str, inputs: dict, runtime_data_dir: str = "runtime_data") -> dict:
    target = str(manifest_id or "").strip()
    if not target:
        return _failure_result("", "manifest_id is required.")

    try:
        manifest = _load_manifest_model(target)
        normalized_inputs = dict(inputs) if isinstance(inputs, dict) else {}
        missing = _missing_required_inputs(manifest, normalized_inputs)
        if missing:
            return {
                "ok": False,
                "frame_id": "",
                "manifest_id": _string(getattr(manifest, "manifest_id", target)),
                "state": "FAILED_VALIDATION",
                "missing_required_inputs": missing,
                "error": f"Missing required inputs: {', '.join(missing)}",
                "frame": {},
                "summary": build_manifest_summary(manifest),
                "comparison": {},
            }

        orchestrator = Orchestrator(runtime_data_dir=runtime_data_dir)
        frame = orchestrator.create_frame_from_manifest(
            manifest,
            trigger=dict(getattr(manifest, "trigger", {}) or {}),
            inputs=normalized_inputs,
            raw_input=json.dumps(normalized_inputs, indent=2, sort_keys=True),
        )
        frame = orchestrator.prepare_frame(frame)
        save_taskframe(frame, runtime_data_dir)
        _write_manifest_sidecar(frame.frame_id, manifest, runtime_data_dir)
        frame_dict = _frame_to_dict(frame)
        return {
            "ok": True,
            "frame_id": frame.frame_id,
            "manifest_id": frame.manifest_id,
            "state": frame.state,
            "current_step_id": frame.current_step_id or "",
            "frame": frame_dict,
            "summary": build_manifest_summary(manifest),
            "comparison": build_manifest_run_comparison(manifest, frame_dict),
            "error": "",
        }
    except Exception as exc:
        return _failure_result(target, str(exc))


def run_workbench_dry_run(frame_id: str, mode: str, runtime_data_dir: str = "runtime_data", fixture_mode: bool = True) -> dict:
    return _run_workbench_dry_run(frame_id, mode, runtime_data_dir=runtime_data_dir, fixture_mode=fixture_mode)


def _run_workbench_dry_run(frame_id: str, mode: str, runtime_data_dir: str = "runtime_data", fixture_mode: bool = True) -> dict:
    target = str(frame_id or "").strip()
    if not target:
        return _failure_result("", "frame_id is required.")

    try:
        frame_dict = load_taskframe_dict(target, runtime_data_dir)
        frame = taskframe_from_dict(frame_dict)
        manifest = _load_manifest_model(frame.manifest_id, frame.frame_id, runtime_data_dir)
        orchestrator = Orchestrator(runtime_data_dir=runtime_data_dir)

        if frame.state == "CREATED":
            frame = orchestrator.prepare_frame(frame)

        with use_sheet_fixture_mode(fixture_mode, runtime_data_dir):
            if mode in {"step_next", "next"}:
                frame = orchestrator.run_next_step(frame, manifest, dry_run=True)
            else:
                frame = orchestrator.run_until_blocked(frame, manifest, dry_run=True)

        save_taskframe(frame, runtime_data_dir)
        frame_dict = _frame_to_dict(frame)
        selected_step = build_workbench_step_result(manifest, frame_dict, _selected_runtime_step_id(frame_dict))
        run_summary = build_workbench_run_summary(frame_dict, manifest)
        return {
            "ok": True,
            "frame_id": frame.frame_id,
            "manifest_id": frame.manifest_id,
            "state": frame.state,
            "current_step_id": frame.current_step_id or "",
            "frame": frame_dict,
            "summary": build_manifest_summary(manifest),
            "comparison": build_manifest_run_comparison(manifest, frame_dict),
            "run_summary": run_summary,
            "selected_step": selected_step,
            "pending_actions": frame_dict.get("pending_actions", []),
            "completed_steps": _count_step_status(frame_dict, "COMPLETED"),
            "failed_steps": _count_step_status(frame_dict, "FAILED"),
            "skipped_steps": _count_step_status(frame_dict, "SKIPPED"),
            "errors": frame_dict.get("errors", []),
            "error": "",
        }
    except Exception as exc:
        return _failure_result(target, str(exc))


def build_manifest_run_comparison(manifest: Any, frame: Any) -> dict:
    manifest_dict = _manifest_to_dict(manifest)
    frame_dict = _frame_to_dict(frame)
    steps = _list_value(manifest_dict.get("steps"))
    runtime_steps = _list_value(frame_dict.get("steps"))
    completed = _count_step_status(frame_dict, "COMPLETED")
    failed = _count_step_status(frame_dict, "FAILED")
    skipped = _count_step_status(frame_dict, "SKIPPED") + _count_step_status(frame_dict, "PENDING")
    completion_state = _string(frame_dict.get("state"))
    if isinstance(frame_dict.get("completion_gate_result"), dict):
        completion_state = _string(frame_dict["completion_gate_result"].get("status")) or completion_state
    failure_summary = _failure_summary_for_frame(frame_dict)
    return {
        "manifest_expected_steps": len(steps),
        "runtime_steps_created": len(runtime_steps),
        "completed": completed,
        "failed": failed,
        "skipped_not_reached": skipped,
        "completion_state": completion_state,
        "failure_category": failure_summary.get("failure_category", ""),
        "failed_step_id": failure_summary.get("failed_step_id", ""),
        "operator_explanation": failure_summary.get("operator_explanation", ""),
    }


def build_workbench_step_result(manifest: Any, frame: Any, step_id: str | None = None) -> dict:
    manifest_dict = _manifest_to_dict(manifest)
    frame_dict = _frame_to_dict(frame)
    resolved_step_id = str(step_id or "").strip() or _selected_runtime_step_id(frame_dict) or _first_manifest_step_id(manifest_dict)
    manifest_step = find_manifest_step(manifest_dict, resolved_step_id)
    runtime_step = find_runtime_step(frame_dict, resolved_step_id)
    output_alias = _step_output_alias(manifest_step, runtime_step)
    output_value = _output_value(frame_dict, output_alias)
    tool_call = _step_related_items(frame_dict, resolved_step_id, "tool_calls")
    llm_call = _step_related_items(frame_dict, resolved_step_id, "llm_calls")
    validations = collect_step_validations(frame_dict, resolved_step_id)
    evidence = collect_step_evidence(frame_dict, resolved_step_id)
    errors = collect_step_errors(frame_dict, resolved_step_id)
    failure = _classify_workbench_failure(_step_failure_error(frame_dict, resolved_step_id), runtime_step or manifest_step)
    step_outcome = _build_step_outcome(manifest_step, runtime_step, output_alias, output_value, tool_call, failure)
    return {
        "step_id": resolved_step_id,
        "command": _string(manifest_step.get("command") if isinstance(manifest_step, dict) else ""),
        "kind": _string(manifest_step.get("kind") if isinstance(manifest_step, dict) else ""),
        "step_status": _string(runtime_step.get("status") if isinstance(runtime_step, dict) else ""),
        "output_alias": output_alias,
        "output_value": output_value,
        "tool_result_metadata": _tool_result_metadata(output_value),
        "step_outcome": step_outcome,
        "tool_call_result": _summarize_related_call(tool_call, preferred_alias=output_alias, output_value=output_value, failure=failure),
        "llm_call_result": _summarize_related_call(llm_call, preferred_alias=output_alias, output_value=output_value),
        "failure": failure,
        "validation_result": validations,
        "evidence": evidence,
        "errors": errors,
        "raw_manifest_step": manifest_step,
        "raw_runtime_step": runtime_step,
    }


def build_workbench_selected_step_detail(manifest: Any, frame: Any, step_id: str | None = None) -> dict:
    return build_workbench_step_result(manifest, frame, step_id)


def classify_workbench_failure(error: dict | str, step: dict | None = None) -> dict:
    return _classify_workbench_failure(error, step)


def build_workbench_run_summary(frame: dict, manifest: dict | None = None) -> dict:
    frame_dict = _frame_to_dict(frame)
    manifest_dict = _manifest_to_dict(manifest) if manifest is not None else {}
    failure_summary = _failure_summary_for_frame(frame_dict)
    comparison = build_manifest_run_comparison(manifest_dict, frame_dict) if manifest_dict else build_manifest_run_comparison(frame_dict.get("manifest", {}), frame_dict)
    return {
        "frame_id": _string(frame_dict.get("frame_id")),
        "state": _string(frame_dict.get("state")),
        "comparison": comparison,
        "failure_category": failure_summary.get("failure_category", ""),
        "failed_step_id": failure_summary.get("failed_step_id", ""),
        "operator_explanation": failure_summary.get("operator_explanation", ""),
        "recommended_action": failure_summary.get("recommended_action", ""),
        "failure_summary": failure_summary,
    }


def generate_workbench_run_report(frame_id: str, runtime_data_dir: str = "runtime_data") -> dict:
    return generate_report_for_frame(frame_id, runtime_data_dir)


def open_workbench_run_report(path: str) -> dict:
    return open_report_html(path)


def _candidate_manifest_dirs(manifest_dir: str) -> list[str]:
    dirs = [manifest_dir]
    if Path(manifest_dir).name == "manifests":
        dirs.extend(MANIFEST_DIRS[1:])
    ordered: list[str] = []
    for item in dirs:
        normalized = str(item).strip()
        if normalized and normalized not in ordered:
            ordered.append(normalized)
    return ordered


def _catalog_entry_for_path(path: Path) -> dict | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "ok": False,
            "path": str(path),
            "manifest_id": "",
            "name": path.stem,
            "version": "",
            "trigger": "",
            "step_count": 0,
            "validation_count": 0,
            "error": "Unable to read manifest JSON.",
        }

    if not isinstance(raw, dict):
        return None
    if "manifest_id" not in raw and "id" not in raw:
        return None

    try:
        manifest = runtime_load_manifest(path)
        summary = build_manifest_summary(manifest)
        return {
            "ok": True,
            "path": str(path),
            "manifest_id": summary.get("manifest_id", ""),
            "name": summary.get("name", ""),
            "version": summary.get("version", ""),
            "trigger": summary.get("trigger", ""),
            "step_count": summary.get("step_count", 0),
            "validation_count": summary.get("validation_count", 0),
            "error": "",
            "raw": raw,
        }
    except Exception as exc:
        return {
            "ok": False,
            "path": str(path),
            "manifest_id": _string(raw.get("manifest_id") or raw.get("id")),
            "name": _string(raw.get("name")),
            "version": raw.get("version", ""),
            "trigger": _trigger_text(raw.get("trigger") if isinstance(raw.get("trigger"), dict) else raw.get("trigger_type")),
            "step_count": len(_list_value(raw.get("steps"))),
            "validation_count": len(_list_value(raw.get("validations"))),
            "error": str(exc),
            "raw": raw,
        }


def _load_manifest_record(path_or_id: str) -> dict:
    candidate = Path(path_or_id)
    if candidate.is_file():
        manifest = runtime_load_manifest(candidate)
        return {"path": str(candidate), "manifest": manifest}

    catalog = list_manifest_catalog()
    match = next((item for item in catalog if item.get("manifest_id") == path_or_id and item.get("ok", True) and item.get("path")), None)
    if match:
        manifest = runtime_load_manifest(match["path"])
        return {"path": str(match["path"]), "manifest": manifest}
    raise ManifestLoadError(f"Manifest not found for manifest_id: {path_or_id}")


def _load_manifest_model(path_or_id: str, frame_id: str | None = None, runtime_data_dir: str = "runtime_data") -> Any:
    if frame_id:
        sidecar = _manifest_sidecar_path(frame_id, runtime_data_dir)
        if sidecar.is_file():
            return runtime_load_manifest(sidecar)
    record = _load_manifest_record(path_or_id)
    return record["manifest"]


def _missing_required_inputs(manifest: Any, inputs: dict) -> list[str]:
    required = _required_inputs(_manifest_to_dict(manifest))
    missing = []
    for item in required:
        if item not in inputs or inputs.get(item) in {"", None}:
            missing.append(item)
    return missing


def _required_inputs(data: dict) -> list[str]:
    inputs = data.get("inputs", [])
    if isinstance(inputs, list):
        return [str(item) for item in inputs if str(item).strip()]
    if isinstance(inputs, dict):
        required = inputs.get("required", [])
        if isinstance(required, list):
            return [str(item) for item in required if str(item).strip()]
    return []


def _compact_json(value: Any) -> str:
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _trigger_text(trigger: Any) -> str:
    if isinstance(trigger, dict):
        for key in ("type", "route_id", "event_type"):
            value = trigger.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return _compact_json(trigger)
    if isinstance(trigger, str):
        return trigger
    return ""


def _manifest_to_dict(manifest: Any) -> dict:
    if manifest is None:
        return {}
    if isinstance(manifest, dict):
        return dict(manifest)
    return {
        "manifest_id": getattr(manifest, "manifest_id", ""),
        "id": getattr(manifest, "manifest_id", ""),
        "name": getattr(manifest, "name", ""),
        "version": getattr(manifest, "version", ""),
        "trigger": dict(getattr(manifest, "trigger", {}) or {}),
        "inputs": list(getattr(manifest, "inputs", []) or []),
        "steps": [dict(step.__dict__) if hasattr(step, "__dict__") else step for step in getattr(manifest, "steps", []) or []],
        "validations": list(getattr(manifest, "validations", []) or []),
        "completion": dict(getattr(manifest, "completion", {}) or {}),
        "live_execution": dict(getattr(manifest, "live_execution", {}) or {}),
        "side_effect": bool(getattr(manifest, "side_effect", False)),
    }


def _frame_to_dict(frame: Any) -> dict:
    if frame is None:
        return {}
    if isinstance(frame, dict):
        return dict(frame)
    if hasattr(frame, "frame_id") and hasattr(frame, "steps"):
        try:
            return taskframe_to_dict(frame)
        except Exception:
            pass
    if hasattr(frame, "__dict__"):
        return dict(frame.__dict__)
    return {}


def _count_step_status(frame: dict, status: str) -> int:
    return sum(1 for item in _list_value(frame.get("steps")) if isinstance(item, dict) and str(item.get("status", "")).upper() == status.upper())


def _selected_runtime_step_id(frame: dict) -> str:
    current = _string(frame.get("current_step_id"))
    if current:
        return current
    for item in _list_value(frame.get("steps")):
        if isinstance(item, dict) and str(item.get("status", "")).upper() == "COMPLETED":
            return _string(item.get("step_id") or item.get("id"))
    for item in _list_value(frame.get("steps")):
        if isinstance(item, dict):
            return _string(item.get("step_id") or item.get("id"))
    return ""


def _first_manifest_step_id(manifest: dict) -> str:
    for item in _list_value(manifest.get("steps")):
        if isinstance(item, dict):
            return _string(item.get("step_id") or item.get("id"))
    return ""


def _step_output_alias(manifest_step: dict, runtime_step: dict) -> str:
    for key in ("output_alias", "output", "result_ref"):
        if isinstance(manifest_step, dict):
            value = manifest_step.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(runtime_step, dict):
            value = runtime_step.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _output_value(frame: dict, output_alias: str) -> Any:
    if not output_alias:
        return {}
    outputs = frame.get("outputs", {})
    if not isinstance(outputs, dict):
        return {}
    return outputs.get(output_alias, {})


def _step_related_items(frame: dict, step_id: str, key: str) -> list[dict]:
    items = frame.get(key, [])
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict) and (not step_id or _string(item.get("step_id") or item.get("id")) == step_id)]


def _summarize_output_value(value: Any) -> dict:
    if isinstance(value, dict):
        metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
        if {"label", "confidence", "reason"}.intersection(value.keys()):
            return {
                "title": "Classification result",
                "lines": [
                    f"Classified as: {_string(value.get('label'))}",
                    f"Confidence: {_string(value.get('confidence'))}",
                    f"Reason: {_string(value.get('reason'))}",
                ],
            }
        if metadata:
            lines = []
            if metadata.get("source") == "workbench_fixture":
                lines.append("Source: fixture data")
            elif metadata.get("source"):
                lines.append(f"Source: {_string(metadata.get('source'))}")
            if "live_external_call" in metadata:
                lines.append(f"Live external call: {'yes' if metadata.get('live_external_call') else 'no'}")
            if "dry_run" in value:
                lines.append(f"Dry-run: {'yes' if value.get('dry_run') else 'no'}")
            if "fixture_mode" in value:
                lines.append(f"Fixture mode: {'yes' if value.get('fixture_mode') else 'no'}")
            if value.get("row_count") is not None:
                lines.append(f"Rows: {_string(value.get('row_count'))}")
            if not lines:
                lines = [f"{key}: {_string(val)}" for key, val in value.items() if key != "raw"]
            return {"title": "Fixture result" if metadata.get("source") == "workbench_fixture" else "Output value", "lines": lines or ["No structured output value."]}
        lines = [f"{key}: {_string(val)}" for key, val in value.items() if key != "raw"]
        return {"title": "Output value", "lines": lines or ["No structured output value."]}
    if value is None:
        return {"title": "Output value", "lines": ["No output value."]}
    return {"title": "Output value", "lines": [str(value)]}


def _summarize_related_call(items: list[dict], preferred_alias: str = "", output_value: Any = None, failure: dict | None = None) -> dict:
    if not items:
        if failure and failure.get("category"):
            return {
                "title": failure.get("title", "Call result"),
                "lines": [
                    f"Failure type: { _failure_label(failure.get('category', 'unknown_failure'))}",
                    f"Reason: {_string(failure.get('reason') or failure.get('summary'))}",
                    f"Recommended action: {_string(failure.get('recommended_action'))}",
                ],
            }
        return {"title": "No call result", "lines": ["No call result available."]}
    first = items[-1]
    lines = []
    if first.get("action"):
        lines.append(f"Action: {_string(first.get('action'))}")
    if preferred_alias:
        lines.append(f"Output alias: {preferred_alias}")
    status = _string(first.get("status"))
    if status:
        lines.append(f"Status: {status}")
    if isinstance(output_value, dict) and {"label", "confidence", "reason"}.intersection(output_value.keys()):
        lines.append(f"Classified as: {_string(output_value.get('label'))}")
    if isinstance(output_value, dict):
        metadata = output_value.get("metadata") if isinstance(output_value.get("metadata"), dict) else {}
        if metadata.get("source") == "workbench_fixture":
            lines.append("Source: fixture data")
        elif metadata.get("source"):
            lines.append(f"Source: {_string(metadata.get('source'))}")
        if "live_external_call" in metadata:
            lines.append(f"Live external call: {'yes' if metadata.get('live_external_call') else 'no'}")
        if "fixture_mode" in output_value:
            lines.append(f"Fixture mode: {'yes' if output_value.get('fixture_mode') else 'no'}")
    return {"title": "LLM call result" if first.get("action", "").startswith("classify") or first.get("action", "").startswith("draft") else "Tool call result", "lines": lines or ["Call completed."]}


def _tool_result_metadata(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    metadata = value.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _step_failure_error(frame: dict, step_id: str) -> dict | str:
    if not isinstance(frame, dict):
        return ""
    for error in _list_value(frame.get("errors")):
        if isinstance(error, dict) and (not step_id or _string(error.get("step_id")) == step_id):
            return error
    for item in _list_value(frame.get("validations")):
        if isinstance(item, dict) and item.get("ok") is False and (not step_id or _string(item.get("step_id")) == step_id):
            return item
    return ""


def _failure_summary_for_frame(frame: dict) -> dict:
    if not isinstance(frame, dict):
        return {}
    from runtime.failure_summary import build_failure_summary

    return build_failure_summary(frame)


def _build_step_outcome(manifest_step: dict, runtime_step: dict, output_alias: str, output_value: Any, tool_call: list[dict], failure: dict) -> dict:
    if failure.get("category"):
        lines = []
        tool_args = _latest_tool_args(tool_call)
        if failure.get("category") == "external_auth_failure":
            range_name = _string(tool_args.get("range_name")) if isinstance(tool_args, dict) else ""
            spreadsheet_id = _string(tool_args.get("spreadsheet_id")) if isinstance(tool_args, dict) else ""
            if range_name and spreadsheet_id:
                lines.insert(0, f"Could not read {range_name} from spreadsheet {spreadsheet_id}.")
            else:
                lines.insert(0, _string(failure.get("summary")) or "This step failed.")
            lines.extend(
                [
                    f"Failure type: {_failure_label(failure.get('category', 'unknown_failure'))}",
                    f"Reason: {_string(failure.get('reason') or failure.get('summary'))}",
                    "Safe outcome: Workflow stopped before any side effect was created.",
                    f"Recommended action: {_string(failure.get('recommended_action'))}",
                ]
            )
        elif failure.get("category") == "fixture_missing":
            lines.extend(
                [
                    "Fixture data not available for this tool/range.",
                    f"Failure type: {_failure_label(failure.get('category', 'unknown_failure'))}",
                    f"Recommended action: {_string(failure.get('recommended_action'))}",
                ]
            )
        else:
            lines.append("This step failed.")
            lines.extend(
                [
                    f"Failure type: {_failure_label(failure.get('category', 'unknown_failure'))}",
                    f"Reason: {_string(failure.get('reason') or failure.get('summary'))}",
                    f"Recommended action: {_string(failure.get('recommended_action'))}",
                ]
            )
        return {"title": failure.get("title", "This step failed."), "summary": failure.get("summary", "This step failed."), "lines": lines}
    return _summarize_output_value(output_value)


def _latest_tool_args(tool_call: list[dict]) -> dict:
    if not tool_call:
        return {}
    item = tool_call[-1] if isinstance(tool_call[-1], dict) else {}
    args = item.get("args", {})
    return args if isinstance(args, dict) else {}


def _failure_label(category: str) -> str:
    return {
        "manifest_validation_failure": "Manifest/config problem",
        "missing_required_input": "Missing required input",
        "tool_execution_failure": "Tool/runtime failure",
        "external_auth_failure": "External authentication failure",
        "external_dependency_unavailable": "External dependency unavailable",
        "business_validation_failure": "Business validation failure",
        "fixture_missing": "Fixture data not available",
        "unknown_failure": "Unknown failure",
    }.get(category, "Unknown failure")


def _list_value(value: Any) -> list:
    return value if isinstance(value, list) else []


def _dict_value(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _failure_result(target: str, error: str) -> dict:
    return {
        "ok": False,
        "frame_id": "",
        "manifest_id": "",
        "path": target,
        "state": "FAILED",
        "summary": {},
        "comparison": {},
        "step_rows": [],
        "manifest": {},
        "frame": {},
        "errors": [error] if error else [],
        "error": error,
    }


def _write_manifest_sidecar(frame_id: str, manifest: Any, runtime_data_dir: str) -> None:
    try:
        manifest_path = _manifest_sidecar_path(frame_id, runtime_data_dir)
        raw = _manifest_raw_data(manifest)
        if raw:
            write_json_atomic(manifest_path, raw)
    except Exception:
        pass


def _manifest_sidecar_path(frame_id: str, runtime_data_dir: str) -> Path:
    return get_frame_dir(frame_id, runtime_data_dir) / "manifest.json"


def _manifest_raw_data(manifest: Any) -> dict:
    if manifest is None:
        return {}
    if isinstance(manifest, dict):
        return dict(manifest)
    raw = getattr(manifest, "raw", None)
    if isinstance(raw, dict) and raw:
        return dict(raw)
    return _manifest_to_dict(manifest)
