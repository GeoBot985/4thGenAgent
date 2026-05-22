from __future__ import annotations


TOKENS = {
    "admin": "test-admin-token",
    "operator": "test-operator-token",
    "viewer": "test-viewer-token",
}


def auth_headers(role: str) -> dict[str, str]:
    token = TOKENS[role]
    return {"Authorization": f"Bearer {token}"}
