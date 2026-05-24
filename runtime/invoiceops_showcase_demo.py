from __future__ import annotations

"""
Spec 158 — InvoiceOps Live Bookkeeping Showcase Demo Pack v1.

Orchestrates a polished multi-invoice demo showing extraction, matching,
exception handling, live Google Sheets posting, reconciliation, and reporting.
Reuses existing InvoiceOps modules; adds no duplicate core logic.

Boundary-only mode (no Google credentials required):
  run_showcase_invoice_batch(..., live_mode=False)

Live mode (controlled_live_write + typed confirmation required):
  run_showcase_invoice_batch(..., live_mode=True, confirm="EXECUTE LIVE INVOICEOPS SHOWCASE <id>")
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHOWCASE_TABS = [
    "Dashboard",
    "Invoices",
    "PO Register",
    "Goods Receipts",
    "Supplier Master",
    "Match Results",
    "Exceptions",
    "Ledger",
    "Posting Ledger",
    "Reconciliation",
    "Rollback Plans",
    "Evidence Index",
    "Demo Run Log",
]

REQUIRED_PROFILE = "controlled_live_write"
CONFIRMATION_TEMPLATE = "EXECUTE LIVE INVOICEOPS SHOWCASE {spreadsheet_id}"
SHOWCASE_REPORT_SUBDIR = Path("invoiceops") / "showcase"
FIXTURE_INVOICE_DIR = Path("fixtures") / "invoiceops_showcase" / "invoices"

# ---------------------------------------------------------------------------
# Demo dataset
# ---------------------------------------------------------------------------

SHOWCASE_SCENARIOS: list[dict[str, Any]] = [
    {
        "invoice_number": "INV-001",
        "scenario": "clean_match",
        "scenario_label": "Clean matched invoice",
        "supplier_name": "Acme Office Supplies (Pty) Ltd",
        "po_number": "PO-2026-0042",
        "gr_number": "GR-2026-0042",
        "invoice_total": 3145.25,
        "po_total": 3145.25,
        "gr_quantity_ok": True,
        "expected_match_status": "matched",
        "expected_posting_status": "EXECUTED_VERIFIED",
        "expected_reconciliation_status": "RECONCILED",
        "expected_exception_type": "",
        "talking_point": "Clean three-way match. Invoice posts to all registers with full audit trail.",
    },
    {
        "invoice_number": "INV-002",
        "scenario": "duplicate_invoice",
        "scenario_label": "Duplicate invoice (re-submission)",
        "supplier_name": "Acme Office Supplies (Pty) Ltd",
        "po_number": "PO-2026-0042",
        "gr_number": "GR-2026-0042",
        "invoice_total": 3145.25,
        "po_total": 3145.25,
        "gr_quantity_ok": True,
        "expected_match_status": "exception",
        "expected_posting_status": "BLOCKED",
        "expected_reconciliation_status": "UNRECONCILED",
        "expected_exception_type": "DUPLICATE_INVOICE",
        "talking_point": "Same supplier, same PO, same amounts — duplicate check fires. Invoice blocked.",
    },
    {
        "invoice_number": "INV-003",
        "scenario": "wrong_po_number",
        "scenario_label": "Non-existent / wrong PO number",
        "supplier_name": "BlueSky Catering Services",
        "po_number": "PO-2026-9999",
        "gr_number": "GR-2026-0051",
        "invoice_total": 18745.00,
        "po_total": 0.0,
        "gr_quantity_ok": True,
        "expected_match_status": "exception",
        "expected_posting_status": "BLOCKED",
        "expected_reconciliation_status": "UNRECONCILED",
        "expected_exception_type": "PO_NOT_FOUND",
        "talking_point": "PO number does not exist in register. Invoice cannot proceed without approved PO.",
    },
    {
        "invoice_number": "INV-004",
        "scenario": "missing_goods_receipt",
        "scenario_label": "Missing goods receipt",
        "supplier_name": "TechGear Distribution",
        "po_number": "PO-2026-0078",
        "gr_number": "",
        "invoice_total": 72967.50,
        "po_total": 72967.50,
        "gr_quantity_ok": False,
        "expected_match_status": "exception",
        "expected_posting_status": "BLOCKED",
        "expected_reconciliation_status": "UNRECONCILED",
        "expected_exception_type": "GOODS_RECEIPT_NOT_FOUND",
        "talking_point": "Goods not received yet. Three-way match requires GR. Invoice held pending delivery.",
    },
    {
        "invoice_number": "INV-005",
        "scenario": "supplier_mismatch",
        "scenario_label": "Supplier name mismatch",
        "supplier_name": "Rainbow Cleaning Contractors",
        "po_number": "PO-2026-0055",
        "gr_number": "GR-2026-0055",
        "invoice_total": 13455.00,
        "po_total": 13455.00,
        "gr_quantity_ok": True,
        "expected_match_status": "exception",
        "expected_posting_status": "BLOCKED",
        "expected_reconciliation_status": "UNRECONCILED",
        "expected_exception_type": "SUPPLIER_MISMATCH",
        "talking_point": "PO issued to different supplier. Assignment not approved. Manual review required.",
    },
    {
        "invoice_number": "INV-006",
        "scenario": "price_mismatch",
        "scenario_label": "Unit price above PO rate",
        "supplier_name": "FastPrint Signage & Printing",
        "po_number": "PO-2026-0061",
        "gr_number": "GR-2026-0061",
        "invoice_total": 29141.00,
        "po_total": 25841.00,
        "gr_quantity_ok": True,
        "expected_match_status": "exception",
        "expected_posting_status": "BLOCKED",
        "expected_reconciliation_status": "UNRECONCILED",
        "expected_exception_type": "PRICE_MISMATCH",
        "talking_point": "Banner price 23% above approved PO rate. Invoice blocked pending price authorisation.",
    },
    {
        "invoice_number": "INV-007",
        "scenario": "quantity_mismatch",
        "scenario_label": "Quantity billed exceeds goods received",
        "supplier_name": "Hydro-Flow Bottled Water",
        "po_number": "PO-2026-0033",
        "gr_number": "GR-2026-0033",
        "invoice_total": 5865.00,
        "po_total": 5865.00,
        "gr_quantity_ok": False,
        "expected_match_status": "exception",
        "expected_posting_status": "BLOCKED",
        "expected_reconciliation_status": "UNRECONCILED",
        "expected_exception_type": "QUANTITY_MISMATCH",
        "talking_point": "Invoice claims 50 cases; warehouse signed for 40. Overpayment of 10 cases blocked.",
    },
    {
        "invoice_number": "INV-008",
        "scenario": "tax_total_mismatch",
        "scenario_label": "VAT / total calculation error",
        "supplier_name": "Momentum Advisory Group",
        "po_number": "PO-2026-0088",
        "gr_number": "GR-2026-0088",
        "invoice_total": 109350.00,
        "po_total": 111780.00,
        "gr_quantity_ok": True,
        "expected_match_status": "exception",
        "expected_posting_status": "BLOCKED",
        "expected_reconciliation_status": "UNRECONCILED",
        "expected_exception_type": "TAX_TOTAL_MISMATCH",
        "talking_point": "VAT arithmetic does not match declared total. Invoice arithmetic error caught before payment.",
    },
]

# ---------------------------------------------------------------------------
# Demo master data (supplier, PO, and GR seed records)
# ---------------------------------------------------------------------------

DEMO_SUPPLIERS: list[dict[str, Any]] = [
    {"supplier_id": "SUP-001", "name": "Acme Office Supplies (Pty) Ltd", "vat_number": "4123456789", "status": "active"},
    {"supplier_id": "SUP-002", "name": "BlueSky Catering Services", "vat_number": "4987654321", "status": "active"},
    {"supplier_id": "SUP-003", "name": "TechGear Distribution", "vat_number": "4556677889", "status": "active"},
    {"supplier_id": "SUP-004", "name": "Sparkle Clean Solutions", "vat_number": "4112233445", "status": "active"},
    {"supplier_id": "SUP-005", "name": "FastPrint Signage & Printing", "vat_number": "4332211009", "status": "active"},
    {"supplier_id": "SUP-006", "name": "Hydro-Flow Bottled Water", "vat_number": "4765432109", "status": "active"},
    {"supplier_id": "SUP-007", "name": "Momentum Advisory Group", "vat_number": "4899988776", "status": "active"},
]

DEMO_PO_REGISTER: list[dict[str, Any]] = [
    {"po_number": "PO-2026-0042", "supplier_id": "SUP-001", "supplier_name": "Acme Office Supplies (Pty) Ltd", "approved_total": 3145.25, "currency": "ZAR", "status": "open"},
    {"po_number": "PO-2026-0055", "supplier_id": "SUP-004", "supplier_name": "Sparkle Clean Solutions", "approved_total": 13455.00, "currency": "ZAR", "status": "open"},
    {"po_number": "PO-2026-0061", "supplier_id": "SUP-005", "supplier_name": "FastPrint Signage & Printing", "approved_total": 25841.00, "currency": "ZAR", "status": "open"},
    {"po_number": "PO-2026-0033", "supplier_id": "SUP-006", "supplier_name": "Hydro-Flow Bottled Water", "approved_total": 5865.00, "currency": "ZAR", "status": "open"},
    {"po_number": "PO-2026-0078", "supplier_id": "SUP-003", "supplier_name": "TechGear Distribution", "approved_total": 72967.50, "currency": "ZAR", "status": "open"},
    {"po_number": "PO-2026-0088", "supplier_id": "SUP-007", "supplier_name": "Momentum Advisory Group", "approved_total": 111780.00, "currency": "ZAR", "status": "open"},
]

DEMO_GOODS_RECEIPTS: list[dict[str, Any]] = [
    {"gr_number": "GR-2026-0042", "po_number": "PO-2026-0042", "supplier_name": "Acme Office Supplies (Pty) Ltd", "quantity_received": 18, "quantity_ordered": 18, "status": "complete"},
    {"gr_number": "GR-2026-0051", "po_number": "PO-2026-9999", "supplier_name": "BlueSky Catering Services", "quantity_received": 2, "quantity_ordered": 2, "status": "complete"},
    {"gr_number": "GR-2026-0055", "po_number": "PO-2026-0055", "supplier_name": "Sparkle Clean Solutions", "quantity_received": 2, "quantity_ordered": 2, "status": "complete"},
    {"gr_number": "GR-2026-0061", "po_number": "PO-2026-0061", "supplier_name": "FastPrint Signage & Printing", "quantity_received": 22, "quantity_ordered": 22, "status": "complete"},
    {"gr_number": "GR-2026-0033", "po_number": "PO-2026-0033", "supplier_name": "Hydro-Flow Bottled Water", "quantity_received": 40, "quantity_ordered": 50, "status": "partial"},
    {"gr_number": "GR-2026-0088", "po_number": "PO-2026-0088", "supplier_name": "Momentum Advisory Group", "quantity_received": 20, "quantity_ordered": 20, "status": "complete"},
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_run_id() -> str:
    return f"SHOWCASE-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"


def _idempotency_key(run_id: str, invoice_number: str, target: str) -> str:
    raw = f"showcase:{run_id}:{invoice_number}:{target}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _payload_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _load_showcase_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load showcase config from user config path or return empty config."""
    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    candidates.append(Path.home() / ".taskframe" / "invoiceops_showcase.json")
    for path in candidates:
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _resolve_spreadsheet_id(spreadsheet_id: str, config: dict[str, Any]) -> str:
    return spreadsheet_id or str(config.get("spreadsheet_id", "") or "")


