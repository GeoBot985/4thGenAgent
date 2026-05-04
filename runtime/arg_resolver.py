from __future__ import annotations

from typing import Any

from .errors import ArgumentResolutionError
from .models import TaskFrame


def resolve_command_args(frame: TaskFrame, args: dict[str, str]) -> dict[str, object]:
    return {key: resolve_value(frame, value) for key, value in args.items()}


def resolve_value(frame: TaskFrame, value: str) -> object:
    if not isinstance(value, str):
        return value
    if not value.startswith("$"):
        return value
    return resolve_ref(frame, value)


def resolve_ref(frame: TaskFrame, ref: str) -> object:
    if not ref.startswith("$"):
        raise ArgumentResolutionError(f"Invalid reference: {ref}")

    parts = ref[1:].split(".")
    if not parts or not parts[0]:
        raise ArgumentResolutionError(f"Invalid reference: {ref}")

    root = parts[0]
    if root == "event":
        current: Any = frame.trigger
    elif root == "inputs":
        current = frame.inputs
    else:
        if root not in frame.outputs:
            raise ArgumentResolutionError(f"Missing output alias: {root}")
        current = frame.outputs[root]

    for part in parts[1:]:
        if part == "first":
            if not isinstance(current, list):
                raise ArgumentResolutionError(f"Cannot take first from non-list reference: {ref}")
            if not current:
                raise ArgumentResolutionError(f"Cannot take first from empty list reference: {ref}")
            current = current[0]
            continue
        if part == "last":
            if not isinstance(current, list):
                raise ArgumentResolutionError(f"Cannot take last from non-list reference: {ref}")
            if not current:
                raise ArgumentResolutionError(f"Cannot take last from empty list reference: {ref}")
            current = current[-1]
            continue
        if not isinstance(current, dict):
            raise ArgumentResolutionError(f"Cannot access field on non-dict reference: {ref}")
        if part not in current:
            if root == "event":
                raise ArgumentResolutionError(f"Missing event field: {part}")
            if root == "inputs":
                raise ArgumentResolutionError(f"Missing input field: {part}")
            raise ArgumentResolutionError(f"Missing field {part} in reference: {ref}")
        current = current[part]

    return current

