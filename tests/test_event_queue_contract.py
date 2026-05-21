"""Spec 137 — Test: event queue contract shape and helpers."""
from __future__ import annotations

import unittest

from runtime.event_queue_contract import (
    DEFAULT_MAX_ATTEMPTS,
    FAILURE_LLM_TRANSIENT_FAILURE,
    FAILURE_MANIFEST_NOT_FOUND,
    FAILURE_POLICY_BLOCKED,
    FAILURE_ROUTE_NOT_FOUND,
    FAILURE_RUNTIME_EXCEPTION,
    FAILURE_TRANSIENT_TOOL_FAILURE,
    FAILURE_VALIDATION_FAILED,
    NON_RETRYABLE_FAILURE_CATEGORIES,
    RETRYABLE_FAILURE_CATEGORIES,
    RETRY_POLICY,
    STATUS_CANCELLED,
    STATUS_CLAIMED,
    STATUS_COMPLETED,
    STATUS_DEAD_LETTER,
    STATUS_FAILED_PERMANENT,
    STATUS_FAILED_RETRYABLE,
    STATUS_PENDING,
    STATUS_PROCESSING,
    TERMINAL_STATUSES,
    ACTIVE_STATUSES,
    build_durable_queue_record,
    build_dedupe_key,
    classify_failure_from_status,
    is_retryable_failure_category,
    is_terminal_status,
    update_durable_queue_record,
)


def _make_event(source: str = "operator_ui", event_type: str = "test.event", event_id: str = "evt-001") -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "event_type": event_type,
        "payload": {"customer_id": "CUST-1"},
    }


class TestStatusConstants(unittest.TestCase):

    def test_terminal_statuses_are_correct(self):
        self.assertIn(STATUS_COMPLETED, TERMINAL_STATUSES)
        self.assertIn(STATUS_FAILED_PERMANENT, TERMINAL_STATUSES)
        self.assertIn(STATUS_DEAD_LETTER, TERMINAL_STATUSES)
        self.assertIn(STATUS_CANCELLED, TERMINAL_STATUSES)

    def test_active_statuses_are_correct(self):
        self.assertIn(STATUS_PENDING, ACTIVE_STATUSES)
        self.assertIn(STATUS_CLAIMED, ACTIVE_STATUSES)
        self.assertIn(STATUS_PROCESSING, ACTIVE_STATUSES)
        self.assertIn(STATUS_FAILED_RETRYABLE, ACTIVE_STATUSES)

    def test_no_overlap_between_terminal_and_active(self):
        self.assertEqual(TERMINAL_STATUSES & ACTIVE_STATUSES, frozenset())

    def test_is_terminal_status(self):
        for s in (STATUS_COMPLETED, STATUS_FAILED_PERMANENT, STATUS_DEAD_LETTER, STATUS_CANCELLED):
            self.assertTrue(is_terminal_status(s), f"{s} should be terminal")
        for s in (STATUS_PENDING, STATUS_CLAIMED, STATUS_PROCESSING, STATUS_FAILED_RETRYABLE):
            self.assertFalse(is_terminal_status(s), f"{s} should not be terminal")


class TestFailureCategories(unittest.TestCase):

    def test_retryable_categories(self):
        self.assertIn(FAILURE_TRANSIENT_TOOL_FAILURE, RETRYABLE_FAILURE_CATEGORIES)
        self.assertIn(FAILURE_LLM_TRANSIENT_FAILURE, RETRYABLE_FAILURE_CATEGORIES)
        self.assertIn(FAILURE_RUNTIME_EXCEPTION, RETRYABLE_FAILURE_CATEGORIES)

    def test_non_retryable_categories(self):
        self.assertIn(FAILURE_ROUTE_NOT_FOUND, NON_RETRYABLE_FAILURE_CATEGORIES)
        self.assertIn(FAILURE_MANIFEST_NOT_FOUND, NON_RETRYABLE_FAILURE_CATEGORIES)
        self.assertIn(FAILURE_VALIDATION_FAILED, NON_RETRYABLE_FAILURE_CATEGORIES)
        self.assertIn(FAILURE_POLICY_BLOCKED, NON_RETRYABLE_FAILURE_CATEGORIES)

    def test_is_retryable_failure_category(self):
        self.assertTrue(is_retryable_failure_category(FAILURE_RUNTIME_EXCEPTION))
        self.assertFalse(is_retryable_failure_category(FAILURE_ROUTE_NOT_FOUND))
        self.assertFalse(is_retryable_failure_category(""))

    def test_classify_failure_from_status(self):
        self.assertEqual(classify_failure_from_status("NO_ROUTE"), FAILURE_ROUTE_NOT_FOUND)
        self.assertEqual(classify_failure_from_status("MANIFEST_NOT_FOUND"), FAILURE_MANIFEST_NOT_FOUND)
        from runtime.event_queue_contract import FAILURE_INPUT_MAPPING_FAILED
        self.assertEqual(classify_failure_from_status("ROUTE_MAPPING_FAILED"), FAILURE_INPUT_MAPPING_FAILED)
        self.assertEqual(classify_failure_from_status("FAILED_VALIDATION"), FAILURE_VALIDATION_FAILED)
        self.assertEqual(classify_failure_from_status("UNKNOWN_STUFF"), FAILURE_RUNTIME_EXCEPTION)


