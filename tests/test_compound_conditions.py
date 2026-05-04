import json
import unittest

from runtime.conditions import (
    evaluate_condition,
    evaluate_condition_with_trace,
    is_compound_condition,
    validate_condition,
)
from runtime.errors import ConditionEvaluationError, ConditionValidationError
from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe


def make_frame():
    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.inputs = {
        "channel": "whatsapp",
        "priority": "urgent",
        "category": "refund",
    }
    frame.trigger = {
        "source": "manual",
        "channel": "whatsapp",
    }
    frame.outputs = {
        "category": {
            "label": "refund",
            "confidence": "high",
            "customer": {"order_ref": "ORD-10042"},
        },
        "tags": ["urgent", "vip"],
        "reply": "We will review your refund request.",
    }
    return frame


class CompoundConditionTests(unittest.TestCase):
    def test_validate_condition_accepts_all_with_atomic_children(self):
        validate_condition(
            {
                "all": [
                    {"output": "category", "field": "label", "equals": "refund"},
                    {"input": "channel", "equals": "whatsapp"},
                ]
            }
        )

    def test_validate_condition_accepts_any_with_atomic_children(self):
        validate_condition(
            {
                "any": [
                    {"output": "category", "field": "label", "equals": "complaint"},
                    {"output": "category", "field": "confidence", "equals": "low"},
                ]
            }
        )

    def test_validate_condition_accepts_not_with_atomic_child(self):
        validate_condition({"not": {"input": "channel", "equals": "email"}})

    def test_validate_condition_accepts_nested_all_any(self):
        validate_condition(
            {
                "all": [
                    {"output": "category", "field": "label", "in": ["refund", "complaint"]},
                    {
                        "any": [
                            {"input": "channel", "equals": "whatsapp"},
                            {"input": "channel", "equals": "email"},
                        ]
                    },
                ]
            }
        )

    def test_validate_condition_rejects_all_empty_list(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"all": []})

    def test_validate_condition_rejects_any_empty_list(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"any": []})

    def test_validate_condition_rejects_not_list(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"not": []})

    def test_validate_condition_rejects_not_empty_dict(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"not": {}})

    def test_validate_condition_rejects_multiple_compound_operators(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition(
                {
                    "all": [{"input": "channel", "equals": "whatsapp"}],
                    "any": [{"input": "priority", "equals": "urgent"}],
                }
            )

    def test_validate_condition_rejects_compound_plus_atomic_source_same_level(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition(
                {
                    "all": [{"input": "channel", "equals": "whatsapp"}],
                    "output": "category",
                }
            )

    def test_validate_condition_rejects_child_that_is_not_dict(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"all": ["not a condition"]})

    def test_evaluate_all_passes_when_all_children_pass(self):
        frame = make_frame()
        self.assertTrue(
            evaluate_condition(
                frame,
                {
                    "all": [
                        {"output": "category", "field": "label", "equals": "refund"},
                        {"input": "channel", "equals": "whatsapp"},
                    ]
                },
            )
        )

    def test_evaluate_all_fails_when_one_child_fails(self):
        frame = make_frame()
        self.assertFalse(
            evaluate_condition(
                frame,
                {
                    "all": [
                        {"output": "category", "field": "label", "equals": "refund"},
                        {"input": "priority", "equals": "low"},
                    ]
                },
            )
        )

    def test_evaluate_any_passes_when_one_child_passes(self):
        frame = make_frame()
        self.assertTrue(
            evaluate_condition(
                frame,
                {
                    "any": [
                        {"output": "category", "field": "label", "equals": "complaint"},
                        {"input": "channel", "equals": "whatsapp"},
                    ]
                },
            )
        )

    def test_evaluate_any_fails_when_all_children_fail(self):
        frame = make_frame()
        self.assertFalse(
            evaluate_condition(
                frame,
                {
                    "any": [
                        {"output": "category", "field": "label", "equals": "complaint"},
                        {"input": "priority", "equals": "low"},
                    ]
                },
            )
        )

    def test_evaluate_not_inverts_true_to_false(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"not": {"input": "channel", "equals": "whatsapp"}}))

    def test_evaluate_not_inverts_false_to_true(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"not": {"input": "channel", "equals": "email"}}))

    def test_evaluate_nested_compound_passes(self):
        frame = make_frame()
        self.assertTrue(
            evaluate_condition(
                frame,
                {
                    "all": [
                        {"output": "category", "field": "label", "in": ["refund", "complaint"]},
                        {
                            "any": [
                                {"input": "channel", "equals": "whatsapp"},
                                {"input": "channel", "equals": "email"},
                            ]
                        },
                    ]
                },
            )
        )

    def test_evaluate_nested_compound_fails(self):
        frame = make_frame()
        self.assertFalse(
            evaluate_condition(
                frame,
                {
                    "all": [
                        {"output": "category", "field": "label", "equals": "refund"},
                        {
                            "any": [
                                {"input": "channel", "equals": "sms"},
                                {"input": "priority", "equals": "low"},
                            ]
                        },
                    ]
                },
            )
        )

    def test_evaluate_compound_raises_on_missing_referenced_output(self):
        frame = make_frame()
        with self.assertRaises(ConditionEvaluationError):
            evaluate_condition(frame, {"all": [{"output": "missing", "equals": "x"}]})

    def test_evaluate_condition_with_trace_returns_json_serializable_trace(self):
        frame = make_frame()
        trace = evaluate_condition_with_trace(
            frame,
            {
                "all": [
                    {"output": "category", "field": "label", "equals": "refund"},
                    {"input": "channel", "equals": "whatsapp"},
                ]
            },
        )
        json.dumps(trace)
        self.assertTrue(trace["ok"])
        self.assertEqual(trace["operator"], "all")
        self.assertEqual(len(trace["children"]), 2)

    def test_trace_includes_operator_and_child_results(self):
        frame = make_frame()
        trace = evaluate_condition_with_trace(
            frame,
            {
                "any": [
                    {"output": "category", "field": "label", "equals": "complaint"},
                    {"input": "priority", "equals": "low"},
                ]
            },
        )
        self.assertFalse(trace["ok"])
        self.assertEqual(trace["operator"], "any")
        self.assertEqual(len(trace["children"]), 2)
        self.assertFalse(trace["children"][0]["ok"])
        self.assertFalse(trace["children"][1]["ok"])

    def test_is_compound_condition_detects_compound(self):
        self.assertTrue(is_compound_condition({"all": [{"input": "channel", "equals": "whatsapp"}]}))
        self.assertFalse(is_compound_condition({"input": "channel", "equals": "whatsapp"}))


if __name__ == "__main__":
    unittest.main()
