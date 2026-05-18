from __future__ import annotations

from typing import Any

SOURCE_TYPES = [
    "operator_ui",
    "schedule",
    "customer_inbox",
    "gmail",
    "calendar",
    "sheet",
    "rpa",
    "system",
]

DELIVERY_MODES = ["push", "pull", "polling"]
SIDE_EFFECT_LEVELS = ["none", "low", "medium", "high"]

_CANONICAL_CONTRACT_KEYS = {
    "source_type",
    "display_name",
    "description",
    "delivery_mode",
    "side_effect_level",
    "required_payload_fields",
    "optional_payload_fields",
    "allowed_event_types",
    "metadata",
}


def build_event_source_contract(
    source_type: str,
    display_name: str,
    description: str,
    delivery_mode: str,
    side_effect_level: str,
    required_payload_fields: list[str] | None = None,
    optional_payload_fields: list[str] | None = None,
    allowed_event_types: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source_type": str(source_type),
        "display_name": str(display_name),
        "description": str(description),
        "delivery_mode": str(delivery_mode),
        "side_effect_level": str(side_effect_level),
        "required_payload_fields": list(required_payload_fields or []),
        "optional_payload_fields": list(optional_payload_fields or []),
        "allowed_event_types": list(allowed_event_types or []),
        "metadata": dict(metadata or {}),
    }


def validate_contract_shape(contract: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return False, ["contract must be a dict."]
    source_type = contract.get("source_type")
    if not isinstance(source_type, str) or not source_type.strip():
        errors.append("source_type must be a non-empty string.")
    delivery_mode = contract.get("delivery_mode")
    if delivery_mode not in DELIVERY_MODES:
        errors.append(f"delivery_mode must be one of {DELIVERY_MODES}.")
    side_effect_level = contract.get("side_effect_level")
    if side_effect_level not in SIDE_EFFECT_LEVELS:
        errors.append(f"side_effect_level must be one of {SIDE_EFFECT_LEVELS}.")
    for field in ("required_payload_fields", "optional_payload_fields", "allowed_event_types"):
        val = contract.get(field)
        if not isinstance(val, list):
            errors.append(f"{field} must be a list.")
    return len(errors) == 0, errors
