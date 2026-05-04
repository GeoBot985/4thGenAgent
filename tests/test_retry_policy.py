import unittest
from types import SimpleNamespace
from unittest.mock import patch

from runtime.errors import RetryPolicyValidationError, StepTimeoutExceeded, ToolFunctionError
from runtime.retry_policy import (
    DEFAULT_RETRY_POLICY,
    classify_error,
    get_step_max_attempts,
    is_retryable_error,
    normalize_retry_policy,
    should_retry_step,
    sleep_before_retry,
    validate_retry_policy,
)


class RetryPolicyTests(unittest.TestCase):
    def test_normalize_retry_policy_defaults_when_none(self):
        self.assertEqual(normalize_retry_policy(None), DEFAULT_RETRY_POLICY)

    def test_normalize_retry_policy_fills_missing_fields(self):
        policy = normalize_retry_policy({"max_attempts": 3})
        self.assertEqual(policy["max_attempts"], 3)
        self.assertEqual(policy["delay_seconds"], 0)
        self.assertEqual(policy["retry_on"], ["any"])
        self.assertTrue(policy["fail_on_exhausted"])

    def test_validate_retry_policy_accepts_valid_policy(self):
        validate_retry_policy(
            {
                "max_attempts": 3,
                "delay_seconds": 1,
                "retry_on": ["any"],
                "fail_on_exhausted": True,
            }
        )

    def test_validate_retry_policy_rejects_non_dict(self):
        with self.assertRaises(RetryPolicyValidationError):
            validate_retry_policy(None)  # type: ignore[arg-type]

    def test_validate_retry_policy_rejects_max_attempts_bounds(self):
        with self.assertRaises(RetryPolicyValidationError):
            validate_retry_policy({"max_attempts": 0, "delay_seconds": 0, "retry_on": ["any"], "fail_on_exhausted": True})
        with self.assertRaises(RetryPolicyValidationError):
            validate_retry_policy({"max_attempts": 6, "delay_seconds": 0, "retry_on": ["any"], "fail_on_exhausted": True})
        with self.assertRaises(RetryPolicyValidationError):
            validate_retry_policy({"max_attempts": "2", "delay_seconds": 0, "retry_on": ["any"], "fail_on_exhausted": True})  # type: ignore[arg-type]

    def test_validate_retry_policy_rejects_delay_bounds(self):
        with self.assertRaises(RetryPolicyValidationError):
            validate_retry_policy({"max_attempts": 1, "delay_seconds": -1, "retry_on": ["any"], "fail_on_exhausted": True})
        with self.assertRaises(RetryPolicyValidationError):
            validate_retry_policy({"max_attempts": 1, "delay_seconds": 31, "retry_on": ["any"], "fail_on_exhausted": True})
        with self.assertRaises(RetryPolicyValidationError):
            validate_retry_policy({"max_attempts": 1, "delay_seconds": "x", "retry_on": ["any"], "fail_on_exhausted": True})  # type: ignore[arg-type]

    def test_validate_retry_policy_rejects_retry_on_and_fail_on_exhausted(self):
        with self.assertRaises(RetryPolicyValidationError):
            validate_retry_policy({"max_attempts": 1, "delay_seconds": 0, "retry_on": "any", "fail_on_exhausted": True})  # type: ignore[arg-type]
        with self.assertRaises(RetryPolicyValidationError):
            validate_retry_policy({"max_attempts": 1, "delay_seconds": 0, "retry_on": [], "fail_on_exhausted": True})
        with self.assertRaises(RetryPolicyValidationError):
            validate_retry_policy({"max_attempts": 1, "delay_seconds": 0, "retry_on": ["any", 1], "fail_on_exhausted": True})  # type: ignore[list-item]
        with self.assertRaises(RetryPolicyValidationError):
            validate_retry_policy({"max_attempts": 1, "delay_seconds": 0, "retry_on": ["any"], "fail_on_exhausted": "yes"})  # type: ignore[arg-type]

    def test_classify_error_handles_exception_string_and_dict(self):
        exc_info = classify_error(ToolFunctionError("temporary failure"))
        self.assertEqual(exc_info["error_type"], "ToolFunctionError")
        self.assertEqual(exc_info["message"], "temporary failure")
        self.assertEqual(exc_info["tag"], "transient")

        timeout_info = classify_error(StepTimeoutExceeded("timed out"))
        self.assertEqual(timeout_info["error_type"], "StepTimeoutExceeded")
        self.assertEqual(timeout_info["tag"], "timeout")

        string_info = classify_error("something bad")
        self.assertEqual(string_info["error_type"], "RuntimeError")
        self.assertEqual(string_info["tag"], "unknown")

        dict_info = classify_error({"error_type": "X", "message": "m", "tag": "t"})
        self.assertEqual(dict_info["error_type"], "X")
        self.assertEqual(dict_info["message"], "m")
        self.assertEqual(dict_info["tag"], "t")

    def test_is_retryable_error_matches_any_error_type_and_tag(self):
        policy = {"retry_on": ["any"]}
        self.assertTrue(is_retryable_error({"error_type": "X", "tag": "y", "message": ""}, policy))

        policy = {"retry_on": ["ToolFunctionError"]}
        self.assertTrue(is_retryable_error({"error_type": "ToolFunctionError", "tag": "unknown", "message": ""}, policy))
        self.assertFalse(is_retryable_error({"error_type": "Other", "tag": "unknown", "message": ""}, policy))

        policy = {"retry_on": ["transient"]}
        self.assertTrue(is_retryable_error({"error_type": "Other", "tag": "transient", "message": ""}, policy))
        self.assertFalse(is_retryable_error({"error_type": "Other", "tag": "unknown", "message": ""}, policy))

        policy = {"retry_on": ["timeout"]}
        self.assertTrue(is_retryable_error({"error_type": "StepTimeoutExceeded", "tag": "timeout", "message": ""}, policy))

        policy = {"retry_on": ["StepTimeoutExceeded"]}
        self.assertTrue(is_retryable_error({"error_type": "StepTimeoutExceeded", "tag": "timeout", "message": ""}, policy))

    def test_should_retry_step_false_when_attempts_exhausted(self):
        step = SimpleNamespace(kind="tool", retry={"max_attempts": 1, "delay_seconds": 0, "retry_on": ["any"]}, attempts=1)
        self.assertFalse(should_retry_step(step, {"error_type": "ToolFunctionError", "tag": "transient", "message": "x"}))

    def test_should_retry_step_true_when_attempts_remain(self):
        step = SimpleNamespace(kind="tool", retry={"max_attempts": 2, "delay_seconds": 0, "retry_on": ["any"]}, attempts=1)
        self.assertTrue(should_retry_step(step, {"error_type": "ToolFunctionError", "tag": "transient", "message": "x"}))

    def test_sleep_before_retry_calls_sleep_when_delay_positive(self):
        with patch("runtime.retry_policy.sleep") as sleep_mock:
            sleep_before_retry(1)
            sleep_mock.assert_called_once_with(1)

    def test_sleep_before_retry_does_nothing_when_delay_zero(self):
        with patch("runtime.retry_policy.sleep") as sleep_mock:
            sleep_before_retry(0)
            sleep_mock.assert_not_called()

    def test_get_step_max_attempts_uses_retry_policy(self):
        self.assertEqual(get_step_max_attempts({"max_attempts": 4}), 4)


if __name__ == "__main__":
    unittest.main()