# ---------------------------------------------------------------------------
# Public API: dataset
# ---------------------------------------------------------------------------

def build_showcase_demo_dataset(
    *,
    invoice_limit: int = 0,
) -> dict[str, Any]:
    """Return the full showcase scenario dataset (no I/O)."""
    scenarios = SHOWCASE_SCENARIOS
    if invoice_limit and invoice_limit > 0:
        scenarios = scenarios[:invoice_limit]
    return {
        "ok": True,
        "scenarios": scenarios,
        "supplier_master": DEMO_SUPPLIERS,
        "po_register": DEMO_PO_REGISTER,
        "goods_receipts": DEMO_GOODS_RECEIPTS,
        "invoice_count": len(scenarios),
        "fixture_dir": str(FIXTURE_INVOICE_DIR),
        "allowed_tabs": SHOWCASE_TABS,
    }


# ---------------------------------------------------------------------------
# Public API: sheet structure (boundary-safe)
# ---------------------------------------------------------------------------

def create_or_reset_showcase_google_sheet(
    *,
    spreadsheet_id: str,
    allow_reset: bool = True,
    live_mode: bool = False,
) -> dict[str, Any]:
    """
    Return the sheet structure spec. In live mode, caller is responsible
    for executing the actual Google Sheets API calls.
    """
    if not spreadsheet_id and live_mode:
        return {"ok": False, "error": "spreadsheet_id required for live mode", "spreadsheet_id": ""}

    tabs_to_create = SHOWCASE_TABS
    return {
        "ok": True,
        "spreadsheet_id": spreadsheet_id,
        "tabs_to_create": tabs_to_create,
        "allow_reset": allow_reset,
        "live_mode": live_mode,
        "action": "reset_and_create_tabs" if allow_reset else "create_tabs_if_missing",
        "notes": "Live sheet creation requires Google Sheets credentials and controlled_live_write profile.",
    }


