from __future__ import annotations

from typing import Any


def echo(message: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = dict(metadata or {})
    return {
        "ok": True,
        "type": "echo_result",
        "data": {
            "message": message,
            "metadata": metadata,
            "echo": message,
        },
        "evidence": {
            "tool": "echo/echo",
            "mode": "dry_run",
            "source": "toolpack",
            "operation": "read",
            "input_refs": ["message"],
            "output_ref": "echo_result",
            "kind": "toolpack_echo",
            "message": message,
            "metadata_keys": sorted(metadata.keys()),
        },
        "error": "",
    }


def summarize_args(message: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = dict(metadata or {})
    return {
        "ok": True,
        "type": "echo_summary_result",
        "data": {
            "message": message,
            "metadata_keys": sorted(metadata.keys()),
            "message_length": len(message),
        },
        "evidence": {
            "tool": "echo/summarize_args",
            "mode": "dry_run",
            "source": "toolpack",
            "operation": "read",
            "input_refs": ["message"],
            "output_ref": "echo_summary_result",
            "kind": "toolpack_summary",
            "message_length": len(message),
            "metadata_keys": sorted(metadata.keys()),
        },
        "error": "",
    }


def fail(message: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = dict(metadata or {})
    return {
        "ok": False,
        "type": "echo_failure_result",
        "data": {
            "message": message,
            "metadata": metadata,
        },
        "evidence": {
            "tool": "echo/fail",
            "mode": "dry_run",
            "source": "toolpack",
            "operation": "validation",
            "input_refs": ["message"],
            "output_ref": "echo_failure_result",
            "failure_stage": "requested_failure",
        },
        "error": "Demo Echo pack failure requested.",
    }
