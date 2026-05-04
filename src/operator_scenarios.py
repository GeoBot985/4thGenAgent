from __future__ import annotations

from copy import deepcopy


SCENARIO_CATEGORIES = {
    "happy_path": "Happy Path",
    "negative_path": "Negative Path",
    "approval": "Approval",
    "data_business": "Data / Business",
    "reporting": "Reporting",
    "messages": "Messages",
    "procurement": "Procurement",
    "accounting": "Accounting",
}


_SCENARIOS = [
    {
        "id": "customer_status_happy_path",
        "label": "Customer Status - Happy Path",
        "category": "happy_path",
        "description": "Valid customer asks for valid order status. Reply is drafted, fact-checked, and staged for approval.",
        "requires_dataset_seed": True,
        "requires_inbox_seed": False,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_scenario_pack",
        "payload": {"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?", "channel": "callcentre"},
        "expected": {"final_state": "WAITING_FOR_EXECUTE", "pending_action_count": 1, "executed_action_count": 0, "must_have_failure": False, "must_have_approval_pack": True, "required_outputs": ["order_ref", "category", "customer", "order", "shipment", "order_context", "status_context", "ownership_check", "draft_reply", "reply_check", "reply_validation"], "required_pending_tools": ["wa/send"], "required_llm_actions": ["extract_order_ref", "classify_customer_message", "draft_customer_status_reply", "compare_reply_to_facts"], "required_domain_tools": ["customer/order_context", "customer/validate_owns_order", "customer/build_status_context", "customer/validate_status_reply", "customer/prepare_message_action"]},
    },
    {
        "id": "customer_status_approve_execute_dry_run",
        "label": "Customer Status - Approve + Execute Dry Run",
        "category": "approval",
        "description": "Runs happy path, approves staged send action, then executes approved action in dry-run mode.",
        "requires_dataset_seed": True,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_scenario_pack",
        "payload": {"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?", "channel": "callcentre"},
        "post_actions": [
            {"type": "approve_first_pending_action", "approved_by": "scenario_pack", "reason": "Scenario approval dry-run."},
            {"type": "execute_approved_dry_run"},
        ],
        "expected": {"final_state": "COMPLETED", "pending_action_status": "EXECUTED", "pending_action_count": 1, "executed_action_count": 1, "must_have_failure": False, "must_have_approval_pack": True, "required_outputs": ["customer_reply_send"]},
    },
    {
        "id": "customer_status_missing_customer",
        "label": "Customer Status - Missing Customer",
        "category": "negative_path",
        "description": "Unknown customer asks about unknown order. Runtime fails safely.",
        "requires_dataset_seed": True,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_scenario_pack",
        "payload": {"customer_id": "CUST-9999", "message": "Where is my order ORD-99999?", "channel": "callcentre"},
        "expected": {"state_prefix": "FAILED", "pending_action_count": 0, "executed_action_count": 0, "must_have_failure": True, "must_have_approval_pack": False},
    },
    {
        "id": "customer_status_missing_order",
        "label": "Customer Status - Missing Order",
        "category": "negative_path",
        "description": "Known customer asks about non-existent order. Runtime fails safely.",
        "requires_dataset_seed": True,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_scenario_pack",
        "payload": {"customer_id": "CUST-1001", "message": "Where is my order ORD-99999?", "channel": "callcentre"},
        "expected": {"state_prefix": "FAILED", "pending_action_count": 0, "executed_action_count": 0, "must_have_failure": True, "must_have_approval_pack": False},
    },
    {
        "id": "customer_status_wrong_customer_order",
        "label": "Customer Status - Wrong Customer / Order Pairing",
        "category": "negative_path",
        "description": "Customer CUST-1001 asks about order ORD-10044, which belongs to CUST-1004. Runtime blocks reply.",
        "requires_dataset_seed": True,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_scenario_pack",
        "payload": {"customer_id": "CUST-1001", "message": "Where is order ORD-10044?", "channel": "callcentre"},
        "expected": {"state_prefix": "FAILED", "pending_action_count": 0, "executed_action_count": 0, "must_have_failure": True, "expected_failure_contains": "customer"},
    },
    {
        "id": "customer_status_unsupported_intent",
        "label": "Customer Status - Unsupported Intent",
        "category": "negative_path",
        "description": "Refund request is sent through the order-status workflow and is blocked as unsupported.",
        "requires_dataset_seed": True,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "test_only": True,
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_scenario_pack",
        "payload": {"customer_id": "CUST-1002", "message": "I want a refund for order ORD-10043.", "channel": "callcentre"},
        "expected": {"state_prefix": "FAILED", "pending_action_count": 0, "executed_action_count": 0, "must_have_failure": True, "expected_output_values": {"category.label": "refund"}},
    },
    {
        "id": "customer_status_bad_llm_reply",
        "label": "Customer Status - Bad LLM Reply",
        "category": "negative_path",
        "description": "LLM invents compensation. Runtime validation blocks staged send.",
        "requires_dataset_seed": True,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "test_only": True,
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_scenario_pack",
        "payload": {"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?", "channel": "callcentre"},
        "expected": {"state_prefix": "FAILED", "pending_action_count": 0, "executed_action_count": 0, "must_have_failure": True, "expected_output_values": {"draft_reply.invented_compensation": True}},
    },
    {
        "id": "dataset_validation_seed_ok",
        "label": "Dataset Validation - Seed Dataset OK",
        "category": "data_business",
        "description": "Seeds and validates mock business dataset v2.",
        "requires_dataset_seed": True,
        "scenario_type": "dataset_validation",
        "expected": {"dataset_validation_ok": True, "must_have_failure": False},
    },
    {
        "id": "messages_absa_debit_orders_2026_capture",
        "label": "Messages - ABSA Debit Orders 2026 Capture",
        "category": "messages",
        "description": "Reads visible ABSA transaction SMS from Google Messages, extracts 2026 debit-order entries, and stages them for Google Sheets approval.",
        "requires_dataset_seed": False,
        "uses_llm": False,
        "event_type": "manual.messages_absa_debit_orders_2026",
        "source": "operator_scenario_pack",
        "payload_from_config": "config/absa_messages_sheet.json",
        "payload": {
            "spreadsheet_id": "",
            "output_range": "ABSA_Debit_Orders!A:H",
            "search_query": "Absa",
            "year": 2026,
            "max_scrolls": 240,
            "runtime_root": "runtime_data",
            "browser_user_data_dir": "runtime_data/absa_workflow_profile",
            "browser_profile_dir": "Profile 2",
        },
        "expected": {
            "final_state": "WAITING_FOR_EXECUTE",
            "pending_action_count": 1,
            "executed_action_count": 0,
            "must_have_failure": False,
            "must_have_approval_pack": True,
            "required_outputs": ["absa_transactions", "absa_sheet_write"],
            "required_pending_tools": ["sheet/write_rows"],
        },
    },
    {
        "id": "report_generation_happy_path",
        "label": "Report Generation - Happy Path Report",
        "category": "reporting",
        "description": "Runs happy path and generates markdown/html/evidence bundle.",
        "requires_dataset_seed": True,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "event_type": "manual.customer_status_llm_e2e",
        "source": "operator_scenario_pack",
        "payload": {"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?", "channel": "callcentre"},
        "generate_report": True,
        "expected": {"final_state": "WAITING_FOR_EXECUTE", "pending_action_count": 1, "executed_action_count": 0, "must_have_report": True, "must_have_evidence_bundle": True},
    },
    {
        "id": "procurement_low_stock_happy_path",
        "label": "Procurement - Low Stock Reorder Happy Path",
        "category": "procurement",
        "description": "Finds low-stock inventory, builds a deterministic draft PO, drafts supplier message with bounded LLM, and stages supplier send for approval.",
        "requires_dataset_seed": True,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "event_type": "manual.procurement_low_stock_reorder",
        "source": "operator_scenario_pack",
        "payload": {},
        "expected": {
            "final_state": "WAITING_FOR_EXECUTE",
            "pending_action_count": 1,
            "executed_action_count": 0,
            "must_have_failure": False,
            "must_have_approval_pack": True,
            "required_outputs": ["low_stock_items", "reorder_candidates", "duplicate_po_check", "selected_supplier", "draft_po", "po_validation", "supplier_message", "supplier_message_send"],
            "required_pending_tools": ["supplier/prepare_message_action"],
            "required_llm_actions": ["draft_supplier_reorder_message"],
        },
    },
    {
        "id": "procurement_low_stock_approve_execute_dry_run",
        "label": "Procurement - Approve + Execute Dry Run",
        "category": "procurement",
        "description": "Runs low-stock reorder, approves staged supplier message, executes approved supplier send in dry-run mode, and reaches completed state.",
        "requires_dataset_seed": True,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "event_type": "manual.procurement_low_stock_reorder",
        "source": "operator_scenario_pack",
        "payload": {},
        "post_actions": [
            {"type": "approve_first_pending_action", "approved_by": "scenario_pack", "reason": "Procurement scenario approval dry-run."},
            {"type": "execute_approved_dry_run"},
        ],
        "expected": {
            "final_state": "COMPLETED",
            "pending_action_status": "EXECUTED",
            "pending_action_count": 1,
            "executed_action_count": 1,
            "must_have_failure": False,
            "must_have_approval_pack": True,
            "required_outputs": ["supplier_message_send"],
        },
    },
    {
        "id": "procurement_low_stock_report_generation",
        "label": "Procurement - Report Generation",
        "category": "procurement",
        "description": "Runs low-stock reorder, leaves supplier send staged for approval, and generates report/evidence bundle.",
        "requires_dataset_seed": True,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "event_type": "manual.procurement_low_stock_reorder",
        "source": "operator_scenario_pack",
        "payload": {},
        "generate_report": True,
        "expected": {
            "final_state": "WAITING_FOR_EXECUTE",
            "pending_action_count": 1,
            "executed_action_count": 0,
            "must_have_report": True,
            "must_have_approval_pack": True,
            "must_have_evidence_bundle": True,
            "must_have_failure": False,
        },
    },

    {
        "id": "accounting_payment_reconciliation_happy_path",
        "label": "Accounting - Payment Reconciliation",
        "category": "accounting",
        "description": "Reads accounting data from Google Sheets, reconciles payments to orders/invoices/ledger entries, drafts exception summary, and stages reconciliation result writes for approval.",
        "requires_dataset_seed": False,
        "uses_llm": True,
        "llm_mode": "real",
        "event_type": "manual.accounting_payment_reconciliation",
        "source": "operator_scenario_pack",
        "payload_from_config": "config/accounting_google_sheet.json",
        "payload": {"spreadsheet_id": "", "payments_range": "Payments!A:I", "orders_range": "Orders!A:F", "invoices_range": "CustomerInvoices!A:H", "ledger_range": "Ledger!A:I", "recon_runs_range": "ReconRuns!A:J", "recon_exceptions_range": "ReconExceptions!A:M"},
        "expected": {"final_state": "WAITING_FOR_EXECUTE", "pending_action_count": 2, "executed_action_count": 0, "must_have_failure": False, "must_have_approval_pack": True, "required_outputs": ["payments_sheet", "orders_sheet", "invoices_sheet", "ledger_sheet", "payments", "accounting_orders", "invoices", "ledger_entries", "reconciliation_result", "reconciliation_validation", "exception_summary", "recon_sheet_rows", "recon_run_write", "recon_exception_write"], "required_pending_tools": ["sheet/write_rows"], "required_llm_actions": ["draft_reconciliation_exception_summary"]}
    },
    {
        "id": "accounting_payment_reconciliation_approve_execute_dry_run",
        "label": "Accounting - Approve + Execute Sheet Write Dry Run",
        "category": "accounting",
        "description": "Runs accounting payment reconciliation, approves staged ReconRuns and ReconExceptions sheet writes, executes them in dry-run mode, and reaches completed state.",
        "requires_dataset_seed": False,
        "uses_llm": True,
        "llm_mode": "real",
        "event_type": "manual.accounting_payment_reconciliation",
        "source": "operator_scenario_pack",
        "payload_from_config": "config/accounting_google_sheet.json",
        "payload": {"spreadsheet_id": "", "payments_range": "Payments!A:I", "orders_range": "Orders!A:F", "invoices_range": "CustomerInvoices!A:H", "ledger_range": "Ledger!A:I", "recon_runs_range": "ReconRuns!A:J", "recon_exceptions_range": "ReconExceptions!A:M"},
        "post_actions": [
            {"type": "approve_all_pending_actions", "approved_by": "scenario_pack", "reason": "Accounting scenario approval dry-run."},
            {"type": "execute_approved_dry_run"}
        ],
        "expected": {"final_state": "COMPLETED", "pending_action_status": "EXECUTED", "pending_action_count": 2, "executed_action_count": 2, "must_have_failure": False, "must_have_approval_pack": True, "required_outputs": ["recon_run_write", "recon_exception_write"], "required_executed_tools": ["sheet/write_rows"], "required_llm_actions": ["draft_reconciliation_exception_summary"]}
    },
    {
        "id": "accounting_payment_reconciliation_report_generation",
        "label": "Accounting - Reconciliation Report Generation",
        "category": "accounting",
        "description": "Runs accounting payment reconciliation and generates markdown, HTML, and evidence bundle while sheet writes remain staged for approval.",
        "requires_dataset_seed": False,
        "uses_llm": True,
        "llm_mode": "real",
        "event_type": "manual.accounting_payment_reconciliation",
        "source": "operator_scenario_pack",
        "payload_from_config": "config/accounting_google_sheet.json",
        "payload": {"spreadsheet_id": "", "payments_range": "Payments!A:I", "orders_range": "Orders!A:F", "invoices_range": "CustomerInvoices!A:H", "ledger_range": "Ledger!A:I", "recon_runs_range": "ReconRuns!A:J", "recon_exceptions_range": "ReconExceptions!A:M"},
        "generate_report": True,
        "expected": {"final_state": "WAITING_FOR_EXECUTE", "pending_action_count": 2, "executed_action_count": 0, "must_have_report": True, "must_have_evidence_bundle": True, "must_have_failure": False}
    },
    {
        "id": "procurement_low_stock_bad_llm_message",
        "label": "Procurement - Bad Supplier Message",
        "category": "procurement",
        "description": "LLM invents unsupported supplier terms and runtime blocks staged send.",
        "requires_dataset_seed": True,
        "uses_llm": True,
        "llm_mode": "real",
        "llm_provider": "ollama",
        "llm_model": "granite3.3:8b",
        "test_only": True,
        "event_type": "manual.procurement_low_stock_reorder",
        "source": "operator_scenario_pack",
        "payload": {},
        "expected": {
            "state_prefix": "FAILED",
            "pending_action_count": 0,
            "executed_action_count": 0,
            "must_have_failure": True,
        },
    },
]


def list_categories() -> list[dict]:
    return [{"id": key, "label": value} for key, value in SCENARIO_CATEGORIES.items()]


def list_scenarios(category: str | None = None, include_test_only: bool = True) -> list[dict]:
    scenarios = _SCENARIOS if not category else [scenario for scenario in _SCENARIOS if scenario.get("category") == category]
    if not include_test_only:
        scenarios = [scenario for scenario in scenarios if not scenario.get("test_only")]
    return [deepcopy(item) for item in scenarios]


def get_scenario(scenario_id: str) -> dict:
    for scenario in _SCENARIOS:
        if scenario.get("id") == scenario_id:
            return deepcopy(scenario)
    raise ValueError(f"Unknown scenario: {scenario_id}")


def validate_scenario_definition(scenario: dict) -> list[str]:
    errors: list[str] = []
    required = ("id", "label", "category", "description", "expected")
    for key in required:
        if key not in scenario:
            errors.append(f"missing:{key}")
    if scenario.get("category") not in SCENARIO_CATEGORIES:
        errors.append("invalid_category")
    if scenario.get("scenario_type") != "dataset_validation":
        for key in ("event_type", "source", "payload"):
            if key not in scenario:
                errors.append(f"missing:{key}")
    return errors
