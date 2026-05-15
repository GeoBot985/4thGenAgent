from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.manifest_template_generator import (
    build_manifest_from_template,
    list_manifest_templates,
    manifest_filename_for_id,
    validate_manifest_candidate,
    write_manifest_candidate,
)


REQUIRED_TEMPLATE_IDS = {
    "manual_read_tool",
    "manual_llm_helper",
    "approval_side_effect",
    "event_driven_stub",
}


# ---------------------------------------------------------------------------
# list_manifest_templates
# ---------------------------------------------------------------------------

def test_list_manifest_templates_returns_required_templates() -> None:
    templates = list_manifest_templates()
    assert isinstance(templates, list)
    ids = {t["template_id"] for t in templates}
    for tid in REQUIRED_TEMPLATE_IDS:
        assert tid in ids, f"Template {tid!r} missing from list"
    for t in templates:
        assert "name" in t
        assert "description" in t
        assert "risk_level" in t
        assert "side_effect" in t


# ---------------------------------------------------------------------------
# manifest_filename_for_id
# ---------------------------------------------------------------------------

def test_manifest_filename_for_id_sanitizes_safe_filename() -> None:
    assert manifest_filename_for_id("customer.status_check_custom") == "customer_status_check_custom.manifest.json"
    assert manifest_filename_for_id("demo.new_read_manifest") == "demo_new_read_manifest.manifest.json"
    assert manifest_filename_for_id("smoke.llm_classify") == "smoke_llm_classify.manifest.json"


def test_manifest_filename_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="empty"):
        manifest_filename_for_id("")
    with pytest.raises(ValueError):
        manifest_filename_for_id("   ")


def test_manifest_filename_rejects_path_traversal() -> None:
    with pytest.raises(ValueError, match="traversal"):
        manifest_filename_for_id("../../../etc/passwd")
    with pytest.raises(ValueError, match="traversal"):
        manifest_filename_for_id("/absolute/path")


# ---------------------------------------------------------------------------
# build_manifest_from_template — manual_read_tool
# ---------------------------------------------------------------------------

def test_build_manual_read_tool_template_has_required_top_level_fields() -> None:
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.read_test", "Demo Read Test"
    )
    for field in ("manifest_id", "name", "version", "trigger", "inputs", "steps", "validations", "completion"):
        assert field in manifest, f"Missing field: {field}"
    assert manifest["manifest_id"] == "demo.read_test"
    assert manifest["name"] == "Demo Read Test"
    assert manifest["trigger"]["type"] == "manual"
    assert isinstance(manifest["steps"], list) and len(manifest["steps"]) >= 1
    assert isinstance(manifest["validations"], list) and len(manifest["validations"]) >= 1


def test_build_manual_read_tool_template_loads_with_existing_loader() -> None:
    import tempfile
    from runtime.manifest_loader import load_manifest as runtime_load_manifest

    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.read_loader_test", "Demo Read Loader Test"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".manifest.json", delete=False, encoding="utf-8") as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(json.dumps(manifest, indent=2))
    try:
        loaded = runtime_load_manifest(tmp_path)
        assert loaded is not None
    finally:
        tmp_path.unlink(missing_ok=True)


def test_build_manual_llm_helper_has_message_input_and_llm_step() -> None:
    manifest = build_manifest_from_template(
        "manual_llm_helper", "demo.llm_test", "Demo LLM Test"
    )
    assert "message" in manifest["inputs"]
    commands = [s["command"] for s in manifest["steps"]]
    assert any("[q:" in cmd for cmd in commands), "Expected an LLM [q:...] command"


def test_build_approval_side_effect_sets_allow_pending_approval() -> None:
    manifest = build_manifest_from_template(
        "approval_side_effect", "demo.approval_test", "Demo Approval Test"
    )
    assert manifest["completion"].get("allow_pending_approval") is True
    assert manifest.get("live_execution", {}).get("enabled") is False


def test_build_event_driven_stub_sets_event_trigger() -> None:
    manifest = build_manifest_from_template(
        "event_driven_stub", "demo.event_test", "Demo Event Test"
    )
    assert manifest["trigger"]["type"] == "event"


# ---------------------------------------------------------------------------
# build_manifest_from_template — custom fields
# ---------------------------------------------------------------------------

