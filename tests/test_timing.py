import json
import unittest

from runtime.errors import TimeoutPolicyError
from runtime.timing import (
    build_timing_record,
    duration_ms,
    timeout_exceeded,
    validate_timeout_seconds,
)


class TimingTests(unittest.TestCase):
    def test_validate_timeout_seconds_accepts_int(self):
        self.assertEqual(validate_timeout_seconds(5), 5.0)

    def test_validate_timeout_seconds_accepts_float(self):
        self.assertEqual(validate_timeout_seconds(5.5), 5.5)

    def test_validate_timeout_seconds_accepts_none(self):
        self.assertIsNone(validate_timeout_seconds(None))

    def test_validate_timeout_seconds_rejects_string(self):
        with self.assertRaises(TimeoutPolicyError):
            validate_timeout_seconds("fast")  # type: ignore[arg-type]

    def test_validate_timeout_seconds_rejects_zero(self):
        with self.assertRaises(TimeoutPolicyError):
            validate_timeout_seconds(0)

    def test_validate_timeout_seconds_rejects_negative(self):
        with self.assertRaises(TimeoutPolicyError):
            validate_timeout_seconds(-1)

    def test_validate_timeout_seconds_rejects_too_large(self):
        with self.assertRaises(TimeoutPolicyError):
            validate_timeout_seconds(1000)

    def test_duration_ms_returns_positive_number(self):
        self.assertEqual(duration_ms(1.0, 1.5), 500.0)

    def test_timeout_exceeded_false_when_no_timeout(self):
        self.assertFalse(timeout_exceeded(1.0, None))

    def test_timeout_exceeded_false_under_timeout(self):
        self.assertFalse(timeout_exceeded(0.5, 1.0))

    def test_timeout_exceeded_true_over_timeout(self):
        self.assertTrue(timeout_exceeded(1.5, 1.0))

    def test_build_timing_record_returns_json_serializable_dict(self):
        record = build_timing_record(
            "step_1",
            2,
            "2026-04-30T20:00:00Z",
            "2026-04-30T20:00:01Z",
            1000.0,
            1.0,
            True,
        )
        json.dumps(record)

    def test_build_timing_record_includes_expected_fields(self):
        record = build_timing_record(
            "step_1",
            2,
            "2026-04-30T20:00:00Z",
            "2026-04-30T20:00:01Z",
            1000.0,
            1.0,
            True,
        )
        self.assertEqual(record["step_id"], "step_1")
        self.assertEqual(record["attempt"], 2)
        self.assertEqual(record["duration_ms"], 1000.0)
        self.assertTrue(record["timed_out"])


if __name__ == "__main__":
    unittest.main()
