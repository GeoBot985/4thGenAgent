from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

from runtime.business_data import reset_business_dataset, seed_business_dataset, validate_business_dataset
from runtime.scenario_validation import validate_scenario_result
from src.operator_approval_actions import approve_all_pending_actions_command, approve_pending_action, execute_approved_pending_actions_dry_run, reject_pending_action
from src.operator_demo_runner import run_demo_definition
from src.operator_reports import generate_report_for_frame
from src.operator_scenarios import get_scenario
from runtime.taskframe_reload import load_taskframe
from runtime.taskframe import to_dict as taskframe_to_dict
from src.operator_approval_pack import build_approval_pack_view
from runtime.failure_summary import build_failure_summary


def run_scenario(
    scenario_id: str,
    runtime_data_dir: str = "runtime_data",
    use_local_llm: bool = True,
    reset_dataset: bool = False,
    generate_report: bool = False,
    llm_adapter=None,
    allow_test_fake_llm: bool = False,
) -> dict:
    try:
        scenario = get_scenario(scenario_id)
    except Exception as exc:
        return _failure_shape(scenario_id, str(exc))

    try:
        if reset_dataset or scenario.get("requires_dataset_seed"):
            if reset_dataset:
                seed_result = reset_business_dataset(runtime_data_dir)
            else:
                seed_result = seed_business_dataset(runtime_data_dir, overwrite=False)
        else:
            seed_result = {"ok": True}

        if scenario.get("scenario_type") == "dataset_validation":
            dataset_validation = validate_business_dataset(runtime_data_dir)
            result = {
                "ok": True,
                "scenario_id": scenario_id,
                "label": scenario.get("label", ""),
                "category": scenario.get("category", ""),
                "frame_id": "",
                "manifest_id": "",
                "state": "DATASET_VALIDATED",
                "summary": {},
                "snapshot": {},
                "timeline": [],
                "approval_pack": {},
                "failure_summary": {},
                "dataset_validation": dataset_validation,
                "report_result": {},
                "post_action_results": [],
                "error": "",
            }
            result["scenario_validation"] = validate_scenario_result(scenario, result)
            return result

        demo = deepcopy(scenario)
        payload_from_config = scenario.get("payload_from_config")
        if payload_from_config:
            config_path = Path(str(payload_from_config))
            if config_path.is_file():
                try:
                    config_data = json.loads(config_path.read_text(encoding="utf-8"))
                except Exception:
                    config_data = {}
                if isinstance(config_data, dict):
                    payload = demo.get("payload", {}) if isinstance(demo.get("payload", {}), dict) else {}
                    demo["payload"] = {**payload, **config_data}
        demo["selection_id"] = scenario["id"]
        test_env = _in_test_environment()
        if allow_test_fake_llm or test_env:
            demo["fake_llm_responses"] = _fake_llm_responses_for_scenario(scenario)
        else:
            demo.pop("fake_llm_responses", None)

        if test_env and llm_adapter is None:
            use_local_llm = False

        result = run_demo_definition(
            demo,
            runtime_data_dir=runtime_data_dir,
            use_local_llm=use_local_llm,
            llm_adapter=llm_adapter,
            allow_test_fake_llm=allow_test_fake_llm,
        )
        result.update({"scenario_id": scenario_id, "label": scenario.get("label", ""), "category": scenario.get("category", "")})

        post_results: list[dict] = []
        if result.get("ok"):
            for action in scenario.get("post_actions", []) or []:
                if action.get("type") == "approve_first_pending_action":
                    approval_pack = result.get("approval_pack", {})
                    pending = approval_pack.get("approval_packs", []) if isinstance(approval_pack, dict) else []
                    if pending:
                        action_id = pending[0].get("action_id", "")
                        post_results.append(approve_pending_action(result["frame_id"], action_id, approved_by=action.get("approved_by", "scenario_pack"), reason=action.get("reason", ""), runtime_data_dir=runtime_data_dir))
                elif action.get("type") == "approve_all_pending_actions":
                    post_results.append(approve_all_pending_actions_command(result["frame_id"], approved_by=action.get("approved_by", "scenario_pack"), reason=action.get("reason", ""), runtime_data_dir=runtime_data_dir))
                elif action.get("type") == "execute_approved_dry_run":
                    post_results.append(execute_approved_pending_actions_dry_run(result["frame_id"], runtime_data_dir=runtime_data_dir))
                elif action.get("type") == "reject_first_pending_action":
                    approval_pack = result.get("approval_pack", {})
                    pending = approval_pack.get("approval_packs", []) if isinstance(approval_pack, dict) else []
                    if pending:
                        action_id = pending[0].get("action_id", "")
                        post_results.append(reject_pending_action(result["frame_id"], action_id, rejected_by=action.get("rejected_by", "scenario_pack"), reason=action.get("reason", ""), runtime_data_dir=runtime_data_dir))
                elif action.get("type") == "generate_report":
                    post_results.append(generate_report_for_frame(result["frame_id"], runtime_data_dir))
        result["post_action_results"] = post_results
        result.setdefault("post_action_results", [])
        if result.get("frame_id"):
            frame_obj = load_taskframe(result["frame_id"], runtime_data_dir)
            frame_dict = taskframe_to_dict(frame_obj) if frame_obj is not None else {}
            result["snapshot"] = {
                "ok": True,
                "active_event": frame_dict.get("trigger", {}),
                "active_frame": frame_dict,
                "outputs": frame_dict.get("outputs", {}),
                "validations": frame_dict.get("validations", []),
                "pending_actions": frame_dict.get("pending_actions", []),
                "executed_actions": frame_dict.get("executed_actions", []),
                "trace_lines": frame_dict.get("trace_lines", []),
                "errors": frame_dict.get("errors", []),
                "llm_calls": frame_dict.get("llm_calls", []),
                "tool_calls": frame_dict.get("tool_calls", []),
            }
            result["state"] = frame_dict.get("state", result.get("state", ""))
            result["summary"] = frame_dict.get("summary", {}) or result.get("summary", {})
            result["timeline"] = result.get("timeline") or []
            result["approval_pack"] = build_approval_pack_view(frame_dict or result.get("snapshot", {}).get("active_frame", {}))
            result["failure_summary"] = build_failure_summary(frame_dict or result.get("snapshot", {}).get("active_frame", {}))
            if scenario_id.startswith("supplier_invoice_match_"):
                outputs = frame_dict.get("outputs", {}) if isinstance(frame_dict.get("outputs", {}), dict) else {}
                invoice = outputs.get("invoice", {}) if isinstance(outputs, dict) else {}
                purchase_order = outputs.get("purchase_order", {}) if isinstance(outputs, dict) else {}
                receipts = outputs.get("receipts", {}) if isinstance(outputs, dict) else {}
                match_result = outputs.get("match_result", {}) if isinstance(outputs, dict) else {}
                duplicate_check = outputs.get("duplicate_check", {}) if isinstance(outputs, dict) else {}
                exception_report = outputs.get("exception_report", {}) if isinstance(outputs, dict) else {}
                pending_actions = frame_dict.get("pending_actions", []) if isinstance(frame_dict.get("pending_actions", []), list) else []
                invoice_data = invoice.get("data", {}) if isinstance(invoice, dict) else {}
                purchase_order_data = purchase_order.get("data", {}) if isinstance(purchase_order, dict) else {}
                receipts_data = receipts.get("data", {}) if isinstance(receipts, dict) else {}
                match_result_data = match_result.get("data", {}) if isinstance(match_result, dict) else {}
                duplicate_check_data = duplicate_check.get("data", {}) if isinstance(duplicate_check, dict) else {}
                exception_report_data = exception_report.get("data", {}) if isinstance(exception_report, dict) else {}
                result.update(
                    {
                        "invoice_ref": invoice_data.get("invoice_ref", scenario.get("payload", {}).get("invoice_ref", "")) if isinstance(invoice_data, dict) else scenario.get("payload", {}).get("invoice_ref", ""),
                        "supplier_id": invoice_data.get("supplier_id", "") if isinstance(invoice_data, dict) else "",
                        "po_ref": invoice_data.get("po_ref", "") if isinstance(invoice_data, dict) else "",
                        "receipt_ref": (
                            receipts_data.get("receipt_refs", [""])[0]
                            if isinstance(receipts_data, dict) and isinstance(receipts_data.get("receipt_refs", []), list) and receipts_data.get("receipt_refs")
                            else ""
                        ),
                        "match_status": match_result_data.get("match_status", "") if isinstance(match_result_data, dict) else "",
                        "exception_count": len(match_result_data.get("exceptions", [])) if isinstance(match_result_data, dict) and isinstance(match_result_data.get("exceptions", []), list) else 0,
                        "ledger_decision": "stage_ledger" if any(p.get("output_alias") == "ledger_write" for p in pending_actions if isinstance(p, dict)) else "exception_only",
                        "pending_actions": [p.get("output_alias", "") for p in pending_actions if isinstance(p, dict)],
                        "completion_outcome": frame_dict.get("state", result.get("state", "")),
                        "duplicate_check": duplicate_check_data,
                        "purchase_order": purchase_order_data,
                        "receipts": receipts_data,
                        "exception_report": exception_report_data,
                    }
                )
        if not result.get("state"):
            if result.get("ok", False):
                result["state"] = "COMPLETED"
            else:
                failure_summary = result.get("failure_summary", {})
                if isinstance(failure_summary, dict) and str(failure_summary.get("state") or "").strip():
                    result["state"] = str(failure_summary.get("state"))
                else:
                    result["state"] = "FAILED_EXECUTION"
        if generate_report or scenario.get("generate_report"):
            result["report_result"] = generate_report_for_frame(result["frame_id"], runtime_data_dir) if result.get("frame_id") else {}
        else:
            result["report_result"] = {}
        result["dataset_validation"] = seed_result if scenario.get("scenario_type") == "dataset_validation" else {}
        result["scenario_validation"] = validate_scenario_result(scenario, result)
        return result
    except Exception as exc:
        return _failure_shape(scenario_id, str(exc))


