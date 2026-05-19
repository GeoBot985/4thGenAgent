from __future__ import annotations

import json
from pathlib import Path

import runtime.invoiceops_exception_tools as _mod
from runtime.invoiceops_exception_tools import (
    invoiceops_build_exception_action_plan,
    invoiceops_classify_exceptions,
    invoiceops_search_po_fallback,
    invoiceops_search_receipt_fallback,
    invoiceops_search_supplier_fallback,
)
from runtime.invoiceops_contracts import validate_exception_shape
from runtime.invoiceops_matching_tools import invoiceops_match_three_way

_FIXTURE_BASE = Path("tests/fixtures/invoiceops/exceptions")

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_BASE_INVOICE = {
    "invoice_id": "INV-INV-2024-001",
    "supplier_id": "SUP-001",
    "supplier_name": "Acme Supplies (Pty) Ltd",
    "invoice_number": "INV-2024-001",
    "invoice_date": "2024-01-15",
    "po_number": "PO-2024-042",
    "currency": "ZAR",
    "subtotal": 3000.0,
    "tax_total": 450.0,
    "invoice_total": 3450.0,
    "line_items": [
        {"line_no": 1, "sku": "SKU-WIDGET-A", "description": "Widget A", "quantity": 10.0, "unit_price": 150.0, "tax_amount": 0.0, "line_total": 1500.0},
        {"line_no": 2, "sku": "SKU-WIDGET-B", "description": "Widget B", "quantity": 5.0,  "unit_price": 200.0, "tax_amount": 0.0, "line_total": 1000.0},
        {"line_no": 3, "sku": "SKU-CABLE-01", "description": "Cable 1m",  "quantity": 20.0, "unit_price":  25.0, "tax_amount": 0.0, "line_total":  500.0},
    ],
}

_BASE_PO = {
    "po_number": "PO-2024-042",
    "supplier_id": "SUP-001",
    "supplier_name": "Acme Supplies (Pty) Ltd",
    "status": "open",
    "currency": "ZAR",
    "po_total": 3450.0,
    "line_items": [
        {"line_no": 1, "sku": "SKU-WIDGET-A", "description": "Widget A", "ordered_quantity": 10.0, "unit_price": 150.0, "line_total": 1500.0},
        {"line_no": 2, "sku": "SKU-WIDGET-B", "description": "Widget B", "ordered_quantity":  5.0, "unit_price": 200.0, "line_total": 1000.0},
        {"line_no": 3, "sku": "SKU-CABLE-01", "description": "Cable 1m",  "ordered_quantity": 20.0, "unit_price":  25.0, "line_total":  500.0},
    ],
}

_BASE_RECEIPT = {
    "receipt_id": "GRN-001",
    "po_number": "PO-2024-042",
    "supplier_id": "SUP-001",
    "receipt_date": "2024-01-10",
    "status": "received",
    "line_items": [
        {"line_no": 1, "sku": "SKU-WIDGET-A", "description": "Widget A", "received_quantity": 10.0},
        {"line_no": 2, "sku": "SKU-WIDGET-B", "description": "Widget B", "received_quantity":  5.0},
        {"line_no": 3, "sku": "SKU-CABLE-01", "description": "Cable 1m",  "received_quantity": 20.0},
    ],
}


def _make_exception(
    exception_type: str,
    blocking: bool = True,
    severity: str = "blocker",
    exception_id: str = "EXC-001",
) -> dict:
    return {
        "exception_id": exception_id,
        "exception_type": exception_type,
        "severity": severity,
        "invoice_id": "INV-INV-2024-001",
        "po_number": "PO-2024-042",
        "message": f"Test exception: {exception_type}",
        "recommended_action": "Review before proceeding.",
        "blocking": blocking,
    }


# ---------------------------------------------------------------------------
# classify_exceptions — happy path (no exceptions)
# ---------------------------------------------------------------------------

def test_classify_empty_match_result_ok() -> None:
    r = invoiceops_classify_exceptions({}, _BASE_INVOICE)
    assert r["ok"] is True


def test_classify_empty_returns_zero_exceptions() -> None:
    r = invoiceops_classify_exceptions({}, _BASE_INVOICE)
    assert r["data"]["exception_count"] == 0
    assert r["data"]["exceptions"] == []


