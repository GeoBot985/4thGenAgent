"""Spec 138 — Test: release verifier check for scheduler_runtime."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestSchedulerReleaseVerifier(unittest.TestCase):

    def test_check_scheduler_runtime_importable(self):
        from tools.run_release_candidate_verification import _check_scheduler_runtime
        self.assertTrue(callable(_check_scheduler_runtime))

    def test_check_scheduler_runtime_passes(self):
        from tools.run_release_candidate_verification import _check_scheduler_runtime
        result = _check_scheduler_runtime()
        self.assertEqual(result.get("name"), "scheduler_runtime")
        self.assertEqual(result.get("status"), "PASS", f"Failures: {result.get('missing')}")

    def test_check_returns_dict_with_required_keys(self):
        from tools.run_release_candidate_verification import _check_scheduler_runtime
        result = _check_scheduler_runtime()
        self.assertIn("name", result)
        self.assertIn("status", result)
        self.assertIn("missing", result)
