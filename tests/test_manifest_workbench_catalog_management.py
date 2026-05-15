from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from src.manifest_workbench import (
    archive_manifest,
    duplicate_manifest,
    list_archived_manifests,
    list_manifest_catalog,
    rename_manifest,
    restore_archived_manifest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_MANIFEST = {
    "manifest_id": "test.catalog_mgmt",
    "name": "Catalog Management Test",
    "version": 1,
    "trigger": {"type": "manual"},
    "inputs": [],
    "steps": [
        {
            "id": "step_one",
            "command": "[q:classify_customer_message -> category] text=$inputs.message",
        }
    ],
    "validations": [
        {
            "id": "category_exists",
            "type": "output_exists",
            "output": "category",
            "message": "Classification output must exist.",
        }
    ],
    "completion": {"success_outputs": ["category"]},
}


def _write_manifest(directory: Path, manifest: dict) -> Path:
    mid = manifest["manifest_id"].replace(".", "_")
    path = directory / f"{mid}.manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


@pytest.fixture()
def manifest_dir(tmp_path: Path) -> Path:
    """Temporary manifests directory with one test manifest pre-loaded."""
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    _write_manifest(mdir, MINIMAL_MANIFEST)
    return mdir


# ---------------------------------------------------------------------------
# duplicate_manifest
# ---------------------------------------------------------------------------

def test_duplicate_manifest_creates_copy_with_new_id(manifest_dir: Path) -> None:
    result = duplicate_manifest("test.catalog_mgmt", manifest_dir=str(manifest_dir))
    assert result["ok"], result.get("error")
    assert result["new_manifest_id"] == "test.catalog_mgmt_copy"
    assert Path(result["path"]).is_file()
    data = json.loads(Path(result["path"]).read_text())
    assert data["manifest_id"] == "test.catalog_mgmt_copy"


def test_duplicate_manifest_increments_copy_suffix_when_needed(manifest_dir: Path) -> None:
    # Create the _copy variant first
    copy_manifest = dict(MINIMAL_MANIFEST)
    copy_manifest["manifest_id"] = "test.catalog_mgmt_copy"
    copy_manifest["name"] = "Catalog Management Test Copy"
    _write_manifest(manifest_dir, copy_manifest)

    result = duplicate_manifest("test.catalog_mgmt", manifest_dir=str(manifest_dir))
    assert result["ok"], result.get("error")
    assert result["new_manifest_id"] == "test.catalog_mgmt_copy_2"


def test_duplicate_manifest_preserves_steps_validations_completion(manifest_dir: Path) -> None:
    result = duplicate_manifest("test.catalog_mgmt", manifest_dir=str(manifest_dir))
    assert result["ok"], result.get("error")
    data = json.loads(Path(result["path"]).read_text())
    assert len(data["steps"]) == len(MINIMAL_MANIFEST["steps"])
    assert len(data["validations"]) == len(MINIMAL_MANIFEST["validations"])
    assert data["completion"] == MINIMAL_MANIFEST["completion"]


# ---------------------------------------------------------------------------
# rename_manifest
# ---------------------------------------------------------------------------

def test_rename_manifest_updates_id_name_and_filename(manifest_dir: Path) -> None:
    result = rename_manifest(
        "test.catalog_mgmt",
        "test.catalog_mgmt_renamed",
        new_name="Renamed Manifest",
        manifest_dir=str(manifest_dir),
    )
    assert result["ok"], result.get("error")
    assert result["new_manifest_id"] == "test.catalog_mgmt_renamed"
    assert not Path(result["old_path"]).exists(), "Old file should be removed"
    new_file = Path(result["new_path"])
    assert new_file.is_file()
    data = json.loads(new_file.read_text())
    assert data["manifest_id"] == "test.catalog_mgmt_renamed"
    assert data["name"] == "Renamed Manifest"


def test_rename_manifest_blocks_existing_manifest_id(manifest_dir: Path) -> None:
    # Add a second manifest
    second = dict(MINIMAL_MANIFEST)
    second["manifest_id"] = "test.catalog_mgmt_other"
    second["name"] = "Other"
    _write_manifest(manifest_dir, second)

    result = rename_manifest(
        "test.catalog_mgmt",
        "test.catalog_mgmt_other",
        manifest_dir=str(manifest_dir),
    )
    assert not result["ok"]
    assert "already exists" in result["error"].lower()


# ---------------------------------------------------------------------------
# archive_manifest
# ---------------------------------------------------------------------------

def test_archive_manifest_moves_file_to_archive(manifest_dir: Path) -> None:
    result = archive_manifest("test.catalog_mgmt", manifest_dir=str(manifest_dir))
    assert result["ok"], result.get("error")
    assert not Path(result["from_path"]).exists(), "Original file should be gone"
    archive_path = Path(result["archive_path"])
    assert archive_path.is_file(), "Archived file should exist"
    assert "archive" in str(archive_path)


def test_archive_manifest_removes_manifest_from_active_catalog(manifest_dir: Path) -> None:
    archive_manifest("test.catalog_mgmt", manifest_dir=str(manifest_dir))
    catalog = list_manifest_catalog(str(manifest_dir))
    ids = {e.get("manifest_id") for e in catalog}
    assert "test.catalog_mgmt" not in ids


# ---------------------------------------------------------------------------
# restore_archived_manifest
# ---------------------------------------------------------------------------

def test_restore_archived_manifest_moves_file_back_to_active_catalog(manifest_dir: Path) -> None:
    archive_result = archive_manifest("test.catalog_mgmt", manifest_dir=str(manifest_dir))
    assert archive_result["ok"]

    restore_result = restore_archived_manifest(
        archive_result["archive_path"], manifest_dir=str(manifest_dir)
    )
    assert restore_result["ok"], restore_result.get("error")
    restored = Path(restore_result["restored_path"])
    assert restored.is_file()
    assert not Path(restore_result["archive_path"]).exists()

    catalog = list_manifest_catalog(str(manifest_dir))
    ids = {e.get("manifest_id") for e in catalog}
    assert "test.catalog_mgmt" in ids


def test_restore_archived_manifest_blocks_active_duplicate_id(manifest_dir: Path) -> None:
    # Archive a copy, then re-create the original active file so restore is blocked
    archive_result = archive_manifest("test.catalog_mgmt", manifest_dir=str(manifest_dir))
    assert archive_result["ok"]
    # Re-create an active manifest with same ID
    _write_manifest(manifest_dir, MINIMAL_MANIFEST)

    restore_result = restore_archived_manifest(
        archive_result["archive_path"], manifest_dir=str(manifest_dir)
    )
    assert not restore_result["ok"]
    assert "already exists" in restore_result["error"].lower()


# ---------------------------------------------------------------------------
# list_archived_manifests
# ---------------------------------------------------------------------------

def test_list_archived_manifests_returns_archived_items(manifest_dir: Path) -> None:
    assert list_archived_manifests(str(manifest_dir)) == []

    archive_manifest("test.catalog_mgmt", manifest_dir=str(manifest_dir))
    archived = list_archived_manifests(str(manifest_dir))
    assert len(archived) == 1
    assert archived[0]["manifest_id"] == "test.catalog_mgmt"


# ---------------------------------------------------------------------------
# Active catalog isolation: archive and drafts must not appear
# ---------------------------------------------------------------------------

def test_catalog_actions_do_not_include_drafts_or_archive_in_active_catalog(manifest_dir: Path) -> None:
    # Archive one manifest
    archive_manifest("test.catalog_mgmt", manifest_dir=str(manifest_dir))

    # Create a drafts directory with a manifest
    drafts_dir = manifest_dir / "drafts"
    drafts_dir.mkdir()
    draft = dict(MINIMAL_MANIFEST)
    draft["manifest_id"] = "test.draft_manifest"
    draft["name"] = "Draft"
    (drafts_dir / "test_draft_manifest.manifest.json").write_text(
        json.dumps(draft, indent=2), encoding="utf-8"
    )

    catalog = list_manifest_catalog(str(manifest_dir))
    ids = {e.get("manifest_id") for e in catalog}
    assert "test.catalog_mgmt" not in ids, "Archived manifest must not appear in active catalog"
    assert "test.draft_manifest" not in ids, "Draft manifest must not appear in active catalog"


# ---------------------------------------------------------------------------
# Optional UI smoke test
# ---------------------------------------------------------------------------

def test_operator_ui_exposes_catalog_management_buttons() -> None:
    import inspect
    from src import operator_ui

    source = inspect.getsource(operator_ui)
    assert "Duplicate manifest" in source
    assert "Rename manifest" in source
    assert "Archive manifest" in source
    assert "Restore archived" in source
    assert "on_workbench_duplicate_manifest" in source
    assert "on_workbench_rename_manifest" in source
    assert "on_workbench_archive_manifest" in source
    assert "on_workbench_restore_archived" in source
