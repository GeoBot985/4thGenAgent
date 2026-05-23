from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic
from typing import Any

from .errors import TimeoutPolicyError


MAX_TIMEOUT_SECONDS = 600
MIN_TIMEOUT_SECONDS = 0.001


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def monotonic_now() -> float:
    return monotonic()


def validate_timeout_seconds(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TimeoutPolicyError("timeout_seconds must be a number.")
    timeout = float(value)
    if timeout < MIN_TIMEOUT_SECONDS:
        raise TimeoutPolicyError(f"timeout_seconds must be at least {MIN_TIMEOUT_SECONDS}.")
    if timeout > MAX_TIMEOUT_SECONDS:
        raise TimeoutPolicyError(f"timeout_seconds must not exceed {MAX_TIMEOUT_SECONDS}.")
    return timeout


def duration_ms(start_monotonic: float, end_monotonic: float) -> float:
    return max(0.0, (end_monotonic - start_monotonic) * 1000.0)


def timeout_exceeded(duration_seconds: float, timeout_seconds: float | None) -> bool:
    if timeout_seconds is None:
        return False
    return duration_seconds > timeout_seconds


def build_timing_record(
    step_id: str,
    attempt: int,
    started_at: str,
    ended_at: str,
    duration_ms: float,
    timeout_seconds: float | None,
    timed_out: bool,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "attempt": attempt,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": duration_ms,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
    }
