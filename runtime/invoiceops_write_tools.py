from __future__ import annotations

from typing import Any

from .invoiceops_contracts import (
    validate_exception_shape,
    validate_invoice_shape,
    validate_ledger_row_shape,
    validate_match_result_shape,
    validate_prepared_write_shape,
    validate_rollback_plan_shape,
)
from .tool_result_contract import build_tool_evidence

_RESULT_TYPE = "invoiceops_prepared_write"
_ROLLBACK_RESULT_TYPE = "invoiceops_rollback_plan"

_TOOL_KEYS = {
    "invoice_register": "invoiceops/prepare_invoice_register_write",
    "match_register": "invoiceops/prepare_match_register_write",
    "exception_register": "invoiceops/prepare_exception_register_write",
    "ledger": "invoiceops/prepare_ledger_write",
    "rollback_plan": "invoiceops/prepare_rollback_plan",
}

_TARGETS = {
    "invoice_register": "InvoiceRegister",
    "match_register": "MatchRegister",
    "exception_register": "ExceptionRegister",
    "ledger": "Ledger",
}

_ROLLBACK_TYPES = {
    "invoice_register": "delete_appended_rows",
    "match_register": "delete_appended_rows",
    "exception_register": "delete_appended_rows",
    "ledger": "mark_reversed",
}

_INVALID_CODES = {
    "invoice_register": "INVALID_INVOICE_FOR_WRITE",
    "match_register": "INVALID_MATCH_RESULT_FOR_WRITE",
    "exception_register": "INVALID_EXCEPTION_FOR_WRITE",
    "ledger": "INVALID_LEDGER_ROW_FOR_WRITE",
}


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

def invoiceops_prepare_invoice_register_write(invoice: dict) -> dict:
    record = _unwrap_dict(invoice)
    if not isinstance(record, dict):
        return _failed_prepare("invoice_register", _INVALID_CODES["invoice_register"], "Invoice input must be a dict.")

    record = _unwrap_nested_record(record, "invoice")
    v = validate_invoice_shape(record)
    if not v["ok"]:
        return _failed_prepare("invoice_register", _INVALID_CODES["invoice_register"], "Invoice input failed validation.", v)

    prepared_write = _build_prepared_write(
        kind="invoice_register",
        rows=[dict(record)],
        source_ids=[record.get("invoice_id", ""), record.get("invoice_number", "")],
    )
    return _prepared_write_result("invoice_register", prepared_write, [record.get("invoice_id", ""), record.get("invoice_number", "")])


def invoiceops_prepare_match_register_write(match_result: dict) -> dict:
    record = _unwrap_dict(match_result)
    if not isinstance(record, dict):
        return _failed_prepare("match_register", _INVALID_CODES["match_register"], "Match result input must be a dict.")

    record = _unwrap_nested_record(record, "match_result")
    v = validate_match_result_shape(record)
    if not v["ok"]:
        return _failed_prepare("match_register", _INVALID_CODES["match_register"], "Match result input failed validation.", v)

    prepared_write = _build_prepared_write(
        kind="match_register",
        rows=[dict(record)],
        source_ids=[record.get("match_id", ""), record.get("invoice_id", ""), record.get("po_number", "")],
    )
    return _prepared_write_result("match_register", prepared_write, [record.get("match_id", ""), record.get("invoice_id", "")])


def invoiceops_prepare_exception_register_write(exceptions: list[dict]) -> dict:
    records = _unwrap_list(exceptions)
    if records is None or not records:
        return _failed_prepare("exception_register", _INVALID_CODES["exception_register"], "Exceptions input must be a non-empty list of dicts.")

    validated: list[dict] = []
    source_ids: list[str] = []
    for idx, exc in enumerate(records):
        if not isinstance(exc, dict):
            return _failed_prepare(
                "exception_register",
                _INVALID_CODES["exception_register"],
                f"exceptions[{idx}] must be a dict.",
            )
        v = validate_exception_shape(exc)
        if not v["ok"]:
            return _failed_prepare(
                "exception_register",
                _INVALID_CODES["exception_register"],
                "Exception input failed validation.",
                v,
            )
        validated.append(dict(exc))
        source_ids.append(str(exc.get("exception_id", "")).strip())

    prepared_write = _build_prepared_write(
        kind="exception_register",
        rows=validated,
        source_ids=source_ids,
    )
    return _prepared_write_result("exception_register", prepared_write, source_ids)


