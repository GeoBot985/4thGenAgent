from __future__ import annotations

import json
from datetime import date as _date
from datetime import time as _time
from typing import Any

from .errors import ConditionEvaluationError, ConditionValidationError
from .models import TaskFrame


COMPOUND_OPERATORS = {"all", "any", "not"}
ATOMIC_SOURCES = {"output", "input", "event"}
ATOMIC_OPERATORS = {
    "exists",
    "missing",
    "equals",
    "not_equals",
    "in",
    "not_in",
    "contains",
    "truthy",
    "falsey",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "between",
    "not_between",
    "on_date",
    "before_date",
    "on_or_before_date",
    "after_date",
    "on_or_after_date",
    "between_dates",
    "not_between_dates",
    "at_time",
    "before_time",
    "on_or_before_time",
    "after_time",
    "on_or_after_time",
    "between_time",
    "not_between_time",
}


def is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def is_compound_condition(condition: dict[str, Any]) -> bool:
    return isinstance(condition, dict) and any(key in condition for key in COMPOUND_OPERATORS)


def validate_condition(condition: dict[str, Any]) -> None:
    if not isinstance(condition, dict) or not condition:
        raise ConditionValidationError("Condition must be a non-empty dict.")

    if is_compound_condition(condition):
        validate_compound_condition(condition)
        return

    validate_atomic_condition(condition)


def validate_atomic_condition(condition: dict[str, Any]) -> None:
    if not isinstance(condition, dict) or not condition:
        raise ConditionValidationError("Condition must be a non-empty dict.")

    if any(key in condition for key in COMPOUND_OPERATORS):
        raise ConditionValidationError("Atomic conditions cannot include compound operators.")

    sources = [key for key in ATOMIC_SOURCES if key in condition]
    if len(sources) != 1:
        raise ConditionValidationError("Condition must specify exactly one source.")

    operators = [key for key in ATOMIC_OPERATORS if key in condition]
    if len(operators) != 1:
        raise ConditionValidationError("Condition must specify exactly one operator.")

    unknown = [key for key in condition if key not in ATOMIC_SOURCES and key not in ATOMIC_OPERATORS and key != "field"]
    if unknown:
        raise ConditionValidationError(f"Unknown condition keys: {', '.join(sorted(unknown))}")

    operator = operators[0]
    source = sources[0]
    value = condition[operator]

    if operator in {"exists", "missing", "truthy", "falsey"} and not isinstance(value, bool):
        raise ConditionValidationError(f"Condition operator {operator} requires a boolean value.")

    if operator in {"equals", "not_equals"} and value is None:
        raise ConditionValidationError(f"Condition operator {operator} requires a comparison value.")

    if operator in {"in", "not_in"} and not isinstance(value, list):
        raise ConditionValidationError(f"Condition operator {operator} requires a list value.")

    if operator == "contains" and is_empty(value):
        raise ConditionValidationError("Condition operator contains requires a value.")

    if operator in {"greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal"}:
        coerce_number(value)

    if operator in {"between", "not_between"}:
        _validate_two_value_list(value, coerce_number, "numeric")

    if operator in {"on_date", "before_date", "on_or_before_date", "after_date", "on_or_after_date"}:
        parse_iso_date(value)

    if operator in {"between_dates", "not_between_dates"}:
        bounds = _validate_two_value_list(value, parse_iso_date, "date")
        if bounds[0] > bounds[1]:
            raise ConditionValidationError("Date range start must be before or equal to end.")

    if operator in {"at_time", "before_time", "on_or_before_time", "after_time", "on_or_after_time"}:
        parse_hhmm_time(value)

    if operator in {"between_time", "not_between_time"}:
        _validate_two_value_list(value, parse_hhmm_time, "time")

    if source == "output" and not isinstance(condition["output"], str):
        raise ConditionValidationError("Condition output must be a string.")
    if source == "input" and not isinstance(condition["input"], str):
        raise ConditionValidationError("Condition input must be a string.")
    if source == "event" and not isinstance(condition["event"], str):
        raise ConditionValidationError("Condition event must be a string.")


