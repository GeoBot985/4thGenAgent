from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .errors import MemoryKeyError, MemoryStoreError
from .models import MemoryItem, MemoryResult
from .taskframe import utc_now


_MEMORY_KEY_RE = re.compile(r"^[A-Za-z0-9._:/-]+$")


class MemoryStore:
    def __init__(self, path: str | Path = "runtime_data/memory_store.json"):
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            data = {"schema_version": 1, "items": {}}
            self.save(data)
            return data

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise MemoryStoreError(f"Unable to read memory store: {self.path}") from exc
        except json.JSONDecodeError as exc:
            raise MemoryStoreError(f"Invalid JSON in memory store: {self.path}") from exc

        if not isinstance(raw, dict):
            raise MemoryStoreError("Memory store root must be an object.")

        items = raw.get("items", {})
        if not isinstance(items, dict):
            raise MemoryStoreError("Memory store items must be an object.")

        schema_version = raw.get("schema_version", 1)
        if schema_version != 1:
            raise MemoryStoreError(f"Unsupported memory store schema_version: {schema_version}")

        return {
            "schema_version": schema_version,
            "items": items,
        }

    def save(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise MemoryStoreError("Memory store data must be an object.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def get(self, key: str) -> MemoryResult:
        self._validate_key(key)
        data = self.load()
        item = data["items"].get(key)
        if item is None:
            return MemoryResult(ok=True, action="get", key=key, value=None, found=False)
        return MemoryResult(
            ok=True,
            action="get",
            key=key,
            value=item.get("value"),
            found=True,
            metadata=dict(item.get("metadata", {})),
        )

    def set(
        self,
        key: str,
        value: Any,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryResult:
        self._validate_key(key)
        self._validate_value(value)
        if metadata is not None and not isinstance(metadata, dict):
            raise MemoryStoreError("metadata must be a dict.")

        data = self.load()
        items = data.setdefault("items", {})
        existing = items.get(key)
        timestamp = utc_now()
        created_at = existing.get("created_at", timestamp) if isinstance(existing, dict) else timestamp
        merged_metadata = {}
        if isinstance(existing, dict):
            merged_metadata.update(dict(existing.get("metadata", {})))
        if metadata:
            merged_metadata.update(metadata)
        item = MemoryItem(
            key=key,
            value=value,
            created_at=created_at,
            updated_at=timestamp,
            metadata=merged_metadata,
        )
        items[key] = {
            "key": item.key,
            "value": item.value,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "metadata": dict(item.metadata),
        }
        self.save(data)
        return MemoryResult(
            ok=True,
            action="set",
            key=key,
            value=value,
            found=True,
            metadata=dict(item.metadata),
        )

    def list(self, prefix: str = "") -> MemoryResult:
        if not isinstance(prefix, str):
            raise MemoryStoreError("prefix must be a string.")
        data = self.load()
        items = []
        for key in sorted(data["items"].keys()):
            if prefix and not key.startswith(prefix):
                continue
            item = data["items"][key]
            items.append(
                {
                    "key": item.get("key", key),
                    "value": item.get("value"),
                    "created_at": item.get("created_at", ""),
                    "updated_at": item.get("updated_at", ""),
                    "metadata": dict(item.get("metadata", {})),
                }
            )
        return MemoryResult(ok=True, action="list", items=items, metadata={"prefix": prefix, "count": len(items)})

    def exists(self, key: str) -> bool:
        self._validate_key(key)
        data = self.load()
        return key in data["items"]

    def _validate_key(self, key: str) -> None:
        if not isinstance(key, str) or not key.strip():
            raise MemoryKeyError("Memory key must be a non-empty string.")
        if not _MEMORY_KEY_RE.fullmatch(key):
            raise MemoryKeyError(f"Invalid memory key: {key}")

    def _validate_value(self, value: Any) -> None:
        try:
            json.dumps(value)
        except TypeError as exc:
            raise MemoryStoreError("Memory value must be JSON serializable.") from exc
