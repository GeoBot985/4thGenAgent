from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest


SCRIPT_PATH = Path("tools/run_release_candidate_verification.py")
pytestmark = pytest.mark.release


def _load_module():
    spec = importlib.util.spec_from_file_location("rc_verifier_manifest_health", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_release_verifier_runs_manifest_catalog_health_check() -> None:
    module = _load_module()
    source = inspect.getsource(module)
    assert "_check_manifest_catalog_health()" in source
    assert '"manifest_catalog_health": "PENDING"' in source


def test_manifest_catalog_health_failure_blocks_release() -> None:
    module = _load_module()
    source = inspect.getsource(module)
    assert 'elif check["name"] == "manifest_catalog_health":' in source
    assert 'release_blockers.append("manifest catalog health failed")' in source


def test_manifest_catalog_health_report_is_evidence(monkeypatch) -> None:
    module = _load_module()
    source = inspect.getsource(module)
    assert 'manifest_health_check = next((check for check in static_checks if check.get("name") == "manifest_catalog_health"), {})' in source
    assert "evidence_paths.append(_display_path(Path(value)))" in source
    monkeypatch.setattr(
        module,
        "run_manifest_health_check",
        lambda **_kwargs: {
            "ok": True,
            "status": "HEALTHY",
            "summary": {"validation_failed": 0, "critical": 0},
            "manifests": [],
        },
    )
    monkeypatch.setattr(
        module,
        "write_manifest_health_report",
        lambda *_args, **_kwargs: {
            "ok": True,
            "json_path": "runtime_data/manifest_health/manifest_health_report.json",
            "markdown_path": "runtime_data/manifest_health/manifest_health_report.md",
        },
    )
    check = module._check_manifest_catalog_health()
    assert check["status"] == "PASS"
    assert check["json_path"].endswith("manifest_health_report.json")
    assert check["markdown_path"].endswith("manifest_health_report.md")


def test_manifest_catalog_health_ignores_quarantined_smoke_manifests() -> None:
    module = _load_module()
    check = module._check_manifest_catalog_health()
    assert check["summary"]["critical"] == 0


def test_manifest_catalog_health_fails_active_critical_manifest(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "run_manifest_health_check",
        lambda **_kwargs: {
            "ok": True,
            "status": "HAS_FAILURES",
            "summary": {"validation_failed": 0, "critical": 1},
            "manifests": [],
        },
    )
    monkeypatch.setattr(
        module,
        "write_manifest_health_report",
        lambda *_args, **_kwargs: {
            "ok": True,
            "json_path": "runtime_data/manifest_health/manifest_health_report.json",
            "markdown_path": "runtime_data/manifest_health/manifest_health_report.md",
        },
    )
    assert module._check_manifest_catalog_health()["status"] == "FAIL"


def test_release_verifier_manifest_health_passes_after_quarantine() -> None:
    module = _load_module()
    assert module._check_manifest_catalog_health()["status"] == "PASS"
