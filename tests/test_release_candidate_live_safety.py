from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest


SCRIPT_PATH = Path("tools/run_release_candidate_verification.py")
pytestmark = pytest.mark.release


def _load_module():
    spec = importlib.util.spec_from_file_location("rc_verifier_live_safety", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_release_verifier_has_live_safety_checks():
    module = _load_module()
    source = inspect.getsource(module)
    assert "_check_live_safety_docs()" in source
    assert "_check_live_cli_guardrails()" in source
    assert "_check_live_execution_default_dry_run()" in source
    assert '"live_safety_docs": "PENDING"' in source
    assert '"live_cli_guardrails": "PENDING"' in source
    assert '"live_execution_default_dry_run": "PENDING"' in source


def test_live_safety_check_reports_pass():
    module = _load_module()
    check = module._check_live_safety_docs()
    assert check["name"] == "live_safety_docs"
    assert check["status"] == "PASS"
