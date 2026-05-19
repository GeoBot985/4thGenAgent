from __future__ import annotations

import re
from typing import Any

from .invoiceops_contracts import validate_exception_shape
from .tool_result_contract import build_tool_evidence

_CLASSIFY_TYPE = "invoiceops_exception_classification"
_FALLBACK_TYPE = "invoiceops_fallback_result"
_ACTION_PLAN_TYPE = "invoiceops_exception_action_plan"

_ACTIVE_PO_STATUSES = frozenset({"open", "part_received"})
_ACTIVE_RECEIPT_STATUSES = frozenset({"received", "partial"})

# Exception types that set safe_to_continue = False
_UNSAFE_CONTINUATION_TYPES = frozenset({
    "duplicate_invoice",
    "missing_po",
    "wrong_po",
    "missing_receipt",
    "supplier_mismatch",
    "quantity_mismatch",
    "bad_invoice_input",
})

_RECOMMENDED_ACTION_MAP: dict[str, str] = {
    "duplicate_invoice": "reject_duplicate",
    "bad_invoice_input": "manual_resolution",
    "missing_po": "correct_po",
    "wrong_po": "correct_po",
    "missing_receipt": "required_document",
    "supplier_mismatch": "supplier_query",
    "quantity_mismatch": "operator_review",
    "amount_mismatch": "operator_review",
    "tax_mismatch": "operator_review",
}

# Ordered by priority for recommended_action selection
_ACTION_PRIORITY = [
    "duplicate_invoice",
    "bad_invoice_input",
    "missing_po",
    "wrong_po",
    "missing_receipt",
    "supplier_mismatch",
    "quantity_mismatch",
    "amount_mismatch",
    "tax_mismatch",
]


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

def invoiceops_classify_exceptions(match_result: dict, invoice: dict) -> dict:
    mr = _unwrap_match_result(match_result)
    raw_exceptions: list = mr.get("exceptions", []) if isinstance(mr, dict) else []

    invoice_id = str(invoice.get("invoice_id", "")) if isinstance(invoice, dict) else ""
    po_number = str(invoice.get("po_number", "")) if isinstance(invoice, dict) else ""

    classified: list[dict] = []
    warnings: list[str] = []

    for i, exc in enumerate(raw_exceptions):
        if not isinstance(exc, dict):
            warnings.append(f"exceptions[{i}] is not a dict; skipped.")
            continue

        record: dict[str, Any] = {
            "exception_id": exc.get("exception_id") or f"EXC-CLASSIFY-{i + 1}",
            "exception_type": exc.get("exception_type") or "bad_invoice_input",
            "severity": exc.get("severity") or "high",
            "invoice_id": exc.get("invoice_id") or invoice_id,
            "po_number": exc.get("po_number") or po_number,
            "message": exc.get("message") or "",
            "recommended_action": exc.get("recommended_action") or _recommended_action(
                exc.get("exception_type") or "bad_invoice_input"
            ),
            "blocking": bool(exc.get("blocking", False)),
        }

        v = validate_exception_shape(record)
        for err in v.get("errors", []):
            warnings.append(f"exceptions[{i}] shape error: {err}")

        classified.append(record)

    blocking_count = sum(1 for e in classified if e.get("blocking") is True)

    evidence = build_tool_evidence(
        tool="invoiceops/classify_exceptions",
        mode="dry_run",
        source="builtin",
        operation="validation",
        input_refs=[invoice_id, po_number],
        output_ref=_CLASSIFY_TYPE,
        extra={"exception_count": len(classified), "blocking_count": blocking_count},
    )

    return {
        "ok": True,
        "type": _CLASSIFY_TYPE,
        "data": {
            "exceptions": classified,
            "exception_count": len(classified),
            "blocking_count": blocking_count,
            "classification_warnings": warnings,
        },
        "evidence": evidence,
        "error": "",
        "metadata": {
            "invoice_id": invoice_id,
            "po_number": po_number,
        },
    }


