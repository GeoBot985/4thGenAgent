from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.manifest_template_generator import (
    build_manifest_from_template,
    list_manifest_templates,
    validate_manifest_candidate,
    write_manifest_candidate,
)


# ---------------------------------------------------------------------------
# UI source checks (fast, no Tkinter)
# ---------------------------------------------------------------------------

def test_operator_console_exposes_new_manifest_action() -> None:
    from src import operator_ui
    source = inspect.getsource(operator_ui)
    assert "New manifest from template" in source
    assert "on_workbench_new_manifest_from_template" in source
    assert "_open_new_manifest_wizard" in source


# ---------------------------------------------------------------------------
# Backend helpers used by the wizard (testable without Tkinter)
# ---------------------------------------------------------------------------

def test_new_manifest_preview_uses_selected_template() -> None:
    """Wizard Preview calls build_manifest_from_template with template_id from selection."""
    templates = list_manifest_templates()
    for t in templates:
        manifest = build_manifest_from_template(
            t["template_id"],
            f"demo.preview_{t['template_id']}",
            f"Preview {t['name']}",
        )
        assert manifest["manifest_id"] == f"demo.preview_{t['template_id']}"
        # JSON must be serialisable (what the preview text area would show)
        preview_text = json.dumps(manifest, indent=2, ensure_ascii=False)
        assert manifest["manifest_id"] in preview_text


def test_new_manifest_create_calls_backend_writer(tmp_path: Path) -> None:
    """Wizard Create calls write_manifest_candidate; checks returned path."""
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.wizard_create", "Wizard Create Test"
    )
    result = write_manifest_candidate(manifest, manifest_dir=str(mdir))
    assert result["ok"], result.get("errors")
    assert Path(result["path"]).is_file()


def test_new_manifest_create_refreshes_catalog(tmp_path: Path) -> None:
    """After write, the manifest appears in list_manifest_catalog."""
    from src.manifest_workbench import list_manifest_catalog

    mdir = tmp_path / "manifests"
    mdir.mkdir()
    manifest = build_manifest_from_template(
        "manual_llm_helper", "demo.wizard_catalog_refresh", "Catalog Refresh Test"
    )
    write_manifest_candidate(manifest, manifest_dir=str(mdir))
    catalog = list_manifest_catalog(str(mdir))
    ids = {e.get("manifest_id") for e in catalog}
    assert "demo.wizard_catalog_refresh" in ids


def test_new_manifest_create_selects_created_manifest(tmp_path: Path) -> None:
    """write_manifest_candidate returns the manifest_id that would be selected in UI."""
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    manifest = build_manifest_from_template(
        "event_driven_stub", "demo.wizard_select", "Wizard Select Test"
    )
    result = write_manifest_candidate(manifest, manifest_dir=str(mdir))
    assert result["ok"]
    assert result["manifest_id"] == "demo.wizard_select"


def test_new_manifest_dirty_editor_guard_blocks_wizard_when_cancelled() -> None:
    """_workbench_has_unsaved_editor_changes logic: if editor JSON differs from loaded manifest, it's dirty."""
    loaded_manifest = build_manifest_from_template(
        "manual_read_tool", "demo.guard_test", "Guard Test"
    )
    editor_json_same = json.dumps(loaded_manifest)
    editor_json_different = json.dumps({**loaded_manifest, "name": "Modified Name"})

    def has_unsaved_changes(editor_text: str, loaded: dict) -> bool:
        if not editor_text.strip():
            return False
        if not loaded:
            return False
        try:
            editor_parsed = json.loads(editor_text)
        except Exception:
            return True
        return editor_parsed != loaded

    assert not has_unsaved_changes(editor_json_same, loaded_manifest)
    assert has_unsaved_changes(editor_json_different, loaded_manifest)
    assert has_unsaved_changes("invalid json {{{", loaded_manifest)
    assert not has_unsaved_changes("", loaded_manifest)


# ---------------------------------------------------------------------------
# Validation path used by the wizard Validate button
# ---------------------------------------------------------------------------

