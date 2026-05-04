import unittest

from runtime.conditions import ATOMIC_OPERATORS, evaluate_condition, get_nested_field, is_empty, resolve_condition_value, validate_condition
from runtime.errors import ConditionEvaluationError, ConditionValidationError
from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe


def make_frame():
    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.inputs = {"channel": "whatsapp", "mode": "manual"}
    frame.trigger = {"source": "scheduler", "kind": "event"}
    frame.outputs = {
        "category": {"label": "refund", "confidence": "high"},
        "tags": ["urgent", "vip"],
        "nested": {"customer": {"order_ref": "ORD-10042"}},
        "empty_list": [],
        "empty_text": "",
        "empty_dict": {},
        "falsy_zero": 0,
        "falsy_bool": False,
    }
    return frame


class ConditionTests(unittest.TestCase):
    def test_validate_condition_accepts_output_equals(self):
        validate_condition({"output": "category", "field": "label", "equals": "refund"})

    def test_validate_condition_accepts_input_equals(self):
        validate_condition({"input": "channel", "equals": "whatsapp"})

    def test_validate_condition_accepts_event_equals(self):
        validate_condition({"event": "source", "equals": "scheduler"})

    def test_validate_condition_rejects_empty_condition(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({})

    def test_validate_condition_rejects_multiple_sources(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"output": "category", "input": "channel", "equals": "refund"})

    def test_validate_condition_rejects_missing_source(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"field": "label", "equals": "refund"})

    def test_validate_condition_rejects_missing_operator(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"output": "category"})

    def test_validate_condition_rejects_multiple_operators(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"output": "category", "equals": "refund", "not_equals": "refund"})

    def test_validate_condition_rejects_unknown_operator(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"output": "category", "unknown": "x"})

    def test_validate_condition_rejects_in_when_value_is_not_list(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"output": "category", "in": "refund"})

    def test_validate_condition_rejects_not_in_when_value_is_not_list(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"output": "category", "not_in": "refund"})

    def test_is_empty_detects_none(self):
        self.assertTrue(is_empty(None))

    def test_is_empty_detects_empty_string(self):
        self.assertTrue(is_empty(""))

    def test_is_empty_detects_empty_list(self):
        self.assertTrue(is_empty([]))

    def test_is_empty_detects_empty_dict(self):
        self.assertTrue(is_empty({}))

    def test_is_empty_returns_false_for_zero(self):
        self.assertFalse(is_empty(0))

    def test_is_empty_returns_false_for_false(self):
        self.assertFalse(is_empty(False))

    def test_resolve_condition_value_reads_input(self):
        frame = make_frame()
        self.assertEqual(resolve_condition_value(frame, {"input": "channel", "equals": "whatsapp"}), "whatsapp")

    def test_resolve_condition_value_reads_event(self):
        frame = make_frame()
        self.assertEqual(resolve_condition_value(frame, {"event": "source", "equals": "scheduler"}), "scheduler")

    def test_resolve_condition_value_reads_output(self):
        frame = make_frame()
        self.assertEqual(resolve_condition_value(frame, {"output": "category", "equals": "refund"}), {"label": "refund", "confidence": "high"})

    def test_resolve_condition_value_reads_output_field(self):
        frame = make_frame()
        self.assertEqual(resolve_condition_value(frame, {"output": "category", "field": "label", "equals": "refund"}), "refund")

    def test_resolve_condition_value_reads_nested_output_field(self):
        frame = make_frame()
        self.assertEqual(
            resolve_condition_value(frame, {"output": "nested", "field": "customer.order_ref", "equals": "ORD-10042"}),
            "ORD-10042",
        )

    def test_resolve_condition_value_fails_missing_output(self):
        frame = make_frame()
        with self.assertRaises(ConditionEvaluationError):
            resolve_condition_value(frame, {"output": "missing", "equals": "x"})

    def test_resolve_condition_value_fails_missing_field(self):
        frame = make_frame()
        with self.assertRaises(ConditionEvaluationError):
            resolve_condition_value(frame, {"output": "category", "field": "missing", "equals": "x"})

    def test_evaluate_condition_exists_passes(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"output": "category", "exists": True}))

    def test_evaluate_condition_exists_fails(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"output": "missing", "exists": True}))

    def test_evaluate_condition_missing_passes(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"output": "missing", "missing": True}))

    def test_evaluate_condition_equals_passes(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "channel", "equals": "whatsapp"}))

    def test_evaluate_condition_equals_fails(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"input": "channel", "equals": "email"}))

    def test_evaluate_condition_not_equals_passes(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "channel", "not_equals": "email"}))

    def test_evaluate_condition_in_passes(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "channel", "in": ["whatsapp", "email"]}))

    def test_evaluate_condition_not_in_passes(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "channel", "not_in": ["email", "sms"]}))

    def test_evaluate_condition_contains_string_passes(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "channel", "contains": "hat"}))

    def test_evaluate_condition_contains_list_passes(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"output": "tags", "contains": "urgent"}))

    def test_evaluate_condition_contains_dict_key_passes(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"output": "category", "contains": "label"}))

    def test_evaluate_condition_truthy_passes(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"output": "category", "truthy": True}))

    def test_evaluate_condition_falsey_passes(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"output": "empty_text", "falsey": True}))

    def test_atomic_condition_still_works_after_compound_refactor(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"output": "category", "field": "label", "equals": "refund"}))

    def test_invalid_atomic_condition_still_fails_after_compound_refactor(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"output": "category", "field": "label"})

    def test_atomic_operators_include_comparison_operators(self):
        self.assertIn("greater_than", ATOMIC_OPERATORS)
        self.assertIn("between_dates", ATOMIC_OPERATORS)
        self.assertIn("between_time", ATOMIC_OPERATORS)

    def test_compound_all_works_with_numeric_date_time_children(self):
        frame = make_frame()
        frame.inputs.update({"amount": "1500", "requested_date": "2026-05-15", "requested_time": "18:00"})
        self.assertTrue(
            evaluate_condition(
                frame,
                {
                    "all": [
                        {"input": "amount", "greater_than": 1000},
                        {"input": "requested_date", "on_or_after_date": "2026-05-01"},
                        {"input": "requested_time", "between_time": ["17:00", "20:00"]},
                    ]
                },
            )
        )

    def test_compound_any_works_with_numeric_date_time_children(self):
        frame = make_frame()
        frame.inputs.update({"amount": "50", "requested_date": "2026-04-01", "requested_time": "08:00"})
        self.assertTrue(
            evaluate_condition(
                frame,
                {
                    "any": [
                        {"input": "amount", "greater_than": 1000},
                        {"input": "requested_date", "before_date": "2026-05-01"},
                        {"input": "requested_time", "between_time": ["17:00", "20:00"]},
                    ]
                },
            )
        )


if __name__ == "__main__":
    unittest.main()
