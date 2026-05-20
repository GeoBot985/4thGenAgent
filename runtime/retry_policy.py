from __future__ import annotations

from time import sleep
from typing import Any

from .errors import (
    LLMAdapterError,
    LLMOutputParseError,
    MemoryStoreError,
    RetryPolicyValidationError,
    StepTimeoutExceeded,
    ToolExecutionError,
    ToolFunctionError,
    ToolImportError,
    ToolResultNormalizationError,
)


DEFAULT_RETRY_POLICY = {
    "max_attempts": 1,
    "delay_seconds": 0,
    "retry_on": ["any"],
    "fail_on_exhausted": True,
}

MAX_ALLOWED_ATTEMPTS = 5
MAX_ALLOWED_DELAY_SECONDS = 30


def normalize_retry_policy(retry: dict[str, Any] | None) -> dict[str, Any]:
    if retry is None:
        return dict(DEFAULT_RETRY_POLICY)
    if not isinstance(retry, dict):
        raise RetryPolicyValidationError("Retry policy must be an object.")
    policy = dict(DEFAULT_RETRY_POLICY)
    policy.update(retry)
    return policy


def validate_retry_policy(policy: dict[str, Any]) -> None:
    if not isinstance(policy, dict):
        raise RetryPolicyValidationError("Retry policy must be an object.")

    max_attempts = policy.get("max_attempts", DEFAULT_RETRY_POLICY["max_attempts"])
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool):
        raise RetryPolicyValidationError("Retry policy max_attempts must be an integer.")
    if max_attempts < 1:
        raise RetryPolicyValidationError("Retry policy max_attempts must be at least 1.")
    if max_attempts > MAX_ALLOWED_ATTEMPTS:
        raise RetryPolicyValidationError(f"Retry policy max_attempts must not exceed {MAX_ALLOWED_ATTEMPTS}.")

    delay_seconds = policy.get("delay_seconds", DEFAULT_RETRY_POLICY["delay_seconds"])
    if not isinstance(delay_seconds, (int, float)) or isinstance(delay_seconds, bool):
        raise RetryPolicyValidationError("Retry policy delay_seconds must be a number.")
    if delay_seconds < 0:
        raise RetryPolicyValidationError("Retry policy delay_seconds must be non-negative.")
    if delay_seconds > MAX_ALLOWED_DELAY_SECONDS:
        raise RetryPolicyValidationError(
            f"Retry policy delay_seconds must not exceed {MAX_ALLOWED_DELAY_SECONDS}."
        )

    retry_on = policy.get("retry_on", DEFAULT_RETRY_POLICY["retry_on"])
    if not isinstance(retry_on, list):
        raise RetryPolicyValidationError("Retry policy retry_on must be a list.")
    if not retry_on:
        raise RetryPolicyValidationError("Retry policy retry_on must not be empty.")
    if any(not isinstance(item, str) or not item.strip() for item in retry_on):
        raise RetryPolicyValidationError("Retry policy retry_on items must be non-empty strings.")

    do_not_retry_on = policy.get("do_not_retry_on", [])
    if not isinstance(do_not_retry_on, list):
        raise RetryPolicyValidationError("Retry policy do_not_retry_on must be a list.")
    if any(not isinstance(item, str) or not item.strip() for item in do_not_retry_on):
        raise RetryPolicyValidationError("Retry policy do_not_retry_on items must be non-empty strings.")

    fail_on_exhausted = policy.get("fail_on_exhausted", DEFAULT_RETRY_POLICY["fail_on_exhausted"])
    if not isinstance(fail_on_exhausted, bool):
        raise RetryPolicyValidationError("Retry policy fail_on_exhausted must be a boolean.")


def get_step_max_attempts(retry: dict[str, Any] | None) -> int:
    policy = normalize_retry_policy(retry)
    return int(policy["max_attempts"])


def classify_error(error: Exception | str | dict[str, Any]) -> dict[str, str]:
    if isinstance(error, dict):
        return {
            "error_type": str(error.get("error_type", "UnknownError")),
            "message": str(error.get("message", "")),
            "tag": str(error.get("tag", "unknown")),
        }

    if isinstance(error, str):
        return {"error_type": "RuntimeError", "message": error, "tag": "unknown"}

    error_type = type(error).__name__
    message = str(error)
    if isinstance(error, StepTimeoutExceeded):
        return {"error_type": "StepTimeoutExceeded", "message": message, "tag": "timeout"}
    tag = getattr(error, "retry_tag", None)
    if not tag:
        if isinstance(error, (ToolFunctionError, ToolExecutionError, ToolImportError, ToolResultNormalizationError)):
            tag = "transient"
        elif isinstance(error, (LLMAdapterError, LLMOutputParseError, MemoryStoreError)):
            tag = "transient"
        else:
            tag = "unknown"
    return {"error_type": error_type, "message": message, "tag": str(tag)}


def is_retryable_error(error_info: dict[str, str], retry_policy: dict[str, Any]) -> bool:
    retry_on = retry_policy.get("retry_on", DEFAULT_RETRY_POLICY["retry_on"])
    if not isinstance(retry_on, list):
        return False
    if "any" in retry_on:
        return True
    error_type = error_info.get("error_type", "")
    tag = error_info.get("tag", "")
    return error_type in retry_on or tag in retry_on


def should_retry_step(step, error_info: dict[str, str]) -> bool:
    if isinstance(step, dict):
        kind = str(step.get("kind", "") or "")
        retry_policy = step.get("retry", None)
        attempts = int(step.get("attempts", 0) or 0)
    else:
        kind = str(getattr(step, "kind", "") or "")
        retry_policy = getattr(step, "retry", None)
        attempts = int(getattr(step, "attempts", 0) or 0)
    if kind == "validate":
        return False
    if error_info.get("tag") in {"policy", "validation"}:
        return False
    if error_info.get("error_type") in {"LiveToolExecutionBlocked", "RetryExhaustedError"}:
        return False
    policy = normalize_retry_policy(retry_policy)
    do_not_retry_on = policy.get("do_not_retry_on", [])
    if isinstance(do_not_retry_on, list):
        if error_info.get("error_type") in do_not_retry_on or error_info.get("tag") in do_not_retry_on:
            return False
    if attempts >= int(policy["max_attempts"]):
        return False
    return is_retryable_error(error_info, policy)


def sleep_before_retry(delay_seconds: float) -> None:
    if delay_seconds and delay_seconds > 0:
        sleep(delay_seconds)
