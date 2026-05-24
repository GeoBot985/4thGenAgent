from __future__ import annotations

from tools.run_release_candidate_verification import _check_worker_hardening_soak


def test_release_verifier_includes_worker_hardening_soak_check():
    result = _check_worker_hardening_soak()
    assert result["name"] == "worker_hardening_soak"
    assert result["status"] == "PASS"
    assert result["missing"] == []