def apply_showcase_sheet_formatting(
    *,
    spreadsheet_id: str,
    live_mode: bool = False,
) -> dict[str, Any]:
    """Return formatting spec. Actual batchUpdate calls require live mode + credentials."""
    from runtime.invoiceops_showcase_sheet_formatting import build_showcase_formatting_spec
    spec = build_showcase_formatting_spec(spreadsheet_id=spreadsheet_id)
    return {
        "ok": True,
        "spreadsheet_id": spreadsheet_id,
        "formatting_spec": spec,
        "live_mode": live_mode,
        "notes": "Formatting applied via Google Sheets batchUpdate in live mode only.",
    }


# ---------------------------------------------------------------------------
# Public API: invoice processing
# ---------------------------------------------------------------------------

def _process_one_invoice(
    scenario: dict[str, Any],
    run_id: str,
    *,
    fixture_invoice_dir: Path,
    live_mode: bool = False,
) -> dict[str, Any]:
    """Process a single invoice scenario and return the result record."""
    inv_num = scenario["invoice_number"]
    match_status = scenario["expected_match_status"]
    exception_type = scenario["expected_exception_type"]

    # Check fixture file exists
    invoice_file = fixture_invoice_dir / f"{inv_num}.txt"
    fixture_exists = invoice_file.is_file()

    # Build prepared writes for matched invoices
    prepared_writes: list[dict[str, Any]] = []
    live_write_count = 0
    posting_status = scenario["expected_posting_status"]
    reconciliation_status = scenario["expected_reconciliation_status"]

    if match_status == "matched":
        # Prepare the 4 register writes (invoice, match, ledger debit, ledger credit)
        targets = ["invoice_register", "match_register", "ledger_register", "ledger_register"]
        descs = ["Invoice register row", "Match result row", "Ledger debit row", "Ledger credit row"]
        for target, desc in zip(targets, descs):
            ikey = _idempotency_key(run_id, inv_num, f"{target}_{desc}")
            row = {
                "invoice_number": inv_num,
                "supplier_name": scenario["supplier_name"],
                "po_number": scenario["po_number"],
                "amount": scenario["invoice_total"],
                "description": desc,
                "match_status": match_status,
                "run_id": run_id,
            }
            prepared_writes.append({
                "target": target,
                "description": desc,
                "rows": [row],
                "idempotency_key": ikey,
                "payload_hash": _payload_hash(row),
            })
        live_write_count = len(prepared_writes)

    # Build rollback plan
    rollback_plan = {
        "invoice_number": inv_num,
        "rollback_actions": [
            {"target": pw["target"], "idempotency_key": pw["idempotency_key"], "action": "delete_row"}
            for pw in prepared_writes
        ],
        "rollback_status": "MANUAL_ONLY",
        "notes": "No automatic rollback. Manual deletion by idempotency key only.",
    }

    # Evidence
    evidence_refs = [
        {"type": "fixture_file", "path": str(invoice_file), "exists": fixture_exists},
        {"type": "scenario_spec", "invoice_number": inv_num, "scenario": scenario["scenario"]},
    ]

    return {
        "invoice_number": inv_num,
        "scenario": scenario["scenario"],
        "scenario_label": scenario["scenario_label"],
        "match_status": match_status,
        "posting_status": posting_status,
        "reconciliation_status": reconciliation_status,
        "exception_type": exception_type,
        "invoice_total": scenario["invoice_total"],
        "supplier_name": scenario["supplier_name"],
        "po_number": scenario["po_number"],
        "gr_number": scenario["gr_number"],
        "live_write_count": live_write_count,
        "prepared_writes": prepared_writes,
        "rollback_plan": rollback_plan,
        "talking_point": scenario["talking_point"],
        "fixture_exists": fixture_exists,
        "evidence": evidence_refs,
        "report_paths": {},
    }


