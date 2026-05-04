import unittest

from runtime.conditions import (
    compare_numeric,
    evaluate_condition,
    evaluate_condition_with_trace,
    coerce_number,
    validate_condition,
)
from runtime.errors import ConditionValidationError
from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe
from runtime.validation import run_validation


def make_frame():
    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.inputs = {"amount": "1500", "other_amount": "500", "text_amount": "R1000"}
    return frame


class ComparisonConditionTests(unittest.TestCase):
    def test_coerce_number_accepts_int(self):
        self.assertEqual(coerce_number(1000), 1000)

    def test_coerce_number_accepts_float(self):
        self.assertEqual(coerce_number(1000.5), 1000.5)

    def test_coerce_number_accepts_numeric_string(self):
        self.assertEqual(coerce_number("1000.5"), 1000.5)

    def test_coerce_number_rejects_comma_number_string(self):
        with self.assertRaises(ConditionValidationError):
            coerce_number("1,000")

    def test_coerce_number_rejects_currency_string(self):
        with self.assertRaises(ConditionValidationError):
            coerce_number("R1000")

    def test_coerce_number_rejects_word_number(self):
        with self.assertRaises(ConditionValidationError):
            coerce_number("one thousand")

    def test_coerce_number_rejects_empty_string(self):
        with self.assertRaises(ConditionValidationError):
            coerce_number("")

    def test_coerce_number_rejects_none(self):
        with self.assertRaises(ConditionValidationError):
            coerce_number(None)

    def test_greater_than_passes(self):
        self.assertTrue(compare_numeric("1500", "greater_than", 1000))

    def test_greater_than_fails_equal(self):
        self.assertFalse(compare_numeric("1000", "greater_than", 1000))

    def test_greater_than_or_equal_passes_equal(self):
        self.assertTrue(compare_numeric("1000", "greater_than_or_equal", 1000))

    def test_less_than_passes(self):
        self.assertTrue(compare_numeric("900", "less_than", 1000))

    def test_less_than_or_equal_passes_equal(self):
        self.assertTrue(compare_numeric("1000", "less_than_or_equal", 1000))

    def test_between_passes_lower_boundary(self):
        self.assertTrue(compare_numeric("1000", "between", [1000, 2000]))

    def test_between_passes_upper_boundary(self):
        self.assertTrue(compare_numeric("2000", "between", [1000, 2000]))

    def test_between_passes_middle(self):
        self.assertTrue(compare_numeric("1500", "between", [1000, 2000]))

    def test_between_fails_below(self):
        self.assertFalse(compare_numeric("999", "between", [1000, 2000]))

    def test_between_fails_above(self):
        self.assertFalse(compare_numeric("2001", "between", [1000, 2000]))

    def test_not_between_passes_below(self):
        self.assertTrue(compare_numeric("999", "not_between", [1000, 2000]))

    def test_not_between_passes_above(self):
        self.assertTrue(compare_numeric("2001", "not_between", [1000, 2000]))

    def test_not_between_fails_middle(self):
        self.assertFalse(compare_numeric("1500", "not_between", [1000, 2000]))

    def test_validate_condition_accepts_numeric_greater_than(self):
        validate_condition({"input": "amount", "greater_than": 1000})

    def test_validate_condition_accepts_numeric_between(self):
        validate_condition({"input": "amount", "between": [1000, 2000]})

    def test_validate_condition_rejects_invalid_numeric_expected(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"input": "amount", "greater_than": "low"})

    def test_validate_condition_rejects_between_wrong_list_length(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"input": "amount", "between": [1]})

    def test_validate_condition_rejects_between_non_numeric_bounds(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"input": "amount", "between": ["low", "high"]})

    def test_evaluate_condition_with_trace_includes_numeric_normalized_values(self):
        frame = make_frame()
        trace = evaluate_condition_with_trace(frame, {"input": "amount", "greater_than": 1000})
        self.assertTrue(trace["ok"])
        self.assertEqual(trace["resolved_normalized"], 1500)
        self.assertEqual(trace["expected_normalized"], 1000)

    def test_condition_true_validation_passes_for_numeric_condition(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {
                "id": "amount_above_threshold",
                "type": "condition_true",
                "condition": {"input": "amount", "greater_than": 1000},
            },
        )
        self.assertTrue(result.ok)

    def test_condition_false_validation_passes_when_numeric_condition_false(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {
                "id": "amount_not_above_threshold",
                "type": "condition_false",
                "condition": {"input": "other_amount", "greater_than": 1000},
            },
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
