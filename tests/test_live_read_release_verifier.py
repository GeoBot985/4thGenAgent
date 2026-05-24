from __future__ import annotations

import json
import subprocess
import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_governed_live_read_proof_check_exists():
    from tools.run_release_candidate_verification import _check_governed_live_read_proof
    assert callable(_check_governed_live_read_proof)


def test_governed_live_read_proof_check_returns_dict():
    from tools.run_release_candidate_verification import _check_governed_live_read_proof
    result = _check_governed_live_read_proof()
    assert isinstance(result, dict)


def test_governed_live_read_proof_check_has_name():
    from tools.run_release_candidate_verification import _check_governed_live_read_proof
    result = _check_governed_live_read_proof()
    assert result.get("name") == "governed_live_read_proof"


def test_governed_live_read_proof_check_has_status():
    from tools.run_release_candidate_verification import _check_governed_live_read_proof
    result = _check_governed_live_read_proof()
    assert result.get("status") in ("PASS", "FAIL")


def test_governed_live_read_proof_check_passes():
    from tools.run_release_candidate_verification import _check_governed_live_read_proof
    result = _check_governed_live_read_proof()
    assert result.get("status") == "PASS", (
        f"governed_live_read_proof check failed. Details: {result.get('details', [])}"
    )


def test_verifier_has_governed_live_read_in_bootstrap_checks():
    from tools import run_release_candidate_verification as rv
    src = Path(rv.__file__).read_text(encoding="utf-8")
    assert "governed_live_read_proof" in src


def test_live_read_proof_module_importable():
    from runtime.live_read_proof import (
        build_live_read_proof_plan,
        run_live_read_proof_pack,
        validate_live_read_boundary,
        write_live_read_proof_report,
        render_live_read_proof_markdown,
        build_live_read_status,
    )
    assert callable(build_live_read_proof_plan)
    assert callable(run_live_read_proof_pack)
    assert callable(validate_live_read_boundary)
    assert callable(write_live_read_proof_report)
    assert callable(render_live_read_proof_markdown)
    assert callable(build_live_read_status)


def test_release_verifier_boundary_only_no_credentials():
    r = subprocess.run(
        [
            sys.executable, "-m", "src.taskframe_cli",
            "live-read", "proof",
            "--profile", "controlled_live_read",
            "--no-live-probes",
            "--json",
        ],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT),
    )
    assert r.returncode == 0, f"CLI failed: {r.stderr}"
    data = json.loads(r.stdout)
    assert data.get("ok") is True
    assert data.get("live_side_effects_performed") is False


def test_release_verifier_uses_no_live_probes():
    from tools.run_release_candidate_verification import _check_governed_live_read_proof
    import inspect
    src = inspect.getsource(_check_governed_live_read_proof)
    assert "--no-live-probes" in src


def test_release_verifier_check_blocked_side_effects():
    from tools.run_release_candidate_verification import _check_governed_live_read_proof
    import inspect
    src = inspect.getsource(_check_governed_live_read_proof)
    assert "blocked-side-effects" in src or "validate_live_read_boundary" in src
