from __future__ import annotations

import pytest

from tools.run_release_candidate_verification import (
    _check_supplier_invoice_docs_exist,
    _check_supplier_invoice_dry_run_approval,
    _check_supplier_invoice_exception_path_smoke,
    _check_supplier_invoice_happy_path_smoke,
    _check_supplier_invoice_manifest_exists,
    _check_supplier_invoice_report_generation,
    _check_supplier_invoice_routes_exist,
    _check_supplier_invoice_scenarios_exist,
    _check_supplier_invoice_tools_registered,
)

pytestmark = pytest.mark.release


def test_release_verifier_includes_supplier_invoice_checks():
    assert _check_supplier_invoice_manifest_exists()["status"] == "PASS"
    assert _check_supplier_invoice_routes_exist()["status"] == "PASS"
    assert _check_supplier_invoice_tools_registered()["status"] == "PASS"
    assert _check_supplier_invoice_scenarios_exist()["status"] == "PASS"


def test_release_verifier_supplier_invoice_smokes_pass():
    assert _check_supplier_invoice_happy_path_smoke()["status"] == "PASS"
    assert _check_supplier_invoice_exception_path_smoke()["status"] == "PASS"
    assert _check_supplier_invoice_dry_run_approval()["status"] == "PASS"
    assert _check_supplier_invoice_report_generation()["status"] == "PASS"


def test_release_verifier_supplier_invoice_docs_exist():
    assert _check_supplier_invoice_docs_exist()["status"] == "PASS"