def test_classify_result_type() -> None:
    r = invoiceops_classify_exceptions({}, _BASE_INVOICE)
    assert r["type"] == "invoiceops_exception_classification"


# ---------------------------------------------------------------------------
# classify_exceptions — each exception type
# ---------------------------------------------------------------------------

def _classify_one(exc_type: str, blocking: bool = True) -> dict:
    exc = _make_exception(exc_type, blocking=blocking)
    match_result = {"exceptions": [exc]}
    r = invoiceops_classify_exceptions(match_result, _BASE_INVOICE)
    assert r["data"]["exception_count"] == 1
    return r["data"]["exceptions"][0]


def test_classify_wrong_po() -> None:
    exc = _classify_one("wrong_po")
    assert exc["exception_type"] == "wrong_po"


def test_classify_missing_po() -> None:
    exc = _classify_one("missing_po")
    assert exc["exception_type"] == "missing_po"


def test_classify_missing_receipt() -> None:
    exc = _classify_one("missing_receipt")
    assert exc["exception_type"] == "missing_receipt"


def test_classify_duplicate_invoice() -> None:
    exc = _classify_one("duplicate_invoice")
    assert exc["exception_type"] == "duplicate_invoice"


def test_classify_supplier_mismatch() -> None:
    exc = _classify_one("supplier_mismatch")
    assert exc["exception_type"] == "supplier_mismatch"


def test_classify_amount_mismatch() -> None:
    exc = _classify_one("amount_mismatch", blocking=True)
    assert exc["exception_type"] == "amount_mismatch"


def test_classify_tax_mismatch() -> None:
    exc = _classify_one("tax_mismatch", blocking=False)
    assert exc["exception_type"] == "tax_mismatch"


def test_classify_quantity_mismatch() -> None:
    exc = _classify_one("quantity_mismatch")
    assert exc["exception_type"] == "quantity_mismatch"


def test_classify_bad_invoice_input() -> None:
    exc = _classify_one("bad_invoice_input")
    assert exc["exception_type"] == "bad_invoice_input"


def test_classify_exceptions_pass_shape_validation() -> None:
    for exc_type in (
        "wrong_po", "missing_po", "missing_receipt", "duplicate_invoice",
        "supplier_mismatch", "amount_mismatch", "tax_mismatch",
        "quantity_mismatch", "bad_invoice_input",
    ):
        exc = _make_exception(exc_type)
        r = invoiceops_classify_exceptions({"exceptions": [exc]}, _BASE_INVOICE)
        classified = r["data"]["exceptions"][0]
        v = validate_exception_shape(classified)
        assert v["ok"] is True, f"{exc_type} shape invalid: {v['errors']}"


def test_classify_blocking_count() -> None:
    excs = [
        _make_exception("missing_po", blocking=True,  exception_id="EXC-001"),
        _make_exception("tax_mismatch", blocking=False, exception_id="EXC-002"),
    ]
    r = invoiceops_classify_exceptions({"exceptions": excs}, _BASE_INVOICE)
    assert r["data"]["blocking_count"] == 1


def test_classify_fills_missing_invoice_id() -> None:
    exc = {
        "exception_id": "EXC-001",
        "exception_type": "missing_po",
        "severity": "blocker",
        "invoice_id": "",
        "po_number": "PO-2024-042",
        "message": "No PO.",
        "recommended_action": "Fix it.",
        "blocking": True,
    }
    r = invoiceops_classify_exceptions({"exceptions": [exc]}, _BASE_INVOICE)
    classified = r["data"]["exceptions"][0]
    assert classified["invoice_id"] == _BASE_INVOICE["invoice_id"]


def test_classify_from_full_toolresult() -> None:
    # classify_exceptions should handle the full ToolResult dict from match_three_way
    mr = invoiceops_match_three_way(
        _BASE_INVOICE,
        {**_BASE_PO, "supplier_id": "SUP-WRONG"},  # supplier mismatch → blocked
        _BASE_RECEIPT,
        [],
    )
    r = invoiceops_classify_exceptions(mr, _BASE_INVOICE)
    assert r["ok"] is True
    assert r["data"]["exception_count"] >= 1
    types = [e["exception_type"] for e in r["data"]["exceptions"]]
    assert "supplier_mismatch" in types