def validate_compound_condition(condition: dict[str, Any]) -> None:
    if not isinstance(condition, dict) or not condition:
        raise ConditionValidationError("Condition must be a non-empty dict.")

    compound_keys = [key for key in COMPOUND_OPERATORS if key in condition]
    if len(compound_keys) != 1:
        raise ConditionValidationError("Condition must specify exactly one compound operator.")

    if any(key not in COMPOUND_OPERATORS for key in condition):
        raise ConditionValidationError("Compound conditions cannot include atomic keys.")

    operator = compound_keys[0]
    value = condition[operator]

    if operator in {"all", "any"}:
        if not isinstance(value, list) or not value:
            raise ConditionValidationError(f"Compound operator {operator} requires a non-empty list of child conditions.")
        for child in value:
            if not isinstance(child, dict):
                raise ConditionValidationError(f"Compound operator {operator} requires child conditions to be dicts.")
            validate_condition(child)
        return

    if operator == "not":
        if not isinstance(value, dict) or not value:
            raise ConditionValidationError("Compound operator not requires exactly one child condition.")
        validate_condition(value)
        return

    raise ConditionValidationError(f"Unsupported compound operator: {operator}")


def resolve_condition_value(frame: TaskFrame, condition: dict[str, Any]) -> Any:
    validate_atomic_condition(condition)
    value, _ = _resolve_atomic_value(frame, condition, strict=True)
    return value


def get_nested_field(value: Any, field_path: str) -> Any:
    if not field_path:
        return value
    current = value
    for part in field_path.split("."):
        if not isinstance(current, dict):
            raise ConditionEvaluationError(f"Cannot access nested field on non-dict value: {field_path}")
        if part not in current:
            raise ConditionEvaluationError(f"Missing nested field: {field_path}")
        current = current[part]
    return current


def evaluate_condition(frame: TaskFrame, condition: dict[str, Any]) -> bool:
    validate_condition(condition)
    if is_compound_condition(condition):
        return evaluate_compound_condition(frame, condition)
    return evaluate_atomic_condition(frame, condition)


def evaluate_atomic_condition(frame: TaskFrame, condition: dict[str, Any]) -> bool:
    validate_atomic_condition(condition)
    operator = next(key for key in ATOMIC_OPERATORS if key in condition)
    expected = condition[operator]
    value, missing = _resolve_atomic_value(frame, condition, strict=False)
    if missing:
        return operator == "missing"
    return _apply_atomic_operator(operator, value, expected)


def evaluate_compound_condition(frame: TaskFrame, condition: dict[str, Any]) -> bool:
    validate_compound_condition(condition)
    operator = next(key for key in COMPOUND_OPERATORS if key in condition)
    value = condition[operator]

    if operator == "all":
        return all(_evaluate_condition_strict(frame, child) for child in value)
    if operator == "any":
        return any(_evaluate_condition_strict(frame, child) for child in value)
    if operator == "not":
        return not _evaluate_condition_strict(frame, value)

    raise ConditionEvaluationError(f"Unsupported compound operator: {operator}")


def evaluate_condition_with_trace(
    frame: TaskFrame,
    condition: dict[str, Any],
) -> dict[str, Any]:
    validate_condition(condition)
    if is_compound_condition(condition):
        return _trace_compound(frame, condition)
    return _trace_atomic(frame, condition)


def compare_numeric(value: Any, operator: str, expected: Any) -> bool:
    left = coerce_number(value)
    if operator in {"greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal"}:
        right = coerce_number(expected)
        if operator == "greater_than":
            return left > right
        if operator == "greater_than_or_equal":
            return left >= right
        if operator == "less_than":
            return left < right
        if operator == "less_than_or_equal":
            return left <= right

    if operator in {"between", "not_between"}:
        bounds = _normalize_numeric_bounds(expected)
        in_range = bounds[0] <= left <= bounds[1]
        return in_range if operator == "between" else not in_range

    raise ConditionEvaluationError(f"Unsupported numeric operator: {operator}")


