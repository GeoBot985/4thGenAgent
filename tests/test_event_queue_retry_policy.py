"""Spec 137 — Test: durable queue retry policy and failure classification."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.event_queue import (
    claim_next_event,
    enqueue_event,
    mark_event_failed,
    mark_event_processing,
    retry_event,
)
from runtime.event_queue_contract import (
    DEFAULT_MAX_ATTEMPTS,
    FAILURE_INPUT_MAPPING_FAILED,
    FAILURE_LLM_TRANSIENT_FAILURE,
    FAILURE_MANIFEST_NOT_FOUND,
    FAILURE_POLICY_BLOCKED,
    FAILURE_ROUTE_NOT_FOUND,
    FAILURE_RUNTIME_EXCEPTION,
    FAILURE_TRANSIENT_TOOL_FAILURE,
    FAILURE_VALIDATION_FAILED,
    STATUS_DEAD_LETTER,
    STATUS_FAILED_PERMANENT,
    STATUS_FAILED_RETRYABLE,
    STATUS_PENDING,
    RETRY_POLICY,
)
from runtime.persistence_backends.filesystem_backend import FilesystemPersistenceBackend


def _make_event(event_id: str = "evt-rp-001") -> dict:
    return {
        "event_id": event_id,
        "source": "operator_ui",
        "event_type": "test.retry",
        "payload": {"key": "value"},
    }


def _enqueue_and_claim(rd: Path, event_id: str = "evt-rp-001", max_attempts: int = 3) -> str:
    r = enqueue_event(_make_event(event_id), runtime_data_dir=rd, max_attempts=max_attempts)
    queue_id = r["queue_id"]
    claim_next_event("w1", rd)
    mark_event_processing(queue_id, rd)
    return queue_id


class TestRetryPolicy(unittest.TestCase):

    def test_retryable_category_produces_failed_retryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd)
            failed = mark_event_failed(queue_id, {"message": "timeout", "category": FAILURE_RUNTIME_EXCEPTION}, rd)
            self.assertEqual(failed["status"], STATUS_FAILED_RETRYABLE)

    def test_transient_tool_failure_is_retryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd)
            failed = mark_event_failed(queue_id, {"message": "tool down", "category": FAILURE_TRANSIENT_TOOL_FAILURE}, rd)
            self.assertEqual(failed["status"], STATUS_FAILED_RETRYABLE)

    def test_llm_transient_failure_is_retryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd)
            failed = mark_event_failed(queue_id, {"message": "llm unavailable", "category": FAILURE_LLM_TRANSIENT_FAILURE}, rd)
            self.assertEqual(failed["status"], STATUS_FAILED_RETRYABLE)

    def test_route_not_found_is_permanent(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd)
            failed = mark_event_failed(queue_id, {"message": "no route", "category": FAILURE_ROUTE_NOT_FOUND}, rd)
            self.assertEqual(failed["status"], STATUS_FAILED_PERMANENT)

    def test_manifest_not_found_is_permanent(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd)
            failed = mark_event_failed(queue_id, {"message": "no manifest", "category": FAILURE_MANIFEST_NOT_FOUND}, rd)
            self.assertEqual(failed["status"], STATUS_FAILED_PERMANENT)

    def test_validation_failed_is_permanent(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd)
            failed = mark_event_failed(queue_id, {"message": "validation error", "category": FAILURE_VALIDATION_FAILED}, rd)
            self.assertEqual(failed["status"], STATUS_FAILED_PERMANENT)

    def test_policy_blocked_is_permanent(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd)
            failed = mark_event_failed(queue_id, {"message": "live blocked", "category": FAILURE_POLICY_BLOCKED}, rd)
            self.assertEqual(failed["status"], STATUS_FAILED_PERMANENT)

    def test_input_mapping_failed_is_permanent(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd)
            failed = mark_event_failed(queue_id, {"message": "map failed", "category": FAILURE_INPUT_MAPPING_FAILED}, rd)
            self.assertEqual(failed["status"], STATUS_FAILED_PERMANENT)

    def test_max_attempts_moves_retryable_to_dead_letter(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd, max_attempts=DEFAULT_MAX_ATTEMPTS)
            # Fail twice (retryable)
            for _ in range(DEFAULT_MAX_ATTEMPTS - 1):
                failed = mark_event_failed(queue_id, {"message": "err", "category": FAILURE_RUNTIME_EXCEPTION}, rd)
                self.assertEqual(failed["status"], STATUS_FAILED_RETRYABLE)
                retry_event(queue_id, rd)
                claim_next_event("w1", rd)
                mark_event_processing(queue_id, rd)
            # Third failure hits max
            final = mark_event_failed(queue_id, {"message": "err", "category": FAILURE_RUNTIME_EXCEPTION}, rd)
            self.assertEqual(final["status"], STATUS_DEAD_LETTER)

    def test_retry_preserves_original_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd)
            mark_event_failed(queue_id, {"message": "err", "category": FAILURE_RUNTIME_EXCEPTION}, rd)
            retry_event(queue_id, rd)
            backend = FilesystemPersistenceBackend(rd)
            record = backend.get_durable_queue_record(queue_id)
            self.assertEqual(record["payload_json"], {"key": "value"})

    def test_attempt_count_increments_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd)
            failed = mark_event_failed(queue_id, {"message": "err", "category": FAILURE_RUNTIME_EXCEPTION}, rd)
            self.assertEqual(failed["attempt_count"], 1)

    def test_retry_policy_constants(self):
        self.assertEqual(RETRY_POLICY["max_attempts"], 3)
        self.assertEqual(RETRY_POLICY["retry_delay_seconds"], 0)
        self.assertIn(FAILURE_RUNTIME_EXCEPTION, RETRY_POLICY["retryable_categories"])
        self.assertIn(FAILURE_TRANSIENT_TOOL_FAILURE, RETRY_POLICY["retryable_categories"])
        self.assertIn(FAILURE_LLM_TRANSIENT_FAILURE, RETRY_POLICY["retryable_categories"])

    def test_dead_letter_cannot_be_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            queue_id = _enqueue_and_claim(rd, max_attempts=1)
            mark_event_failed(queue_id, {"message": "err", "category": FAILURE_RUNTIME_EXCEPTION}, rd)
            retry_result = retry_event(queue_id, rd)
            self.assertFalse(retry_result["ok"])