def test_classify_non_dict_exception_skipped_with_warning() -> None:
    r = invoiceops_classify_exceptions({"exceptions": ["not-a-dict"]}, _BASE_INVOICE)
    assert r["data"]["exception_count"] == 0
    assert any("not a dict" in w for w in r["data"]["classification_warnings"])


# ---------------------------------------------------------------------------
# search_po_fallback — result contract
# ---------------------------------------------------------------------------

def _load_po_register() -> list[dict]:
    return json.loads((_FIXTURE_BASE / "po_fallback_register.json").read_text())


def test_po_fallback_ok() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    assert r["ok"] is True


def test_po_fallback_type() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    assert r["type"] == "invoiceops_fallback_result"


def test_po_fallback_data_keys() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    for key in ("fallback_type", "candidates", "selected_candidate", "confidence", "requires_operator_review"):
        assert key in r["data"]


def test_po_fallback_type_field() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    assert r["data"]["fallback_type"] == "po"


def test_po_fallback_requires_operator_review() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    assert r["data"]["requires_operator_review"] is True


def test_po_fallback_selected_candidate_is_none() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    assert r["data"]["selected_candidate"] is None


def test_po_fallback_excludes_cancelled_pos() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    candidate_ids = [c["candidate_id"] for c in r["data"]["candidates"]]
    assert "PO-2023-010" not in candidate_ids


