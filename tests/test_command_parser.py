import unittest

from runtime.command_parser import parse_command
from runtime.errors import CommandParseError


class CommandParserTests(unittest.TestCase):
    def test_tool_command_with_args(self):
        parsed = parse_command('[t:g/check -> unread_mail] max_results=5')
        self.assertEqual(parsed.kind, "tool")
        self.assertEqual(parsed.namespace, "g")
        self.assertEqual(parsed.action, "check")
        self.assertEqual(parsed.output_alias, "unread_mail")
        self.assertEqual(parsed.payload, "max_results=5")
        self.assertEqual(parsed.args, {"max_results": "5"})

    def test_calendar_command_with_args(self):
        parsed = parse_command('[t:cal/search -> events] query="squash"; days=14')
        self.assertEqual(parsed.kind, "tool")
        self.assertEqual(parsed.namespace, "cal")
        self.assertEqual(parsed.action, "search")
        self.assertEqual(parsed.output_alias, "events")
        self.assertEqual(parsed.args, {"query": "squash", "days": "14"})

    def test_sheet_command_with_args(self):
        parsed = parse_command('[t:sheet/read -> rows] spreadsheet_id="abc"; range_name="Sheet1!A1:D10"')
        self.assertEqual(parsed.kind, "tool")
        self.assertEqual(parsed.namespace, "sheet")
        self.assertEqual(parsed.action, "read")
        self.assertEqual(parsed.output_alias, "rows")
        self.assertEqual(
            parsed.args,
            {"spreadsheet_id": "abc", "range_name": "Sheet1!A1:D10"},
        )

    def test_whatsapp_command_with_args(self):
        parsed = parse_command('[t:wa/send -> sent] chat="Cornelia"; message="Running late"')
        self.assertEqual(parsed.kind, "tool")
        self.assertEqual(parsed.namespace, "wa")
        self.assertEqual(parsed.action, "send")
        self.assertEqual(parsed.output_alias, "sent")
        self.assertEqual(parsed.args, {"chat": "Cornelia", "message": "Running late"})

    def test_gobook_open_courts_command_with_args(self):
        parsed = parse_command('[t:gb/open_courts -> open_slots] date="2026-05-01"; start="17:00"; end="20:00"; slowmo=100')
        self.assertEqual(parsed.kind, "tool")
        self.assertEqual(parsed.namespace, "gb")
        self.assertEqual(parsed.action, "open_courts")
        self.assertEqual(parsed.output_alias, "open_slots")
        self.assertEqual(
            parsed.args,
            {
                "date": "2026-05-01",
                "start": "17:00",
                "end": "20:00",
                "slowmo": "100",
            },
        )

    def test_pending_command_with_args(self):
        parsed = parse_command('[pending:gb/book -> booking] date="2026-05-01"; time_value="18:00"; court="Court 1"; confirm=false')
        self.assertEqual(parsed.kind, "pending")
        self.assertEqual(parsed.namespace, "gb")
        self.assertEqual(parsed.action, "book")
        self.assertEqual(parsed.output_alias, "booking")
        self.assertEqual(
            parsed.args,
            {
                "date": "2026-05-01",
                "time_value": "18:00",
                "court": "Court 1",
                "confirm": "false",
            },
        )

    def test_llm_helper_command(self):
        parsed = parse_command('[q:draft -> reply] Draft reply using $messages')
        self.assertEqual(parsed.kind, "llm")
        self.assertEqual(parsed.namespace, "q")
        self.assertEqual(parsed.action, "draft")
        self.assertEqual(parsed.output_alias, "reply")
        self.assertEqual(parsed.payload, "Draft reply using $messages")
        self.assertEqual(parsed.args, {})

    def test_llm_summarize_command(self):
        parsed = parse_command('[q:summarize -> summary] text=$inputs.message; max_words=30')
        self.assertEqual(parsed.kind, "llm")
        self.assertEqual(parsed.namespace, "q")
        self.assertEqual(parsed.action, "summarize")
        self.assertEqual(parsed.output_alias, "summary")
        self.assertEqual(parsed.args, {"text": "$inputs.message", "max_words": "30"})

    def test_llm_extract_command(self):
        parsed = parse_command('[q:extract -> extracted] schema="order_ref"; text=$inputs.message')
        self.assertEqual(parsed.kind, "llm")
        self.assertEqual(parsed.namespace, "q")
        self.assertEqual(parsed.action, "extract")
        self.assertEqual(parsed.output_alias, "extracted")
        self.assertEqual(parsed.args, {"schema": "order_ref", "text": "$inputs.message"})

    def test_llm_classify_command(self):
        parsed = parse_command('[q:classify -> category] labels="order_status,refund,other"; text=$inputs.message')
        self.assertEqual(parsed.kind, "llm")
        self.assertEqual(parsed.namespace, "q")
        self.assertEqual(parsed.action, "classify")
        self.assertEqual(parsed.output_alias, "category")

    def test_llm_compare_command(self):
        parsed = parse_command('[q:compare -> comparison] left=$inputs.a; right=$inputs.b; criteria="same meaning"')
        self.assertEqual(parsed.kind, "llm")
        self.assertEqual(parsed.namespace, "q")
        self.assertEqual(parsed.action, "compare")
        self.assertEqual(parsed.output_alias, "comparison")

    def test_invalid_llm_command_missing_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[q:extract] text="x"')

    def test_invalid_llm_command_missing_action(self):
        with self.assertRaises(CommandParseError):
            parse_command('[q -> output] payload')

    def test_invalid_llm_command_empty_action(self):
        with self.assertRaises(CommandParseError):
            parse_command('[q:/extract -> output] text="x"')

    def test_invalid_llm_command_execute_not_allowed(self):
        with self.assertRaises(CommandParseError):
            parse_command('[q:execute -> result] payload')

    def test_invalid_llm_command_approve_not_allowed(self):
        with self.assertRaises(CommandParseError):
            parse_command('[q:approve -> result] payload')

    def test_validation_command(self):
        parsed = parse_command('[validate:reply_safe_to_send]')
        self.assertEqual(parsed.kind, "validate")
        self.assertIsNone(parsed.namespace)
        self.assertEqual(parsed.action, "reply_safe_to_send")
        self.assertIsNone(parsed.output_alias)
        self.assertEqual(parsed.payload, "")
        self.assertEqual(parsed.args, {})

    def test_invalid_validation_missing_rule(self):
        with self.assertRaises(CommandParseError):
            parse_command('[validate]')

    def test_invalid_validation_empty_rule(self):
        with self.assertRaises(CommandParseError):
            parse_command('[validate:]')

    def test_invalid_validation_empty_rule_with_space(self):
        with self.assertRaises(CommandParseError):
            parse_command('[validate: ]')

    def test_invalid_validation_with_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[validate:some_rule -> output]')

    def test_invalid_validation_with_payload(self):
        with self.assertRaises(CommandParseError):
            parse_command('[validate:some_rule] payload')

    def test_memory_get_command(self):
        parsed = parse_command('[m:get -> supplier_pref] key="supplier.ABC.preferred_channel"')
        self.assertEqual(parsed.kind, "memory")
        self.assertEqual(parsed.namespace, "m")
        self.assertEqual(parsed.action, "get")
        self.assertEqual(parsed.output_alias, "supplier_pref")
        self.assertEqual(parsed.args, {"key": "supplier.ABC.preferred_channel"})

    def test_memory_set_command(self):
        parsed = parse_command('[m:set -> saved_fact] key="supplier.ABC.lead_time_days"; value="5"')
        self.assertEqual(parsed.kind, "memory")
        self.assertEqual(parsed.namespace, "m")
        self.assertEqual(parsed.action, "set")
        self.assertEqual(parsed.output_alias, "saved_fact")
        self.assertEqual(parsed.args, {"key": "supplier.ABC.lead_time_days", "value": "5"})

    def test_memory_list_command(self):
        parsed = parse_command('[m:list -> supplier_facts] prefix="supplier.ABC."')
        self.assertEqual(parsed.kind, "memory")
        self.assertEqual(parsed.namespace, "m")
        self.assertEqual(parsed.action, "list")
        self.assertEqual(parsed.output_alias, "supplier_facts")
        self.assertEqual(parsed.args, {"prefix": "supplier.ABC."})

    def test_inspection_list_runs_command(self):
        parsed = parse_command('[i:list_runs -> runs] limit=10')
        self.assertEqual(parsed.kind, "inspection")
        self.assertEqual(parsed.namespace, "i")
        self.assertEqual(parsed.action, "list_runs")
        self.assertEqual(parsed.output_alias, "runs")
        self.assertEqual(parsed.args, {"limit": "10"})

    def test_inspection_summary_command(self):
        parsed = parse_command('[i:summary -> summary] frame_id=$inputs.frame_id')
        self.assertEqual(parsed.kind, "inspection")
        self.assertEqual(parsed.action, "summary")
        self.assertEqual(parsed.output_alias, "summary")

    def test_inspection_outputs_command(self):
        parsed = parse_command('[i:outputs -> outputs] frame_id=$inputs.frame_id')
        self.assertEqual(parsed.kind, "inspection")
        self.assertEqual(parsed.action, "outputs")
        self.assertEqual(parsed.output_alias, "outputs")

    def test_inspection_audit_command(self):
        parsed = parse_command('[i:audit -> audit] frame_id=$inputs.frame_id; limit=20')
        self.assertEqual(parsed.kind, "inspection")
        self.assertEqual(parsed.action, "audit")
        self.assertEqual(parsed.output_alias, "audit")
        self.assertEqual(parsed.args, {"frame_id": "$inputs.frame_id", "limit": "20"})

    def test_inspection_validations_command(self):
        parsed = parse_command('[i:validations -> failed_validations] frame_id=$inputs.frame_id; failed_only=true')
        self.assertEqual(parsed.kind, "inspection")
        self.assertEqual(parsed.action, "validations")
        self.assertEqual(parsed.output_alias, "failed_validations")
        self.assertEqual(parsed.args, {"frame_id": "$inputs.frame_id", "failed_only": "true"})

    def test_invalid_command_missing_opening_bracket(self):
        with self.assertRaises(CommandParseError):
            parse_command('t:g/check -> unread_mail] max_results=5')

    def test_invalid_command_missing_arrow(self):
        with self.assertRaises(CommandParseError):
            parse_command('[t:g/check unread_mail] max_results=5')

    def test_invalid_command_missing_namespace(self):
        with self.assertRaises(CommandParseError):
            parse_command('[t:/check -> unread_mail]')

    def test_invalid_empty_command(self):
        with self.assertRaises(CommandParseError):
            parse_command('[]')

    def test_invalid_unknown_kind(self):
        with self.assertRaises(CommandParseError):
            parse_command('[unknown]')

    def test_invalid_memory_get_without_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[m:get] key="x"')

    def test_invalid_memory_set_without_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[m:set ->] key="x"; value="y"')

    def test_invalid_memory_action_with_empty_namespace(self):
        with self.assertRaises(CommandParseError):
            parse_command('[m:/get -> x]')

    def test_invalid_inspection_missing_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[i:summary]')

    def test_invalid_inspection_empty_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[i:summary ->]')

    def test_invalid_inspection_missing_action(self):
        with self.assertRaises(CommandParseError):
            parse_command('[i]')

    def test_invalid_inspection_malformed_namespace(self):
        with self.assertRaises(CommandParseError):
            parse_command('[i:/summary -> x]')

    def test_invalid_inspection_blocked_delete(self):
        with self.assertRaises(CommandParseError):
            parse_command('[i:delete -> x] frame_id="tf_abc"')

    def test_invalid_inspection_blocked_resume(self):
        with self.assertRaises(CommandParseError):
            parse_command('[i:resume -> x] frame_id="tf_abc"')

    def test_invalid_inspection_blocked_approve(self):
        with self.assertRaises(CommandParseError):
            parse_command('[i:approve -> x] frame_id="tf_abc"')

    def test_cleanup_plan_command(self):
        parsed = parse_command('[c:plan -> cleanup_plan] mode="derived_artifacts_only"; max_report_age_days=30')
        self.assertEqual(parsed.kind, "cleanup")
        self.assertEqual(parsed.namespace, "c")
        self.assertEqual(parsed.action, "plan")
        self.assertEqual(parsed.output_alias, "cleanup_plan")
        self.assertEqual(parsed.args, {"mode": "derived_artifacts_only", "max_report_age_days": "30"})

    def test_cleanup_execute_command(self):
        parsed = parse_command('[c:execute -> cleanup_result] mode="reports_only"; dry_run=false; confirm_cleanup=true')
        self.assertEqual(parsed.kind, "cleanup")
        self.assertEqual(parsed.namespace, "c")
        self.assertEqual(parsed.action, "execute")
        self.assertEqual(parsed.output_alias, "cleanup_result")

    def test_cleanup_reports_plan_command(self):
        parsed = parse_command('[c:reports_plan -> report_cleanup] max_report_age_days=0')
        self.assertEqual(parsed.kind, "cleanup")
        self.assertEqual(parsed.action, "reports_plan")
        self.assertEqual(parsed.output_alias, "report_cleanup")

    def test_cleanup_index_plan_command(self):
        parsed = parse_command('[c:index_plan -> index_cleanup]')
        self.assertEqual(parsed.kind, "cleanup")
        self.assertEqual(parsed.action, "index_plan")
        self.assertEqual(parsed.output_alias, "index_cleanup")

    def test_cleanup_temp_plan_command(self):
        parsed = parse_command('[c:temp_plan -> temp_cleanup] max_temp_age_days=0')
        self.assertEqual(parsed.kind, "cleanup")
        self.assertEqual(parsed.action, "temp_plan")
        self.assertEqual(parsed.output_alias, "temp_cleanup")

    def test_maintenance_index_rebuild_command(self):
        parsed = parse_command('[mt:index_rebuild -> index_result]')
        self.assertEqual(parsed.kind, "maintenance")
        self.assertEqual(parsed.namespace, "mt")
        self.assertEqual(parsed.action, "index_rebuild")
        self.assertEqual(parsed.output_alias, "index_result")

    def test_maintenance_cleanup_dry_run_command(self):
        parsed = parse_command('[mt:cleanup_dry_run -> cleanup_plan] mode="derived_artifacts_only"')
        self.assertEqual(parsed.kind, "maintenance")
        self.assertEqual(parsed.action, "cleanup_dry_run")
        self.assertEqual(parsed.output_alias, "cleanup_plan")

    def test_maintenance_report_failed_runs_command(self):
        parsed = parse_command('[mt:report_failed_runs -> report_result] limit=20; rebuild=true')
        self.assertEqual(parsed.kind, "maintenance")
        self.assertEqual(parsed.action, "report_failed_runs")
        self.assertEqual(parsed.output_alias, "report_result")

    def test_maintenance_report_pending_runs_command(self):
        parsed = parse_command('[mt:report_pending_runs -> report_result] limit=20; rebuild=true')
        self.assertEqual(parsed.kind, "maintenance")
        self.assertEqual(parsed.action, "report_pending_runs")
        self.assertEqual(parsed.output_alias, "report_result")

    def test_maintenance_report_live_packs_command(self):
        parsed = parse_command('[mt:report_live_packs -> report_result] limit=20; rebuild=true')
        self.assertEqual(parsed.kind, "maintenance")
        self.assertEqual(parsed.action, "report_live_packs")
        self.assertEqual(parsed.output_alias, "report_result")

    def test_maintenance_summary_command(self):
        parsed = parse_command('[mt:summary -> maintenance_summary] rebuild=true')
        self.assertEqual(parsed.kind, "maintenance")
        self.assertEqual(parsed.action, "summary")
        self.assertEqual(parsed.output_alias, "maintenance_summary")

    def test_invalid_cleanup_missing_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[c:plan]')

    def test_invalid_cleanup_empty_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[c:plan ->]')

    def test_invalid_cleanup_missing_action(self):
        with self.assertRaises(CommandParseError):
            parse_command('[c]')

    def test_invalid_cleanup_malformed_namespace(self):
        with self.assertRaises(CommandParseError):
            parse_command('[c:/plan -> x]')

    def test_invalid_cleanup_blocked_delete_all(self):
        with self.assertRaises(CommandParseError):
            parse_command('[c:delete_all -> x]')

    def test_invalid_cleanup_blocked_delete_runs(self):
        with self.assertRaises(CommandParseError):
            parse_command('[c:delete_runs -> x]')

    def test_invalid_cleanup_blocked_purge(self):
        with self.assertRaises(CommandParseError):
            parse_command('[c:purge -> x]')

    def test_invalid_cleanup_blocked_wipe(self):
        with self.assertRaises(CommandParseError):
            parse_command('[c:wipe -> x]')

    def test_invalid_cleanup_blocked_force(self):
        with self.assertRaises(CommandParseError):
            parse_command('[c:force -> x]')

    def test_invalid_maintenance_missing_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[mt:index_rebuild]')

    def test_invalid_maintenance_empty_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[mt:index_rebuild ->]')

    def test_invalid_maintenance_missing_action(self):
        with self.assertRaises(CommandParseError):
            parse_command('[mt]')

    def test_invalid_maintenance_malformed_namespace(self):
        with self.assertRaises(CommandParseError):
            parse_command('[mt:/index_rebuild -> x]')

    def test_invalid_maintenance_blocked_delete(self):
        with self.assertRaises(CommandParseError):
            parse_command('[mt:delete -> x]')

    def test_invalid_maintenance_blocked_execute(self):
        with self.assertRaises(CommandParseError):
            parse_command('[mt:execute -> x]')

    def test_invalid_maintenance_blocked_approve(self):
        with self.assertRaises(CommandParseError):
            parse_command('[mt:approve -> x]')

    def test_invalid_maintenance_blocked_live(self):
        with self.assertRaises(CommandParseError):
            parse_command('[mt:live -> x]')

    def test_approval_list_pending_command(self):
        parsed = parse_command('[a:list_pending -> pending] frame_id=$inputs.frame_id')
        self.assertEqual(parsed.kind, "approval")
        self.assertEqual(parsed.namespace, "a")
        self.assertEqual(parsed.action, "list_pending")
        self.assertEqual(parsed.output_alias, "pending")

    def test_approval_approve_command(self):
        parsed = parse_command('[a:approve -> approval_result] frame_id=$inputs.frame_id; action_id=$inputs.action_id; approved_by="test"; reason="ok"')
        self.assertEqual(parsed.kind, "approval")
        self.assertEqual(parsed.namespace, "a")
        self.assertEqual(parsed.action, "approve")
        self.assertEqual(parsed.output_alias, "approval_result")

    def test_approval_reject_command(self):
        parsed = parse_command('[a:reject -> rejection_result] frame_id=$inputs.frame_id; action_id=$inputs.action_id; rejected_by="test"; reason="bad"')
        self.assertEqual(parsed.kind, "approval")
        self.assertEqual(parsed.action, "reject")
        self.assertEqual(parsed.output_alias, "rejection_result")

    def test_approval_execute_approved_command(self):
        parsed = parse_command('[a:execute_approved -> execution_result] frame_id=$inputs.frame_id')
        self.assertEqual(parsed.kind, "approval")
        self.assertEqual(parsed.action, "execute_approved")
        self.assertEqual(parsed.output_alias, "execution_result")

    def test_approval_approve_and_execute_command(self):
        parsed = parse_command('[a:approve_and_execute -> result] frame_id=$inputs.frame_id; action_id=$inputs.action_id; approved_by="test"')
        self.assertEqual(parsed.kind, "approval")
        self.assertEqual(parsed.action, "approve_and_execute")
        self.assertEqual(parsed.output_alias, "result")

    def test_approval_execute_live_approved_command(self):
        parsed = parse_command('[a:execute_live_approved -> result] frame_id=$inputs.frame_id; confirm_live=true')
        self.assertEqual(parsed.kind, "approval")
        self.assertEqual(parsed.action, "execute_live_approved")
        self.assertEqual(parsed.output_alias, "result")
        self.assertEqual(parsed.args, {"frame_id": "$inputs.frame_id", "confirm_live": "true"})

    def test_invalid_approval_missing_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[a:approve]')

    def test_invalid_approval_empty_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[a:approve ->]')

    def test_invalid_approval_missing_action(self):
        with self.assertRaises(CommandParseError):
            parse_command('[a]')

    def test_invalid_approval_malformed_namespace(self):
        with self.assertRaises(CommandParseError):
            parse_command('[a:/approve -> result]')

    def test_invalid_approval_blocked_delete(self):
        with self.assertRaises(CommandParseError):
            parse_command('[a:delete -> result] frame_id="tf_abc"')

    def test_invalid_approval_blocked_resume(self):
        with self.assertRaises(CommandParseError):
            parse_command('[a:resume -> result] frame_id="tf_abc"')

    def test_invalid_approval_blocked_approve_all(self):
        with self.assertRaises(CommandParseError):
            parse_command('[a:approve_all -> result] frame_id="tf_abc"')

    def test_invalid_approval_blocked_live_execute(self):
        with self.assertRaises(CommandParseError):
            parse_command('[a:live_execute -> result] frame_id="tf_abc"')

    def test_invalid_approval_blocked_force_execute(self):
        with self.assertRaises(CommandParseError):
            parse_command('[a:force_execute -> result] frame_id="tf_abc"')


if __name__ == "__main__":
    unittest.main()