def compare_date(value: Any, operator: str, expected: Any) -> bool:
    left = parse_iso_date(value)
    if operator in {"on_date", "before_date", "on_or_before_date", "after_date", "on_or_after_date"}:
        right = parse_iso_date(expected)
        if operator == "on_date":
            return left == right
        if operator == "before_date":
            return left < right
        if operator == "on_or_before_date":
            return left <= right
        if operator == "after_date":
            return left > right
        if operator == "on_or_after_date":
            return left >= right

    if operator in {"between_dates", "not_between_dates"}:
        start, end = _normalize_date_bounds(expected)
        in_range = start <= left <= end
        return in_range if operator == "between_dates" else not in_range

    raise ConditionEvaluationError(f"Unsupported date operator: {operator}")


def compare_time(value: Any, operator: str, expected: Any) -> bool:
    left = parse_hhmm_time(value)
    if operator in {"at_time", "before_time", "on_or_before_time", "after_time", "on_or_after_time"}:
        right = parse_hhmm_time(expected)
        if operator == "at_time":
            return left == right
        if operator == "before_time":
            return left < right
        if operator == "on_or_before_time":
            return left <= right
        if operator == "after_time":
            return left > right
        if operator == "on_or_after_time":
            return left >= right

    if operator in {"between_time", "not_between_time"}:
        start, end = _normalize_time_bounds(expected)
        in_range = is_between_time(left, start, end)
        return in_range if operator == "between_time" else not in_range

    raise ConditionEvaluationError(f"Unsupported time operator: {operator}")


def is_between_time(value_time: _time, start_time: _time, end_time: _time) -> bool:
    if end_time >= start_time:
        return start_time <= value_time <= end_time
    return value_time >= start_time or value_time <= end_time


def coerce_number(value: Any) -> int | float:
    if isinstance(value, bool) or value is None:
        raise ConditionValidationError("Value must be numeric.")
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        raise ConditionValidationError("Value must be numeric.")

    text = value.strip()
    if not text:
        raise ConditionValidationError("Value must be numeric.")
    if "," in text:
        raise ConditionValidationError("Value must be numeric.")

    try:
        number = float(text)
    except ValueError as exc:
        raise ConditionValidationError("Value must be numeric.") from exc

    if number.is_integer():
        return int(number)
    return number


def parse_iso_date(value: Any) -> _date:
    if not isinstance(value, str):
        raise ConditionValidationError("Date value must be a string.")
    text = value.strip()
    if len(text) != 10:
        raise ConditionValidationError("Date value must be YYYY-MM-DD.")
    try:
        parsed = _date.fromisoformat(text)
    except ValueError as exc:
        raise ConditionValidationError("Date value must be YYYY-MM-DD.") from exc
    if parsed.isoformat() != text:
        raise ConditionValidationError("Date value must be YYYY-MM-DD.")
    return parsed


def parse_hhmm_time(value: Any) -> _time:
    if not isinstance(value, str):
        raise ConditionValidationError("Time value must be a string.")
    text = value.strip()
    if len(text) != 5:
        raise ConditionValidationError("Time value must be HH:MM.")
    try:
        parsed = _time.fromisoformat(text)
    except ValueError as exc:
        raise ConditionValidationError("Time value must be HH:MM.") from exc
    if parsed.isoformat(timespec="minutes") != text:
        raise ConditionValidationError("Time value must be HH:MM.")
    return parsed


def _apply_atomic_operator(operator: str, value: Any, expected: Any) -> bool:
    if operator == "exists":
        return not is_empty(value)
    if operator == "missing":
        return is_empty(value)
    if operator == "equals":
        return value == expected
    if operator == "not_equals":
        return value != expected
    if operator == "in":
        return value in expected
    if operator == "not_in":
        return value not in expected
    if operator == "contains":
        if isinstance(value, str):
            return str(expected) in value
        if isinstance(value, list):
            return expected in value
        if isinstance(value, dict):
            return expected in value
        raise ConditionEvaluationError("contains is only supported for strings, lists, and dicts.")
    if operator == "truthy":
        return bool(value) is True
    if operator == "falsey":
        return bool(value) is False
    if operator in {"greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal", "between", "not_between"}:
        return compare_numeric(value, operator, expected)
    if operator in {"on_date", "before_date", "on_or_before_date", "after_date", "on_or_after_date", "between_dates", "not_between_dates"}:
        return compare_date(value, operator, expected)
    if operator in {"at_time", "before_time", "on_or_before_time", "after_time", "on_or_after_time", "between_time", "not_between_time"}:
        return compare_time(value, operator, expected)
    raise ConditionEvaluationError(f"Unsupported operator: {operator}")