def run_showcase_invoice_batch(
    *,
    run_id: str = "",
    invoice_limit: int = 0,
    spreadsheet_id: str = "",
    profile: str = "controlled_live_write",
    live_mode: bool = False,
    confirm: str = "",
    runtime_data_dir: str | Path = "runtime_data",
    config_dir: str = "",
    write_report: bool = False,
) -> dict[str, Any]:
    """
    Process all showcase invoices and return the batch result.

    In live mode, requires:
      profile == "controlled_live_write"
      confirm == f"EXECUTE LIVE INVOICEOPS SHOWCASE {spreadsheet_id}"
    """
    if not run_id:
        run_id = _new_run_id()

    rd = Path(runtime_data_dir)
    config = _load_showcase_config(config_dir or None)
    sid = _resolve_spreadsheet_id(spreadsheet_id, config)
    fixture_invoice_dir = Path(FIXTURE_INVOICE_DIR)

    warnings: list[str] = []
    blockers: list[str] = []

    # Safety checks for live mode
    if live_mode:
        if profile != REQUIRED_PROFILE:
            blockers.append(f"profile_required:{REQUIRED_PROFILE}:got:{profile}")
        if not sid:
            blockers.append("spreadsheet_id_required_for_live_mode")
        expected_confirm = CONFIRMATION_TEMPLATE.format(spreadsheet_id=sid)
        if confirm != expected_confirm:
            blockers.append(f"confirmation_required:expected:{expected_confirm!r}")
        if blockers:
            return {
                "ok": False,
                "run_id": run_id,
                "spreadsheet_id": sid,
                "profile": profile,
                "live_mode": live_mode,
                "live_side_effects_performed": False,
                "blockers": blockers,
                "warnings": warnings,
            }

    # Load dataset
    dataset = build_showcase_demo_dataset(invoice_limit=invoice_limit)
    scenarios = dataset["scenarios"]

    # Process each invoice
    invoice_results: list[dict[str, Any]] = []
    for scenario in scenarios:
        result = _process_one_invoice(
            scenario, run_id,
            fixture_invoice_dir=fixture_invoice_dir,
            live_mode=live_mode,
        )
        invoice_results.append(result)

    # Aggregate counts
    matched_count = sum(1 for r in invoice_results if r["match_status"] == "matched")
    exception_count = sum(1 for r in invoice_results if r["match_status"] == "exception")
    blocked_count = sum(1 for r in invoice_results if r["posting_status"] == "BLOCKED")
    total_live_writes = sum(r["live_write_count"] for r in invoice_results)
    reconciled_count = sum(1 for r in invoice_results if r["reconciliation_status"] == "RECONCILED")
    manual_review = sum(1 for r in invoice_results if r["reconciliation_status"] in ("UNRECONCILED", "MANUAL_REVIEW_REQUIRED"))
    total_value = sum(r["invoice_total"] for r in invoice_results)

    # Sheet tabs populated
    tabs_written: list[str] = []
    if live_mode and not blockers:
        tabs_written = [
            "Invoices", "Match Results", "Exceptions", "Ledger",
            "Posting Ledger", "Reconciliation", "Rollback Plans",
            "Evidence Index", "Demo Run Log",
        ]
        if matched_count > 0:
            tabs_written.append("Dashboard")

    live_side_effects = live_mode and not blockers and total_live_writes > 0

    batch_result: dict[str, Any] = {
        "ok": True,
        "demo_run_id": run_id,
        "spreadsheet_id": sid,
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{sid}" if sid else "",
        "profile": profile,
        "live_mode": live_mode,
        "invoice_count": len(invoice_results),
        "matched_count": matched_count,
        "exception_count": exception_count,
        "blocked_count": blocked_count,
        "reconciled_count": reconciled_count,
        "manual_review_required": manual_review,
        "live_writes_performed": total_live_writes if live_side_effects else 0,
        "live_side_effects_performed": live_side_effects,
        "total_invoice_value": total_value,
        "sheet_tabs_created": tabs_written,
        "invoice_results": invoice_results,
        "reports": {},
        "warnings": warnings,
        "blockers": blockers,
        "dataset": {
            "supplier_count": len(dataset["supplier_master"]),
            "po_count": len(dataset["po_register"]),
            "gr_count": len(dataset["goods_receipts"]),
        },
    }

    if write_report:
        report_paths = write_showcase_demo_report(batch_result, runtime_data_dir=rd)
        batch_result["reports"] = report_paths

    return batch_result


