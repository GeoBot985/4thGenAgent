"""Spec 139 — Fixture JSON event source adapter.

Reads deterministic local fixture records for tests and demos.
Read-only, no external dependencies.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .base import build_poll_result

ADAPTER_ID = "fixture_json"


class FixtureJsonAdapter:
    adapter_id = ADAPTER_ID

    def health(
        self,
        config: dict[str, Any],
        runtime_data_dir: str = "runtime_data",
    ) -> dict[str, Any]:
        poll_cfg = dict(config.get("poll") or {})
        fixture_path_str = str(poll_cfg.get("fixture_path") or "")
        if not fixture_path_str:
            return {"ok": False, "status": "misconfigured", "error": "poll.fixture_path not set."}
        path = Path(fixture_path_str)
        if not path.is_file():
            return {"ok": False, "status": "fixture_missing", "error": f"Fixture file not found: {fixture_path_str}"}
        return {"ok": True, "status": "ready", "fixture_path": str(path)}

    def poll(
        self,
        config: dict[str, Any],
        state: dict[str, Any],
        runtime_data_dir: str = "runtime_data",
    ) -> dict[str, Any]:
        source_id = str(config.get("source_id") or "")
        poll_cfg = dict(config.get("poll") or {})
        fixture_path_str = str(poll_cfg.get("fixture_path") or "")
        max_events = int(poll_cfg.get("max_events_per_poll") or 10)

        if not fixture_path_str:
            return build_poll_result(
                source_id, ADAPTER_ID, "fixture",
                ok=False, error="poll.fixture_path not set.",
                error_category="malformed_fixture",
            )

        path = Path(fixture_path_str)
        if not path.is_file():
            return build_poll_result(
                source_id, ADAPTER_ID, "fixture",
                ok=False, error=f"Fixture file not found: {fixture_path_str}",
                error_category="malformed_fixture",
            )

        try:
            raw_text = path.read_text(encoding="utf-8")
            raw_records = json.loads(raw_text)
        except (OSError, json.JSONDecodeError) as exc:
            return build_poll_result(
                source_id, ADAPTER_ID, "fixture",
                ok=False, error=f"Failed to parse fixture: {exc}",
                error_category="malformed_fixture",
            )

        if not isinstance(raw_records, list):
            return build_poll_result(
                source_id, ADAPTER_ID, "fixture",
                ok=False, error="Fixture must be a JSON array.",
                error_category="malformed_fixture",
            )

        cursor = dict(state.get("cursor") or {})
        seen_ids: set[str] = set(cursor.get("seen_ids") or [])
        dedupe_cfg = dict(config.get("dedupe") or {})
        key_template = str(dedupe_cfg.get("key_template") or "fixture:{message_id}")

        events: list[dict[str, Any]] = []
        new_seen_ids: list[str] = []
        warnings: list[str] = []

        for raw in raw_records:
            if not isinstance(raw, dict):
                warnings.append(f"Skipping non-dict fixture record: {raw!r}")
                continue
            try:
                event = self.normalize(raw, config)
            except Exception as exc:
                warnings.append(f"Normalization failed for record: {exc}")
                continue

            dedupe_key = _render_dedupe_key(key_template, raw)
            if dedupe_key in seen_ids:
                continue

            events.append(event)
            new_seen_ids.append(dedupe_key)

            if len(events) >= max_events:
                break

        cursor_update: dict[str, Any] = {}
        if new_seen_ids:
            cursor_update["seen_ids"] = new_seen_ids

        return build_poll_result(
            source_id, ADAPTER_ID, "fixture",
            ok=True,
            raw_count=len(raw_records),
            event_count=len(events),
            events=events,
            cursor_update=cursor_update,
            warnings=warnings,
        )

    def normalize(
        self,
        raw_record: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        event_source = str(config.get("event_source") or "fixture")
        event_type = str(config.get("event_type") or "message_received")

        message_id = str(raw_record.get("message_id") or uuid.uuid4().hex)
        safe_id = message_id.replace("-", "_").replace(" ", "_")
        event_id = f"evt_fixture_{safe_id}"

        received_at = str(raw_record.get("received_at") or "")

        payload: dict[str, Any] = {
            "message_id": message_id,
            "customer_id": raw_record.get("customer_id", ""),
            "from": raw_record.get("from", ""),
            "subject": raw_record.get("subject", ""),
            "message": raw_record.get("body", raw_record.get("message", "")),
            "channel": "email",
        }
        for key, val in raw_record.items():
            if key not in ("message_id", "customer_id", "from", "subject", "body", "message", "received_at"):
                payload[key] = val

        return {
            "event_id": event_id,
            "source": event_source,
            "event_type": event_type,
            "received_at": received_at,
            "payload": payload,
        }


def _render_dedupe_key(template: str, record: dict[str, Any]) -> str:
    key = template
    for field_name, value in record.items():
        key = key.replace(f"{{{field_name}}}", str(value))
    for remaining in _find_unresolved_placeholders(key):
        key = key.replace(f"{{{remaining}}}", "")
    return key


def _find_unresolved_placeholders(template: str) -> list[str]:
    import re
    return re.findall(r"\{(\w+)\}", template)
