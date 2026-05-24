from __future__ import annotations

"""
Spec 156 — InvoiceOps Posting Ledger.

Append-only JSONL ledger for InvoiceOps live sheet posting evidence.
Stored under runtime_data/invoiceops/live_posting/.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POSTING_LEDGER_DIR = "invoiceops/live_posting"
POSTING_LEDGER_FILENAME = "invoiceops_live_posting_ledger.jsonl"
POSTING_LATEST_FILENAME = "invoiceops_live_posting_latest.json"

# Status values
STATUS_EXECUTED_VERIFIED = "EXECUTED_VERIFIED"
STATUS_EXECUTED_UNVERIFIED = "EXECUTED_UNVERIFIED"
STATUS_BLOCKED = "BLOCKED"
STATUS_FAILED = "FAILED"
STATUS_PENDING = "PENDING"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ledger_dir(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / POSTING_LEDGER_DIR


def _ledger_path(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return _ledger_dir(runtime_data_dir) / POSTING_LEDGER_FILENAME


def _latest_path(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return _ledger_dir(runtime_data_dir) / POSTING_LATEST_FILENAME


def build_posting_ledger_entry(
    *,
    frame_id: str,
    posting_plan_id: str,
    invoice_id: str,
    invoice_number: str,
    supplier_name: str,
    target_register: str,
    action_id: str,
    tool: str = "sheet/write_rows",
    profile: str = "controlled_live_write",
    approved_by: str,
    worker_identity: dict[str, Any] | str,
    idempotency_key: str,
    payload_hash: str,
    status: str,
    side_effect_performed: bool,
    verification: dict[str, Any] | None = None,
    rollback_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    posting_ledger_id = f"PLG-{uuid.uuid4().hex[:12]}"
    return {
        "posting_ledger_id": posting_ledger_id,
        "frame_id": frame_id,
        "posting_plan_id": posting_plan_id,
        "invoice_id": invoice_id,
        "invoice_number": invoice_number,
        "supplier_name": supplier_name,
        "target_register": target_register,
        "action_id": action_id,
        "tool": tool,
        "profile": profile,
        "approved_by": approved_by,
        "worker_identity": worker_identity if isinstance(worker_identity, dict) else {"identity": str(worker_identity)},
        "idempotency_key": idempotency_key,
        "payload_hash": payload_hash,
        "status": status,
        "side_effect_performed": side_effect_performed,
        "verification": verification or {},
        "rollback_plan": rollback_plan or {},
        "created_at": _utc_now(),
    }


def append_posting_ledger_entry(
    entry: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> None:
    path = _ledger_path(runtime_data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")
    # Update latest pointer
    _write_latest(entry, runtime_data_dir=runtime_data_dir)


def _write_latest(entry: dict[str, Any], *, runtime_data_dir: str | Path) -> None:
    latest_path = _latest_path(runtime_data_dir)
    try:
        latest_path.write_text(json.dumps(entry, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass


def read_posting_ledger_entries(
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


def get_posting_ledger_entry_by_action(
    action_id: str,
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any] | None:
    found: dict[str, Any] | None = None
    for entry in read_posting_ledger_entries(runtime_data_dir=runtime_data_dir):
        if str(entry.get("action_id") or "") == action_id:
            found = entry
    return found


def get_posting_ledger_entry_by_idempotency_key(
    idempotency_key: str,
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any] | None:
    found: dict[str, Any] | None = None
    for entry in read_posting_ledger_entries(runtime_data_dir=runtime_data_dir):
        if str(entry.get("idempotency_key") or "") == idempotency_key:
            found = entry
    return found


def build_posting_ledger_report(
    *,
    runtime_data_dir: str | Path = "runtime_data",
    limit: int = 20,
) -> dict[str, Any]:
    entries = read_posting_ledger_entries(runtime_data_dir=runtime_data_dir)
    recent = entries[-limit:] if len(entries) > limit else entries
    executed_verified = [e for e in entries if e.get("status") == STATUS_EXECUTED_VERIFIED]
    executed_unverified = [e for e in entries if e.get("status") == STATUS_EXECUTED_UNVERIFIED]
    blocked = [e for e in entries if e.get("status") == STATUS_BLOCKED]
    failed = [e for e in entries if e.get("status") == STATUS_FAILED]
    side_effects = [e for e in entries if e.get("side_effect_performed")]

    return {
        "total_entries": len(entries),
        "executed_verified_count": len(executed_verified),
        "executed_unverified_count": len(executed_unverified),
        "blocked_count": len(blocked),
        "failed_count": len(failed),
        "side_effects_performed_count": len(side_effects),
        "recent_entries": list(reversed(recent)),
        "ledger_path": str(_ledger_path(runtime_data_dir)),
    }


def record_posting_execution(
    *,
    posting_plan: dict[str, Any],
    action: dict[str, Any],
    execution_result: dict[str, Any],
    verification: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """
    Build and append a posting ledger entry from execution context.
    Returns the ledger entry dict.
    """
    executed = bool(execution_result.get("executed", False))
    verified = bool(verification.get("verified", False))

    if not executed:
        status = STATUS_BLOCKED if execution_result.get("blocked") else STATUS_FAILED
    elif verified:
        status = STATUS_EXECUTED_VERIFIED
    else:
        status = STATUS_EXECUTED_UNVERIFIED

    entry = build_posting_ledger_entry(
        frame_id=str(posting_plan.get("frame_id") or ""),
        posting_plan_id=str(posting_plan.get("posting_plan_id") or ""),
        invoice_id=str(posting_plan.get("invoice_id") or ""),
        invoice_number=str(posting_plan.get("invoice_number") or action.get("business_ref") or ""),
        supplier_name=str(posting_plan.get("supplier_name") or ""),
        target_register=str(action.get("target_register") or ""),
        action_id=str(action.get("action_id") or ""),
        tool=str(action.get("tool") or "sheet/write_rows"),
        profile=str(action.get("profile") or "controlled_live_write"),
        approved_by=str(action.get("approved_by") or ""),
        worker_identity=action.get("worker_identity") or {},
        idempotency_key=str(action.get("idempotency_key") or ""),
        payload_hash=str(action.get("prepared_payload_hash") or ""),
        status=status,
        side_effect_performed=executed,
        verification=verification,
        rollback_plan=dict(action.get("rollback_plan") or {}),
    )
    append_posting_ledger_entry(entry, runtime_data_dir=runtime_data_dir)
    return entry
