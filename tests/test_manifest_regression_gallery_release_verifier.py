from __future__ import annotations

from tools.run_release_candidate_verification import _check_manifest_regression_gallery


def test_release_verifier_includes_manifest_regression_gallery_check() -> None:
    result = _check_manifest_regression_gallery()
    assert result["name"] == "manifest_regression_gallery"
    assert result["status"] == "PASS"


def test_release_verifier_fails_if_gallery_index_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.manifest_regression_gallery.validate_gallery_index",
        lambda *args, **kwargs: {"ok": False, "status": "FAIL", "errors": ["missing"], "warnings": []},
    )
    result = _check_manifest_regression_gallery()
    assert result["status"] == "FAIL"
    assert result["validation"]["status"] == "FAIL"


def test_release_verifier_fails_if_gallery_expectation_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.manifest_regression_gallery.run_gallery",
        lambda *args, **kwargs: {"ok": False, "status": "FAIL", "failed": 1, "passed": 0, "total_fixtures": 1},
    )
    result = _check_manifest_regression_gallery()
    assert result["status"] == "FAIL"
    assert result["result"]["failed"] == 1


def test_release_verifier_confirms_gallery_fixtures_excluded_from_active_catalog() -> None:
    result = _check_manifest_regression_gallery()
    assert result["status"] == "PASS"
    assert result["report_ok"] is True
