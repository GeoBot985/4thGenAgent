"""Spec 146 — Structured error response builders for backend hardening."""
from __future__ import annotations

from typing import Any


def too_large_error() -> dict[str, Any]:
    return {
        "ok": False,
        "error_code": "REQUEST_TOO_LARGE",
        "error": "Request body exceeds the configured maximum size.",
    }


def invalid_json_error() -> dict[str, Any]:
    return {
        "ok": False,
        "error_code": "INVALID_JSON",
        "error": "Request body is not valid JSON.",
    }


def invalid_request_body_error() -> dict[str, Any]:
    return {
        "ok": False,
        "error_code": "INVALID_REQUEST_BODY",
        "error": "Request body must be a JSON object.",
    }


def invalid_id_error() -> dict[str, Any]:
    return {
        "ok": False,
        "error_code": "INVALID_ID",
        "error": "Request contains an invalid identifier.",
    }


def invalid_query_error(detail: str = "") -> dict[str, Any]:
    return {
        "ok": False,
        "error_code": "INVALID_QUERY",
        "error": detail or "Query parameter is invalid.",
    }


def rate_limited_error() -> dict[str, Any]:
    return {
        "ok": False,
        "error_code": "RATE_LIMITED",
        "error": "Rate limit exceeded for this operation.",
    }