def _resolve_atomic_value(frame: TaskFrame, condition: dict[str, Any], *, strict: bool) -> tuple[Any, bool]:
    if "output" in condition:
        output_name = condition["output"]
        if output_name not in frame.outputs:
            if strict:
                raise ConditionEvaluationError(f"Missing output: {output_name}")
            return None, True
        value = frame.outputs[output_name]
        field = condition.get("field")
        if field:
            value = get_nested_field(value, field)
        return value, False

    if "input" in condition:
        input_name = condition["input"]
        if input_name not in frame.inputs:
            if strict:
                raise ConditionEvaluationError(f"Missing input: {input_name}")
            return None, True
        return frame.inputs[input_name], False

    event_name = condition["event"]
    if event_name not in frame.trigger:
        if strict:
            raise ConditionEvaluationError(f"Missing event field: {event_name}")
        return None, True
    return frame.trigger[event_name], False


def _trace_atomic(frame: TaskFrame, condition: dict[str, Any]) -> dict[str, Any]:
    validate_atomic_condition(condition)
    operator = next(key for key in ATOMIC_OPERATORS if key in condition)
    expected = condition[operator]
    value, missing = _resolve_atomic_value(frame, condition, strict=False)
    ok = operator == "missing" if missing else _apply_atomic_operator(operator, value, expected)

    trace: dict[str, Any] = {
        "ok": ok,
        "condition": _json_safe(condition),
        "operator": operator,
        "source": _atomic_source(condition),
        "resolved_value": _json_safe(value),
        "expected": _json_safe(expected),
    }

    if operator in {"greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal", "between", "not_between"}:
        trace["resolved_normalized"] = _json_safe(coerce_number(value))
        trace["expected_normalized"] = _json_safe(_normalize_numeric_expected(operator, expected))
    elif operator in {"on_date", "before_date", "on_or_before_date", "after_date", "on_or_after_date", "between_dates", "not_between_dates"}:
        normalized_value = parse_iso_date(value).isoformat() if not missing else None
        trace["resolved_normalized"] = _json_safe(normalized_value)
        trace["expected_normalized"] = _json_safe(_normalize_date_expected(operator, expected))
    elif operator in {"at_time", "before_time", "on_or_before_time", "after_time", "on_or_after_time", "between_time", "not_between_time"}:
        normalized_value = parse_hhmm_time(value).isoformat(timespec="minutes") if not missing else None
        trace["resolved_normalized"] = _json_safe(normalized_value)
        trace["expected_normalized"] = _json_safe(_normalize_time_expected(operator, expected))
        if operator in {"between_time", "not_between_time"}:
            start, end = _normalize_time_bounds(expected)
            trace["overnight"] = end < start
    return trace


def _trace_compound(frame: TaskFrame, condition: dict[str, Any]) -> dict[str, Any]:
    validate_compound_condition(condition)
    operator = next(key for key in COMPOUND_OPERATORS if key in condition)
    value = condition[operator]

    if operator == "all":
        children = [_trace_condition_strict(frame, child) for child in value]
        return {"ok": all(child["ok"] for child in children), "condition": _json_safe(condition), "operator": "all", "children": children}
    if operator == "any":
        children = [_trace_condition_strict(frame, child) for child in value]
        return {"ok": any(child["ok"] for child in children), "condition": _json_safe(condition), "operator": "any", "children": children}
    if operator == "not":
        child = _trace_condition_strict(frame, value)
        return {"ok": not bool(child["ok"]), "condition": _json_safe(condition), "operator": "not", "children": [child]}
    raise ConditionEvaluationError(f"Unsupported compound operator: {operator}")


