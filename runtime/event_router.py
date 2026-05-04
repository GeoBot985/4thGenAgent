from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .events import RuntimeEvent
from .errors import ManifestRouteNotFoundError, EventValidationError
from .manifest_loader import load_manifest_by_id, load_manifest_catalog
from .models import Manifest


class EventRouter:
    def __init__(
        self,
        routes_path: str | Path = "manifests/event_routes.json",
        manifest_dir: str | Path = "manifests",
    ):
        self.routes_path = Path(routes_path)
        self.manifest_dir = Path(manifest_dir)

    def load_routes(self) -> list[dict[str, Any]]:
        if not self.routes_path.is_file():
            raise EventValidationError(f"Route file not found: {self.routes_path}")

        try:
            raw = json.loads(self.routes_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise EventValidationError(f"Unable to read route file: {self.routes_path}") from exc
        except json.JSONDecodeError as exc:
            raise EventValidationError(f"Invalid JSON in route file: {self.routes_path}") from exc

        if not isinstance(raw, dict):
            raise EventValidationError("Route file root must be a JSON object.")

        routes = raw.get("routes")
        if not isinstance(routes, list):
            raise EventValidationError("routes must be a list.")

        catalog = load_manifest_catalog(self.manifest_dir)
        seen_enabled: set[str] = set()
        normalized_routes: list[dict[str, Any]] = []

        for index, route in enumerate(routes):
            if not isinstance(route, dict):
                raise EventValidationError(f"Route {index} must be an object.")

            event_type = route.get("event_type")
            manifest_id = route.get("manifest_id")
            enabled = bool(route.get("enabled", True))

            if not isinstance(event_type, str) or not event_type.strip():
                raise EventValidationError(f"Route {index} is missing event_type.")
            if not isinstance(manifest_id, str) or not manifest_id.strip():
                raise EventValidationError(f"Route {event_type} is missing manifest_id.")

            if enabled:
                if event_type in seen_enabled:
                    raise EventValidationError(f"Duplicate enabled event_type route: {event_type}")
                seen_enabled.add(event_type)
                if manifest_id not in catalog:
                    raise ManifestRouteNotFoundError(
                        f"Route target manifest not found for enabled route: {event_type} -> {manifest_id}"
                    )

            normalized_routes.append(
                {
                    **route,
                    "event_type": event_type,
                    "manifest_id": manifest_id,
                    "enabled": enabled,
                }
            )

        return normalized_routes

    def resolve_manifest_id(self, event: RuntimeEvent) -> str:
        if not isinstance(event, RuntimeEvent):
            raise EventValidationError("event must be a RuntimeEvent.")

        for route in self.load_routes():
            if route["event_type"] == event.event_type and route.get("enabled", True):
                return route["manifest_id"]

        raise ManifestRouteNotFoundError(f"No enabled route found for event_type: {event.event_type}")

    def resolve_manifest(self, event: RuntimeEvent) -> Manifest:
        manifest_id = self.resolve_manifest_id(event)
        return load_manifest_by_id(manifest_id, self.manifest_dir)
