import unittest

from runtime.conditions import (
    evaluate_condition,
    evaluate_condition_with_trace,
    parse_hhmm_time,
    parse_iso_date,
    validate_condition,
)
from runtime.errors import ConditionValidationError
from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe
from runtime.validation import run_validation


def make_frame():
    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.inputs = {
        "requested_date": "2026-05-15",
        "other_date": "2026-06-01",
        "requested_time": "18:00",
        "other_time": "09:30",
        "overnight_start": "22:00",
        "overnight_time": "23:30",
        "overnight_boundary": "00:30",
        "overnight_end": "02:00",
    }
    return frame


class DateTimeConditionTests(unittest.TestCase):
    def test_parse_iso_date_accepts_yyyy_mm_dd(self):
        self.assertEqual(parse_iso_date("2026-05-01").isoformat(), "2026-05-01")

    def test_parse_iso_date_rejects_dd_mm_yyyy(self):
        with self.assertRaises(ConditionValidationError):
            parse_iso_date("01/05/2026")

    def test_parse_iso_date_rejects_yyyy_mm_dd_slash(self):
        with self.assertRaises(ConditionValidationError):
            parse_iso_date("2026/05/01")

    def test_parse_iso_date_rejects_natural_language(self):
        with self.assertRaises(ConditionValidationError):
            parse_iso_date("tomorrow")

    def test_parse_iso_date_rejects_empty_string(self):
        with self.assertRaises(ConditionValidationError):
            parse_iso_date("")

    def test_on_date_passes_exact(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_date", "on_date": "2026-05-15"}))

    def test_before_date_passes_earlier(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_date", "before_date": "2026-05-31"}))

    def test_before_date_fails_same_date(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"input": "requested_date", "before_date": "2026-05-15"}))

    def test_on_or_before_date_passes_same_date(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_date", "on_or_before_date": "2026-05-15"}))

    def test_after_date_passes_later(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_date", "after_date": "2026-05-01"}))

    def test_after_date_fails_same_date(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"input": "requested_date", "after_date": "2026-05-15"}))

    def test_on_or_after_date_passes_same_date(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_date", "on_or_after_date": "2026-05-15"}))

    def test_between_dates_passes_lower_boundary(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_date", "between_dates": ["2026-05-15", "2026-05-31"]}))

    def test_between_dates_passes_upper_boundary(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_date", "between_dates": ["2026-05-01", "2026-05-15"]}))

    def test_between_dates_passes_middle(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_date", "between_dates": ["2026-05-01", "2026-05-31"]}))

    def test_between_dates_fails_outside(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"input": "requested_date", "between_dates": ["2026-05-16", "2026-05-31"]}))

    def test_not_between_dates_passes_outside(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_date", "not_between_dates": ["2026-05-16", "2026-05-31"]}))

    def test_not_between_dates_fails_inside(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"input": "requested_date", "not_between_dates": ["2026-05-01", "2026-05-31"]}))

    def test_validate_condition_rejects_between_dates_reversed_range(self):
        with self.assertRaises(ConditionValidationError):
            validate_condition({"input": "requested_date", "between_dates": ["2026-05-31", "2026-05-01"]})

    def test_parse_hhmm_time_accepts_hhmm(self):
        self.assertEqual(parse_hhmm_time("17:00").isoformat(timespec="minutes"), "17:00")

    def test_parse_hhmm_time_rejects_h_mm(self):
        with self.assertRaises(ConditionValidationError):
            parse_hhmm_time("7:00")

    def test_parse_hhmm_time_rejects_hhmmss(self):
        with self.assertRaises(ConditionValidationError):
            parse_hhmm_time("17:00:00")

    def test_parse_hhmm_time_rejects_24_00(self):
        with self.assertRaises(ConditionValidationError):
            parse_hhmm_time("24:00")

    def test_parse_hhmm_time_rejects_5pm(self):
        with self.assertRaises(ConditionValidationError):
            parse_hhmm_time("5pm")

    def test_at_time_passes_exact(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_time", "at_time": "18:00"}))

    def test_before_time_passes_earlier(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_time", "before_time": "20:00"}))

    def test_before_time_fails_same(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"input": "requested_time", "before_time": "18:00"}))

    def test_on_or_before_time_passes_same(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_time", "on_or_before_time": "18:00"}))

    def test_after_time_passes_later(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_time", "after_time": "17:00"}))

    def test_after_time_fails_same(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"input": "requested_time", "after_time": "18:00"}))

    def test_on_or_after_time_passes_same(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_time", "on_or_after_time": "18:00"}))

    def test_between_time_passes_lower_boundary(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_time", "between_time": ["18:00", "20:00"]}))

    def test_between_time_passes_upper_boundary(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_time", "between_time": ["17:00", "18:00"]}))

    def test_between_time_passes_middle(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_time", "between_time": ["17:00", "20:00"]}))

    def test_between_time_fails_outside(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"input": "requested_time", "between_time": ["19:00", "20:00"]}))

    def test_not_between_time_passes_outside(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "requested_time", "not_between_time": ["19:00", "20:00"]}))

    def test_not_between_time_fails_inside(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"input": "requested_time", "not_between_time": ["17:00", "20:00"]}))

    def test_between_time_supports_overnight_window_at_2330(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "overnight_time", "between_time": ["22:00", "02:00"]}))

    def test_between_time_supports_overnight_window_at_0030(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "overnight_boundary", "between_time": ["22:00", "02:00"]}))

    def test_between_time_supports_overnight_boundary_start(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "overnight_start", "between_time": ["22:00", "02:00"]}))
        self.assertTrue(evaluate_condition(frame, {"input": "overnight_time", "between_time": ["22:00", "02:00"]}))

    def test_between_time_supports_overnight_boundary_end(self):
        frame = make_frame()
        self.assertTrue(evaluate_condition(frame, {"input": "overnight_end", "between_time": ["22:00", "02:00"]}))

    def test_between_time_overnight_fails_outside(self):
        frame = make_frame()
        self.assertFalse(evaluate_condition(frame, {"input": "other_time", "between_time": ["22:00", "02:00"]}))

    def test_evaluate_condition_with_trace_includes_date_normalized_values(self):
        frame = make_frame()
        trace = evaluate_condition_with_trace(frame, {"input": "requested_date", "on_or_after_date": "2026-05-01"})
        self.assertTrue(trace["ok"])
        self.assertEqual(trace["resolved_normalized"], "2026-05-15")
        self.assertEqual(trace["expected_normalized"], "2026-05-01")

    def test_evaluate_condition_with_trace_includes_time_normalized_values(self):
        frame = make_frame()
        trace = evaluate_condition_with_trace(frame, {"input": "requested_time", "between_time": ["17:00", "20:00"]})
        self.assertTrue(trace["ok"])
        self.assertEqual(trace["resolved_normalized"], "18:00")
        self.assertEqual(trace["expected_normalized"], ["17:00", "20:00"])
        self.assertFalse(trace["overnight"])

    def test_condition_true_validation_passes_for_time_condition(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {
                "id": "time_window",
                "type": "condition_true",
                "condition": {"input": "requested_time", "between_time": ["17:00", "20:00"]},
            },
        )
        self.assertTrue(result.ok)

    def test_condition_false_validation_passes_for_date_condition_false(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {
                "id": "date_window",
                "type": "condition_false",
                "condition": {"input": "requested_date", "before_date": "2026-05-01"},
            },
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
