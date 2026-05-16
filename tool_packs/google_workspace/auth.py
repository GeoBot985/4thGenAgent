from __future__ import annotations

import importlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from src.config_profiles import load_config_profile, resolve_google_credentials_path, resolve_google_token_path
from .schemas import GOOGLE_WORKSPACE_SERVICE_NAMES, REDACT_KEYS

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def google_dependency_state() -> dict[str, Any]:
    modules = [
        "google.auth.transport.requests",
        "google.oauth2.credentials",
        "google_auth_oauthlib.flow",
        "googleapiclient.discovery",
        "googleapiclient.errors",
    ]
    missing: list[str] = []
    for module_name in modules:
        try:
            found = importlib.util.find_spec(module_name)
        except Exception:
            found = None
        if found is None:
            missing = [*missing, module_name]
    return {"ok": not missing, "missing": missing}


def google_auth_files() -> dict[str, Any]:
    profile = load_config_profile()
    credentials_path = resolve_google_credentials_path(profile.config_dir)
    token_path = resolve_google_token_path(profile.config_dir)
    return {
        "profile": profile.name,
        "config_dir": str(profile.config_dir),
        "credentials_path": str(credentials_path),
        "credentials_file_present": credentials_path.is_file(),
        "token_path": str(token_path),
        "token_file_present": token_path.is_file(),
        "google_enabled": bool(profile.google_enabled),
        "configured_services": list(GOOGLE_WORKSPACE_SERVICE_NAMES),
    }


def build_google_service(service_name: str, version: str):
    deps = google_dependency_state()
    if not deps["ok"]:
        raise RuntimeError("Google client dependencies are not installed.")

    credentials_path = resolve_google_credentials_path()
    token_path = resolve_google_token_path()
    if not credentials_path.is_file() and not token_path.is_file():
        raise RuntimeError("Google credentials are not configured.")

    requests = importlib.import_module("google.auth.transport.requests")
    credentials_mod = importlib.import_module("google.oauth2.credentials")
    flow_mod = importlib.import_module("google_auth_oauthlib.flow")
    discovery = importlib.import_module("googleapiclient.discovery")

    creds = None
    if token_path.is_file():
        creds = credentials_mod.Credentials.from_authorized_user_file(str(token_path), GOOGLE_SCOPES)

    if creds and getattr(creds, "valid", False):
        return discovery.build(service_name, version, credentials=creds)

    if creds and getattr(creds, "expired", False) and getattr(creds, "refresh_token", None):
        creds.refresh(requests.Request())
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return discovery.build(service_name, version, credentials=creds)

    flow = flow_mod.InstalledAppFlow.from_client_secrets_file(str(credentials_path), GOOGLE_SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return discovery.build(service_name, version, credentials=creds)


def redact_google_auth_state(state: dict[str, Any]) -> dict[str, Any]:
    return _redact_value(state)


def _redact_value(value: Any, *, key: str = "") -> Any:
    lowered = key.lower()
    if isinstance(value, dict):
        return {item_key: _redact_value(item_value, key=item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, key=key) for item in value]
    if any(term in lowered for term in REDACT_KEYS):
        return "***REDACTED***"
    if isinstance(value, str):
        if any(term in value.lower() for term in ("token", "secret", "credential", "cookie", "authorization")) and "://" not in value:
            return "***REDACTED***"
    return value
