"""Spec 137 — Test: durable queue CLI commands (taskframe queue *)."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from src.taskframe_cli import main


class TestQueueStatusCLI(unittest.TestCase):

    def test_queue_status_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "status", "--runtime-data-dir", tmp])
            self.assertEqual(code, 0)

    def test_queue_status_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                code = main(["queue", "status", "--runtime-data-dir", tmp, "--json"])
            finally:
                sys.stdout = old
            self.assertEqual(code, 0)
            parsed = json.loads(buf.getvalue().strip())
            self.assertIn("ok", parsed)
            self.assertIn("backend", parsed)
            self.assertIn("counts_by_status", parsed)

    def test_queue_status_shows_pending_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            main(["queue", "enqueue-fixture", "customer_status", "--runtime-data-dir", tmp])
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                main(["queue", "status", "--runtime-data-dir", tmp, "--json"])
            finally:
                sys.stdout = old
            parsed = json.loads(buf.getvalue().strip())
            self.assertGreaterEqual(parsed.get("pending_count", 0), 1)


class TestQueueListCLI(unittest.TestCase):

    def test_queue_list_empty_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "list", "--runtime-data-dir", tmp])
            self.assertEqual(code, 0)

    def test_queue_list_json_has_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                code = main(["queue", "list", "--runtime-data-dir", tmp, "--json"])
            finally:
                sys.stdout = old
            self.assertEqual(code, 0)
            parsed = json.loads(buf.getvalue().strip())
            self.assertIn("records", parsed)
            self.assertIsInstance(parsed["records"], list)

    def test_queue_list_status_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "list", "--status", "PENDING", "--limit", "5", "--runtime-data-dir", tmp])
            self.assertEqual(code, 0)


class TestQueueEnqueueFixtureCLI(unittest.TestCase):

    def test_enqueue_customer_status_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "enqueue-fixture", "customer_status", "--runtime-data-dir", tmp])
            self.assertEqual(code, 0)

    def test_enqueue_order_status_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "enqueue-fixture", "order_status", "--runtime-data-dir", tmp])
            self.assertEqual(code, 0)

    def test_enqueue_system_health_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "enqueue-fixture", "system_health", "--runtime-data-dir", tmp])
            self.assertEqual(code, 0)

    def test_enqueue_fixture_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                main(["queue", "enqueue-fixture", "customer_status", "--runtime-data-dir", tmp, "--json"])
            finally:
                sys.stdout = old
            parsed = json.loads(buf.getvalue().strip())
            self.assertIn("ok", parsed)

    def test_enqueue_unknown_fixture_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "enqueue-fixture", "no_such_fixture", "--runtime-data-dir", tmp])
            self.assertEqual(code, 1)

    def test_enqueue_adds_to_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            main(["queue", "enqueue-fixture", "customer_status", "--runtime-data-dir", tmp])
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                main(["queue", "list", "--runtime-data-dir", tmp, "--json"])
            finally:
                sys.stdout = old
            parsed = json.loads(buf.getvalue().strip())
            self.assertGreaterEqual(len(parsed.get("records", [])), 1)


class TestQueueProcessNextCLI(unittest.TestCase):

    def test_process_next_empty_queue_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "process-next", "--runtime-data-dir", tmp])
            self.assertEqual(code, 0)

    def test_process_next_with_fixture_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            main(["queue", "enqueue-fixture", "customer_status", "--runtime-data-dir", tmp])
            code = main(["queue", "process-next", "--runtime-data-dir", tmp])
            self.assertIn(code, (0, 1))


class TestQueueDeadLetterCLI(unittest.TestCase):

    def test_dead_letter_empty_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "dead-letter", "--runtime-data-dir", tmp])
            self.assertEqual(code, 0)

    def test_dead_letter_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                main(["queue", "dead-letter", "--runtime-data-dir", tmp, "--json"])
            finally:
                sys.stdout = old
            parsed = json.loads(buf.getvalue().strip())
            self.assertIn("records", parsed)


class TestQueueRecoverStaleCLI(unittest.TestCase):

    def test_recover_stale_empty_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "recover-stale", "--runtime-data-dir", tmp])
            self.assertEqual(code, 0)

    def test_recover_stale_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                main(["queue", "recover-stale", "--runtime-data-dir", tmp, "--json"])
            finally:
                sys.stdout = old
            parsed = json.loads(buf.getvalue().strip())
            self.assertIn("ok", parsed)
            self.assertIn("recovered_count", parsed)


class TestQueueProcessBatchCLI(unittest.TestCase):

    def test_process_batch_empty_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "process-batch", "--limit", "5", "--runtime-data-dir", tmp])
            self.assertEqual(code, 0)

    def test_process_batch_with_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            main(["queue", "enqueue-fixture", "customer_status", "--runtime-data-dir", tmp])
            code = main(["queue", "process-batch", "--limit", "3", "--runtime-data-dir", tmp])
            self.assertEqual(code, 0)


class TestQueueRetryCancelCLI(unittest.TestCase):

    def test_retry_nonexistent_queue_id_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "retry", "nonexistent-id", "--runtime-data-dir", tmp])
            self.assertEqual(code, 1)

    def test_cancel_nonexistent_queue_id_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["queue", "cancel", "nonexistent-id", "--runtime-data-dir", tmp])
            self.assertEqual(code, 1)
