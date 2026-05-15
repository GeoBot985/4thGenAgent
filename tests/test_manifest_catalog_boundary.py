from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.errors import ManifestLoadError
from runtime.manifest_loader import load_manifest, load_manifest_by_id, load_manifest_catalog
from src.manifest_health import run_manifest_health_check
from src.manifest_template_generator import build_manifest_from_template
from src.manifest_workbench import list_manifest_catalog


SMOKE_MANIFEST_DIR = Path("tests/fixtures/smoke_manifests")
SMOKE_FILES = (
    "smoke_live_sheet_create_allowed.manifest.json",
    "smoke_live_sheet_write_allowed.manifest.json",
    "smoke_live_side_effect_blocked_by_tool.manifest.json",
)
SMOKE_IDS = {
    "smoke.live_sheet_create_allowed",
    "smoke.live_sheet_write_allowed",
    "smoke.live_side_effect_blocked_by_tool",
}


def test_active_manifest_catalog_excludes_smoke_fixture_manifests() -> None:
    catalog = load_manifest_catalog("manifests")
    assert SMOKE_IDS.isdisjoint(catalog)


def test_smoke_fixture_manifests_exist() -> None:
    for filename in SMOKE_FILES:
        assert (SMOKE_MANIFEST_DIR / filename).is_file()


def test_smoke_fixture_manifests_load_by_explicit_path() -> None:
    ids = {load_manifest(SMOKE_MANIFEST_DIR / filename).manifest_id for filename in SMOKE_FILES}
    assert ids == SMOKE_IDS


def test_smoke_fixture_manifests_not_loadable_by_active_catalog_id() -> None:
    for manifest_id in SMOKE_IDS:
        with pytest.raises(ManifestLoadError):
            load_manifest_by_id(manifest_id, "manifests")


def test_manifest_health_excludes_smoke_fixture_manifests() -> None:
    result = run_manifest_health_check(manifest_dir="manifests", smoke_limit=0)
    ids = {item["manifest_id"] for item in result["manifests"]}
    assert SMOKE_IDS.isdisjoint(ids)


def test_release_health_passes_when_only_smoke_fixtures_are_critical() -> None:
    result = run_manifest_health_check(manifest_dir="manifests", smoke_limit=0)
    assert result["summary"]["critical"] == 0


def test_active_catalog_still_flags_critical_manifest_if_placed_there(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    manifest = build_manifest_from_template("manual_read_tool", "active.critical", "Active Critical")
    manifest["live_execution"] = {"enabled": True, "requires_approval": True}
    (manifest_dir / "active_critical.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = run_manifest_health_check(manifest_dir=manifest_dir, runtime_data_dir=tmp_path / "runtime")
    assert result["summary"]["critical"] == 1
    assert result["status"] == "HAS_FAILURES"


def test_operator_catalog_does_not_show_smoke_fixture_manifests() -> None:
    catalog = list_manifest_catalog("manifests")
    ids = {item.get("manifest_id") for item in catalog}
    assert SMOKE_IDS.isdisjoint(ids)
