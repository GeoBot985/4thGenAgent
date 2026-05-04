import unittest

from runtime.errors import CleanupConfirmationError, CleanupPolicyError, RetentionPolicyError
from runtime.retention_policy import (
    DEFAULT_RETENTION_POLICY,
    cleanup_mode_allows,
    is_destructive_cleanup,
    normalize_retention_policy,
    validate_retention_policy,
)


class RetentionPolicyTests(unittest.TestCase):
    def test_normalize_retention_policy_returns_defaults(self):
        self.assertEqual(normalize_retention_policy(None), DEFAULT_RETENTION_POLICY)

    def test_normalize_retention_policy_merges_overrides(self):
        policy = normalize_retention_policy({"mode": "reports_only", "max_report_age_days": 10})
        self.assertEqual(policy["mode"], "reports_only")
        self.assertEqual(policy["max_report_age_days"], 10)
        self.assertTrue(policy["delete_reports"])
        self.assertTrue(policy["dry_run"])

    def test_validate_retention_policy_accepts_default_policy(self):
        validate_retention_policy(DEFAULT_RETENTION_POLICY)

    def test_validate_retention_policy_rejects_non_dict(self):
        with self.assertRaises(RetentionPolicyError):
            validate_retention_policy([])  # type: ignore[arg-type]

    def test_validate_retention_policy_rejects_unsupported_mode(self):
        policy = normalize_retention_policy({"mode": "unknown"})
        with self.assertRaises(CleanupPolicyError):
            validate_retention_policy(policy)

    def test_validate_retention_policy_rejects_delete_run_dirs_true(self):
        policy = normalize_retention_policy({"delete_run_dirs": True})
        with self.assertRaises(CleanupPolicyError):
            validate_retention_policy(policy)

    def test_validate_retention_policy_rejects_dry_run_false_without_confirmation(self):
        policy = normalize_retention_policy({"dry_run": False, "confirm_cleanup": False})
        with self.assertRaises(CleanupConfirmationError):
            validate_retention_policy(policy)

    def test_validate_retention_policy_rejects_non_bool_delete_flags(self):
        policy = normalize_retention_policy({"delete_reports": "true"})
        with self.assertRaises(RetentionPolicyError):
            validate_retention_policy(policy)

    def test_validate_retention_policy_rejects_negative_age_fields(self):
        policy = normalize_retention_policy({"max_report_age_days": -1})
        with self.assertRaises(RetentionPolicyError):
            validate_retention_policy(policy)

    def test_validate_retention_policy_rejects_non_list_protect_states(self):
        policy = normalize_retention_policy({"protect_states": "WAITING_FOR_EXECUTE"})
        with self.assertRaises(RetentionPolicyError):
            validate_retention_policy(policy)

    def test_is_destructive_cleanup_false_for_dry_run(self):
        policy = normalize_retention_policy({"dry_run": True})
        self.assertFalse(is_destructive_cleanup(policy))

    def test_is_destructive_cleanup_true_for_non_dry_run(self):
        policy = normalize_retention_policy({"dry_run": False, "confirm_cleanup": True})
        self.assertTrue(is_destructive_cleanup(policy))

    def test_cleanup_mode_allows_reports_only_report_true(self):
        policy = normalize_retention_policy({"mode": "reports_only"})
        self.assertTrue(cleanup_mode_allows(policy, "report"))

    def test_cleanup_mode_allows_reports_only_temp_false(self):
        policy = normalize_retention_policy({"mode": "reports_only"})
        self.assertFalse(cleanup_mode_allows(policy, "temp_file"))

    def test_cleanup_mode_allows_indexes_only_artifact_index_true(self):
        policy = normalize_retention_policy({"mode": "indexes_only"})
        self.assertTrue(cleanup_mode_allows(policy, "artifact_index"))

    def test_cleanup_mode_allows_derived_artifacts_only_report_true(self):
        policy = normalize_retention_policy({"mode": "derived_artifacts_only"})
        self.assertTrue(cleanup_mode_allows(policy, "report"))

    def test_cleanup_mode_allows_derived_artifacts_only_run_dir_false(self):
        policy = normalize_retention_policy({"mode": "derived_artifacts_only"})
        self.assertFalse(cleanup_mode_allows(policy, "run_dir"))


if __name__ == "__main__":
    unittest.main()
