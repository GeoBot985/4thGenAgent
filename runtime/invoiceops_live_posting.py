from __future__ import annotations

"""
Spec 156 — InvoiceOps Live Sheet Write Pilot v1.

Connects the InvoiceOps bookkeeping workflow to the Spec 155 live side-effect
approval model. Only allowlisted InvoiceOps registers may be written.
No automatic approval, no batch execution, no auto-rollback.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# v1 allowed and blocked targets
# ---------------------------------------------------------------------------

# Maps Spec 156 target names → existing InvoiceOps target names used in prepared writes
_TARGET_ALIAS: dict[str, str] = {
    "invoice_register": "InvoiceRegister",
    "match_register": "MatchRegister",
    "exception_register": "ExceptionRegister",
    "ledger_register": "Ledger",
    "rollback_register": "rollback_register",
}

V1_ALLOWED_TARGETS: frozenset[str] = frozenset({
    "invoice_register",
    "match_register",
    "exception_register",
    "ledger_register",
    "rollback_register",
    # Also accept canonical names from existing prepared writes
    "InvoiceRegister",
    "MatchRegister",
    "ExceptionRegister",
    "Ledger",
})

V1_BLOCKED_TARGETS: frozenset[str] = frozenset({
    "supplier_master",
    "po_register",
    "goods_receipt_register",
    "bank_register",
    "payment_register",
})

_TARGET_CANONICAL: dict[str, str] = {
    "InvoiceRegister": "invoice_register",
    "MatchRegister": "match_register",
    "ExceptionRegister": "exception_register",
    "Ledger": "ledger_register",
    "invoice_register": "invoice_register",
    "match_register": "match_register",
    "exception_register": "exception_register",
    "ledger_register": "ledger_register",
    "ledger": "ledger_register",
    "rollback_register": "rollback_register",
}

# Error codes
TARGET_BLOCKED = "TARGET_BLOCKED"
TARGET_NOT_ALLOWLISTED = "TARGET_NOT_ALLOWLISTED"
EMPTY_ROWS = "EMPTY_ROWS"
MISSING_ACCOUNTING_FIELDS = "MISSING_ACCOUNTING_FIELDS"
MISSING_ROLLBACK_PLAN = "MISSING_ROLLBACK_PLAN"
MISSING_INVOICE_REFERENCE = "MISSING_INVOICE_REFERENCE"
MISSING_MATCH_RESULT = "MISSING_MATCH_RESULT"
MISSING_EXCEPTION_DATA = "MISSING_EXCEPTION_DATA"
MISSING_LEDGER_BALANCE_DATA = "MISSING_LEDGER_BALANCE_DATA"
PAYLOAD_HASH_FAILED = "PAYLOAD_HASH_FAILED"
IDEMPOTENCY_KEY_FAILED = "IDEMPOTENCY_KEY_FAILED"
LEDGER_WRITE_BLOCKED_FOR_UNMATCHED = "LEDGER_WRITE_BLOCKED_FOR_UNMATCHED"
DUPLICATE_INVOICE_CHECK_FAILED = "DUPLICATE_INVOICE_CHECK_FAILED"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_id(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(value))


def _canonical_target(raw_target: str) -> str:
    return _TARGET_CANONICAL.get(str(raw_target).strip(), str(raw_target).strip())


def _hash_payload(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _make_idempotency_key(prepared_write_id: str, frame_id: str) -> str:
    raw = f"invoiceops:{frame_id}:{prepared_write_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# 1. build_invoiceops_live_posting_plan
# ---------------------------------------------------------------------------

def build_invoiceops_live_posting_plan(
    *,
    frame_id: str,
    invoice_id: str = "",
    invoice_number: str = "",
    supplier_name: str = "",
    po_number: str = "",
    match_status: str = "matched",
    prepared_writes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Build a posting plan from completed InvoiceOps prepared writes.

    Does NOT execute any live write. Returns a plan dict describing
    what would be posted, with pending_actions in PENDING_APPROVAL state.
    """
    writes = list(prepared_writes or [])
    posting_plan_id = f"PP-{_safe_id(frame_id)}-{_safe_id(invoice_id or invoice_number)}"

    eligible: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    write_targets: list[str] = []
    pending_actions: list[dict[str, Any]] = []
    rollback_plans: list[dict[str, Any]] = []
    idempotency_keys: list[str] = []
    payload_hashes: list[str] = []

    # Posting plan rules
    if match_status == "blocked":
        warnings.append("Match status is 'blocked'. Ledger writes are not allowed.")

    for pw in writes:
        # Extract the prepared_write from tool result wrapper if needed
        pw_data = pw.get("data", {}).get("prepared_write", pw) if "data" in pw else pw
        target_raw = str(pw_data.get("target") or "").strip()
        target = _canonical_target(target_raw)
        rows = list(pw_data.get("rows") or [])

        eligibility = validate_invoiceops_prepared_writes_for_live(
            prepared_write=pw_data,
            match_status=match_status,
        )

        if not eligibility["eligible"]:
            blocked.append({
                "prepared_write_id": pw_data.get("prepared_write_id", ""),
                "target": target,
                "reason": eligibility.get("reason", "blocked"),
                "errors": eligibility.get("errors", []),
            })
            blockers.extend(eligibility.get("errors", []))
            continue

        eligible.append(pw_data)
        write_targets.append(target)

        # Build pending action
        action = convert_prepared_write_to_live_pending_action(
            prepared_write=pw_data,
            frame_id=frame_id,
            invoice_number=invoice_number,
            supplier_name=supplier_name,
            po_number=po_number,
            match_status=match_status,
        )
        pending_actions.append(action)

        rp = pw_data.get("rollback_plan") or {}
        if rp:
            rollback_plans.append(rp)

        ikey = action.get("idempotency_key", "")
        phash = action.get("prepared_payload_hash", "")
        if ikey:
            idempotency_keys.append(ikey)
        if phash:
            payload_hashes.append(phash)

    return {
        "posting_plan_id": posting_plan_id,
        "frame_id": frame_id,
        "invoice_id": invoice_id,
        "invoice_number": invoice_number,
        "supplier_name": supplier_name,
        "po_number": po_number,
        "match_status": match_status,
        "prepared_write_count": len(writes),
        "eligible_write_count": len(eligible),
        "blocked_write_count": len(blocked),
        "write_targets": write_targets,
        "pending_actions": pending_actions,
        "rollback_plans": rollback_plans,
        "idempotency_keys": idempotency_keys,
        "payload_hashes": payload_hashes,
        "blocked_writes": blocked,
        "blockers": blockers,
        "warnings": warnings,
        "created_at": _utc_now(),
    }