def test_po_fallback_returns_ranked_candidates() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    candidates = r["data"]["candidates"]
    assert len(candidates) >= 1
    scores = [c["score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_po_fallback_top_candidate_has_reason() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    top = r["data"]["candidates"][0]
    assert top["reason"]
    assert top["candidate_id"]
    assert isinstance(top["record"], dict)


def test_po_fallback_same_supplier_scores_higher() -> None:
    # PO-2024-099 matches supplier, total, and SKUs → should rank above PO-2024-100
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    candidates = r["data"]["candidates"]
    ids = [c["candidate_id"] for c in candidates]
    assert ids.index("PO-2024-099") < ids.index("PO-2024-100")


def test_po_fallback_high_confidence_for_strong_match() -> None:
    # PO-2024-099: same supplier (+3), same PO prefix (+2), same total (+2), 3 SKU overlap (+3), open (+1) = 11
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    assert r["data"]["confidence"] == "high"


def test_po_fallback_low_confidence_no_matches() -> None:
    # No supplier match, no PO prefix overlap, no total match, no SKU overlap → score = 0
    inv = {**_BASE_INVOICE, "supplier_id": "SUP-NOBODY", "invoice_total": 99999.0,
           "po_number": "XX-0000", "line_items": []}
    r = invoiceops_search_po_fallback(inv, _load_po_register())
    assert r["data"]["confidence"] in ("none", "low")


def test_po_fallback_empty_register_returns_no_candidates() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, [])
    assert r["data"]["candidates"] == []
    assert r["data"]["confidence"] == "none"


# ---------------------------------------------------------------------------
# search_receipt_fallback — result contract
# ---------------------------------------------------------------------------

_RECEIPT_REGISTER = [
    _BASE_RECEIPT,
    {
        "receipt_id": "GRN-002",
        "po_number": "PO-2024-043",
        "supplier_id": "SUP-001",
        "receipt_date": "2024-01-12",
        "status": "partial",
        "line_items": [
            {"line_no": 1, "sku": "SKU-WIDGET-A", "description": "Widget A", "received_quantity": 5.0},
        ],
    },
]


def test_receipt_fallback_ok() -> None:
    r = invoiceops_search_receipt_fallback(_BASE_INVOICE, _RECEIPT_REGISTER)
    assert r["ok"] is True


def test_receipt_fallback_type() -> None:
    r = invoiceops_search_receipt_fallback(_BASE_INVOICE, _RECEIPT_REGISTER)
    assert r["type"] == "invoiceops_fallback_result"


def test_receipt_fallback_type_field() -> None:
    r = invoiceops_search_receipt_fallback(_BASE_INVOICE, _RECEIPT_REGISTER)
    assert r["data"]["fallback_type"] == "receipt"


def test_receipt_fallback_requires_operator_review() -> None:
    r = invoiceops_search_receipt_fallback(_BASE_INVOICE, _RECEIPT_REGISTER)
    assert r["data"]["requires_operator_review"] is True


def test_receipt_fallback_returns_ranked_candidates() -> None:
    r = invoiceops_search_receipt_fallback(_BASE_INVOICE, _RECEIPT_REGISTER)
    candidates = r["data"]["candidates"]
    assert len(candidates) >= 1
    scores = [c["score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_receipt_fallback_po_match_scores_highest() -> None:
    # GRN-001 matches PO number exactly → should be first
    r = invoiceops_search_receipt_fallback(_BASE_INVOICE, _RECEIPT_REGISTER)
    assert r["data"]["candidates"][0]["candidate_id"] == "GRN-001"


def test_receipt_fallback_high_confidence_for_po_and_supplier_match() -> None:
    # GRN-001: po_number (+4) + supplier (+2) + 3 SKUs (+3) + received (+1) = 10
    r = invoiceops_search_receipt_fallback(_BASE_INVOICE, _RECEIPT_REGISTER)
    assert r["data"]["confidence"] == "high"


def test_receipt_fallback_empty_register() -> None:
    r = invoiceops_search_receipt_fallback(_BASE_INVOICE, [])
    assert r["data"]["candidates"] == []
    assert r["data"]["confidence"] == "none"


def test_receipt_fallback_candidate_has_record() -> None:
    r = invoiceops_search_receipt_fallback(_BASE_INVOICE, _RECEIPT_REGISTER)
    for c in r["data"]["candidates"]:
        assert isinstance(c["record"], dict)
        assert c["candidate_id"]


# ---------------------------------------------------------------------------
# search_supplier_fallback — result contract
# ---------------------------------------------------------------------------

def _load_supplier_master() -> list[dict]:
    return json.loads((_FIXTURE_BASE / "supplier_fallback_master.json").read_text())


def test_supplier_fallback_ok() -> None:
    r = invoiceops_search_supplier_fallback(_BASE_INVOICE, _load_supplier_master())
    assert r["ok"] is True


def test_supplier_fallback_type() -> None:
    r = invoiceops_search_supplier_fallback(_BASE_INVOICE, _load_supplier_master())
    assert r["type"] == "invoiceops_fallback_result"


def test_supplier_fallback_type_field() -> None:
    r = invoiceops_search_supplier_fallback(_BASE_INVOICE, _load_supplier_master())
    assert r["data"]["fallback_type"] == "supplier"


def test_supplier_fallback_requires_operator_review() -> None:
    r = invoiceops_search_supplier_fallback(_BASE_INVOICE, _load_supplier_master())
    assert r["data"]["requires_operator_review"] is True


def test_supplier_fallback_exact_id_match_ranks_first() -> None:
    r = invoiceops_search_supplier_fallback(_BASE_INVOICE, _load_supplier_master())
    candidates = r["data"]["candidates"]
    assert candidates[0]["candidate_id"] == "SUP-001"


def test_supplier_fallback_high_confidence_for_exact_id() -> None:
    r = invoiceops_search_supplier_fallback(_BASE_INVOICE, _load_supplier_master())
    assert r["data"]["confidence"] == "high"


def test_supplier_fallback_normalized_name_match() -> None:
    # Invoice has supplier_name with punctuation; master has slightly different spelling
    inv = {**_BASE_INVOICE, "supplier_id": "SUP-UNKNOWN", "supplier_name": "Acme Supplies Pty Ltd"}
    r = invoiceops_search_supplier_fallback(inv, _load_supplier_master())
    ids = [c["candidate_id"] for c in r["data"]["candidates"]]
    # SUP-002 has exact name match, SUP-001 has normalized match
    assert "SUP-002" in ids


def test_supplier_fallback_no_unrelated_supplier_included() -> None:
    inv = {**_BASE_INVOICE, "supplier_id": "SUP-NOBODY", "supplier_name": "Nobody Inc"}
    r = invoiceops_search_supplier_fallback(inv, _load_supplier_master())
    assert r["data"]["candidates"] == []
    assert r["data"]["confidence"] == "none"


def test_supplier_fallback_returns_ranked_candidates() -> None:
    r = invoiceops_search_supplier_fallback(_BASE_INVOICE, _load_supplier_master())
    scores = [c["score"] for c in r["data"]["candidates"]]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# low-confidence fallback requires operator review
# ---------------------------------------------------------------------------

def test_low_confidence_fallback_requires_operator_review() -> None:
    # No supplier, no total, no SKU overlap → low/none confidence; operator review still required
    inv = {**_BASE_INVOICE, "supplier_id": "SUP-NOBODY", "invoice_total": 99999.0, "line_items": []}
    r = invoiceops_search_po_fallback(inv, _load_po_register())
    assert r["data"]["requires_operator_review"] is True
    assert r["data"]["confidence"] in ("none", "low")


def test_fallback_always_requires_operator_review_regardless_of_confidence() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, _load_po_register())
    assert r["data"]["requires_operator_review"] is True
    r2 = invoiceops_search_po_fallback(
        {**_BASE_INVOICE, "supplier_id": "SUP-NOBODY"}, _load_po_register()
    )
    assert r2["data"]["requires_operator_review"] is True


# ---------------------------------------------------------------------------
# build_exception_action_plan — blocks unsafe continuation
# ---------------------------------------------------------------------------

def test_action_plan_ok() -> None:
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [], None)
    assert r["ok"] is True


def test_action_plan_type() -> None:
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [], None)
    assert r["type"] == "invoiceops_exception_action_plan"