def invoiceops_prepare_ledger_write(ledger_rows: list[dict]) -> dict:
    records = _unwrap_list(ledger_rows)
    if records is None or not records:
        return _failed_prepare("ledger", _INVALID_CODES["ledger"], "Ledger rows input must be a non-empty list of dicts.")

    validated: list[dict] = []
    source_ids: list[str] = []
    for idx, row in enumerate(records):
        if not isinstance(row, dict):
            return _failed_prepare("ledger", _INVALID_CODES["ledger"], f"ledger_rows[{idx}] must be a dict.")
        v = validate_ledger_row_shape(row)
        if not v["ok"]:
            return _failed_prepare(
                "ledger",
                _INVALID_CODES["ledger"],
                "Ledger row input failed validation.",
                v,
            )
        validated.append(dict(row))
        source_ids.append(str(row.get("ledger_entry_id", "")).strip())

    prepared_write = _build_prepared_write(
        kind="ledger",
        rows=validated,
        source_ids=source_ids,
    )
    return _prepared_write_result("ledger", prepared_write, source_ids)


def invoiceops_prepare_rollback_plan(prepared_write: dict) -> dict:
    record = _unwrap_dict(prepared_write)
    if not isinstance(record, dict):
        return _failed_rollback("ROLLBACK_PLAN_REQUIRED", "Prepared write input must be a dict.")

    record = _unwrap_nested_record(record, "prepared_write")
    if "rollback_plan" not in record or not isinstance(record.get("rollback_plan"), dict) or not record.get("rollback_plan"):
        return _failed_rollback("ROLLBACK_PLAN_REQUIRED", "Prepared write must include a rollback plan.")

    validation = validate_prepared_write_shape(record)
    if not validation["ok"]:
        return _failed_rollback("PREPARED_WRITE_BUILD_FAILED", "Prepared write input failed validation.", validation)

    rollback_plan = dict(record["rollback_plan"])
    rollback_validation = validate_rollback_plan_shape(rollback_plan)
    if not rollback_validation["ok"]:
        return _failed_rollback("PREPARED_WRITE_BUILD_FAILED", "Rollback plan input failed validation.", rollback_validation)

    evidence = build_tool_evidence(
        tool=_TOOL_KEYS["rollback_plan"],
        mode="dry_run",
        source="builtin",
        operation="prepare",
        input_refs=[str(record.get("prepared_write_id", "")).strip()],
        output_ref=_ROLLBACK_RESULT_TYPE,
        extra={
            "target": rollback_plan.get("target", ""),
            "rollback_type": rollback_plan.get("rollback_type", ""),
            "safe_to_auto_prepare": rollback_plan.get("safe_to_auto_prepare", False),
        },
    )

    return {
        "ok": True,
        "type": _ROLLBACK_RESULT_TYPE,
        "data": {"rollback_plan": rollback_plan},
        "evidence": evidence,
        "error": "",
        "metadata": {
            "dry_run": True,
            "live_side_effect": False,
            "prepared_write_id": record.get("prepared_write_id", ""),
            "target": rollback_plan.get("target", ""),
            "rollback_type": rollback_plan.get("rollback_type", ""),
        },
    }


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------

def _build_prepared_write(*, kind: str, rows: list[dict], source_ids: list[str]) -> dict[str, Any]:
    target = _TARGETS[kind]
    prepared_write_id = _build_prepared_write_id(kind, source_ids)
    rollback_plan = _build_rollback_plan(
        kind=kind,
        prepared_write_id=prepared_write_id,
        rows=rows,
        source_ids=source_ids,
    )

    prepared_write = {
        "prepared_write_id": prepared_write_id,
        "target": target,
        "operation": "append",
        "rows": [dict(row) for row in rows],
        "dry_run": True,
        "requires_approval": True,
        "rollback_plan": rollback_plan,
    }
    validation = validate_prepared_write_shape(prepared_write)
    if not validation["ok"]:
        raise ValueError(f"Prepared write validation failed: {validation['errors']}")
    return prepared_write


def _build_prepared_write_id(kind: str, source_ids: list[str]) -> str:
    clean = [item for item in source_ids if str(item).strip()]
    if clean:
        return f"PW-{kind.upper()}-{clean[0]}"
    return f"PW-{kind.upper()}-UNKNOWN"


