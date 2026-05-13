from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.errors import ManifestLoadError, ManifestValidationError
from runtime.manifest_loader import load_manifest as runtime_load_manifest
from runtime.orchestrator import Orchestrator
from runtime.persistence import get_frame_dir, load_taskframe_dict, save_taskframe, write_json_atomic
from runtime.taskframe import to_dict as taskframe_to_dict
from runtime.taskframe_reload import taskframe_from_dict

from src.operator_data import collect_step_errors, collect_step_evidence, collect_step_outputs, collect_step_validations, find_manifest_step, find_runtime_step
from src.operator_reports import generate_report_for_frame, open_report_html


MANIFEST_DIRS = ("manifests", "config/manifests")


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


def run_workbench_dry_run(frame_id: str, mode: str, runtime_data_dir: str = "runtime_data") -> dict:
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

        if mode in {"step_next", "next"}:
            frame = orchestrator.run_next_step(frame, manifest, dry_run=True)
        else:
            frame = orchestrator.run_until_blocked(frame, manifest, dry_run=True)

        save_taskframe(frame, runtime_data_dir)
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
    return {
        "manifest_expected_steps": len(steps),
        "runtime_steps_created": len(runtime_steps),
        "completed": completed,
        "failed": failed,
        "skipped_not_reached": skipped,
        "completion_state": completion_state,
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
