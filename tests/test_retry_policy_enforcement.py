from __future__ import annotations

from runtime.retry_policy import should_retry_step, validate_retry_policy


def test_dict_step_honors_do_not_retry_on() -> None:
    step = {
        "kind": "tool",
        "attempts": 1,
        "retry": {
            "max_attempts": 3,
            "retry_on": ["any"],
            "do_not_retry_on": ["business_validation_failure", "duplicate_side_effect_risk"],
        },
    }
    error_info = {"error_type": "ValidationError", "message": "bad", "tag": "business_validation_failure"}

    assert should_retry_step(step, error_info) is False


def test_dict_step_allows_retry_for_retryable_transient_error() -> None:
    step = {
        "kind": "tool",
        "attempts": 0,
        "retry": {
            "max_attempts": 3,
            "retry_on": ["external_dependency_unavailable", "timeout"],
            "do_not_retry_on": ["business_validation_failure", "duplicate_side_effect_risk"],
        },
    }
    error_info = {"error_type": "TimeoutError", "message": "timeout", "tag": "external_dependency_unavailable"}

    assert should_retry_step(step, error_info) is True


def test_validation_step_is_never_auto_retried() -> None:
    step = {"kind": "validate", "attempts": 0, "retry": {"max_attempts": 3, "retry_on": ["any"], "do_not_retry_on": []}}
    error_info = {"error_type": "TimeoutError", "message": "timeout", "tag": "timeout"}

    assert should_retry_step(step, error_info) is False


def test_validate_retry_policy_accepts_do_not_retry_on_list() -> None:
    validate_retry_policy(
        {
            "max_attempts": 2,
            "delay_seconds": 1,
            "retry_on": ["timeout"],
            "do_not_retry_on": ["duplicate_side_effect_risk"],
            "fail_on_exhausted": True,
        }
    )
