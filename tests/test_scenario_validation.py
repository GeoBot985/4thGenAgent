from __future__ import annotations

import unittest

from runtime.scenario_validation import validate_scenario_result


class ScenarioValidationTests(unittest.TestCase):
    def test_validate_scenario_result_passes_happy_path(self):
        scenario = {"expected": {"final_state": "WAITING_FOR_EXECUTE", "pending_action_count": 1, "executed_action_count": 0, "must_have_failure": False, "must_have_approval_pack": True}}
        result = {"state": "WAITING_FOR_EXECUTE", "snapshot": {"outputs": {"order_ref": {}}, "pending_actions": [{}], "executed_actions": [], "llm_calls": [{"action": "extract_order_ref"}, {"action": "classify_customer_message"}, {"action": "draft_customer_status_reply"}, {"action": "compare_reply_to_facts"}]}, "approval_pack": {"ok": True, "pending_action_count": 1, "approval_packs": [{}]}, "failure_summary": {"failure_message": ""}, "report_result": {"ok": True, "markdown_path": "a", "html_path": "b", "evidence_bundle_path": "c"}, "summary": {"output_keys": ["order_ref"]}}
        verdict = validate_scenario_result(scenario, result)
        self.assertEqual(verdict["verdict"], "PASS")

    def test_validate_scenario_result_fails_wrong_final_state(self):
        scenario = {"expected": {"final_state": "WAITING_FOR_EXECUTE"}}
        result = {"state": "FAILED_EXECUTION", "snapshot": {}, "approval_pack": {}, "failure_summary": {}}
        verdict = validate_scenario_result(scenario, result)
        self.assertEqual(verdict["verdict"], "FAIL")

    def test_validate_scenario_result_fails_missing_required_output(self):
        scenario = {"expected": {"required_outputs": ["draft_reply"]}}
        result = {"state": "WAITING_FOR_EXECUTE", "snapshot": {"outputs": {}}, "approval_pack": {}, "failure_summary": {}}
        verdict = validate_scenario_result(scenario, result)
        self.assertEqual(verdict["verdict"], "FAIL")
        self.assertTrue(any("draft_reply" in item["id"] for item in verdict["checks"]))

    def test_validate_scenario_result_checks_dotted_output_values(self):
        scenario = {"expected": {"expected_output_values": {"category.label": "refund", "draft_reply.invented_compensation": True}}}
        result = {"state": "FAILED_EXECUTION", "snapshot": {"outputs": {"category": {"label": "refund"}, "draft_reply": {"invented_compensation": True}}}, "approval_pack": {}, "failure_summary": {}}
        verdict = validate_scenario_result(scenario, result)
        self.assertEqual(verdict["verdict"], "PASS")

    def test_validate_scenario_result_checks_failure_summary(self):
        scenario = {"expected": {"must_have_failure": True}}
        result = {"state": "FAILED_VALIDATION", "snapshot": {}, "approval_pack": {}, "failure_summary": {"failure_message": "blocked"}}
        verdict = validate_scenario_result(scenario, result)
        self.assertEqual(verdict["verdict"], "PASS")

    def test_validate_scenario_result_checks_report_paths(self):
        scenario = {"expected": {"must_have_report": True, "must_have_evidence_bundle": True}}
        result = {"state": "WAITING_FOR_EXECUTE", "snapshot": {}, "approval_pack": {}, "failure_summary": {}, "report_result": {"ok": True, "markdown_path": "a", "html_path": "b", "evidence_bundle_path": "c"}}
        verdict = validate_scenario_result(scenario, result)
        self.assertEqual(verdict["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
