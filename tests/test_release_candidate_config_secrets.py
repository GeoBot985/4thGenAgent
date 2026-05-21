from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest


SCRIPT_PATH = Path("tools/run_release_candidate_verification.py")
pytestmark = pytest.mark.release


def _load_module():
    spec = importlib.util.spec_from_file_location("rc_verifier_config_hygiene", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_release_verifier_runs_config_hygiene_check() -> None:
    module = _load_module()
    source = inspect.getsource(module)
    assert "_check_config_secrets_hygiene()" in source
    assert '"config_secrets_hygiene": "PENDING"' in source
    check = module._check_config_secrets_hygiene()
    assert check["name"] == "config_secrets_hygiene"
    assert "commands" in check


def test_release_verifier_config_hygiene_is_evidence() -> None:
    module = _load_module()
    check = module._check_config_secrets_hygiene()
    assert check["name"] == "config_secrets_hygiene"
    assert "command_failures" in check
