from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any

from .event_source_contracts import SOURCE_TYPES, build_event_source_contract, validate_contract_shape

_DEFAULT_CONTRACTS_PATH = Path(__file__).resolve().parents[1] / "config" / "event_source_contracts.json"


def _load_contracts_file(path: Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path else _DEFAULT_CONTRACTS_PATH
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict):
        contracts = data.get("contracts", [])
    elif isinstance(data, list):
        contracts = data
    else:
        return []
    return [c for c in contracts if isinstance(c, dict)]


def list_event_source_contracts(contracts_path: Path | None = None) -> list[dict[str, Any]]:
    return _load_contracts_file(contracts_path)


def get_event_source_contract(source_type: str, contracts_path: Path | None = None) -> dict[str, Any] | None:
    contracts = _load_contracts_file(contracts_path)
    for c in contracts:
        if str(c.get("source_type", "")) == source_type:
            return c
    return None


def validate_event_source_contract(contract: dict[str, Any]) -> dict[str, Any]:
    ok, errors = validate_contract_shape(contract)
    return {
        "ok": ok,
        "source_type": str(contract.get("source_type", "")),
        "errors": errors,
        "warnings": [],
    }


def validate_all_event_source_contracts(contracts_path: Path | None = None) -> dict[str, Any]:
    contracts = _load_contracts_file(contracts_path)
    results = []
    all_ok = True
    for c in contracts:
        r = validate_event_source_contract(c)
        results.append(r)
        if not r["ok"]:
            all_ok = False
    seen_types = [str(c.get("source_type", "")) for c in contracts]
    missing = [s for s in SOURCE_TYPES if s not in seen_types]
    warnings = [f"Missing built-in contract for: {s}" for s in missing]
    return {
        "ok": all_ok and not missing,
        "count": len(contracts),
        "results": results,
        "missing_builtin_sources": missing,
        "warnings": warnings,
    }


def validate_event_against_source_contract(
    event: dict[str, Any],
    contracts_path: Path | None = None,
) -> dict[str, Any]:
    source = str(event.get("source", "")).strip()
    event_type = str(event.get("event_type", "")).strip()
    payload = event.get("payload") or {}

    if not source:
        return {"ok": False, "source_type": "", "errors": ["event.source is required."], "warnings": []}

    contract = get_event_source_contract(source, contracts_path)
    if contract is None:
        return {
            "ok": True,
            "source_type": source,
            "errors": [],
            "warnings": [f"No contract registered for source '{source}'. Validation skipped."],
            "contract_found": False,
        }

    errors: list[str] = []
    warnings: list[str] = []

    # Validate required payload fields
    if not isinstance(payload, dict):
        errors.append("payload must be a dict.")
    else:
        for field in contract.get("required_payload_fields", []):
            if field not in payload:
                errors.append(f"Missing required payload field: '{field}'.")

    # Validate event_type pattern
    allowed_patterns = contract.get("allowed_event_types", [])
    if allowed_patterns and event_type:
        matched = any(fnmatch.fnmatch(event_type, pat) for pat in allowed_patterns)
        if not matched:
            warnings.append(
                f"event_type '{event_type}' does not match any allowed pattern for source '{source}': {allowed_patterns}"
            )

    return {
        "ok": len(errors) == 0,
        "source_type": source,
        "errors": errors,
        "warnings": warnings,
        "contract_found": True,
        "contract": contract,
    }
