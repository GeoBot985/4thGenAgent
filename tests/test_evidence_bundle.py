from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.evidence_bundle import build_evidence_bundle, write_evidence_bundle
from src.operator_demo_runner import run_demo_manifest


class EvidenceBundleTests(unittest.TestCase):
    def test_build_evidence_bundle_contains_core_taskframe_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo_manifest("customer_status_llm_e2e", runtime_data_dir=tmp)
            bundle = build_evidence_bundle(result["frame_id"], tmp)
            for key in ("frame_id", "manifest_id", "state", "trigger", "inputs", "steps", "outputs", "validations", "pending_actions", "tool_calls", "llm_calls"):
                self.assertIn(key, bundle)

    def test_write_evidence_bundle_creates_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo_manifest("customer_status_llm_e2e", runtime_data_dir=tmp)
            written = write_evidence_bundle(result["frame_id"], tmp)
            self.assertTrue(written["ok"])
            path = Path(written["bundle_path"])
            self.assertTrue(path.is_file())
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_evidence_bundle_contains_failure_summary_for_failed_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo_manifest("customer_status_wrong_customer_order", runtime_data_dir=tmp)
            bundle = build_evidence_bundle(result["frame_id"], tmp)
            self.assertTrue(str(bundle["state"]).startswith("FAILED"))
            self.assertNotEqual(bundle["failure_summary"]["failure_message"], "")

    def test_evidence_bundle_contains_approval_pack_for_staged_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo_manifest("customer_status_llm_e2e", runtime_data_dir=tmp)
            bundle = build_evidence_bundle(result["frame_id"], tmp)
            self.assertEqual(len(bundle["pending_actions"]), 1)
            self.assertEqual(bundle["approval_pack"]["pending_action_count"], 1)
            self.assertTrue(bundle["approval_pack"]["approval_packs"])

    def test_evidence_bundle_missing_frame_returns_error_or_raises_clear_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception):
                build_evidence_bundle("missing", tmp)


if __name__ == "__main__":
    unittest.main()