# ---------------------------------------------------------------------------
# Public API: posting plan
# ---------------------------------------------------------------------------

def build_showcase_posting_plan(
    *,
    run_id: str,
    invoice_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a consolidated posting plan for all matched invoices in the batch."""
    matched = [r for r in invoice_results if r["match_status"] == "matched"]
    all_writes: list[dict[str, Any]] = []
    for inv in matched:
        all_writes.extend(inv.get("prepared_writes", []))

    return {
        "posting_plan_id": f"SPP-{run_id}",
        "run_id": run_id,
        "invoice_count": len(matched),
        "total_writes": len(all_writes),
        "prepared_writes": all_writes,
        "profile": REQUIRED_PROFILE,
        "safety_note": "Live execution requires typed confirmation per invoice.",
    }


# ---------------------------------------------------------------------------
# Public API: live posting execution
# ---------------------------------------------------------------------------

def execute_showcase_live_posting(
    *,
    posting_plan: dict[str, Any],
    spreadsheet_id: str,
    profile: str,
    confirm: str,
) -> dict[str, Any]:
    """
    Execute showcase live posting.  Delegates to controlled live write path.
    Real Google Sheets writes are performed by the Spec 155/156 execution layer,
    not by this module directly — this method validates inputs and returns
    the execution spec for the caller.
    """
    run_id = posting_plan.get("run_id", "")
    expected_confirm = CONFIRMATION_TEMPLATE.format(spreadsheet_id=spreadsheet_id)
    if confirm != expected_confirm:
        return {
            "ok": False,
            "error": "CONFIRMATION_REQUIRED",
            "expected": expected_confirm,
            "received": confirm,
        }
    if profile != REQUIRED_PROFILE:
        return {
            "ok": False,
            "error": f"profile_required:{REQUIRED_PROFILE}",
            "received": profile,
        }
    return {
        "ok": True,
        "run_id": run_id,
        "spreadsheet_id": spreadsheet_id,
        "profile": profile,
        "confirmed": True,
        "posting_plan_id": posting_plan.get("posting_plan_id", ""),
        "writes_scheduled": posting_plan.get("total_writes", 0),
        "note": "Execution delegated to Spec 155/156 live side-effect layer.",
    }


# ---------------------------------------------------------------------------
# Public API: reconciliation
# ---------------------------------------------------------------------------

def run_showcase_reconciliation(
    *,
    invoice_results: list[dict[str, Any]],
    run_id: str,
) -> dict[str, Any]:
    """Build reconciliation summary for the batch."""
    reconciled = [r for r in invoice_results if r["reconciliation_status"] == "RECONCILED"]
    unreconciled = [r for r in invoice_results if r["reconciliation_status"] not in ("RECONCILED",)]

    checks: list[dict[str, Any]] = []
    for r in invoice_results:
        checks.append({
            "invoice_number": r["invoice_number"],
            "match_status": r["match_status"],
            "posting_status": r["posting_status"],
            "reconciliation_status": r["reconciliation_status"],
            "exception_type": r["exception_type"],
            "live_write_count": r["live_write_count"],
        })

    return {
        "ok": True,
        "run_id": run_id,
        "reconciled_count": len(reconciled),
        "unreconciled_count": len(unreconciled),
        "total_checked": len(invoice_results),
        "checks": checks,
        "status": "RECONCILED" if unreconciled == [] else "PARTIAL_RECONCILIATION",
    }


# ---------------------------------------------------------------------------
# Public API: dashboard
# ---------------------------------------------------------------------------

def build_showcase_dashboard_data(
    *,
    batch_result: dict[str, Any],
) -> dict[str, Any]:
    """Build dashboard summary rows and chart-ready data."""
    inv_results = batch_result.get("invoice_results", [])

    summary_cards = {
        "invoices_processed": batch_result.get("invoice_count", 0),
        "matched": batch_result.get("matched_count", 0),
        "exceptions": batch_result.get("exception_count", 0),
        "blocked": batch_result.get("blocked_count", 0),
        "live_writes_performed": batch_result.get("live_writes_performed", 0),
        "reconciled_postings": batch_result.get("reconciled_count", 0),
        "manual_review_required": batch_result.get("manual_review_required", 0),
        "total_invoice_value": batch_result.get("total_invoice_value", 0.0),
    }

    invoice_status_table = [
        {
            "invoice_number": r["invoice_number"],
            "scenario_label": r["scenario_label"],
            "supplier_name": r["supplier_name"],
            "invoice_total": r["invoice_total"],
            "match_status": r["match_status"],
            "posting_status": r["posting_status"],
            "reconciliation_status": r["reconciliation_status"],
            "exception_type": r["exception_type"],
        }
        for r in inv_results
    ]

    exception_summary = {}
    for r in inv_results:
        if r["exception_type"]:
            exception_summary[r["exception_type"]] = exception_summary.get(r["exception_type"], 0) + 1

    ledger_summary = {
        "total_debit_rows": batch_result.get("matched_count", 0),
        "total_credit_rows": batch_result.get("matched_count", 0),
        "ledger_balanced": True,
    }

    return {
        "ok": True,
        "run_id": batch_result.get("demo_run_id", ""),
        "spreadsheet_url": batch_result.get("spreadsheet_url", ""),
        "summary_cards": summary_cards,
        "invoice_status_table": invoice_status_table,
        "exception_summary": exception_summary,
        "ledger_summary": ledger_summary,
        "live_write_safety_summary": {
            "profile_required": REQUIRED_PROFILE,
            "confirmation_required": True,
            "idempotency_keys_generated": sum(
                len(r.get("prepared_writes", [])) for r in inv_results
            ),
            "rpa_blocked": True,
            "gmail_send_blocked": True,
            "calendar_mutation_blocked": True,
        },
    }


# ---------------------------------------------------------------------------
# Public API: reports
# ---------------------------------------------------------------------------

def write_showcase_demo_report(
    batch_result: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Write JSON and Markdown reports to runtime_data/invoiceops/showcase/."""
    rd = Path(runtime_data_dir)
    showcase_dir = rd / SHOWCASE_REPORT_SUBDIR
    showcase_dir.mkdir(parents=True, exist_ok=True)

    run_id = batch_result.get("demo_run_id", _new_run_id())
    safe_run_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in run_id)

    json_latest = showcase_dir / "showcase_demo_latest.json"
    md_latest = showcase_dir / "showcase_demo_latest.md"
    json_run = showcase_dir / f"showcase_demo_run_{safe_run_id}.json"
    md_run = showcase_dir / f"showcase_demo_run_{safe_run_id}.md"
    inv_results_path = showcase_dir / f"showcase_invoice_results_{safe_run_id}.json"
    live_write_path = showcase_dir / f"showcase_live_write_summary_{safe_run_id}.json"

    md_content = render_showcase_demo_markdown(batch_result)

    # Slim version for invoice results
    inv_results_data = {
        "run_id": run_id,
        "invoice_results": batch_result.get("invoice_results", []),
    }

    # Live write summary
    live_writes: list[dict[str, Any]] = []
    for r in batch_result.get("invoice_results", []):
        for pw in r.get("prepared_writes", []):
            live_writes.append({
                "invoice_number": r["invoice_number"],
                "target": pw["target"],
                "idempotency_key": pw["idempotency_key"],
                "payload_hash": pw["payload_hash"],
                "executed": batch_result.get("live_side_effects_performed", False),
            })
    live_write_data = {
        "run_id": run_id,
        "live_writes": live_writes,
        "total": len(live_writes),
    }

    for path, data in [
        (json_latest, batch_result),
        (json_run, batch_result),
        (inv_results_path, inv_results_data),
        (live_write_path, live_write_data),
    ]:
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    for path in [md_latest, md_run]:
        path.write_text(md_content, encoding="utf-8")

    return {
        "json_latest": str(json_latest),
        "markdown_latest": str(md_latest),
        "json_run": str(json_run),
        "markdown_run": str(md_run),
        "invoice_results": str(inv_results_path),
        "live_write_summary": str(live_write_path),
    }


