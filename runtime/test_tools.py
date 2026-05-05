from __future__ import annotations


def echo(message: str = "", event_id: str = "") -> dict:
    return {"ok": True, "received": True, "message": message, "event_id": event_id, "response": f"Demo event processed: {message}"}
