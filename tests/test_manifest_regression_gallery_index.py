from __future__ import annotations

from pathlib import Path

from src.manifest_regression_gallery import validate_gallery_index


GALLERY_DIR = Path("tests/fixtures/manifest_regression_gallery")


def test_gallery_index_exists_and_loads() -> None:
    result = validate_gallery_index(GALLERY_DIR)
    assert result["ok"]
    assert result["status"] == "PASS"
    assert result["fixture_count"] >= 41


def test_gallery_fixture_ids_are_unique() -> None:
    result = validate_gallery_index(GALLERY_DIR)
    assert result["ok"]
    assert result["fixture_count"] == 42


def test_gallery_fixture_paths_exist() -> None:
    result = validate_gallery_index(GALLERY_DIR)
    assert result["ok"]


def test_gallery_fixture_required_fields_present() -> None:
    result = validate_gallery_index(GALLERY_DIR)
    assert result["ok"]


def test_gallery_has_required_categories() -> None:
    result = validate_gallery_index(GALLERY_DIR)
    assert result["ok"]
    for category in ("valid", "structural", "command", "inputs", "validations", "completion", "side_effects", "events", "llm", "governance"):
        assert category in result["categories"]


def test_gallery_has_minimum_fixture_count() -> None:
    result = validate_gallery_index(GALLERY_DIR)
    assert result["fixture_count"] >= 41