def test_action_plan_data_keys() -> None:
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [], None)
    plan = r["data"]["exception_action_plan"]
    for key in (
        "exception_action_plan_id", "invoice_id", "safe_to_continue",
        "recommended_action", "exceptions", "fallback_results", "notes",
    ):
        assert key in plan


def test_action_plan_safe_when_no_exceptions() -> None:
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [], None)
    assert r["data"]["exception_action_plan"]["safe_to_continue"] is True


def test_action_plan_not_safe_duplicate_invoice() -> None:
    exc = _make_exception("duplicate_invoice")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["safe_to_continue"] is False


def test_action_plan_not_safe_missing_po() -> None:
    exc = _make_exception("missing_po")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["safe_to_continue"] is False


def test_action_plan_not_safe_missing_receipt() -> None:
    exc = _make_exception("missing_receipt")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["safe_to_continue"] is False


def test_action_plan_not_safe_supplier_mismatch() -> None:
    exc = _make_exception("supplier_mismatch")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["safe_to_continue"] is False


def test_action_plan_not_safe_quantity_mismatch() -> None:
    exc = _make_exception("quantity_mismatch")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["safe_to_continue"] is False


def test_action_plan_not_safe_bad_invoice_input() -> None:
    exc = _make_exception("bad_invoice_input")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["safe_to_continue"] is False


def test_action_plan_safe_with_warnings_only_and_no_fallback() -> None:
    # tax_mismatch is not in unsafe set + blocking=False
    exc = _make_exception("tax_mismatch", blocking=False, severity="medium")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["safe_to_continue"] is True


def test_action_plan_not_safe_low_confidence_fallback() -> None:
    exc = _make_exception("tax_mismatch", blocking=False, severity="medium")
    # Simulate a low-confidence fallback
    low_conf_fallback = {
        "data": {"confidence": "low", "requires_operator_review": True},
    }
    r = invoiceops_build_exception_action_plan(
        _BASE_INVOICE, [exc], {"po": low_conf_fallback}
    )
    assert r["data"]["exception_action_plan"]["safe_to_continue"] is False


def test_action_plan_safe_with_high_confidence_fallback() -> None:
    exc = _make_exception("tax_mismatch", blocking=False, severity="medium")
    high_conf_fallback = {
        "data": {"confidence": "high", "requires_operator_review": True},
    }
    r = invoiceops_build_exception_action_plan(
        _BASE_INVOICE, [exc], {"po": high_conf_fallback}
    )
    assert r["data"]["exception_action_plan"]["safe_to_continue"] is True


def test_action_plan_recommended_action_duplicate() -> None:
    exc = _make_exception("duplicate_invoice")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["recommended_action"] == "reject_duplicate"


def test_action_plan_recommended_action_missing_po() -> None:
    exc = _make_exception("missing_po")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["recommended_action"] == "correct_po"


def test_action_plan_recommended_action_missing_receipt() -> None:
    exc = _make_exception("missing_receipt")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["recommended_action"] == "required_document"


