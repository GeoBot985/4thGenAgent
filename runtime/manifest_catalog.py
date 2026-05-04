from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .manifest_loader import load_manifest_catalog


def load_event_routes(path: str = "config/event_routes.json") -> list[dict[str, Any]]:
    route_path = Path(path)
    if not route_path.is_file():
        return []
    try:
        raw = json.loads(route_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read event routes file: {route_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in event routes file: {route_path}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Event route file root must be a JSON object.")
    routes = raw.get("routes")
    if not isinstance(routes, list):
        raise ValueError("Event route file routes must be a list.")
    normalized: list[dict[str, Any]] = []
    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            raise ValueError(f"Route {index} must be an object.")
        normalized.append(dict(route))
    return normalized


def validate_event_route(route: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(route, dict):
        return False, ["route must be a dict."]
    for field in ("route_id", "source", "event_type", "manifest_id", "input_map"):
        value = route.get(field)
        if field == "input_map":
            if not isinstance(value, dict):
                errors.append("input_map")
        elif not isinstance(value, str) or not value.strip():
            errors.append(field)
    return len(errors) == 0, errors


def resolve_event_route(event: dict[str, Any], routes: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    source = event.get("source")
    event_type = event.get("event_type")
    if not isinstance(source, str) or not source.strip():
        return None
    if not isinstance(event_type, str) or not event_type.strip():
        return None

    for route in routes:
        ok, _ = validate_event_route(route)
        if not ok:
            continue
        if route.get("source") == source and route.get("event_type") == event_type:
            return dict(route)
    return None


def map_event_inputs(event: dict[str, Any], route: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    mapped: dict[str, Any] = {}
    errors: list[str] = []
    if not isinstance(event, dict) or not isinstance(route, dict):
        return {}, ["event and route must be dicts."]
    input_map = route.get("input_map", {})
    if not isinstance(input_map, dict):
        return {}, ["input_map"]
    for task_input, path in input_map.items():
        if not isinstance(task_input, str) or not task_input.strip():
            errors.append("Invalid task input name")
            continue
        if not isinstance(path, str) or not path.strip():
            errors.append(f"Missing mapped field: {path}")
            continue
        found, ok = _lookup_event_path(event, path.strip())
        if not ok:
            errors.append(f"Missing mapped field: {path}")
            continue
        mapped[task_input] = found
    return mapped, errors


def manifest_exists(manifest_id: str, manifest_dir: str | Path = "manifests") -> bool:
    if not isinstance(manifest_id, str) or not manifest_id.strip():
        return False
    try:
        catalog = load_manifest_catalog(manifest_dir)
    except Exception:
        return False
    return manifest_id in catalog


def _lookup_event_path(event: dict[str, Any], path: str) -> tuple[Any, bool]:
    parts = path.split(".")
    if not parts:
        return None, False
    root = parts[0]
    if root not in {"event_id", "source", "event_type", "received_at", "payload"}:
        return None, False
    current: Any = event.get(root)
    for part in parts[1:]:
        if not isinstance(current, dict) or part not in current:
            return None, False
        current = current[part]
    return current, True
