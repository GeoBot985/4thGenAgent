from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_FILENAME = "live_execution_ledger.jsonl"
LEDGER_DIR = "live_execution"

# Entry status values
LEDGER_STATUS_EXECUTING = "EXECUTING"
LEDGER_STATUS_EXECUTED = "EXECUTED"
LEDGER_STATUS_FAILED = "FAILED"
LEDGER_STATUS_BLOCKED = "BLOCKED"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ledger_path(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / LEDGER_DIR / LEDGER_FILENAME


def build_ledger_entry(
    *,
    frame_id: str,
    action_id: str,
    tool: str,
    idempotency_key: str,
    business_ref: str,
    target_ref: str,
    prepared_payload_hash: str,
    approved_by: str,
    worker_identity: str,
    status: str,
    profile: str = "controlled_live_write",
    rollback_plan: dict[str, Any] | None = None,
    execution_result: dict[str, Any] | None = None,
    error: str = "",
) -> dict[str, Any]:
    return {
        "ledger_entry_version": "1",
        "recorded_at": _utc_now(),
        "frame_id": frame_id,
        "action_id": action_id,
        "tool": tool,
        "profile": profile,
        "idempotency_key": idempotency_key,
        "business_ref": business_ref,
        "target_ref": target_ref,
        "prepared_payload_hash": prepared_payload_hash,
        "approved_by": approved_by,
        "worker_identity": worker_identity,
        "status": status,
        "rollback_plan": rollback_plan or {},
        "execution_result": execution_result or {},
        "error": error,
    }


def append_ledger_entry(
    entry: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> None:
    path = _ledger_path(runtime_data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def read_ledger_entries(
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> list[dict[str, Any]]:
    path = _ledger_path(runtime_data_dir)
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def is_idempotency_key_in_ledger(
    idempotency_key: str,
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> bool:
    """Return True if the key appears with EXECUTED status in the ledger."""
    if not idempotency_key:
        return False
    for entry in read_ledger_entries(runtime_data_dir=runtime_data_dir):
        if (
            str(entry.get("idempotency_key") or "") == idempotency_key
            and str(entry.get("status") or "") == LEDGER_STATUS_EXECUTED
        ):
            return True
    return False


def get_ledger_entry(
    idempotency_key: str,
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any] | None:
    """Return the most recent ledger entry for the given idempotency key."""
    found: dict[str, Any] | None = None
    for entry in read_ledger_entries(runtime_data_dir=runtime_data_dir):
        if str(entry.get("idempotency_key") or "") == idempotency_key:
            found = entry
    return found


def hash_payload(payload: dict[str, Any] | str) -> str:
    """Return a SHA-256 hex digest of the canonical JSON representation of a payload."""
    if isinstance(payload, dict):
        canonical = json.dumps(payload, sort_keys=True, default=str)
    else:
        canonical = str(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_ledger_report(
    *,
    runtime_data_dir: str | Path = "runtime_data",
    limit: int = 20,
) -> dict[str, Any]:
    entries = read_ledger_entries(runtime_data_dir=runtime_data_dir)
    recent = entries[-limit:] if len(entries) > limit else entries
    executed = [e for e in entries if e.get("status") == LEDGER_STATUS_EXECUTED]
    failed = [e for e in entries if e.get("status") == LEDGER_STATUS_FAILED]
    return {
        "total_entries": len(entries),
        "executed_count": len(executed),
        "failed_count": len(failed),
        "recent_entries": list(reversed(recent)),
        "ledger_path": str(_ledger_path(runtime_data_dir)),
    }
