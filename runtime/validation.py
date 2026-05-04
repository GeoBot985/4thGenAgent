from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .errors import UnknownValidationTypeError, ValidationEngineError
from .conditions import evaluate_condition, validate_condition
from .memory_store import MemoryStore
from .models import Manifest, TaskFrame, ValidationResult, validation_fail, validation_ok
from .taskframe import add_audit_event, utc_now


def run_validation(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    validation_type = validation.get("type")
    validation_id = validation.get("id", "")
    handler = VALIDATION_HANDLERS.get(validation_type)
    if handler is None:
        raise UnknownValidationTypeError(f"Unknown validation type: {validation_type}")
    return handler(frame, validation, memory_store=memory_store)


def find_validation_rule(
    manifest: Manifest,
    validation_id: str,
) -> dict[str, Any]:
    for validation in manifest.validations:
        if validation.get("id") == validation_id:
            return validation
    raise ValidationEngineError(f"Validation rule not found: {validation_id}")


def run_validation_step(
    frame: TaskFrame,
    manifest: Manifest,
    validation_id: str,
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    validation = find_validation_rule(manifest, validation_id)
    result = run_validation(frame, validation, memory_store=memory_store)
    record = asdict(result)
    record["type"] = record["validation_type"]
    frame.validations.append(record)
    event_type = "VALIDATION_STEP_PASSED" if result.ok else "VALIDATION_STEP_FAILED"
    add_audit_event(
        frame,
        event_type,
        result.message,
        {"validation_id": result.validation_id, "type": result.validation_type, "ok": result.ok},
    )
    return result


def validate_output_exists(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    output = validation.get("output")
    if not output:
        raise ValidationEngineError("output_exists requires output.")
    if output in frame.outputs:
        return validation_ok(validation["id"], validation["type"], f"Output exists: {output}", {"output": output})
    message = "ORDER_ID_NOT_FOUND" if output == "order_ref" else f"Missing output: {output}"
    return validation_fail(validation["id"], validation["type"], message, {"output": output})


def validate_output_not_empty(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    output = validation.get("output")
    if not output:
        raise ValidationEngineError("output_not_empty requires output.")
    if output not in frame.outputs:
        return validation_fail(validation["id"], validation["type"], f"Missing output: {output}", {"output": output})
    value = frame.outputs[output]
    if _is_empty_value(value):
        return validation_fail(validation["id"], validation["type"], f"Output is empty: {output}", {"output": output})
    return validation_ok(validation["id"], validation["type"], f"Output is not empty: {output}", {"output": output})


def validate_pending_action_exists(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    tool = validation.get("tool")
    output = validation.get("output")
    if not tool and not output:
        raise ValidationEngineError("pending_action_exists requires tool and/or output.")
    for pending in frame.pending_actions:
        if tool and pending.get("tool") != tool:
            continue
        if output and pending.get("output_alias") != output:
            continue
        return validation_ok(
            validation["id"],
            validation["type"],
            "Pending action exists.",
            {"tool": tool, "output": output},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        "Pending action not found.",
        {"tool": tool, "output": output},
    )


def validate_step_completed(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    step_id = validation.get("step")
    step = _find_step(frame, step_id)
    if step is None:
        return validation_fail(validation["id"], validation["type"], f"Step not found: {step_id}", {"step": step_id})
    if step.status == "COMPLETED":
        return validation_ok(validation["id"], validation["type"], f"Step completed: {step_id}", {"step": step_id})
    return validation_fail(validation["id"], validation["type"], f"Step not completed: {step_id}", {"step": step_id, "status": step.status})


def validate_step_staged(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    step_id = validation.get("step")
    step = _find_step(frame, step_id)
    if step is None:
        return validation_fail(validation["id"], validation["type"], f"Step not found: {step_id}", {"step": step_id})
    if step.status == "STAGED":
        return validation_ok(validation["id"], validation["type"], f"Step staged: {step_id}", {"step": step_id})
    return validation_fail(validation["id"], validation["type"], f"Step not staged: {step_id}", {"step": step_id, "status": step.status})


def validate_step_status(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    step_id = validation.get("step")
    expected_status = validation.get("status")
    step = _find_step(frame, step_id)
    if step is None:
        return validation_fail(validation["id"], validation["type"], f"Step not found: {step_id}", {"step": step_id})
    if step.status == expected_status:
        return validation_ok(
            validation["id"],
            validation["type"],
            f"Step status matches: {step_id}",
            {"step": step_id, "status": expected_status},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        f"Step status does not match: {step_id}",
        {"step": step_id, "status": expected_status, "actual": step.status},
    )


def validate_step_duration_under(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    step_id = validation.get("step")
    max_ms = validation.get("max_ms")
    step = _find_step(frame, step_id)
    if step is None:
        return validation_fail(validation["id"], validation["type"], f"Step not found: {step_id}", {"step": step_id})
    if max_ms is None:
        raise ValidationEngineError("step_duration_under requires max_ms.")
    if step.duration_ms <= max_ms:
        return validation_ok(
            validation["id"],
            validation["type"],
            f"Step duration under threshold: {step_id}",
            {"step": step_id, "max_ms": max_ms, "duration_ms": step.duration_ms},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        f"Step duration over threshold: {step_id}",
        {"step": step_id, "max_ms": max_ms, "duration_ms": step.duration_ms},
    )


def validate_step_timed_out(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    return _validate_step_timeout_flag(frame, validation, expected=True)


def validate_step_not_timed_out(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    return _validate_step_timeout_flag(frame, validation, expected=False)


def validate_attempt_count_equals(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    step_id = validation.get("step")
    expected = validation.get("count")
    if expected is None:
        raise ValidationEngineError("attempt_count_equals requires count.")
    actual = _step_attempt_count(frame, step_id)
    if actual is None:
        return validation_fail(validation["id"], validation["type"], f"Step not found: {step_id}", {"step": step_id})
    if actual == expected:
        return validation_ok(
            validation["id"],
            validation["type"],
            "Attempt count matches.",
            {"step": step_id, "count": expected, "actual": actual},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        "Attempt count does not match.",
        {"step": step_id, "count": expected, "actual": actual},
    )


def validate_attempt_count_less_than_or_equal(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    step_id = validation.get("step")
    expected = validation.get("count")
    if expected is None:
        raise ValidationEngineError("attempt_count_less_than_or_equal requires count.")
    actual = _step_attempt_count(frame, step_id)
    if actual is None:
        return validation_fail(validation["id"], validation["type"], f"Step not found: {step_id}", {"step": step_id})
    if actual <= expected:
        return validation_ok(
            validation["id"],
            validation["type"],
            "Attempt count within limit.",
            {"step": step_id, "count": expected, "actual": actual},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        "Attempt count exceeds limit.",
        {"step": step_id, "count": expected, "actual": actual},
    )


def validate_condition_true(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    condition = validation.get("condition")
    if not isinstance(condition, dict):
        raise ValidationEngineError("condition_true requires condition.")
    try:
        validate_condition(condition)
        ok = evaluate_condition(frame, condition)
    except Exception as exc:
        return validation_fail(validation["id"], validation["type"], str(exc), {"condition": condition})
    if ok:
        return validation_ok(validation["id"], validation["type"], "Condition evaluated true.", {"condition": condition})
    return validation_fail(validation["id"], validation["type"], "Condition evaluated false.", {"condition": condition})


def validate_condition_false(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    condition = validation.get("condition")
    if not isinstance(condition, dict):
        raise ValidationEngineError("condition_false requires condition.")
    try:
        validate_condition(condition)
        ok = evaluate_condition(frame, condition)
    except Exception as exc:
        return validation_fail(validation["id"], validation["type"], str(exc), {"condition": condition})
    if not ok:
        return validation_ok(validation["id"], validation["type"], "Condition evaluated false.", {"condition": condition})
    return validation_fail(validation["id"], validation["type"], "Condition evaluated true.", {"condition": condition})


def validate_one_of_steps_completed(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    step_ids = validation.get("steps")
    if not isinstance(step_ids, list) or not step_ids:
        raise ValidationEngineError("one_of_steps_completed requires steps.")

    completed = 0
    missing: list[str] = []
    for step_id in step_ids:
        step = _find_step(frame, step_id)
        if step is None:
            missing.append(step_id)
            continue
        if step.status == "COMPLETED":
            completed += 1

    if missing:
        return validation_fail(
            validation["id"],
            validation["type"],
            f"Step not found: {', '.join(missing)}",
            {"steps": list(step_ids), "missing": missing},
        )

    if completed == 1:
        return validation_ok(
            validation["id"],
            validation["type"],
            "Exactly one branch step completed.",
            {"steps": list(step_ids), "completed": completed},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        "Exactly one branch step must complete.",
        {"steps": list(step_ids), "completed": completed},
    )


def validate_at_least_one_step_completed(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    step_ids = validation.get("steps")
    if not isinstance(step_ids, list) or not step_ids:
        raise ValidationEngineError("at_least_one_step_completed requires steps.")

    completed = 0
    missing: list[str] = []
    for step_id in step_ids:
        step = _find_step(frame, step_id)
        if step is None:
            missing.append(step_id)
            continue
        if step.status == "COMPLETED":
            completed += 1

    if missing:
        return validation_fail(
            validation["id"],
            validation["type"],
            f"Step not found: {', '.join(missing)}",
            {"steps": list(step_ids), "missing": missing},
        )

    if completed >= 1:
        return validation_ok(
            validation["id"],
            validation["type"],
            "At least one branch step completed.",
            {"steps": list(step_ids), "completed": completed},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        "At least one branch step must complete.",
        {"steps": list(step_ids), "completed": completed},
    )


def validate_no_step_failed(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    for step in frame.steps:
        if step.status == "FAILED":
            return validation_fail(validation["id"], validation["type"], "A step has failed.", {"step_id": step.step_id})
    return validation_ok(validation["id"], validation["type"], "No step failed.", {})


def validate_no_errors(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    if frame.errors:
        return validation_fail(validation["id"], validation["type"], "Runtime errors exist.", {"count": len(frame.errors)})
    return validation_ok(validation["id"], validation["type"], "No runtime errors.", {})


def validate_required_input_exists(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    input_name = validation.get("input")
    if not input_name:
        raise ValidationEngineError("required_input_exists requires input.")
    if input_name not in frame.inputs:
        return validation_fail(validation["id"], validation["type"], f"Input missing: {input_name}", {"input": input_name})
    if _is_empty_value(frame.inputs[input_name]):
        return validation_fail(validation["id"], validation["type"], f"Input empty: {input_name}", {"input": input_name})
    return validation_ok(validation["id"], validation["type"], f"Input exists: {input_name}", {"input": input_name})


def validate_required_event_field_exists(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    field = validation.get("field")
    if not field:
        raise ValidationEngineError("required_event_field_exists requires field.")
    if field not in frame.trigger:
        return validation_fail(validation["id"], validation["type"], f"Event field missing: {field}", {"field": field})
    if _is_empty_value(frame.trigger[field]):
        return validation_fail(validation["id"], validation["type"], f"Event field empty: {field}", {"field": field})
    return validation_ok(validation["id"], validation["type"], f"Event field exists: {field}", {"field": field})


def validate_output_has_fields(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    output = validation.get("output")
    fields = validation.get("fields", [])
    if not output:
        raise ValidationEngineError("output_has_fields requires output.")
    if output not in frame.outputs:
        return validation_fail(validation["id"], validation["type"], f"Missing output: {output}", {"output": output})
    value = frame.outputs[output]
    if not isinstance(value, dict):
        return validation_fail(validation["id"], validation["type"], f"Output is not a dict: {output}", {"output": output})
    missing = [field for field in fields if field not in value]
    if missing:
        return validation_fail(
            validation["id"],
            validation["type"],
            f"Output missing fields: {', '.join(missing)}",
            {"output": output, "fields": list(fields), "missing": missing},
        )
    return validation_ok(validation["id"], validation["type"], f"Output has fields: {output}", {"output": output, "fields": list(fields)})


def validate_output_field_equals(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    output = validation.get("output")
    field = validation.get("field")
    expected = validation.get("value")
    if not output or not field:
        raise ValidationEngineError("output_field_equals requires output and field.")
    if output not in frame.outputs:
        return validation_fail(validation["id"], validation["type"], f"Missing output: {output}", {"output": output, "field": field})
    value = frame.outputs[output]
    if not isinstance(value, dict):
        return validation_fail(validation["id"], validation["type"], f"Output is not a dict: {output}", {"output": output, "field": field})
    actual = value.get(field)
    if actual == expected:
        return validation_ok(
            validation["id"],
            validation["type"],
            f"Output field matches: {output}.{field}",
            {"output": output, "field": field, "value": expected},
        )
    message = "CUSTOMER_ORDER_MISMATCH" if output in {"ownership_check", "customer_order_validation"} and field == "ok" else f"Output field does not match: {output}.{field}"
    return validation_fail(
        validation["id"],
        validation["type"],
        message,
        {"output": output, "field": field, "value": expected, "actual": actual},
    )


def validate_output_field_in(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    output = validation.get("output")
    field = validation.get("field")
    values = validation.get("values", [])
    if not output or not field:
        raise ValidationEngineError("output_field_in requires output and field.")
    if not isinstance(values, list) or not values:
        raise ValidationEngineError("output_field_in requires values.")
    if output not in frame.outputs:
        return validation_fail(validation["id"], validation["type"], f"Missing output: {output}", {"output": output, "field": field})
    value = frame.outputs[output]
    if not isinstance(value, dict):
        return validation_fail(validation["id"], validation["type"], f"Output is not a dict: {output}", {"output": output, "field": field})
    actual = value.get(field)
    if actual in values:
        return validation_ok(
            validation["id"],
            validation["type"],
            f"Output field is allowed: {output}.{field}",
            {"output": output, "field": field, "value": actual, "values": list(values)},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        f"Output field not allowed: {output}.{field}",
        {"output": output, "field": field, "value": actual, "values": list(values)},
    )


def validate_output_in_allowed_values(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    output = validation.get("output")
    allowed = validation.get("allowed", [])
    field = validation.get("field")
    if not output:
        raise ValidationEngineError("output_in_allowed_values requires output.")
    if output not in frame.outputs:
        return validation_fail(validation["id"], validation["type"], f"Missing output: {output}", {"output": output})
    value = frame.outputs[output]
    candidate = value
    if field:
        if not isinstance(value, dict):
            return validation_fail(validation["id"], validation["type"], f"Output is not a dict: {output}", {"output": output, "field": field})
        candidate = value.get(field)
    if isinstance(allowed, str):
        allowed_values = [item.strip() for item in allowed.split(",") if item.strip()]
    else:
        allowed_values = list(allowed)
    if candidate in allowed_values:
        return validation_ok(
            validation["id"],
            validation["type"],
            f"Output value allowed: {output}",
            {"output": output, "field": field, "allowed": allowed_values, "value": candidate},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        f"Output value not allowed: {output}",
        {"output": output, "field": field, "allowed": allowed_values, "value": candidate},
    )


def validate_llm_call_exists(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    output = validation.get("output")
    action = validation.get("action")
    if not output and not action:
        raise ValidationEngineError("llm_call_exists requires output and/or action.")
    for call in frame.llm_calls:
        if output and call.get("output_alias") != output:
            continue
        if action and call.get("action") != action:
            continue
        return validation_ok(
            validation["id"],
            validation["type"],
            "LLM call exists.",
            {"output": output, "action": action},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        "LLM call not found.",
        {"output": output, "action": action},
    )


def validate_llm_call_ok(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    output = validation.get("output")
    action = validation.get("action")
    if not output and not action:
        raise ValidationEngineError("llm_call_ok requires output and/or action.")
    for call in frame.llm_calls:
        if output and call.get("output_alias") != output:
            continue
        if action and call.get("action") != action:
            continue
        if call.get("ok") is True:
            return validation_ok(
                validation["id"],
                validation["type"],
                "LLM call succeeded.",
                {"output": output, "action": action},
            )
        return validation_fail(
            validation["id"],
            validation["type"],
            "LLM call failed.",
            {"output": output, "action": action, "ok": call.get("ok")},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        "LLM call not found.",
        {"output": output, "action": action},
    )


def validate_memory_key_exists(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    key = validation.get("key")
    if not key:
        raise ValidationEngineError("memory_key_exists requires key.")
    store = memory_store or MemoryStore()
    if store.exists(key):
        return validation_ok(validation["id"], validation["type"], f"Memory key exists: {key}", {"key": key})
    return validation_fail(validation["id"], validation["type"], f"Memory key missing: {key}", {"key": key})


def validate_memory_output_found(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    output = validation.get("output")
    if not output:
        raise ValidationEngineError("memory_output_found requires output.")
    if output not in frame.outputs:
        return validation_fail(validation["id"], validation["type"], f"Memory output missing: {output}", {"output": output})
    value = frame.outputs[output]
    if isinstance(value, dict) and value.get("found") is True:
        return validation_ok(validation["id"], validation["type"], f"Memory output found: {output}", {"output": output})
    return validation_fail(validation["id"], validation["type"], f"Memory output not found: {output}", {"output": output})


def validate_memory_output_missing(
    frame: TaskFrame,
    validation: dict[str, Any],
    memory_store: MemoryStore | None = None,
) -> ValidationResult:
    output = validation.get("output")
    if not output:
        raise ValidationEngineError("memory_output_missing requires output.")
    if output not in frame.outputs:
        return validation_fail(validation["id"], validation["type"], f"Memory output missing: {output}", {"output": output})
    value = frame.outputs[output]
    if isinstance(value, dict) and value.get("found") is False:
        return validation_ok(validation["id"], validation["type"], f"Memory output missing: {output}", {"output": output})
    return validation_fail(validation["id"], validation["type"], f"Memory output was found: {output}", {"output": output})


VALIDATION_HANDLERS = {
    "output_exists": validate_output_exists,
    "output_not_empty": validate_output_not_empty,
    "pending_action_exists": validate_pending_action_exists,
    "step_completed": validate_step_completed,
    "step_staged": validate_step_staged,
    "step_status": validate_step_status,
    "step_duration_under": validate_step_duration_under,
    "step_timed_out": validate_step_timed_out,
    "step_not_timed_out": validate_step_not_timed_out,
    "attempt_count_equals": validate_attempt_count_equals,
    "attempt_count_less_than_or_equal": validate_attempt_count_less_than_or_equal,
    "condition_true": validate_condition_true,
    "condition_false": validate_condition_false,
    "one_of_steps_completed": validate_one_of_steps_completed,
    "at_least_one_step_completed": validate_at_least_one_step_completed,
    "no_step_failed": validate_no_step_failed,
    "no_errors": validate_no_errors,
    "required_input_exists": validate_required_input_exists,
    "required_event_field_exists": validate_required_event_field_exists,
    "output_has_fields": validate_output_has_fields,
    "output_field_equals": validate_output_field_equals,
    "output_field_in": validate_output_field_in,
    "output_in_allowed_values": validate_output_in_allowed_values,
    "llm_call_exists": validate_llm_call_exists,
    "llm_call_ok": validate_llm_call_ok,
    "memory_key_exists": validate_memory_key_exists,
    "memory_output_found": validate_memory_output_found,
    "memory_output_missing": validate_memory_output_missing,
}


def run_manifest_validations(
    frame: TaskFrame,
    manifest: Manifest,
    memory_store: MemoryStore | None = None,
) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    for validation in manifest.validations:
        result = run_validation(frame, validation, memory_store=memory_store)
        results.append(result)
        record = asdict(result)
        record["type"] = record["validation_type"]
        frame.validations.append(record)
        add_audit_event(
            frame,
            "VALIDATION_PASSED" if result.ok else "VALIDATION_FAILED",
            result.message,
            {"validation_id": result.validation_id, "type": result.validation_type, "ok": result.ok},
        )
    return results


def _find_step(frame: TaskFrame, step_id: str | None):
    if not step_id:
        return None
    for step in frame.steps:
        if step.step_id == step_id:
            return step
    return None


def _step_attempt_count(frame: TaskFrame, step_id: str | None) -> int | None:
    if not step_id:
        return None
    if frame.attempts:
        count = sum(1 for attempt in frame.attempts if attempt.get("step_id") == step_id)
        if count:
            return count
    step = _find_step(frame, step_id)
    if step is None:
        return None
    return step.attempts


def _latest_attempt_for_step(frame: TaskFrame, step_id: str | None) -> dict[str, Any] | None:
    if not step_id:
        return None
    for attempt in reversed(frame.attempts):
        if attempt.get("step_id") == step_id:
            return attempt
    return None


def _validate_step_timeout_flag(
    frame: TaskFrame,
    validation: dict[str, Any],
    expected: bool,
) -> ValidationResult:
    step_id = validation.get("step")
    step = _find_step(frame, step_id)
    if step is None:
        return validation_fail(validation["id"], validation["type"], f"Step not found: {step_id}", {"step": step_id})
    attempt = _latest_attempt_for_step(frame, step_id)
    if attempt is None:
        return validation_fail(validation["id"], validation["type"], f"Step has no attempts: {step_id}", {"step": step_id})
    timed_out = bool(attempt.get("timed_out"))
    if timed_out is expected:
        return validation_ok(
            validation["id"],
            validation["type"],
            "Step timeout flag matches.",
            {"step": step_id, "timed_out": timed_out},
        )
    return validation_fail(
        validation["id"],
        validation["type"],
        "Step timeout flag does not match.",
        {"step": step_id, "timed_out": timed_out},
    )


def _is_empty_value(value: Any) -> bool:
    return value in (None, "", [], {})
