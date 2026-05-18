from __future__ import annotations

from typing import Any


_DEFAULT_TOOL = "unknown_tool"
_DEFAULT_MODE = "local_static_check"
_DEFAULT_SOURCE = "builtin"
_DEFAULT_OPERATION = "validation"


def build_tool_evidence(
    *,
    tool: str,
    mode: str,
    source: str,
    operation: str,
    input_refs: list[str] | None = None,
    output_ref: str = "",
    extra: dict | None = None,
) -> dict:
    evidence = {
        "tool": str(tool or _DEFAULT_TOOL),
        "mode": str(mode or _DEFAULT_MODE),
        "source": str(source or _DEFAULT_SOURCE),
        "operation": str(operation or _DEFAULT_OPERATION),
        "input_refs": [str(item) for item in (input_refs or []) if str(item).strip()],
        "output_ref": str(output_ref or ""),
    }
    if extra:
        for key, value in extra.items():
            if value is None:
                continue
            if key == "input_refs":
                if isinstance(value, list):
                    evidence[key] = [str(item) for item in value if str(item).strip()]
                continue
            evidence[str(key)] = value
    return evidence


def normalize_evidence(
    evidence: object,
    *,
    fallback: dict,
) -> dict:
    fallback_evidence = _coerce_fallback_evidence(fallback)
    if isinstance(evidence, dict):
        normalized = dict(fallback_evidence)
        for key, value in evidence.items():
            if value is None:
                continue
            if key == "input_refs":
                normalized[key] = [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []
                continue
            normalized[str(key)] = value
        return _ensure_minimum_evidence(normalized, fallback_evidence)
    if isinstance(evidence, (list, tuple)):
        collected = [item for item in evidence if isinstance(item, dict)]
        if collected:
            normalized = dict(fallback_evidence)
            normalized["items"] = [dict(item) for item in collected]
            return _ensure_minimum_evidence(normalized, fallback_evidence)
    return _ensure_minimum_evidence(dict(fallback_evidence), fallback_evidence)


def validate_tool_result_contract(
    result: object,
    *,
    expected_type: str = "",
    require_evidence: bool = True,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    mapping = _result_mapping(result)
    if mapping is None:
        return {"ok": False, "errors": ["Result must be a dict-like object."], "warnings": []}

    required_keys = {"ok", "type", "data", "evidence", "error", "metadata"}
    missing = [key for key in required_keys if key not in mapping]
    if missing:
        errors.append(f"Missing required keys: {missing}")

    ok_value = mapping.get("ok")
    if not isinstance(ok_value, bool):
        errors.append("ok must be a bool.")

    result_type = str(mapping.get("type", "")).strip()
    if not result_type:
        errors.append("type must be a non-empty string.")
    elif expected_type and result_type != expected_type:
        errors.append(f"Expected type {expected_type!r}, got {result_type!r}.")

    evidence = mapping.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("evidence must be a dict.")
    elif require_evidence and not evidence:
        errors.append("evidence must not be empty.")

    error_text = str(mapping.get("error", ""))
    if isinstance(ok_value, bool):
        if ok_value and error_text:
            errors.append("error must be empty when ok is true.")
        if not ok_value and not error_text:
            errors.append("error must be populated when ok is false.")

    metadata = mapping.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata must be a dict.")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def _result_mapping(result: object) -> dict[str, Any] | None:
    if isinstance(result, dict):
        return result
    if hasattr(result, "__dict__"):
        return dict(vars(result))
    return None


def _coerce_fallback_evidence(fallback: dict) -> dict:
    data = dict(fallback or {})
    tool = str(data.get("tool", "")).strip() or _DEFAULT_TOOL
    mode = str(data.get("mode", "")).strip() or _DEFAULT_MODE
    source = str(data.get("source", "")).strip() or _DEFAULT_SOURCE
    operation = str(data.get("operation", "")).strip() or _DEFAULT_OPERATION
    input_refs = data.get("input_refs", [])
    if not isinstance(input_refs, list):
        input_refs = []
    output_ref = str(data.get("output_ref", "")).strip()
    result = {
        "tool": tool,
        "mode": mode,
        "source": source,
        "operation": operation,
        "input_refs": [str(item) for item in input_refs if str(item).strip()],
        "output_ref": output_ref,
    }
    for key, value in data.items():
        if key in result or value is None:
            continue
        result[key] = value
    return _ensure_minimum_evidence(result, result)


def _ensure_minimum_evidence(evidence: dict, fallback: dict) -> dict:
    normalized = dict(fallback)
    normalized.update({key: value for key, value in evidence.items() if value is not None})
    normalized["tool"] = str(normalized.get("tool", "")).strip() or _DEFAULT_TOOL
    normalized["mode"] = str(normalized.get("mode", "")).strip() or _DEFAULT_MODE
    normalized["source"] = str(normalized.get("source", "")).strip() or _DEFAULT_SOURCE
    normalized["operation"] = str(normalized.get("operation", "")).strip() or _DEFAULT_OPERATION
    input_refs = normalized.get("input_refs", [])
    if not isinstance(input_refs, list):
        input_refs = []
    normalized["input_refs"] = [str(item) for item in input_refs if str(item).strip()]
    normalized["output_ref"] = str(normalized.get("output_ref", "")).strip()
    if not normalized["input_refs"]:
        normalized["input_refs"] = []
    if "items" in normalized and not isinstance(normalized["items"], list):
        normalized.pop("items", None)
    return normalized
