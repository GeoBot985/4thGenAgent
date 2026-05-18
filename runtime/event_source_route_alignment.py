from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any

from .event_source_registry import get_event_source_contract, list_event_source_contracts

_DEFAULT_ROUTES_PATH = Path(__file__).resolve().parents[1] / "config" / "event_routes.json"


def _load_routes(routes_path: Path | None = None) -> list[dict[str, Any]]:
    p = Path(routes_path) if routes_path else _DEFAULT_ROUTES_PATH
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict):
        return [r for r in data.get("routes", []) if isinstance(r, dict)]
    return []


def validate_event_source_route_alignment(
    routes_path: Path | None = None,
    contracts_path: Path | None = None,
) -> dict[str, Any]:
    routes = _load_routes(routes_path)
    contracts = list_event_source_contracts(contracts_path)
    contracts_by_source = {str(c.get("source_type", "")): c for c in contracts}

    findings: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []

    sources_in_routes: set[str] = set()
    for route in routes:
        source = str(route.get("source", "")).strip()
        event_type = str(route.get("event_type", "")).strip()
        route_id = str(route.get("route_id", "")).strip()
        sources_in_routes.add(source)

        contract = contracts_by_source.get(source)
        if contract is None:
            findings.append({
                "route_id": route_id,
                "source": source,
                "event_type": event_type,
                "status": "NO_CONTRACT",
                "message": f"Route source '{source}' has no registered contract.",
            })
            warnings.append(f"Route '{route_id}': source '{source}' has no contract.")
            continue

        allowed_patterns = contract.get("allowed_event_types", [])
        if allowed_patterns and event_type:
            matched = any(fnmatch.fnmatch(event_type, pat) for pat in allowed_patterns)
            if not matched:
                findings.append({
                    "route_id": route_id,
                    "source": source,
                    "event_type": event_type,
                    "status": "EVENT_TYPE_MISMATCH",
                    "message": (
                        f"Route event_type '{event_type}' does not match any allowed pattern "
                        f"for source '{source}': {allowed_patterns}"
                    ),
                })
                warnings.append(
                    f"Route '{route_id}': event_type '{event_type}' not in allowed patterns for '{source}'."
                )
            else:
                findings.append({
                    "route_id": route_id,
                    "source": source,
                    "event_type": event_type,
                    "status": "OK",
                    "message": "Route aligns with source contract.",
                })
        else:
            findings.append({
                "route_id": route_id,
                "source": source,
                "event_type": event_type,
                "status": "OK",
                "message": "Route aligns with source contract (no allowed_event_types restriction).",
            })

    # Contracts that have no routes
    unused_contracts = [
        c for c in contracts
        if str(c.get("source_type", "")) not in sources_in_routes
    ]
    for c in unused_contracts:
        warnings.append(f"Contract '{c.get('source_type', '')}' has no routes defined.")

    mismatches = [f for f in findings if f["status"] not in {"OK"}]
    ok = len(errors) == 0

    return {
        "ok": ok,
        "route_count": len(routes),
        "contract_count": len(contracts),
        "findings": findings,
        "mismatches": mismatches,
        "unused_contracts": [str(c.get("source_type", "")) for c in unused_contracts],
        "warnings": warnings,
        "errors": errors,
    }