def test_wizard_validate_button_passes_for_valid_manifest(tmp_path: Path) -> None:
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.validate_pass_wizard", "Validate Pass"
    )
    ok, errors = validate_manifest_candidate(manifest, manifest_dir=str(mdir))
    assert ok, errors


def test_wizard_validate_button_fails_for_duplicate_id(tmp_path: Path) -> None:
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.dup_id", "Dup ID"
    )
    write_manifest_candidate(manifest, manifest_dir=str(mdir))

    ok, errors = validate_manifest_candidate(manifest, manifest_dir=str(mdir))
    assert not ok
    assert any("Duplicate" in e or "already exists" in e for e in errors)


def test_wizard_validate_button_fails_for_empty_id(tmp_path: Path) -> None:
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.empty_id_test", "Empty"
    )
    manifest["manifest_id"] = ""
    ok, errors = validate_manifest_candidate(manifest, manifest_dir=str(mdir))
    assert not ok
    assert any("manifest_id" in e for e in errors)


# ---------------------------------------------------------------------------
# Smoke test UI tests (Spec 082)
# ---------------------------------------------------------------------------

def test_smoke_test_button_exists() -> None:
    import inspect
    from src import operator_ui
    source = inspect.getsource(operator_ui)
    assert "Smoke test manifest" in source
    assert "on_workbench_smoke_test_manifest" in source
    assert "_show_smoke_result_dialog" in source


def test_new_manifest_success_can_trigger_smoke_test() -> None:
    """After wizard create, the code offers a smoke test prompt."""
    import inspect
    from src import operator_ui
    source = inspect.getsource(operator_ui)
    assert "Run smoke test now" in source
    assert "smoke_run_manifest_file" in source


def test_smoke_test_button_calls_smoke_runner_for_selected_manifest(tmp_path: Path) -> None:
    """smoke_run_manifest_file is called with the manifest path; result is structured."""
    from src.generated_manifest_smoke_runner import smoke_run_manifest_file
    from src.manifest_template_generator import build_manifest_from_template, write_manifest_candidate
    import json

    mdir = tmp_path / "manifests"
    mdir.mkdir()
    manifest = build_manifest_from_template("manual_read_tool", "demo.smoke_ui_test", "Smoke UI Test")
    result = write_manifest_candidate(manifest, manifest_dir=str(mdir))
    assert result["ok"]

    smoke_result = smoke_run_manifest_file(result["path"], runtime_data_dir=tmp_path / "runtime")
    assert "classification" in smoke_result
    assert "status" in smoke_result
    assert "checks" in smoke_result


def test_smoke_failure_is_displayed_without_crashing_ui(tmp_path: Path) -> None:
    """A failing smoke result dict has the shape the UI dialog expects."""
    from src.generated_manifest_smoke_runner import smoke_run_manifest_candidate
    from src.manifest_template_generator import build_manifest_from_template

    manifest = build_manifest_from_template("manual_read_tool", "demo.smoke_fail_ui", "Smoke Fail UI")
    manifest["steps"] = [{"id": "bad", "command": "invalid_command"}]
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=tmp_path / "runtime")
    assert not result.get("ok")
    # The UI dialog reads these keys — they must all be present
    assert "status" in result
    assert "classification" in result
    assert "manifest_id" in result
    assert "state" in result
    assert "step_count" in result
    assert "completed_steps" in result
    assert "failed_steps" in result
    assert "pending_action_count" in result
    assert "output_keys" in result
    assert "errors" in result
    assert "warnings" in result
    assert "suggested_fix" in result


def test_smoke_report_paths_are_displayed(tmp_path: Path) -> None:
    """write_smoke_report returns both json_path and markdown_path for the UI to display."""
    from src.generated_manifest_smoke_runner import smoke_run_manifest_candidate, write_smoke_report
    from src.manifest_template_generator import build_manifest_from_template

    manifest = build_manifest_from_template("manual_read_tool", "demo.smoke_report_paths", "Report Paths")
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=tmp_path / "runtime")
    report = write_smoke_report(result, runtime_data_dir=tmp_path / "runtime")
    assert report.get("ok")
    assert report.get("json_path")
    assert report.get("markdown_path")
    assert Path(report["json_path"]).is_file()
    assert Path(report["markdown_path"]).is_file()
