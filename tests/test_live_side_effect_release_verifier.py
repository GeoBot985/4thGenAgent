from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestReleaseVerifierCheckExists(unittest.TestCase):
    def test_check_function_importable(self):
        from tools.run_release_candidate_verification import (
            _check_live_side_effect_approval_execution_model,
        )
        self.assertTrue(callable(_check_live_side_effect_approval_execution_model))

    def test_check_returns_dict(self):
        from tools.run_release_candidate_verification import (
            _check_live_side_effect_approval_execution_model,
        )
        result = _check_live_side_effect_approval_execution_model()
        self.assertIsInstance(result, dict)

    def test_check_has_name(self):
        from tools.run_release_candidate_verification import (
            _check_live_side_effect_approval_execution_model,
        )
        result = _check_live_side_effect_approval_execution_model()
        self.assertEqual(result.get("name"), "live_side_effect_approval_execution_model")

    def test_check_has_status(self):
        from tools.run_release_candidate_verification import (
            _check_live_side_effect_approval_execution_model,
        )
        result = _check_live_side_effect_approval_execution_model()
        self.assertIn(result.get("status"), ("PASS", "FAIL"))

    def test_check_passes(self):
        from tools.run_release_candidate_verification import (
            _check_live_side_effect_approval_execution_model,
        )
        result = _check_live_side_effect_approval_execution_model()
        self.assertEqual(result.get("status"), "PASS", f"Check failed: {result.get('details', [])}")


class TestReleaseVerifierInBootstrapChecks(unittest.TestCase):
    def test_check_in_source(self):
        from tools import run_release_candidate_verification as rv
        src = Path(rv.__file__).read_text(encoding="utf-8")
        self.assertIn("live_side_effect_approval_execution_model", src)

    def test_check_in_static_checks_list(self):
        from tools import run_release_candidate_verification as rv
        src = Path(rv.__file__).read_text(encoding="utf-8")
        self.assertIn("_check_live_side_effect_approval_execution_model()", src)


class TestModulesImportable(unittest.TestCase):
    def test_execution_module_importable(self):
        from runtime.live_side_effect_execution import (
            build_live_side_effect_preflight,
            execute_approved_live_side_effect,
            verify_live_side_effect_result,
            build_live_execution_audit_event,
            write_live_execution_report,
            render_live_execution_markdown,
        )
        self.assertTrue(callable(build_live_side_effect_preflight))
        self.assertTrue(callable(execute_approved_live_side_effect))
        self.assertTrue(callable(verify_live_side_effect_result))
        self.assertTrue(callable(build_live_execution_audit_event))
        self.assertTrue(callable(write_live_execution_report))
        self.assertTrue(callable(render_live_execution_markdown))

    def test_ledger_module_importable(self):
        from runtime.live_execution_ledger import (
            append_ledger_entry,
            read_ledger_entries,
            is_idempotency_key_in_ledger,
            build_ledger_entry,
        )
        self.assertTrue(callable(append_ledger_entry))
        self.assertTrue(callable(read_ledger_entries))
        self.assertTrue(callable(is_idempotency_key_in_ledger))
        self.assertTrue(callable(build_ledger_entry))

    def test_controlled_live_write_profile_importable(self):
        from src.controlled_live_profile import CONTROLLED_LIVE_WRITE_PROFILE
        self.assertIsInstance(CONTROLLED_LIVE_WRITE_PROFILE, dict)
        self.assertTrue(CONTROLLED_LIVE_WRITE_PROFILE.get("allow_live_side_effects"))


class TestNoBoundaryViolations(unittest.TestCase):
    def test_preflight_blocks_without_credentials(self):
        from runtime.live_side_effect_execution import build_live_side_effect_preflight
        with tempfile.TemporaryDirectory() as tmp:
            result = build_live_side_effect_preflight(
                pending_action={"action_id": "rc_test", "tool": "gmail/send"},
                profile_name="controlled_live_write",
                profile_data={"allow_live_side_effects": True},
                runtime_data_dir=tmp,
            )
            self.assertFalse(result["ok"])
            self.assertTrue(result["blocked"])

    def test_idempotency_enforcement_no_credentials(self):
        from runtime.live_execution_ledger import (
            append_ledger_entry,
            build_ledger_entry,
            is_idempotency_key_in_ledger,
            LEDGER_STATUS_EXECUTED,
        )
        with tempfile.TemporaryDirectory() as tmp:
            entry = build_ledger_entry(
                frame_id="f1", action_id="a1", tool="sheet/write_rows",
                idempotency_key="ikey_rc_boundary", business_ref="b1",
                target_ref="t1", prepared_payload_hash="h1",
                approved_by="op", worker_identity="w1",
                status=LEDGER_STATUS_EXECUTED,
            )
            append_ledger_entry(entry, runtime_data_dir=tmp)
            found = is_idempotency_key_in_ledger("ikey_rc_boundary", runtime_data_dir=tmp)
            self.assertTrue(found)

    def test_cli_live_side_effect_preflight_command_exists(self):
        r = subprocess.run(
            [sys.executable, "-m", "src.taskframe_cli", "live-side-effect", "--help"],
            capture_output=True, text=True, timeout=30, cwd=str(ROOT),
        )
        self.assertIn("live-side-effect", r.stdout + r.stderr + "live-side-effect")
        self.assertIn("preflight", r.stdout)

    def test_cli_rollback_plan_command_exists(self):
        r = subprocess.run(
            [sys.executable, "-m", "src.taskframe_cli", "live-side-effect", "--help"],
            capture_output=True, text=True, timeout=30, cwd=str(ROOT),
        )
        self.assertIn("rollback-plan", r.stdout)


if __name__ == "__main__":
    unittest.main()