class TestRetryPolicy(unittest.TestCase):

    def test_retry_policy_has_required_fields(self):
        self.assertIn("max_attempts", RETRY_POLICY)
        self.assertIn("retry_delay_seconds", RETRY_POLICY)
        self.assertIn("retryable_categories", RETRY_POLICY)

    def test_default_max_attempts(self):
        self.assertEqual(DEFAULT_MAX_ATTEMPTS, 3)
        self.assertEqual(RETRY_POLICY["max_attempts"], 3)


class TestBuildDurableQueueRecord(unittest.TestCase):

    def test_record_has_required_fields(self):
        event = _make_event()
        record = build_durable_queue_record(event)
        required = [
            "queue_id", "event_id", "source", "event_type", "status",
            "priority", "attempt_count", "max_attempts", "available_at",
            "claimed_at", "claimed_by", "completed_at", "linked_frame_id",
            "dedupe_key", "payload_json", "last_error", "failure_category",
            "created_at", "updated_at",
        ]
        for field in required:
            self.assertIn(field, record, f"Missing required field: {field}")

    def test_initial_status_is_pending(self):
        record = build_durable_queue_record(_make_event())
        self.assertEqual(record["status"], STATUS_PENDING)

    def test_initial_attempt_count_is_zero(self):
        record = build_durable_queue_record(_make_event())
        self.assertEqual(record["attempt_count"], 0)

    def test_default_priority_is_100(self):
        record = build_durable_queue_record(_make_event())
        self.assertEqual(record["priority"], 100)

    def test_default_max_attempts(self):
        record = build_durable_queue_record(_make_event())
        self.assertEqual(record["max_attempts"], DEFAULT_MAX_ATTEMPTS)

    def test_queue_id_is_uuid(self):
        import uuid
        record = build_durable_queue_record(_make_event())
        uuid.UUID(record["queue_id"])

    def test_payload_json_carries_event_payload(self):
        event = _make_event()
        record = build_durable_queue_record(event)
        self.assertEqual(record["payload_json"], event["payload"])

    def test_custom_priority_and_max_attempts(self):
        record = build_durable_queue_record(_make_event(), priority=50, max_attempts=5)
        self.assertEqual(record["priority"], 50)
        self.assertEqual(record["max_attempts"], 5)


class TestUpdateDurableQueueRecord(unittest.TestCase):

    def test_update_merges_overrides(self):
        record = build_durable_queue_record(_make_event())
        updated = update_durable_queue_record(record, status=STATUS_CLAIMED, claimed_by="worker-1")
        self.assertEqual(updated["status"], STATUS_CLAIMED)
        self.assertEqual(updated["claimed_by"], "worker-1")

    def test_update_bumps_updated_at(self):
        import time
        record = build_durable_queue_record(_make_event())
        original_updated_at = record["updated_at"]
        time.sleep(0.01)
        updated = update_durable_queue_record(record, status=STATUS_CLAIMED)
        self.assertGreaterEqual(updated["updated_at"], original_updated_at)

    def test_update_preserves_other_fields(self):
        record = build_durable_queue_record(_make_event())
        updated = update_durable_queue_record(record, status=STATUS_CLAIMED)
        self.assertEqual(updated["queue_id"], record["queue_id"])
        self.assertEqual(updated["event_id"], record["event_id"])
        self.assertEqual(updated["payload_json"], record["payload_json"])
