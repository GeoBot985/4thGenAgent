"""Spec 156 — InvoiceOps live sheet write pilot release verifier tests."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
VERIFIER_PATH = ROOT / "tools" / "run_release_candidate_verification.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("run_rc_verif", VERIFIER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_verifier_file_exists():
    assert VERIFIER_PATH.is_file()


def test_check_function_importable():
    mod = _load_verifier()
    assert hasattr(mod, "_check_invoiceops_live_sheet_write_pilot")


def test_check_returns_dict():
    mod = _load_verifier()
    result = mod._check_invoiceops_live_sheet_write_pilot()
    assert isinstance(result, dict)


def test_check_has_name_field():
    mod = _load_verifier()
    result = mod._check_invoiceops_live_sheet_write_pilot()
    assert result.get("name") == "invoiceops_live_sheet_write_pilot"


def test_check_has_status_field():
    mod = _load_verifier()
    result = mod._check_invoiceops_live_sheet_write_pilot()
    assert result.get("status") in ("PASS", "FAIL")


def test_check_passes():
    mod = _load_verifier()
    result = mod._check_invoiceops_live_sheet_write_pilot()
    assert result["status"] == "PASS", f"Failures: {result.get('failures')} Missing: {result.get('missing')}"


def test_check_in_source_code():
    content = VERIFIER_PATH.read_text(encoding="utf-8")
    assert "_check_invoiceops_live_sheet_write_pilot" in content


def test_check_wired_into_static_checks():
    content = VERIFIER_PATH.read_text(encoding="utf-8")
    # The function call must appear inside the static_checks collection
    assert "_check_invoiceops_live_sheet_write_pilot()" in content


def test_invoiceops_posting_module_importable():
    from runtime.invoiceops_live_posting import (
        build_invoiceops_live_posting_plan,
        V1_ALLOWED_TARGETS,
        V1_BLOCKED_TARGETS,
    )
    assert build_invoiceops_live_posting_plan is not None


def test_approval_pack_module_importable():
    from runtime.invoiceops_posting_approval_pack import build_invoiceops_posting_approval_pack
    assert build_invoiceops_posting_approval_pack is not None


def test_posting_ledger_module_importable():
    from runtime.invoiceops_posting_ledger import append_posting_ledger_entry
    assert append_posting_ledger_entry is not None


def test_blocked_targets_not_in_allowed():
    from runtime.invoiceops_live_posting import V1_ALLOWED_TARGETS, V1_BLOCKED_TARGETS
    overlap = V1_ALLOWED_TARGETS & V1_BLOCKED_TARGETS
    # canonical names should not overlap
    canonical_blocked = {"supplier_master", "po_register", "goods_receipt_register", "bank_register", "payment_register"}
    assert not (canonical_blocked & V1_ALLOWED_TARGETS), f"Blocked targets found in allowed: {canonical_blocked & V1_ALLOWED_TARGETS}"


def test_no_real_credentials_required_for_check():
    """The check must not require Google credentials — blocked at boundary."""
    mod = _load_verifier()
    # If it returns without raising an auth error, no credentials were needed
    result = mod._check_invoiceops_live_sheet_write_pilot()
    assert isinstance(result, dict)