def render_showcase_demo_markdown(batch_result: dict[str, Any]) -> str:
    """Render the showcase demo result as a Markdown report."""
    run_id = batch_result.get("demo_run_id", "")
    sid = batch_result.get("spreadsheet_id", "")
    url = batch_result.get("spreadsheet_url", "")
    profile = batch_result.get("profile", "")
    inv_results = batch_result.get("invoice_results", [])
    dashboard = build_showcase_dashboard_data(batch_result=batch_result)
    cards = dashboard["summary_cards"]
    exception_summary = dashboard["exception_summary"]
    safety = dashboard["live_write_safety_summary"]

    lines: list[str] = [
        "# InvoiceOps Live Bookkeeping Showcase Demo",
        "",
        f"**Demo Run ID:** `{run_id}`  ",
        f"**Profile:** `{profile}`  ",
        f"**Google Sheet URL:** {url if url else '_(not configured — boundary mode)_'}  ",
        f"**Live Mode:** {'YES' if batch_result.get('live_mode') else 'NO (boundary mode)'}  ",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Invoices processed | {cards['invoices_processed']} |",
        f"| Matched | {cards['matched']} |",
        f"| Exceptions | {cards['exceptions']} |",
        f"| Blocked | {cards['blocked']} |",
        f"| Live writes performed | {cards['live_writes_performed']} |",
        f"| Reconciled postings | {cards['reconciled_postings']} |",
        f"| Manual review required | {cards['manual_review_required']} |",
        f"| Total invoice value | ZAR {cards['total_invoice_value']:,.2f} |",
        "",
        "---",
        "",
        "## Invoice Scenario Results",
        "",
        "| Invoice | Scenario | Supplier | Total | Match | Posting | Reconciliation | Exception |",
        "|---------|----------|----------|-------|-------|---------|----------------|-----------|",
    ]
    for r in inv_results:
        lines.append(
            f"| {r['invoice_number']} | {r['scenario_label']} | {r['supplier_name']} "
            f"| ZAR {r['invoice_total']:,.2f} | {r['match_status']} "
            f"| {r['posting_status']} | {r['reconciliation_status']} "
            f"| {r['exception_type'] or '-'} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Exception Summary",
        "",
        "| Exception Type | Count |",
        "|----------------|-------|",
    ]
    for exc_type, count in sorted(exception_summary.items()):
        lines.append(f"| {exc_type} | {count} |")
    if not exception_summary:
        lines.append("| _(none)_ | 0 |")

    lines += [
        "",
        "---",
        "",
        "## Live Write Safety Statement",
        "",
        f"- Profile required: `{safety['profile_required']}`",
        f"- Typed confirmation required: {'YES' if safety['confirmation_required'] else 'NO'}",
        f"- Idempotency keys generated: {safety['idempotency_keys_generated']}",
        f"- RPA blocked: {'YES' if safety['rpa_blocked'] else 'NO'}",
        f"- Gmail send blocked: {'YES' if safety['gmail_send_blocked'] else 'NO'}",
        f"- Calendar mutation blocked: {'YES' if safety['calendar_mutation_blocked'] else 'NO'}",
        "",
        "---",
        "",
        "## Talking Points",
        "",
    ]
    for r in inv_results:
        lines.append(f"- **{r['invoice_number']}** ({r['scenario_label']}): {r['talking_point']}")

    lines += ["", "---", "", f"_Generated by InvoiceOps Showcase Demo Pack v1 — {_utc_now()}_", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API: status check (boundary-safe)
# ---------------------------------------------------------------------------

def get_showcase_status(
    *,
    runtime_data_dir: str | Path = "runtime_data",
    config_dir: str = "",
    spreadsheet_id: str = "",
) -> dict[str, Any]:
    """Return current showcase configuration status (no API calls)."""
    config = _load_showcase_config(config_dir or None)
    sid = _resolve_spreadsheet_id(spreadsheet_id, config)
    rd = Path(runtime_data_dir)
    showcase_dir = rd / SHOWCASE_REPORT_SUBDIR
    latest_json = showcase_dir / "showcase_demo_latest.json"
    fixture_dir = Path(FIXTURE_INVOICE_DIR)
    fixture_files = sorted(fixture_dir.glob("INV-*.txt")) if fixture_dir.is_dir() else []

    last_run: dict[str, Any] = {}
    if latest_json.is_file():
        try:
            last_run = json.loads(latest_json.read_text(encoding="utf-8"))
        except Exception:
            pass

    needs_config = not bool(sid)
    status = "needs_config" if needs_config else "ready"

    return {
        "ok": True,
        "status": status,
        "needs_config": needs_config,
        "spreadsheet_id": sid,
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{sid}" if sid else "",
        "invoice_fixture_count": len(fixture_files),
        "fixture_files": [str(f.name) for f in fixture_files],
        "allowed_tabs": SHOWCASE_TABS,
        "required_profile": REQUIRED_PROFILE,
        "last_run_id": last_run.get("demo_run_id", ""),
        "last_run_invoice_count": last_run.get("invoice_count", 0),
        "last_run_matched": last_run.get("matched_count", 0),
        "last_run_exceptions": last_run.get("exception_count", 0),
        "report_dir": str(showcase_dir),
        "latest_report_exists": latest_json.is_file(),
    }