def _fake_llm_responses_for_scenario(scenario: dict) -> dict:
    scenario_id = scenario.get("id", "")
    llm_mode = scenario.get("llm_mode", "")
    if scenario_id in {"customer_status_happy_path", "customer_status_approve_execute_dry_run", "report_generation_happy_path"}:
        return {
            "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
            "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
            "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit. Estimated delivery is 2026-05-03.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
            "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}',
        }
    if scenario_id == "customer_status_bad_llm_reply" or llm_mode == "bad_reply":
        return {
            "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
            "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
            "draft_customer_status_reply": '{"reply": "Your order ORD-10042 is delayed, so we will refund you 50%.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": true}',
            "compare_reply_to_facts": '{"ok": false, "matches_facts": false, "unsupported_claims": ["Promised refund not present in facts."], "missing_required_facts": [], "reason": "Reply contains unsupported compensation."}',
        }
    if llm_mode == "fake_procurement_reorder":
        return {
            "draft_supplier_reorder_message": '{"subject": "Purchase Order {po_id}", "body": "Good day {supplier_name}, please find draft purchase order {po_id} for {skus}. Please confirm availability and lead time.", "tone": "professional", "included_po_id": true, "included_supplier_name": true, "included_sku_lines": true, "invented_terms": false}'
        }
    if scenario_id == "procurement_low_stock_bad_llm_message" or llm_mode == "bad_procurement_message":
        return {
            "draft_supplier_reorder_message": '{"subject": "Order", "body": "We will pay early and expect a discount.", "tone": "professional", "included_po_id": false, "included_supplier_name": false, "included_sku_lines": false, "invented_terms": true}'
        }
    if llm_mode == "fake_refund_classification":
        return {
            "extract_order_ref": '{"order_ref": "ORD-10043", "confidence": "high", "reason": "Detected explicit order reference."}',
            "classify_customer_message": '{"label": "refund", "confidence": "high", "reason": "Refund request."}',
            "draft_customer_status_reply": '{"reply": "Your order ORD-10043 is being processed.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
            "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}',
        }
    if scenario_id == "customer_status_bad_extract" or llm_mode == "bad_extract":
        return {"extract_order_ref": '{"order_ref": "10042", "confidence": "high", "reason": "Bad format test."}'}
    if scenario_id == "customer_status_bad_classification" or llm_mode == "bad_classification":
        return {"classify_customer_message": '{"label": "random_label", "confidence": "high", "reason": "Bad label test."}'}
    if scenario_id == "accounting_payment_reconciliation_bad_llm_summary" or llm_mode == "fake_accounting_reconciliation":
        return {"draft_reconciliation_exception_summary": '{"summary": "Payments were reconciled against orders, invoices, and ledger entries. Exceptions require operator review before posting.", "risk_level": "high", "key_exceptions": ["One payment has an amount mismatch.", "One payment reference appears more than once.", "One payment appears to already be posted."], "recommended_action": "Review high-severity exceptions before posting or updating the ledger.", "invented_facts": false}'}
    if scenario_id.startswith("supplier_invoice_match_") or llm_mode == "fake_supplier_invoice_match":
        if scenario_id == "supplier_invoice_match_happy_path":
            return {
                "draft_supplier_invoice_exception_summary": '{"summary": "The supplier invoice matches the purchase order and goods receipt records. No exceptions were invented.", "risk_level": "low", "key_exceptions": [], "recommended_action": "Approve the staged match-run and ledger writes.", "invented_facts": false}'
            }
        if scenario_id == "supplier_invoice_match_price_exception":
            return {
                "draft_supplier_invoice_exception_summary": '{"summary": "The supplier invoice shows a price variance against the purchase order.", "risk_level": "high", "key_exceptions": ["PRICE_MISMATCH"], "recommended_action": "Approve the exception write only and review the unit price variance.", "invented_facts": false}'
            }
        if scenario_id == "supplier_invoice_match_quantity_exception":
            return {
                "draft_supplier_invoice_exception_summary": '{"summary": "The supplier invoice shows a receipt quantity variance.", "risk_level": "high", "key_exceptions": ["RECEIPT_MISMATCH"], "recommended_action": "Approve the exception write only and review the received quantity variance.", "invented_facts": false}'
            }
        if scenario_id == "supplier_invoice_match_missing_receipt":
            return {
                "draft_supplier_invoice_exception_summary": '{"summary": "The supplier invoice has no goods receipt match.", "risk_level": "high", "key_exceptions": ["RECEIPT_NOT_FOUND"], "recommended_action": "Approve the exception write only and investigate the missing receipt.", "invented_facts": false}'
            }
        if scenario_id == "supplier_invoice_match_missing_po":
            return {
                "draft_supplier_invoice_exception_summary": '{"summary": "The supplier invoice references a missing purchase order.", "risk_level": "high", "key_exceptions": ["PO_NOT_FOUND"], "recommended_action": "Reject ledger posting and resolve the purchase order reference.", "invented_facts": false}'
            }
        if scenario_id == "supplier_invoice_match_duplicate_invoice":
            return {
                "draft_supplier_invoice_exception_summary": '{"summary": "The supplier invoice appears to be a duplicate invoice number.", "risk_level": "high", "key_exceptions": ["DUPLICATE_INVOICE"], "recommended_action": "Approve the exception write only and investigate the duplicate invoice reference.", "invented_facts": false}'
            }
        if scenario_id == "supplier_invoice_match_approve_execute_dry_run":
            return {
                "draft_supplier_invoice_exception_summary": '{"summary": "The supplier invoice matches the purchase order and goods receipt records. No exceptions were invented.", "risk_level": "low", "key_exceptions": [], "recommended_action": "Approve the staged match-run and ledger writes.", "invented_facts": false}'
            }
        if scenario_id == "supplier_invoice_match_report_generation":
            return {
                "draft_supplier_invoice_exception_summary": '{"summary": "The supplier invoice matches the purchase order and goods receipt records. No exceptions were invented.", "risk_level": "low", "key_exceptions": [], "recommended_action": "Approve the staged match-run and ledger writes.", "invented_facts": false}'
            }
        return {
            "draft_supplier_invoice_exception_summary": '{"summary": "The supplier invoice contains exceptions that require operator review.", "risk_level": "high", "key_exceptions": ["PRICE_MISMATCH"], "recommended_action": "Review the exception report and approve only the non-ledger match-run write.", "invented_facts": false}'
        }
    return {}


def _in_test_environment() -> bool:
    import os

    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _failure_shape(scenario_id: str, error: str) -> dict:
    return {
        "ok": False,
        "scenario_id": scenario_id,
        "label": "",
        "category": "",
        "frame_id": "",
        "manifest_id": "",
        "state": "",
        "summary": {},
        "snapshot": {},
        "timeline": [],
        "approval_pack": {},
        "failure_summary": {},
        "scenario_validation": {"verdict": "FAIL", "checks": []},
        "report_result": {},
        "post_action_results": [],
        "error": error,
    }
