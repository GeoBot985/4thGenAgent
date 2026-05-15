# Manifest Health Report

Generated: 2026-05-15T19:12:54.061300Z

Verdict: HEALTHY

## Summary

| Metric | Count |
|---|---:|
| Total manifests | 56 |
| Healthy | 0 |
| Warnings | 0 |
| Failed | 0 |
| Repairable | 12 |
| Manual fix required | 0 |
| Critical | 0 |

## Manifest Results

| Health | Manifest | Validation | Smoke | Repairable | Top Findings | Next Action |
|---|---|---|---|---:|---|---|
| SMOKE_SKIPPED | customer.status_llm_e2e | PASS | SKIPPED | 3 | input_declared_but_not_used, input_declared_but_not_used, input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | event.stub | PASS | SKIPPED | 0 | event_trigger_without_route_note | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | live.calendar_next | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | live.gmail_check | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | live.gobook_open_courts | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | llm.classify_customer_message | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | llm.customer_status_reply | PASS | SKIPPED | 2 | input_declared_but_not_used, input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | llm.extract_order_ref | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | maintenance.scheduled | PASS | SKIPPED | 0 | event_trigger_without_route_note | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | maintenance.cleanup_dry_run | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | maintenance.artifact_index_rebuild | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | maintenance.report_failed_runs | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | maintenance.report_live_packs | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | maintenance.report_pending_runs | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.approve_pending_action | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.channel_branch_reply | PASS | SKIPPED | 1 | input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | smoke.cleanup_blocked_without_confirmation | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.cleanup_dry_run | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.cleanup_execute_confirmed | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.cleanup_reports_dry_run | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.condition_all | PASS | SKIPPED | 2 | input_declared_but_not_used, input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | smoke.condition_any | PASS | SKIPPED | 2 | input_declared_but_not_used, input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | smoke.condition_date_window | PASS | SKIPPED | 1 | input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | smoke.condition_equals | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.condition_not | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.condition_numeric_comparison | PASS | SKIPPED | 1 | input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | smoke.condition_skip | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.condition_time_window | PASS | SKIPPED | 1 | input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | smoke.execute_approved_pending_actions | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.gmail_check | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.gobook_open_courts | PASS | SKIPPED | 3 | input_declared_but_not_used, input_declared_but_not_used, input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | smoke.gobook_preferred_window | PASS | SKIPPED | 1 | input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | smoke.gobook_stage_booking | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.inspect_recent_runs | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.inspect_run_outputs | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.inspect_run_pending_actions | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.inspect_run_summary | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.llm_branch_escalation | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.llm_classify_conditional_reply | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.llm_classify_with_validation_step | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.memory_set | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.reject_pending_action | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.reload_pending_action_flow | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.retry_llm_success_after_failure | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.retry_no_retry_on_validation | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.retry_tool_exhausted | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.retry_tool_success_after_failure | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.timeout_exceeded | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.timeout_retry_success | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.timeout_success | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.validate_step_output_exists | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | smoke.whatsapp_stage_send | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | accounting.payment_reconciliation | PASS | SKIPPED | 0 | event_trigger_without_route_note | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | customer.message_status_check | PASS | SKIPPED | 3 | input_declared_but_not_used, input_declared_but_not_used, input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | event.mock_ping | PASS | SKIPPED | 3 | input_declared_but_not_used, input_declared_but_not_used, input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | procurement.low_stock_reorder | PASS | SKIPPED | 0 | event_trigger_without_route_note | Run smoke test manually with sample inputs. |