def _trace_condition(frame: TaskFrame, condition: dict[str, Any]) -> dict[str, Any]:
    if is_compound_condition(condition):
        return _trace_compound(frame, condition)
    return _trace_atomic(frame, condition)


def _evaluate_condition_strict(frame: TaskFrame, condition: dict[str, Any]) -> bool:
    if is_compound_condition(condition):
        return evaluate_compound_condition(frame, condition)
    validate_atomic_condition(condition)
    operator = next(key for key in ATOMIC_OPERATORS if key in condition)
    expected = condition[operator]
    value = resolve_condition_value(frame, condition)
    return _apply_atomic_operator(operator, value, expected)


def _trace_condition_strict(frame: TaskFrame, condition: dict[str, Any]) -> dict[str, Any]:
    if is_compound_condition(condition):
        return _trace_compound(frame, condition)
    validate_atomic_condition(condition)
    operator = next(key for key in ATOMIC_OPERATORS if key in condition)
    expected = condition[operator]
    value = resolve_condition_value(frame, condition)
    trace: dict[str, Any] = {
        "ok": _apply_atomic_operator(operator, value, expected),
        "condition": _json_safe(condition),
        "operator": operator,
        "source": _atomic_source(condition),
        "resolved_value": _json_safe(value),
        "expected": _json_safe(expected),
    }
    if operator in {"greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal", "between", "not_between"}:
        trace["resolved_normalized"] = _json_safe(coerce_number(value))
        trace["expected_normalized"] = _json_safe(_normalize_numeric_expected(operator, expected))
    elif operator in {"on_date", "before_date", "on_or_before_date", "after_date", "on_or_after_date", "between_dates", "not_between_dates"}:
        trace["resolved_normalized"] = _json_safe(parse_iso_date(value).isoformat())
        trace["expected_normalized"] = _json_safe(_normalize_date_expected(operator, expected))
    elif operator in {"at_time", "before_time", "on_or_before_time", "after_time", "on_or_after_time", "between_time", "not_between_time"}:
        trace["resolved_normalized"] = _json_safe(parse_hhmm_time(value).isoformat(timespec="minutes"))
        trace["expected_normalized"] = _json_safe(_normalize_time_expected(operator, expected))
        if operator in {"between_time", "not_between_time"}:
            start, end = _normalize_time_bounds(expected)
            trace["overnight"] = end < start
    return trace


def _atomic_source(condition: dict[str, Any]) -> str:
    if "output" in condition:
        return "output"
    if "input" in condition:
        return "input"
    return "event"


def _validate_two_value_list(value: Any, parser, kind: str) -> tuple[Any, Any]:
    if not isinstance(value, list) or len(value) != 2:
        raise ConditionValidationError(f"Condition operator requires a list of exactly 2 {kind} values.")
    first = parser(value[0])
    second = parser(value[1])
    return first, second


def _normalize_numeric_bounds(value: Any) -> tuple[int | float, int | float]:
    first, second = _validate_two_value_list(value, coerce_number, "numeric")
    return first, second


def _normalize_date_bounds(value: Any) -> tuple[_date, _date]:
    first, second = _validate_two_value_list(value, parse_iso_date, "date")
    return first, second


def _normalize_time_bounds(value: Any) -> tuple[_time, _time]:
    first, second = _validate_two_value_list(value, parse_hhmm_time, "time")
    return first, second


def _normalize_numeric_expected(operator: str, expected: Any) -> Any:
    if operator in {"between", "not_between"}:
        first, second = _normalize_numeric_bounds(expected)
        return [first, second]
    return coerce_number(expected)


def _normalize_date_expected(operator: str, expected: Any) -> Any:
    if operator in {"between_dates", "not_between_dates"}:
        first, second = _normalize_date_bounds(expected)
        return [first.isoformat(), second.isoformat()]
    return parse_iso_date(expected).isoformat()


def _normalize_time_expected(operator: str, expected: Any) -> Any:
    if operator in {"between_time", "not_between_time"}:
        first, second = _normalize_time_bounds(expected)
        return [first.isoformat(timespec="minutes"), second.isoformat(timespec="minutes")]
    return parse_hhmm_time(expected).isoformat(timespec="minutes")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)
