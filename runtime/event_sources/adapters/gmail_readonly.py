"""Spec 139 — Gmail read-only event source adapter.

Performs ONLY read/search/list operations on Gmail.
Never sends, archives, deletes, labels, marks read, or mutates messages.
Disabled by default; requires explicit credentials config.
"""
from __future__ import annotations

import uuid
from typing import Any

from .base import build_poll_result

ADAPTER_ID = "gmail_readonly"

# Forbidden operations — listed for documentation and audit purposes only.
# None of these are called anywhere in this module.
_FORBIDDEN_OPERATIONS = frozenset({
    "send", "draft", "archive", "delete", "label",
    "mark_read", "mark_unread", "move", "forward",
    "insert", "modify", "trash",
})


class GmailReadonlyAdapter:
    adapter_id = ADAPTER_ID

    def health(
        self,
        config: dict[str, Any],
        runtime_data_dir: str = "runtime_data",
    ) -> dict[str, Any]:
        creds_result = _check_credentials(config)
        if not creds_result["ok"]:
            return {
                "ok": False,
                "status": "needs_auth",
                "error_category": "credentials_missing",
                "error": creds_result["error"],
            }
        return {"ok": True, "status": "ready", "adapter": ADAPTER_ID}

    def poll(
        self,
        config: dict[str, Any],
        state: dict[str, Any],
        runtime_data_dir: str = "runtime_data",
    ) -> dict[str, Any]:
        source_id = str(config.get("source_id") or "")
        mode = str(config.get("mode") or "")

        if mode not in ("live_read",):
            return build_poll_result(
                source_id, ADAPTER_ID, mode,
                ok=False,
                error=f"Gmail adapter only supports mode=live_read; got {mode!r}.",
                error_category="unsupported_mode",
            )

        creds_result = _check_credentials(config)
        if not creds_result["ok"]:
            return build_poll_result(
                source_id, ADAPTER_ID, mode,
                ok=False,
                error=creds_result["error"],
                error_category="credentials_missing",
            )

        try:
            gmail_service = _build_gmail_service(config)
        except Exception as exc:
            return build_poll_result(
                source_id, ADAPTER_ID, mode,
                ok=False,
                error=f"Failed to build Gmail service: {exc}",
                error_category="auth_failed",
            )

        poll_cfg = dict(config.get("poll") or {})
        query = str(poll_cfg.get("query") or "label:inbox")
        max_events = int(poll_cfg.get("max_events_per_poll") or 20)
        include_body = bool(poll_cfg.get("include_body", True))

        cursor = dict(state.get("cursor") or {})
        seen_ids: set[str] = set(cursor.get("seen_ids") or [])

        try:
            raw_messages = _list_messages(gmail_service, query, max_results=max_events * 2)
        except Exception as exc:
            return build_poll_result(
                source_id, ADAPTER_ID, mode,
                ok=False,
                error=f"Gmail list_messages failed: {exc}",
                error_category="external_dependency_unavailable",
            )

        events: list[dict[str, Any]] = []
        new_seen_ids: list[str] = []
        warnings: list[str] = []
        evidence_items: list[dict[str, Any]] = []

        for msg_stub in raw_messages:
            if len(events) >= max_events:
                break
            msg_id = str(msg_stub.get("id") or "")
            dedupe_key = f"gmail:{msg_id}"
            if dedupe_key in seen_ids:
                continue

            try:
                full_msg = _get_message(gmail_service, msg_id)
            except Exception as exc:
                warnings.append(f"Failed to fetch message {msg_id}: {exc}")
                continue

            raw_record = _extract_message_fields(full_msg, include_body=include_body)
            try:
                event = self.normalize(raw_record, config)
            except Exception as exc:
                warnings.append(f"Normalization failed for message {msg_id}: {exc}")
                continue

            events.append(event)
            new_seen_ids.append(dedupe_key)
            evidence_items.append({
                "message_id": msg_id,
                "subject": raw_record.get("subject", ""),
                "date": raw_record.get("date", ""),
                "from": raw_record.get("from", ""),
                "query": query,
            })

        cursor_update: dict[str, Any] = {}
        if new_seen_ids:
            cursor_update["seen_ids"] = new_seen_ids

        return build_poll_result(
            source_id, ADAPTER_ID, mode,
            ok=True,
            raw_count=len(raw_messages),
            event_count=len(events),
            events=events,
            cursor_update=cursor_update,
            evidence={"messages": evidence_items, "query": query},
            warnings=warnings,
        )

    def normalize(
        self,
        raw_record: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        event_source = str(config.get("event_source") or "gmail")
        event_type = str(config.get("event_type") or "message_received")
        poll_cfg = dict(config.get("poll") or {})
        include_body = bool(poll_cfg.get("include_body", True))

        message_id = str(raw_record.get("message_id") or uuid.uuid4().hex)
        safe_id = message_id.replace("-", "_").replace(" ", "_")
        event_id = f"evt_gmail_{safe_id}"

        payload: dict[str, Any] = {
            "message_id": message_id,
            "from": raw_record.get("from", ""),
            "subject": raw_record.get("subject", ""),
            "date": raw_record.get("date", ""),
            "channel": "email",
        }
        if include_body:
            payload["message"] = raw_record.get("body", raw_record.get("snippet", ""))

        return {
            "event_id": event_id,
            "source": event_source,
            "event_type": event_type,
            "received_at": str(raw_record.get("date") or ""),
            "payload": payload,
        }


# ---------------------------------------------------------------------------
# Internal helpers — read-only Gmail API operations only
# ---------------------------------------------------------------------------

def _check_credentials(config: dict[str, Any]) -> dict[str, Any]:
    auth = dict(config.get("auth") or {})
    requires_credentials = bool(auth.get("requires_credentials", True))
    if not requires_credentials:
        return {"ok": True}
    try:
        _get_credentials(auth)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "error_category": "credentials_missing"}