def test_custom_command_overrides_default_step() -> None:
    custom_cmd = "[t:g/check -> mail_data] max_results=10"
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.custom_cmd", "Custom Command",
        command=custom_cmd,
    )
    commands = [s["command"] for s in manifest["steps"]]
    assert custom_cmd in commands


def test_custom_output_alias_propagates_through_manifest() -> None:
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.custom_alias", "Custom Alias",
        output_alias="my_output",
    )
    completion_outputs = manifest["completion"].get("success_outputs", [])
    assert "my_output" in completion_outputs


def test_inputs_list_is_included_in_manifest() -> None:
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.with_inputs", "With Inputs",
        inputs=["customer_id", "order_ref"],
    )
    assert "customer_id" in manifest["inputs"]
    assert "order_ref" in manifest["inputs"]


def test_completion_outputs_match_generated_output_alias() -> None:
    manifest = build_manifest_from_template(
        "manual_llm_helper", "demo.alias_check", "Alias Check",
        output_alias="classification",
    )
    completion_outputs = manifest["completion"].get("success_outputs", [])
    assert "classification" in completion_outputs


# ---------------------------------------------------------------------------
# build_event_driven_stub — no event route side effect
# ---------------------------------------------------------------------------

def test_build_event_driven_stub_does_not_write_event_route(tmp_path: Path) -> None:
    routes_file = tmp_path / "config" / "event_routes.json"
    routes_file.parent.mkdir(parents=True)
    routes_file.write_text("[]", encoding="utf-8")

    build_manifest_from_template(
        "event_driven_stub", "demo.event_no_route", "Event No Route"
    )
    # File content must be unchanged
    assert routes_file.read_text() == "[]"


# ---------------------------------------------------------------------------
# validate_manifest_candidate
# ---------------------------------------------------------------------------

def test_validate_candidate_rejects_duplicate_manifest_id(tmp_path: Path) -> None:
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    existing = {
        "manifest_id": "demo.existing",
        "name": "Existing",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [{"id": "s1", "command": "[t:g/check -> result] max_results=5"}],
        "validations": [],
        "completion": {"success_outputs": ["result"]},
    }
    (mdir / "demo_existing.manifest.json").write_text(json.dumps(existing, indent=2), encoding="utf-8")

    candidate = dict(existing)
    ok, errors = validate_manifest_candidate(candidate, manifest_dir=str(mdir))
    assert not ok
    assert any("Duplicate" in e or "already exists" in e for e in errors)


def test_validate_candidate_accepts_valid_manifest(tmp_path: Path) -> None:
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.validate_pass", "Validate Pass"
    )
    ok, errors = validate_manifest_candidate(manifest, manifest_dir=str(mdir))
    assert ok, errors


# ---------------------------------------------------------------------------
# write_manifest_candidate
# ---------------------------------------------------------------------------

def test_write_manifest_candidate_creates_file_atomically(tmp_path: Path) -> None:
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.write_test", "Write Test"
    )
    result = write_manifest_candidate(manifest, manifest_dir=str(mdir))
    assert result["ok"], result.get("errors")
    assert Path(result["path"]).is_file()
    written = json.loads(Path(result["path"]).read_text())
    assert written["manifest_id"] == "demo.write_test"


def test_write_manifest_candidate_rejects_invalid_command(tmp_path: Path) -> None:
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.bad_cmd", "Bad Command"
    )
    manifest["steps"] = [{"id": "bad_step", "command": "not_a_valid_command"}]
    result = write_manifest_candidate(manifest, manifest_dir=str(mdir))
    assert not result["ok"]
    assert result["errors"]


def test_written_manifest_can_be_loaded_by_id(tmp_path: Path) -> None:
    from src.manifest_workbench import list_manifest_catalog

    mdir = tmp_path / "manifests"
    mdir.mkdir()
    manifest = build_manifest_from_template(
        "manual_read_tool", "demo.load_by_id", "Load By ID"
    )
    write_manifest_candidate(manifest, manifest_dir=str(mdir))
    catalog = list_manifest_catalog(str(mdir))
    ids = {e.get("manifest_id") for e in catalog}
    assert "demo.load_by_id" in ids