def test_action_plan_recommended_action_supplier_mismatch() -> None:
    exc = _make_exception("supplier_mismatch")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["recommended_action"] == "supplier_query"


def test_action_plan_recommended_action_bad_input() -> None:
    exc = _make_exception("bad_invoice_input")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    assert r["data"]["exception_action_plan"]["recommended_action"] == "manual_resolution"


def test_action_plan_duplicate_takes_priority_over_missing_po() -> None:
    excs = [
        _make_exception("missing_po", exception_id="EXC-001"),
        _make_exception("duplicate_invoice", exception_id="EXC-002"),
    ]
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, excs, None)
    assert r["data"]["exception_action_plan"]["recommended_action"] == "reject_duplicate"


def test_action_plan_notes_is_list() -> None:
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [], None)
    assert isinstance(r["data"]["exception_action_plan"]["notes"], list)


def test_action_plan_notes_mention_blocking() -> None:
    exc = _make_exception("missing_po")
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [exc], None)
    notes = r["data"]["exception_action_plan"]["notes"]
    assert any("Blocking" in note or "blocking" in note for note in notes)


def test_action_plan_fallback_results_in_plan() -> None:
    high_conf = {"data": {"confidence": "high", "requires_operator_review": True}}
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [], {"po": high_conf})
    assert "po" in r["data"]["exception_action_plan"]["fallback_results"]


def test_action_plan_metadata_has_safe_to_continue() -> None:
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [], None)
    assert "safe_to_continue" in r["metadata"]


# ---------------------------------------------------------------------------
# No ledger posting — exception tools never allow posting
# ---------------------------------------------------------------------------

def test_classify_exceptions_has_no_ledger_posting_field() -> None:
    r = invoiceops_classify_exceptions({}, _BASE_INVOICE)
    assert "ledger_posting_allowed" not in r
    assert "ledger_posting_allowed" not in r["data"]


def test_action_plan_has_no_ledger_posting_field() -> None:
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [], None)
    assert "ledger_posting_allowed" not in r
    assert "ledger_posting_allowed" not in r["data"]["exception_action_plan"]


# ---------------------------------------------------------------------------
# ToolResult contract — all outputs are ToolResult-compatible
# ---------------------------------------------------------------------------

def test_classify_toolresult_keys() -> None:
    r = invoiceops_classify_exceptions({}, _BASE_INVOICE)
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_po_fallback_toolresult_keys() -> None:
    r = invoiceops_search_po_fallback(_BASE_INVOICE, [])
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_receipt_fallback_toolresult_keys() -> None:
    r = invoiceops_search_receipt_fallback(_BASE_INVOICE, [])
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_supplier_fallback_toolresult_keys() -> None:
    r = invoiceops_search_supplier_fallback(_BASE_INVOICE, [])
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_action_plan_toolresult_keys() -> None:
    r = invoiceops_build_exception_action_plan(_BASE_INVOICE, [], None)
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_all_tools_return_ok_true() -> None:
    assert invoiceops_classify_exceptions({}, _BASE_INVOICE)["ok"] is True
    assert invoiceops_search_po_fallback(_BASE_INVOICE, [])["ok"] is True
    assert invoiceops_search_receipt_fallback(_BASE_INVOICE, [])["ok"] is True
    assert invoiceops_search_supplier_fallback(_BASE_INVOICE, [])["ok"] is True
    assert invoiceops_build_exception_action_plan(_BASE_INVOICE, [], None)["ok"] is True


def test_all_tools_have_empty_error_string() -> None:
    results = [
        invoiceops_classify_exceptions({}, _BASE_INVOICE),
        invoiceops_search_po_fallback(_BASE_INVOICE, []),
        invoiceops_search_receipt_fallback(_BASE_INVOICE, []),
        invoiceops_search_supplier_fallback(_BASE_INVOICE, []),
        invoiceops_build_exception_action_plan(_BASE_INVOICE, [], None),
    ]
    for r in results:
        assert r["error"] == ""


# ---------------------------------------------------------------------------
# No write functions
# ---------------------------------------------------------------------------

def test_no_write_functions_in_exception_module() -> None:
    write_fns = [
        name for name in dir(_mod)
        if "write" in name.lower() and callable(getattr(_mod, name))
    ]
    assert write_fns == []