def _get_credentials(auth: dict[str, Any]) -> Any:
    """Attempt to load Google OAuth credentials. Raises if unavailable."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        import os

        token_path = str(auth.get("token_path") or "")
        if token_path and __import__("pathlib").Path(token_path).is_file():
            import json as _json
            cred_data = _json.loads(__import__("pathlib").Path(token_path).read_text(encoding="utf-8"))
            creds = Credentials.from_authorized_user_info(cred_data)
            return creds
        raise RuntimeError("No token_path configured or file not found.")
    except ImportError:
        raise RuntimeError(
            "google-auth library not installed. "
            "Install google-auth and google-auth-httplib2 to use Gmail read-only source."
        )


def _build_gmail_service(config: dict[str, Any]) -> Any:
    from googleapiclient.discovery import build as gapi_build
    auth = dict(config.get("auth") or {})
    creds = _get_credentials(auth)
    return gapi_build("gmail", "v1", credentials=creds)


def _list_messages(service: Any, query: str, max_results: int = 50) -> list[dict[str, Any]]:
    result = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results,
    ).execute()
    return list(result.get("messages") or [])


def _get_message(service: Any, message_id: str) -> dict[str, Any]:
    return service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()


def _extract_message_fields(msg: dict[str, Any], *, include_body: bool = True) -> dict[str, Any]:
    headers = {
        h["name"].lower(): h["value"]
        for h in (msg.get("payload") or {}).get("headers") or []
        if isinstance(h, dict)
    }
    record: dict[str, Any] = {
        "message_id": str(msg.get("id") or ""),
        "from": headers.get("from", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "snippet": str(msg.get("snippet") or ""),
    }
    if include_body:
        record["body"] = _extract_body(msg)
    return record


def _extract_body(msg: dict[str, Any]) -> str:
    import base64
    payload = msg.get("payload") or {}
    parts = payload.get("parts") or []
    if parts:
        for part in parts:
            if part.get("mimeType") == "text/plain":
                data = (part.get("body") or {}).get("data", "")
                if data:
                    try:
                        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                    except Exception:
                        pass
    body_data = (payload.get("body") or {}).get("data", "")
    if body_data:
        try:
            return base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
        except Exception:
            pass
    return str(msg.get("snippet") or "")
