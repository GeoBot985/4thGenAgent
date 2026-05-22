from __future__ import annotations

from pathlib import Path

from tests.marker_rules import markers_for_path


def test_major_test_areas_are_classified_by_marker_rules() -> None:
    checks = {
        "tests/test_production_backend_event_intake_api.py": {"backend"},
        "tests/test_manifest_health.py": {"manifest"},
        "tests/test_manifest_regression_gallery_report.py": {"manifest", "gallery"},
        "tests/test_toolpack_lifecycle.py": {"toolpack"},
        "tests/test_runtime_engine.py": {"runtime"},
        "tests/test_operator_run_report.py": {"reports"},
        "tests/test_evidence_bundle.py": {"reports"},
        "tests/test_portfolio_evidence_pack.py": {"reports"},
    }

    for file_name, required in checks.items():
        markers = markers_for_path(Path(file_name))
        assert required.issubset(markers), f"{file_name} markers={markers}"


def test_helper_classes_release_validation_as_full_ci() -> None:
    for file_name in (
        "tests/test_release_candidate_verification_artifacts.py",
        "tests/test_release_verifier_runtime_store.py",
        "tests/test_safety_verification_pack.py",
    ):
        markers = markers_for_path(Path(file_name))
        assert "full_ci" in markers
        assert "reports" in markers
