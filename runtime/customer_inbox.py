from __future__ import annotations

import json
from pathlib import Path

from .persistence import ensure_dir, write_json_atomic


INBOX_FILE = "customer_messages.json"
ALLOWED_STATUSES = {
    "NEW",
    "PROCESSING",
    "STAGED_REPLY",
    "APPROVED",
    "EXECUTED_DRY_RUN",
    "REJECTED",
    "FAILED",
    "COMPLETED",
}

SEED_MESSAGES = [
    {
        "message_id": "msg_001",
        "customer_id": "CUST-1001",
        "customer_name": "Alex",
        "channel": "callcentre",
        "received_at": "2026-05-01T10:00:00Z",
        "status": "NEW",
        "message": "Where is my order ORD-10042?",
        "linked_frame_id": "",
        "pending_action_id": "",
        "processed_at": "",
        "completed_at": "",
        "failure_reason": "",
        "metadata": {},
    },
    {
        "message_id": "msg_002",
        "customer_id": "CUST-1002",
        "customer_name": "Bianca",
        "channel": "callcentre",
        "received_at": "2026-05-01T10:01:00Z",
        "status": "NEW",
        "message": "I want a refund for order ORD-10043.",
        "linked_frame_id": "",
        "pending_action_id": "",
        "processed_at": "",
        "completed_at": "",
        "failure_reason": "",
        "metadata": {},
    },
    {
        "message_id": "msg_003",
        "customer_id": "CUST-1003",
        "customer_name": "Chris",
        "channel": "callcentre",
        "received_at": "2026-05-01T10:02:00Z",
        "status": "NEW",
        "message": "Do you have stock of SKU-CHAIR-01?",
        "linked_frame_id": "",
        "pending_action_id": "",
        "processed_at": "",
        "completed_at": "",
        "failure_reason": "",
        "metadata": {},
    },
    {
        "message_id": "msg_004",
        "customer_id": "CUST-9999",
        "customer_name": "Unknown",
        "channel": "callcentre",
        "received_at": "2026-05-01T10:03:00Z",
        "status": "NEW",
        "message": "Where is my order ORD-99999?",
        "linked_frame_id": "",
        "pending_action_id": "",
        "processed_at": "",
        "completed_at": "",
        "failure_reason": "",
        "metadata": {},
    },
    {
        "message_id": "msg_005",
        "customer_id": "CUST-1001",
        "customer_name": "Alex",
        "channel": "callcentre",
        "received_at": "2026-05-01T10:04:00Z",
        "status": "NEW",
        "message": "Where is order ORD-10044?",
        "linked_frame_id": "",
        "pending_action_id": "",
        "processed_at": "",
        "completed_at": "",
        "failure_reason": "",
        "metadata": {},
    },
    {
        "message_id": "msg_006",
        "customer_id": "CUST-1004",
        "customer_name": "Dana",
        "channel": "callcentre",
        "received_at": "2026-05-01T10:05:00Z",
        "status": "NEW",
        "message": "Is SKU-LAMP-01 still available?",
        "linked_frame_id": "",
        "pending_action_id": "",
        "processed_at": "",
        "completed_at": "",
        "failure_reason": "",
        "metadata": {},
    },
    {
        "message_id": "msg_007",
        "customer_id": "CUST-1002",
        "customer_name": "Bianca",
        "channel": "email",
        "received_at": "2026-05-01T10:06:00Z",
        "status": "NEW",
        "message": "Please reconcile payment for ORD-10043.",
        "linked_frame_id": "",
        "pending_action_id": "",
        "processed_at": "",
        "completed_at": "",
        "failure_reason": "",
        "metadata": {},
    },
    {
        "message_id": "msg_008",
        "customer_id": "CUST-1003",
        "customer_name": "Chris",
        "channel": "email",
        "received_at": "2026-05-01T10:07:00Z",
        "status": "NEW",
        "message": "Need supplier invoice match for PO-5001.",
        "linked_frame_id": "",
        "pending_action_id": "",
        "processed_at": "",
        "completed_at": "",
        "failure_reason": "",
        "metadata": {},
    },
]


def get_inbox_path(runtime_data_dir: str = "runtime_data") -> Path:
    return Path(runtime_data_dir) / "business" / INBOX_FILE


def load_customer_messages(runtime_data_dir: str = "runtime_data") -> list[dict]:
    path = get_inbox_path(runtime_data_dir)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [dict(item) for item in data if isinstance(item, dict)]


def save_customer_messages(messages: list[dict], runtime_data_dir: str = "runtime_data") -> None:
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")
    seen: set[str] = set()
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        message_id = str(message.get("message_id", "")).strip()
        if not message_id:
            raise ValueError("Missing message_id.")
        if message_id in seen:
            raise ValueError(f"Duplicate message_id: {message_id}")
        seen.add(message_id)
        status = str(message.get("status", "")).strip() or "NEW"
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Unknown message status: {status}")
    path = get_inbox_path(runtime_data_dir)
    ensure_dir(path.parent)
    write_json_atomic(path, [dict(item) for item in messages])


def list_customer_messages(runtime_data_dir: str = "runtime_data", status: str | None = None) -> list[dict]:
    messages = load_customer_messages(runtime_data_dir)
    if status:
        return [dict(message) for message in messages if str(message.get("status", "")).upper() == status.upper()]
    return [dict(message) for message in messages]


def get_customer_message(message_id: str, runtime_data_dir: str = "runtime_data") -> dict:
    if not isinstance(message_id, str) or not message_id.strip():
        return {}
    for message in load_customer_messages(runtime_data_dir):
        if str(message.get("message_id", "")) == message_id:
            return dict(message)
    return {}


def update_customer_message(message_id: str, updates: dict, runtime_data_dir: str = "runtime_data") -> dict:
    messages = load_customer_messages(runtime_data_dir)
    updated: list[dict] = []
    found: dict | None = None
    for message in messages:
        if str(message.get("message_id", "")) == message_id:
            merged = dict(message)
            merged.update(dict(updates or {}))
            if str(merged.get("status", "")).strip() not in ALLOWED_STATUSES:
                raise ValueError(f"Unknown message status: {merged.get('status')}")
            found = merged
            updated.append(merged)
        else:
            updated.append(dict(message))
    if found is None:
        raise ValueError(f"Unknown message_id: {message_id}")
    save_customer_messages(updated, runtime_data_dir)
    return found


def reset_customer_inbox(runtime_data_dir: str = "runtime_data") -> dict:
    save_customer_messages([dict(item) for item in SEED_MESSAGES], runtime_data_dir)
    return {"ok": True, "count": len(SEED_MESSAGES), "path": str(get_inbox_path(runtime_data_dir))}


def seed_customer_inbox(runtime_data_dir: str = "runtime_data", overwrite: bool = False) -> dict:
    path = get_inbox_path(runtime_data_dir)
    if path.is_file() and not overwrite:
        return {"ok": True, "count": len(load_customer_messages(runtime_data_dir)), "path": str(path), "seeded": False}
    save_customer_messages([dict(item) for item in SEED_MESSAGES], runtime_data_dir)
    return {"ok": True, "count": len(SEED_MESSAGES), "path": str(path), "seeded": True, "messages": [dict(item) for item in SEED_MESSAGES]}