def invoiceops_search_po_fallback(invoice: dict, po_register: list[dict]) -> dict:
    if not isinstance(invoice, dict):
        invoice = {}
    inv_supplier = str(invoice.get("supplier_id", "")).strip()
    inv_po = str(invoice.get("po_number", "")).strip()
    inv_total = _num(invoice.get("invoice_total", 0))
    inv_skus = _invoice_skus(invoice)

    candidates: list[dict] = []

    for po in (po_register or []):
        if not isinstance(po, dict):
            continue
        status = str(po.get("status", "")).strip()
        if status not in _ACTIVE_PO_STATUSES:
            continue

        score = 0
        reasons: list[str] = []

        if str(po.get("supplier_id", "")).strip() == inv_supplier and inv_supplier:
            score += 3
            reasons.append("supplier_id matches")

        if _po_similar(str(po.get("po_number", "")), inv_po):
            score += 2
            reasons.append("similar PO number prefix")

        po_total = _num(po.get("po_total", 0))
        if abs(po_total - inv_total) <= 0.01 and inv_total > 0:
            score += 2
            reasons.append(f"po_total matches invoice_total ({inv_total})")

        po_skus = {str(li.get("sku", "")).strip() for li in po.get("line_items", []) if isinstance(li, dict)}
        overlap = len(inv_skus & po_skus)
        if overlap:
            sku_pts = min(overlap, 3)
            score += sku_pts
            reasons.append(f"{overlap} SKU(s) overlap")

        if status == "open":
            score += 1
            reasons.append("status=open")

        po_id = str(po.get("po_number", "")).strip() or f"po-{id(po)}"
        candidates.append({
            "candidate_id": po_id,
            "score": score,
            "reason": "; ".join(reasons) if reasons else "partial match",
            "record": dict(po),
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    confidence = _po_confidence(candidates[0]["score"] if candidates else 0)

    return _fallback_result(
        "invoiceops/search_po_fallback",
        "po",
        candidates,
        confidence,
    )


def invoiceops_search_receipt_fallback(invoice: dict, receipt_register: list[dict]) -> dict:
    if not isinstance(invoice, dict):
        invoice = {}
    inv_po = str(invoice.get("po_number", "")).strip()
    inv_supplier = str(invoice.get("supplier_id", "")).strip()
    inv_skus = _invoice_skus(invoice)

    candidates: list[dict] = []

    for receipt in (receipt_register or []):
        if not isinstance(receipt, dict):
            continue
        status = str(receipt.get("status", "")).strip()
        if status not in _ACTIVE_RECEIPT_STATUSES:
            continue

        score = 0
        reasons: list[str] = []

        if str(receipt.get("po_number", "")).strip() == inv_po and inv_po:
            score += 4
            reasons.append("po_number matches")

        if str(receipt.get("supplier_id", "")).strip() == inv_supplier and inv_supplier:
            score += 2
            reasons.append("supplier_id matches")

        receipt_skus = {
            str(li.get("sku", "")).strip()
            for li in receipt.get("line_items", [])
            if isinstance(li, dict)
        }
        overlap = len(inv_skus & receipt_skus)
        if overlap:
            sku_pts = min(overlap, 3)
            score += sku_pts
            reasons.append(f"{overlap} SKU(s) overlap")

        if status == "received":
            score += 1
            reasons.append("status=received")

        rid = str(receipt.get("receipt_id", "")).strip() or f"receipt-{id(receipt)}"
        candidates.append({
            "candidate_id": rid,
            "score": score,
            "reason": "; ".join(reasons) if reasons else "partial match",
            "record": dict(receipt),
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    confidence = _receipt_confidence(candidates[0]["score"] if candidates else 0)

    return _fallback_result(
        "invoiceops/search_receipt_fallback",
        "receipt",
        candidates,
        confidence,
    )


def invoiceops_search_supplier_fallback(invoice: dict, supplier_master: list[dict]) -> dict:
    if not isinstance(invoice, dict):
        invoice = {}
    inv_supplier_id = str(invoice.get("supplier_id", "")).strip()
    inv_supplier_name = str(invoice.get("supplier_name", "")).strip()
    inv_vat = str(invoice.get("vat_number", "")).strip()
    inv_name_norm = _normalize_name(inv_supplier_name)

    candidates: list[dict] = []

    for supplier in (supplier_master or []):
        if not isinstance(supplier, dict):
            continue

        score = 0
        reasons: list[str] = []

        sup_id = str(supplier.get("supplier_id", "")).strip()
        sup_name = str(supplier.get("supplier_name", "")).strip()
        sup_vat = str(supplier.get("vat_number", "")).strip()
        sup_name_norm = _normalize_name(sup_name)

        if sup_id and sup_id == inv_supplier_id:
            score += 4
            reasons.append("exact supplier_id match")
        elif sup_name and sup_name == inv_supplier_name and inv_supplier_name:
            score += 3
            reasons.append("exact supplier_name match")
        elif sup_name_norm and inv_name_norm and sup_name_norm == inv_name_norm:
            score += 2
            reasons.append("normalized supplier_name match")

        if sup_vat and inv_vat and sup_vat == inv_vat:
            score += 3
            reasons.append("vat_number matches")

        if score == 0:
            continue

        sid = sup_id or f"supplier-{id(supplier)}"
        candidates.append({
            "candidate_id": sid,
            "score": score,
            "reason": "; ".join(reasons),
            "record": dict(supplier),
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    confidence = _supplier_confidence(candidates[0]["score"] if candidates else 0)

    return _fallback_result(
        "invoiceops/search_supplier_fallback",
        "supplier",
        candidates,
        confidence,
    )


def invoiceops_build_exception_action_plan(
    invoice: dict,
    exceptions: list[dict],
    fallback_results: dict | None = None,
) -> dict:
    if not isinstance(invoice, dict):
        invoice = {}
    if not isinstance(exceptions, list):
        exceptions = []
    if fallback_results is not None and not isinstance(fallback_results, dict):
        fallback_results = None

    invoice_id = str(invoice.get("invoice_id", ""))
    po_number = str(invoice.get("po_number", ""))

    safe_to_continue = _determine_safe_to_continue(exceptions, fallback_results)
    recommended_action = _pick_recommended_action(exceptions)
    notes = _build_notes(exceptions, fallback_results, safe_to_continue)

    plan: dict[str, Any] = {
        "exception_action_plan_id": f"PLAN-{invoice_id}",
        "invoice_id": invoice_id,
        "safe_to_continue": safe_to_continue,
        "recommended_action": recommended_action,
        "exceptions": list(exceptions),
        "fallback_results": fallback_results or {},
        "notes": notes,
    }

    evidence = build_tool_evidence(
        tool="invoiceops/build_exception_action_plan",
        mode="dry_run",
        source="builtin",
        operation="validation",
        input_refs=[invoice_id, po_number],
        output_ref=_ACTION_PLAN_TYPE,
        extra={
            "safe_to_continue": safe_to_continue,
            "recommended_action": recommended_action,
            "exception_count": len(exceptions),
        },
    )

    return {
        "ok": True,
        "type": _ACTION_PLAN_TYPE,
        "data": {"exception_action_plan": plan},
        "evidence": evidence,
        "error": "",
        "metadata": {"safe_to_continue": safe_to_continue, "invoice_id": invoice_id},
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _unwrap_match_result(match_result: dict) -> dict:
    if not isinstance(match_result, dict):
        return {}
    if "data" in match_result and isinstance(match_result["data"], dict):
        inner = match_result["data"].get("match_result")
        if isinstance(inner, dict):
            return inner
    return match_result


def _invoice_skus(invoice: dict) -> set[str]:
    return {
        str(li.get("sku", "")).strip()
        for li in invoice.get("line_items", [])
        if isinstance(li, dict) and li.get("sku")
    }


def _po_similar(po_a: str, po_b: str) -> bool:
    if not po_a or not po_b:
        return False
    # Strip trailing numeric segment; compare remaining prefix
    prefix_a = re.sub(r"\d+$", "", po_a)
    prefix_b = re.sub(r"\d+$", "", po_b)
    return len(prefix_a) > 2 and prefix_a == prefix_b


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", name.lower())).strip()


def _num(value: Any) -> float:
    try:
        return float(value) if not isinstance(value, bool) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _po_confidence(score: int) -> str:
    if score >= 7:
        return "high"
    if score >= 4:
        return "medium"
    if score >= 2:
        return "low"
    return "none"


def _receipt_confidence(score: int) -> str:
    if score >= 6:
        return "high"
    if score >= 3:
        return "medium"
    if score >= 1:
        return "low"
    return "none"


def _supplier_confidence(score: int) -> str:
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    if score >= 1:
        return "low"
    return "none"


def _fallback_result(tool: str, fallback_type: str, candidates: list[dict], confidence: str) -> dict:
    evidence = build_tool_evidence(
        tool=tool,
        mode="dry_run",
        source="builtin",
        operation="validation",
        input_refs=[],
        output_ref=_FALLBACK_TYPE,
        extra={"candidate_count": len(candidates), "confidence": confidence},
    )
    return {
        "ok": True,
        "type": _FALLBACK_TYPE,
        "data": {
            "fallback_type": fallback_type,
            "candidates": candidates,
            "selected_candidate": None,
            "confidence": confidence,
            "requires_operator_review": True,
        },
        "evidence": evidence,
        "error": "",
        "metadata": {"fallback_type": fallback_type, "candidate_count": len(candidates)},
    }


def _determine_safe_to_continue(exceptions: list[dict], fallback_results: dict | None) -> bool:
    for exc in exceptions:
        if exc.get("blocking") is True:
            return False
        if exc.get("exception_type") in _UNSAFE_CONTINUATION_TYPES:
            return False

    # No hard blockers — check fallback confidence if fallbacks were used
    if fallback_results:
        confidences = [
            v.get("data", {}).get("confidence", "none")
            for v in fallback_results.values()
            if isinstance(v, dict)
        ]
        if confidences and not all(c == "high" for c in confidences):
            return False

    return True


def _pick_recommended_action(exceptions: list[dict]) -> str:
    exc_types = {str(e.get("exception_type", "")) for e in exceptions if isinstance(e, dict)}
    for exc_type in _ACTION_PRIORITY:
        if exc_type in exc_types:
            return _RECOMMENDED_ACTION_MAP.get(exc_type, "operator_review")
    return "operator_review"


def _build_notes(exceptions: list[dict], fallback_results: dict | None, safe_to_continue: bool) -> list[str]:
    notes: list[str] = []

    if not exceptions:
        notes.append("No exceptions present; action plan generated as precaution.")

    blocking = [e for e in exceptions if e.get("blocking") is True]
    if blocking:
        types = ", ".join(str(e.get("exception_type", "unknown")) for e in blocking)
        notes.append(f"Blocking exceptions prevent safe continuation: {types}.")

    warn_only = [e for e in exceptions if e.get("blocking") is False]
    if warn_only and not blocking:
        notes.append(f"{len(warn_only)} non-blocking exception(s) present; operator review required before proceeding.")

    if fallback_results:
        for key, result in fallback_results.items():
            if not isinstance(result, dict):
                continue
            conf = result.get("data", {}).get("confidence", "none")
            count = result.get("data", {}).get("candidates") or []
            n = len(count) if isinstance(count, list) else 0
            notes.append(f"Fallback '{key}': {n} candidate(s) found, confidence={conf!r}.")

    if not safe_to_continue:
        notes.append("Operator must resolve all blocking exceptions before any write operations.")
    else:
        notes.append("Operator review required before any write operations.")

    return notes


def _recommended_action(exc_type: str) -> str:
    return _RECOMMENDED_ACTION_MAP.get(exc_type, "operator_review")
