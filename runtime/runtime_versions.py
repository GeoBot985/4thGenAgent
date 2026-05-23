from __future__ import annotations

from typing import Any

from .taskframe import utc_now


SCHEMA_VERSION = 1
RUNTIME_VERSION_FIELD = "runtime_version"
SCHEMA_VERSION_FIELD = "schema_version"
UPDATED_AT_FIELD = "updated_at"


def normalize_versioned_payload(payload: dict[str, Any] | None, *, runtime_version: int = 1) -> dict[str, Any]:
    data = dict(payload or {})
    data[SCHEMA_VERSION_FIELD] = int(data.get(SCHEMA_VERSION_FIELD, SCHEMA_VERSION) or SCHEMA_VERSION)
    data[RUNTIME_VERSION_FIELD] = int(data.get(RUNTIME_VERSION_FIELD, runtime_version) or runtime_version)
    if not str(data.get(UPDATED_AT_FIELD, "") or "").strip():
        data[UPDATED_AT_FIELD] = utc_now()
    return data


def bump_runtime_version(payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload or {})
    current = int(data.get(RUNTIME_VERSION_FIELD, 0) or 0)
    data[SCHEMA_VERSION_FIELD] = int(data.get(SCHEMA_VERSION_FIELD, SCHEMA_VERSION) or SCHEMA_VERSION)
    data[RUNTIME_VERSION_FIELD] = current + 1 if current > 0 else 1
    data[UPDATED_AT_FIELD] = utc_now()
    return data


def read_runtime_version(payload: dict[str, Any] | None) -> int:
    if not isinstance(payload, dict):
        return 0
    return int(payload.get(RUNTIME_VERSION_FIELD, 0) or 0)