def _build_rollback_plan(
    *,
    kind: str,
    prepared_write_id: str,
    rows: list[dict],
    source_ids: list[str],
) -> dict[str, Any]:
    rollback_type = _ROLLBACK_TYPES[kind]
    target = _TARGETS[kind]
    row_count = len(rows)
    safe_to_auto_prepare = True

    if rollback_type == "delete_appended_rows":
        row_ids = [item for item in source_ids if str(item).strip()]
        steps = [
            {
                "step_no": 1,
                "action": "delete_appended_rows",
                "target": target,
                "data": {
                    "prepared_write_id": prepared_write_id,
                    "row_count": row_count,
                    "row_ids": row_ids,
                },
            }
        ]
        reason = f"Undo appended rows for {target}."
    elif rollback_type == "mark_reversed":
        row_ids = [item for item in source_ids if str(item).strip()]
        steps = [
            {
                "step_no": 1,
                "action": "mark_reversed",
                "target": target,
                "data": {
                    "prepared_write_id": prepared_write_id,
                    "row_count": row_count,
                    "ledger_entry_ids": row_ids,
                    "reverse_status": "reversed",
                },
            }
        ]
        reason = f"Reverse ledger rows for {target}."
    else:
        safe_to_auto_prepare = False
        steps = [
            {
                "step_no": 1,
                "action": "manual_review_required",
                "target": target,
                "data": {
                    "prepared_write_id": prepared_write_id,
                    "row_count": row_count,
                },
            }
        ]
        reason = f"Rollback requires manual review for {target}."

    plan = {
        "rollback_id": f"RBK-{prepared_write_id}",
        "rollback_type": rollback_type,
        "target": target,
        "source_prepared_write_id": prepared_write_id,
        "safe_to_auto_prepare": safe_to_auto_prepare,
        "steps": steps,
        "reason": reason,
    }
    validation = validate_rollback_plan_shape(plan)
    if not validation["ok"]:
        raise ValueError(f"Rollback plan validation failed: {validation['errors']}")
    return plan


def _prepared_write_result(kind: str, prepared_write: dict, input_refs: list[str]) -> dict:
    evidence = build_tool_evidence(
        tool=_TOOL_KEYS[kind],
        mode="dry_run",
        source="builtin",
        operation="prepare",
        input_refs=[item for item in input_refs if str(item).strip()],
        output_ref=_RESULT_TYPE,
        extra={
            "target": prepared_write.get("target", ""),
            "rollback_type": prepared_write.get("rollback_plan", {}).get("rollback_type", ""),
            "row_count": len(prepared_write.get("rows", [])),
        },
    )
    return {
        "ok": True,
        "type": _RESULT_TYPE,
        "data": {"prepared_write": prepared_write},
        "evidence": evidence,
        "error": "",
        "metadata": {
            "dry_run": True,
            "live_side_effect": False,
            "target": prepared_write.get("target", ""),
            "rollback_type": prepared_write.get("rollback_plan", {}).get("rollback_type", ""),
        },
    }


# ---------------------------------------------------------------------------
# Failure helpers
# ---------------------------------------------------------------------------

def _failed_prepare(kind: str, error_code: str, message: str, validation: dict[str, Any] | None = None) -> dict:
    evidence = build_tool_evidence(
        tool=_TOOL_KEYS[kind],
        mode="dry_run",
        source="builtin",
        operation="prepare",
        input_refs=[],
        output_ref=_RESULT_TYPE,
        extra={"error_code": error_code},
    )
    data: dict[str, Any] = {"prepared_write": {}}
    if validation is not None:
        data["validation"] = validation
    return {
        "ok": False,
        "type": _RESULT_TYPE,
        "data": data,
        "evidence": evidence,
        "error": error_code,
        "metadata": {"dry_run": True, "live_side_effect": False, "target": _TARGETS[kind]},
    }


def _failed_rollback(error_code: str, message: str, validation: dict[str, Any] | None = None) -> dict:
    evidence = build_tool_evidence(
        tool=_TOOL_KEYS["rollback_plan"],
        mode="dry_run",
        source="builtin",
        operation="prepare",
        input_refs=[],
        output_ref=_ROLLBACK_RESULT_TYPE,
        extra={"error_code": error_code},
    )
    data: dict[str, Any] = {"rollback_plan": {}}
    if validation is not None:
        data["validation"] = validation
    return {
        "ok": False,
        "type": _ROLLBACK_RESULT_TYPE,
        "data": data,
        "evidence": evidence,
        "error": error_code,
        "metadata": {"dry_run": True, "live_side_effect": False},
    }


# ---------------------------------------------------------------------------
# Input normalization helpers
# ---------------------------------------------------------------------------

def _unwrap_dict(value: Any) -> dict | None:
    return value if isinstance(value, dict) else None


def _unwrap_nested_record(record: dict, key: str) -> dict:
    nested = record.get("data") if isinstance(record.get("data"), dict) else None
    if nested and isinstance(nested.get(key), dict):
        return dict(nested[key])
    if isinstance(record.get(key), dict):
        return dict(record[key])
    return dict(record)


def _unwrap_list(value: Any) -> list[dict] | None:
    return value if isinstance(value, list) else None
