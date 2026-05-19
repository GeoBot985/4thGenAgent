from __future__ import annotations

PO_STATUSES: frozenset[str] = frozenset({"open", "part_received", "closed", "cancelled"})
RECEIPT_STATUSES: frozenset[str] = frozenset({"received", "partial", "cancelled"})
SUPPLIER_STATUSES: frozenset[str] = frozenset({"active", "inactive", "blocked"})
MATCH_STATUSES: frozenset[str] = frozenset({"matched", "exception", "blocked"})
CHECK_STATUSES: frozenset[str] = frozenset({"pass", "fail", "warn", "not_applicable"})
EXCEPTION_TYPES: frozenset[str] = frozenset({
    "wrong_po",
    "missing_po",
    "missing_receipt",
    "duplicate_invoice",
    "supplier_mismatch",
    "amount_mismatch",
    "tax_mismatch",
    "quantity_mismatch",
    "bad_invoice_input",
})
EXCEPTION_SEVERITIES: frozenset[str] = frozenset({"low", "medium", "high", "blocker"})
LEDGER_STATUSES: frozenset[str] = frozenset({"prepared", "posted", "reversed"})
LEDGER_SOURCE_TYPES: frozenset[str] = frozenset({"supplier_invoice"})
PREPARED_WRITE_TARGETS: frozenset[str] = frozenset({
    "invoice_register",
    "ledger",
    "exception_register",
    "match_register",
})
PREPARED_WRITE_OPERATIONS: frozenset[str] = frozenset({"append", "update"})
WRITE_LIKE_OPERATIONS: frozenset[str] = frozenset({"append", "update"})
ROLLBACK_TYPES: frozenset[str] = frozenset({
    "delete_appended_rows",
    "mark_reversed",
    "manual_review_required",
    "not_applicable",
})
EVIDENCE_SOURCE_TYPES: frozenset[str] = frozenset({
    "pdf",
    "text",
    "google_sheet",
    "fixture",
    "tool_output",
})
NUMERIC_TOLERANCE: float = 0.005