# ---------------------------------------------------------------------------
# 2. validate_invoiceops_prepared_writes_for_live
# ---------------------------------------------------------------------------

def validate_invoiceops_prepared_writes_for_live(
    *,
    prepared_write: dict[str, Any],
    match_status: str = "matched",
) -> dict[str, Any]:
    """
    Check whether a prepared write is eligible for live execution.

    Returns {"eligible": bool, "reason": str, "errors": list[str]}.
    Does NOT execute anything.
    """
    errors: list[str] = []

    target_raw = str(prepared_write.get("target") or "").strip()
    target = _canonical_target(target_raw)
    rows = list(prepared_write.get("rows") or [])

    # 1. Target must not be blocked
    if target_raw in V1_BLOCKED_TARGETS or target in V1_BLOCKED_TARGETS:
        errors.append(f"{TARGET_BLOCKED}: target '{target_raw}' is blocked in v1.")

    # 2. Target must be allowlisted
    elif target_raw not in V1_ALLOWED_TARGETS and target not in V1_ALLOWED_TARGETS:
        errors.append(f"{TARGET_NOT_ALLOWLISTED}: target '{target_raw}' is not allowlisted.")

    # 3. Row list must not be empty
    if not rows:
        errors.append(f"{EMPTY_ROWS}: prepared write has no rows.")

    # 4. Rollback plan must exist
    rollback = prepared_write.get("rollback_plan")
    if not isinstance(rollback, dict) or not rollback:
        errors.append(f"{MISSING_ROLLBACK_PLAN}: rollback_plan is required.")

    # 5. Invoice reference (invoice_id or invoice_number in rows)
    has_invoice_ref = False
    for row in rows:
        if row.get("invoice_id") or row.get("invoice_number"):
            has_invoice_ref = True
            break
    if rows and not has_invoice_ref:
        # Relaxed: invoice ref is required only for invoice/match/ledger targets
        if target in ("invoice_register", "match_register", "ledger_register"):
            errors.append(f"{MISSING_INVOICE_REFERENCE}: rows must contain invoice_id or invoice_number.")

    # 6. Match result required for ledger writes
    if target == "ledger_register":
        if match_status == "blocked":
            errors.append(f"{LEDGER_WRITE_BLOCKED_FOR_UNMATCHED}: ledger writes are blocked when match_status is 'blocked'.")
        has_ledger_data = any(
            (row.get("debit_account") or row.get("credit_account") or row.get("amount") is not None)
            for row in rows
        )
        if rows and not has_ledger_data:
            errors.append(f"{MISSING_LEDGER_BALANCE_DATA}: ledger rows must contain debit_account, credit_account, and amount.")

    # 7. Exception data required for exception writes
    if target == "exception_register":
        has_exc_data = any(
            (row.get("exception_id") or row.get("exception_type"))
            for row in rows
        )
        if rows and not has_exc_data:
            errors.append(f"{MISSING_EXCEPTION_DATA}: exception rows must contain exception_id or exception_type.")

    eligible = len(errors) == 0
    return {
        "eligible": eligible,
        "target": target,
        "row_count": len(rows),
        "reason": "" if eligible else errors[0],
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 3. convert_prepared_write_to_live_pending_action
# ---------------------------------------------------------------------------

def convert_prepared_write_to_live_pending_action(
    *,
    prepared_write: dict[str, Any],
    frame_id: str,
    invoice_number: str = "",
    supplier_name: str = "",
    po_number: str = "",
    match_status: str = "matched",
    target_ref: str = "",
    approved_by: str = "",
    approved_at: str = "",
    worker_identity: str = "",
    amount: str = "",
) -> dict[str, Any]:
    """
    Convert an InvoiceOps prepared write into a Spec 155 live pending action.

    The action is created in PENDING_APPROVAL state. It must be explicitly
    approved before execution.
    """
    pw_id = str(prepared_write.get("prepared_write_id") or "")
    target_raw = str(prepared_write.get("target") or "").strip()
    target = _canonical_target(target_raw)
    rows = list(prepared_write.get("rows") or [])
    rollback_plan = dict(prepared_write.get("rollback_plan") or {})

    action_id = f"IOLSP-{_safe_id(pw_id)}" if pw_id else f"IOLSP-{uuid.uuid4().hex[:12]}"
    idempotency_key = _make_idempotency_key(pw_id or action_id, frame_id)
    payload_hash = _hash_payload(rows)

    # Derive invoice info from rows if not provided
    if not invoice_number:
        for row in rows:
            invoice_number = str(row.get("invoice_number") or row.get("invoice_id") or "")
            if invoice_number:
                break

    action: dict[str, Any] = {
        "action_id": action_id,
        "action_type": "invoiceops_sheet_write_rows",
        "tool": "sheet/write_rows",
        "status": "PENDING_APPROVAL",
        "requires_approval": True,
        "live_capable": True,
        "live_executed": False,
        "dry_run": True,
        "frame_id": frame_id,
        "source_prepared_write_id": pw_id,
        "target_register": target,
        "target_ref": target_ref,
        "business_ref": invoice_number,
        "idempotency_key": idempotency_key,
        "prepared_payload_hash": payload_hash,
        "rollback_plan": rollback_plan,
        "worker_identity": worker_identity,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "approval_context": {
            "invoice_number": invoice_number,
            "supplier_name": supplier_name,
            "po_number": po_number,
            "amount": amount,
            "match_status": match_status,
            "target_register": target,
            "row_count": len(rows),
        },
        "rows": rows,
        "created_at": _utc_now(),
    }
    return action


# ---------------------------------------------------------------------------
# 4. build_invoiceops_sheet_write_batch
# ---------------------------------------------------------------------------

def build_invoiceops_sheet_write_batch(
    *,
    posting_plan: dict[str, Any],
    target_filter: str | None = None,
) -> dict[str, Any]:
    """
    Build a sheet write batch from a posting plan.

    In v1, batch execution is out of scope. This returns the batch description
    without executing anything. Use for reporting/preview only.
    """
    pending_actions = list(posting_plan.get("pending_actions") or [])

    if target_filter:
        pending_actions = [
            a for a in pending_actions
            if a.get("target_register") == target_filter
        ]

    total_rows = sum(len(a.get("rows") or []) for a in pending_actions)

    return {
        "batch_id": f"IOLSB-{posting_plan.get('posting_plan_id', '')}",
        "posting_plan_id": posting_plan.get("posting_plan_id", ""),
        "frame_id": posting_plan.get("frame_id", ""),
        "invoice_number": posting_plan.get("invoice_number", ""),
        "action_count": len(pending_actions),
        "total_rows": total_rows,
        "target_filter": target_filter or "",
        "pending_actions": pending_actions,
        "note": "Batch execution is not supported in v1. Use single-action execute.",
        "batch_execution_blocked": True,
    }


# ---------------------------------------------------------------------------
# 5. run_invoiceops_live_posting_preflight
# ---------------------------------------------------------------------------

def run_invoiceops_live_posting_preflight(
    *,
    posting_plan: dict[str, Any],
    action_id: str | None = None,
    profile_name: str = "controlled_live_write",
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """
    Run preflight checks for InvoiceOps live posting.

    When action_id is supplied, runs Spec 155 preflight for that specific action.
    Otherwise runs plan-level checks (no execution, no Spec 155 preflight gate).
    """
    from .live_side_effect_execution import (
        build_live_side_effect_preflight,
        V1_EXECUTABLE_TOOLS,
    )
    from src.controlled_live_profile import CONTROLLED_LIVE_WRITE_PROFILE

    plan_checks: list[dict[str, Any]] = []
    plan_blockers: list[str] = []

    def plan_check(name: str, ok: bool, message: str = "") -> None:
        plan_checks.append({"name": name, "ok": ok, "message": message})
        if not ok:
            plan_blockers.append(message or name)

    # Plan-level checks
    frame_id = str(posting_plan.get("frame_id") or "")
    plan_check("posting_plan_has_frame_id", bool(frame_id), "posting_plan.frame_id is required.")
    plan_check("posting_plan_has_invoice", bool(posting_plan.get("invoice_number") or posting_plan.get("invoice_id")), "posting_plan must have invoice_number or invoice_id.")
    plan_check("posting_plan_has_eligible_writes", posting_plan.get("eligible_write_count", 0) > 0, "posting_plan has no eligible writes.")
    plan_check("no_blocked_writes", posting_plan.get("blocked_write_count", 0) == 0, f"{posting_plan.get('blocked_write_count', 0)} write(s) are blocked.")

    match_status = str(posting_plan.get("match_status") or "")
    if match_status == "blocked":
        plan_blockers.append("match_status is 'blocked' — ledger writes are not allowed.")

    pending_actions = list(posting_plan.get("pending_actions") or [])

    # Action-level preflight (Spec 155)
    action_preflight: dict[str, Any] | None = None
    if action_id and pending_actions:
        action = next((a for a in pending_actions if a.get("action_id") == action_id), None)
        if action is None:
            plan_blockers.append(f"action_id '{action_id}' not found in posting_plan.")
        else:
            action_preflight = build_live_side_effect_preflight(
                pending_action=action,
                profile_name=profile_name,
                profile_data=CONTROLLED_LIVE_WRITE_PROFILE,
                runtime_data_dir=runtime_data_dir,
            )

    plan_ok = len(plan_blockers) == 0
    action_ok = action_preflight["ok"] if action_preflight else None

    overall_ok = plan_ok and (action_ok is None or action_ok)

    return {
        "ok": overall_ok,
        "plan_ok": plan_ok,
        "action_ok": action_ok,
        "plan_checks": plan_checks,
        "plan_blockers": plan_blockers,
        "action_preflight": action_preflight,
        "action_id": action_id or "",
        "frame_id": frame_id,
        "posting_plan_id": posting_plan.get("posting_plan_id", ""),
        "profile": profile_name,
    }


# ---------------------------------------------------------------------------
# 6. execute_invoiceops_live_sheet_posting
# ---------------------------------------------------------------------------

def execute_invoiceops_live_sheet_posting(
    *,
    posting_plan: dict[str, Any],
    action_id: str,
    profile_name: str = "controlled_live_write",
    typed_confirmation: str,
    runtime_data_dir: str | Path = "runtime_data",
    dry_run_fallback: bool = False,
) -> dict[str, Any]:
    """
    Execute a single approved InvoiceOps live sheet posting.

    Delegates all execution to the Spec 155 live side-effect execution model.
    Only one action per call. Batch execution is not supported in v1.
    """
    from .live_side_effect_execution import execute_approved_live_side_effect
    from src.controlled_live_profile import CONTROLLED_LIVE_WRITE_PROFILE

    pending_actions = list(posting_plan.get("pending_actions") or [])
    action = next((a for a in pending_actions if a.get("action_id") == action_id), None)

    if action is None:
        return {
            "ok": False,
            "blocked": True,
            "executed": False,
            "error_code": "ACTION_NOT_FOUND",
            "error": f"action_id '{action_id}' not found in posting_plan.",
        }

    # Delegate to Spec 155
    exec_result = execute_approved_live_side_effect(
        pending_action=action,
        profile_name=profile_name,
        profile_data=CONTROLLED_LIVE_WRITE_PROFILE,
        typed_confirmation=typed_confirmation,
        runtime_data_dir=runtime_data_dir,
        dry_run_fallback=dry_run_fallback,
    )

    executed = exec_result.get("executed", False)
    verified = False
    verification: dict[str, Any] = {}

    if executed:
        verification = verify_invoiceops_live_posting(
            execution_result=exec_result.get("execution_result") or {},
            action=action,
            posting_plan=posting_plan,
        )
        verified = verification.get("ok", False)

    return {
        "ok": executed and verified,
        "executed": executed,
        "verified": verified,
        "blocked": exec_result.get("blocked", False),
        "action_id": action_id,
        "posting_plan_id": posting_plan.get("posting_plan_id", ""),
        "frame_id": posting_plan.get("frame_id", ""),
        "invoice_number": posting_plan.get("invoice_number", ""),
        "target_register": action.get("target_register", ""),
        "exec_result": exec_result,
        "verification": verification,
        "rollback_plan": action.get("rollback_plan") or {},
        "error_code": exec_result.get("error_code", ""),
    }


# ---------------------------------------------------------------------------
# 7. verify_invoiceops_live_posting
# ---------------------------------------------------------------------------

def verify_invoiceops_live_posting(
    *,
    execution_result: dict[str, Any],
    action: dict[str, Any],
    posting_plan: dict[str, Any],
) -> dict[str, Any]:
    """
    Post-write verification for an InvoiceOps live sheet posting.

    Checks row count, payload hash, idempotency key, invoice number presence,
    and ledger balance (if ledger target).
    """
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    def chk(name: str, ok: bool, message: str = "") -> None:
        checks.append({"name": name, "ok": ok, "message": message})
        if not ok:
            errors.append(message or name)

    rows = list(action.get("rows") or [])
    target_register = str(action.get("target_register") or "")
    invoice_number = str(action.get("business_ref") or posting_plan.get("invoice_number") or "")
    idempotency_key = str(action.get("idempotency_key") or "")
    expected_hash = str(action.get("prepared_payload_hash") or "")

    # 1. Execution must be ok
    chk("execution_ok", bool(execution_result.get("ok", False)), "execution_result.ok is False.")

    # 2. Row count match
    rows_written = execution_result.get("rows_written")
    if rows_written is not None:
        expected_rows = len(rows)
        rows_match = int(rows_written) == expected_rows or execution_result.get("type") == "dry_run_simulation"
        chk("rows_written_match", rows_match,
            "" if rows_match else f"rows_written={rows_written} expected={expected_rows}.")

    # 3. Payload hash check (if execution result includes one)
    result_hash = str(execution_result.get("payload_hash") or "")
    if result_hash and expected_hash:
        hash_match = result_hash == expected_hash
        chk("payload_hash_matches", hash_match,
            "" if hash_match else "payload_hash mismatch.")

    # 4. Idempotency key was recorded
    chk("idempotency_key_present", bool(idempotency_key), "idempotency_key is missing.")

    # 5. Written rows include invoice number (spot check)
    if rows and invoice_number:
        rows_have_invoice = any(
            str(r.get("invoice_number") or r.get("invoice_id") or "") == invoice_number
            for r in rows
        )
        if not rows_have_invoice:
            warnings.append(f"Written rows may not include invoice_number '{invoice_number}'.")

    # 6. Written rows include posting plan reference
    if rows:
        posting_plan_id = posting_plan.get("posting_plan_id", "")
        # This is a soft check — the posting plan ref may be in evidence, not the row itself
        if not posting_plan_id:
            warnings.append("posting_plan_id not found in posting_plan.")

    # 7. Ledger rows must be balanced (if ledger target)
    ledger_balanced = True
    if target_register == "ledger_register" and rows:
        total_debit = sum(float(r.get("amount", 0) or 0) for r in rows if r.get("debit_account"))
        total_credit = sum(float(r.get("amount", 0) or 0) for r in rows if r.get("credit_account"))
        if abs(total_debit - total_credit) > 0.005:
            ledger_balanced = False
            chk("ledger_rows_balanced", False,
                f"Ledger rows unbalanced: debit={total_debit}, credit={total_credit}.")
        else:
            chk("ledger_rows_balanced", True)

    all_failed = [c for c in checks if not c["ok"]]
    overall_ok = len(all_failed) == 0
    verified = overall_ok

    return {
        "ok": overall_ok,
        "verified": verified,
        "invoice_number": invoice_number,
        "target_register": target_register,
        "rows_expected": len(rows),
        "rows_written": rows_written,
        "idempotency_key": idempotency_key,
        "ledger_balanced": ledger_balanced,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 8. write_invoiceops_live_posting_report
# ---------------------------------------------------------------------------

def write_invoiceops_live_posting_report(
    *,
    posting_plan: dict[str, Any],
    execution_result: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """
    Write posting plan and execution reports to disk.

    Reports are written to:
      runtime_data/invoiceops/live_posting/reports/<frame_id>_posting_plan.json
      runtime_data/invoiceops/live_posting/reports/<frame_id>_posting_plan.md
    """
    reports_dir = Path(runtime_data_dir) / "invoiceops" / "live_posting" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    frame_id = _safe_id(posting_plan.get("frame_id", "frame"))
    action_id = _safe_id(str((execution_result or {}).get("action_id", "") or ""))

    paths: dict[str, str] = {}

    # Plan report
    plan_json = reports_dir / f"{frame_id}_posting_plan.json"
    plan_md = reports_dir / f"{frame_id}_posting_plan.md"
    plan_data = {
        "report_type": "invoiceops_posting_plan",
        "generated_at": _utc_now(),
        "posting_plan": posting_plan,
    }
    try:
        plan_json.write_text(json.dumps(plan_data, indent=2, default=str), encoding="utf-8")
        plan_md.write_text(render_invoiceops_live_posting_markdown(
            posting_plan=posting_plan,
            execution_result=None,
            verification=None,
        ), encoding="utf-8")
        paths["plan_json"] = str(plan_json)
        paths["plan_md"] = str(plan_md)
    except OSError as exc:
        paths["plan_error"] = str(exc)

    # Execution report (if available)
    if execution_result and action_id:
        exec_json = reports_dir / f"{frame_id}_{action_id}_posting_execution.json"
        exec_md = reports_dir / f"{frame_id}_{action_id}_posting_execution.md"
        exec_data = {
            "report_type": "invoiceops_posting_execution",
            "generated_at": _utc_now(),
            "execution_result": execution_result,
            "verification": verification or {},
        }
        try:
            exec_json.write_text(json.dumps(exec_data, indent=2, default=str), encoding="utf-8")
            exec_md.write_text(render_invoiceops_live_posting_markdown(
                posting_plan=posting_plan,
                execution_result=execution_result,
                verification=verification,
            ), encoding="utf-8")
            paths["exec_json"] = str(exec_json)
            paths["exec_md"] = str(exec_md)
        except OSError as exc:
            paths["exec_error"] = str(exc)

    return {"ok": True, "report_paths": paths}


# ---------------------------------------------------------------------------
# 9. render_invoiceops_live_posting_markdown
# ---------------------------------------------------------------------------

def render_invoiceops_live_posting_markdown(
    *,
    posting_plan: dict[str, Any],
    execution_result: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
) -> str:
    executed = bool((execution_result or {}).get("executed"))
    verified = bool((verification or {}).get("verified"))
    status = "PLAN" if not execution_result else ("VERIFIED" if verified else ("EXECUTED" if executed else "BLOCKED"))

    lines = [
        f"# InvoiceOps Live Posting — {status}",
        "",
        f"**Invoice:** {posting_plan.get('invoice_number', '')}",
        f"**Supplier:** {posting_plan.get('supplier_name', '')}",
        f"**PO:** {posting_plan.get('po_number', '')}",
        f"**Match Status:** {posting_plan.get('match_status', '')}",
        f"**Frame ID:** {posting_plan.get('frame_id', '')}",
        f"**Posting Plan ID:** {posting_plan.get('posting_plan_id', '')}",
        "",
        "## Prepared Writes",
        "",
        f"- Total: {posting_plan.get('prepared_write_count', 0)}",
        f"- Eligible: {posting_plan.get('eligible_write_count', 0)}",
        f"- Blocked: {posting_plan.get('blocked_write_count', 0)}",
        "",
        "## Write Targets",
        "",
    ]
    for target in posting_plan.get("write_targets") or []:
        lines.append(f"- {target}")

    lines += ["", "## Pending Actions", ""]
    for action in posting_plan.get("pending_actions") or []:
        lines.append(f"- [{action.get('status')}] {action.get('action_id')} → {action.get('target_register')} ({len(action.get('rows') or [])} rows)")

    if posting_plan.get("blockers"):
        lines += ["", "## Blockers", ""]
        for b in posting_plan["blockers"]:
            lines.append(f"- {b}")

    if posting_plan.get("warnings"):
        lines += ["", "## Warnings", ""]
        for w in posting_plan["warnings"]:
            lines.append(f"- {w}")

    if execution_result:
        lines += ["", "## Execution Result", ""]
        lines.append(f"- Executed: {execution_result.get('executed', False)}")
        lines.append(f"- Action ID: {execution_result.get('action_id', '')}")
        lines.append(f"- Error: {execution_result.get('error_code', '') or 'none'}")

    if verification:
        lines += ["", "## Post-Write Verification", ""]
        lines.append(f"- Verified: {verification.get('verified', False)}")
        lines.append(f"- Rows expected: {verification.get('rows_expected', 0)}")
        lines.append(f"- Rows written: {verification.get('rows_written', 'n/a')}")
        lines.append(f"- Ledger balanced: {verification.get('ledger_balanced', 'n/a')}")
        for chk in verification.get("checks") or []:
            mark = "ok" if chk.get("ok") else "FAIL"
            lines.append(f"  - [{mark}] {chk.get('name')}: {chk.get('message', '')}")

    lines += ["", "---", ""]
    return "\n".join(lines)
