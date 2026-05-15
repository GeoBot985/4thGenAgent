from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.manifest_authoring_feedback import explain_manifest_failure
from src.manifest_autofix import apply_manifest_fix_preview, propose_manifest_fixes
from src.manifest_regression_gallery import (
    iter_gallery_fixtures,
    load_fixture_manifest,
    load_gallery_index,
)

_GALLERY_DIR = Path("tests/fixtures/broken_manifests")


# ---------------------------------------------------------------------------
# Structural / index tests
# ---------------------------------------------------------------------------


def test_gallery_index_exists_and_loads() -> None:
    index = load_gallery_index(_GALLERY_DIR)
    assert isinstance(index, dict)
    assert index.get("version") == 1
    assert isinstance(index.get("fixtures"), list)
    assert len(index["fixtures"]) >= 11


def test_gallery_fixture_files_exist() -> None:
    fixtures = iter_gallery_fixtures(_GALLERY_DIR)
    for fixture in fixtures:
        path = _GALLERY_DIR / fixture["path"]
        assert path.exists(), f"Fixture file missing: {fixture['path']} (fixture id: {fixture['id']})"


def test_gallery_fixture_ids_are_unique() -> None:
    fixtures = iter_gallery_fixtures(_GALLERY_DIR)
    ids = [f["id"] for f in fixtures]
    assert len(ids) == len(set(ids)), f"Duplicate fixture IDs found: {[x for x in ids if ids.count(x) > 1]}"


def test_gallery_expected_findings_are_declared() -> None:
    fixtures = iter_gallery_fixtures(_GALLERY_DIR)
    for fixture in fixtures:
        assert "expected_findings" in fixture, f"[{fixture['id']}] missing expected_findings"
        assert isinstance(fixture["expected_findings"], list), f"[{fixture['id']}] expected_findings must be a list"
        assert "expected_autofix" in fixture, f"[{fixture['id']}] missing expected_autofix"


# ---------------------------------------------------------------------------
# Per-fixture finding tests
# ---------------------------------------------------------------------------


def test_completion_output_missing_fixture_matches_expected_finding() -> None:
    fixture = _get_fixture("completion_output_missing")
    result = load_fixture_manifest(fixture, _GALLERY_DIR)
    assert result["ok"]
    guidance = explain_manifest_failure(manifest=result["manifest"])
    ids = {f["id"] for f in guidance["findings"]}
    assert "completion_output_missing" in ids


def test_validation_output_missing_fixture_matches_expected_finding() -> None:
    fixture = _get_fixture("validation_output_missing")
    result = load_fixture_manifest(fixture, _GALLERY_DIR)
    assert result["ok"]
    guidance = explain_manifest_failure(manifest=result["manifest"])
    ids = {f["id"] for f in guidance["findings"]}
    assert "validation_references_missing_output" in ids


def test_unknown_tool_fixture_returns_not_supported_autofix() -> None:
    fixture = _get_fixture("unknown_tool")
    result = load_fixture_manifest(fixture, _GALLERY_DIR)
    assert result["ok"]
    # unknown_tool only comes from smoke; inject it manually
    fake_guidance = {
        "ok": True,
        "status": "HAS_FINDINGS",
        "severity": "error",
        "summary": "Unknown tool",
        "findings": [{
            "id": "unknown_tool",
            "severity": "error",
            "location": "steps[0].command",
            "message": "The manifest references a tool that is not registered.",
            "suggested_fix": "Use a registered tool.",
            "source": "smoke_result",
        }],
        "next_action": "Fix tool.",
    }
    fix_result = propose_manifest_fixes(result["manifest"], guidance=fake_guidance)
    unknown_proposals = [p for p in fix_result["proposals"] if p["finding_id"] == "unknown_tool"]
    assert unknown_proposals, "Expected at least one unknown_tool proposal"
    assert all(p["status"] == "NOT_SUPPORTED" for p in unknown_proposals)
    assert all(p["risk"] == "blocked" for p in unknown_proposals)


def test_invalid_command_fixture_returns_not_supported_autofix() -> None:
    fixture = _get_fixture("invalid_command")
    result = load_fixture_manifest(fixture, _GALLERY_DIR)
    assert result["ok"]
    guidance = explain_manifest_failure(manifest=result["manifest"])
    fix_result = propose_manifest_fixes(result["manifest"], guidance=guidance)
    command_proposals = [
        p for p in fix_result["proposals"]
        if p["finding_id"] in ("command_parse_error", "command_invalid")
    ]
    assert command_proposals, "Expected command_parse_error or command_invalid proposal"
    assert all(p["status"] == "NOT_SUPPORTED" for p in command_proposals)


def test_input_used_but_not_declared_fixture_has_supported_autofix() -> None:
    fixture = _get_fixture("input_used_but_not_declared")
    result = load_fixture_manifest(fixture, _GALLERY_DIR)
    assert result["ok"]
    guidance = explain_manifest_failure(manifest=result["manifest"])
    fix_result = propose_manifest_fixes(result["manifest"], guidance=guidance)
    proposals = [p for p in fix_result["proposals"] if p["finding_id"] == "input_used_but_not_declared"]
    assert proposals, "Expected input_used_but_not_declared proposal"
    assert any(p["status"] == "PROPOSED" and p["risk"] == "low" for p in proposals)
    # Verify the patch adds the missing input
    supported = next(p for p in proposals if p["status"] == "PROPOSED")
    add_patches = [patch for patch in supported["patches"] if patch["op"] == "add" and patch.get("new_value") == "message"]
    assert add_patches, "Expected a patch adding 'message' to inputs"


def test_input_declared_but_not_used_fixture_has_supported_autofix() -> None:
    fixture = _get_fixture("input_declared_but_not_used")
    result = load_fixture_manifest(fixture, _GALLERY_DIR)
    assert result["ok"]
    guidance = explain_manifest_failure(manifest=result["manifest"])
    ids = {f["id"] for f in guidance["findings"]}
    assert "input_declared_but_not_used" in ids
    fix_result = propose_manifest_fixes(result["manifest"], guidance=guidance)
    proposals = [p for p in fix_result["proposals"] if p["finding_id"] == "input_declared_but_not_used"]
    assert any(p["status"] == "PROPOSED" and p["risk"] == "low" for p in proposals)
    supported = next(p for p in proposals if p["status"] == "PROPOSED")
    assert any(patch["op"] == "remove" for patch in supported["patches"])


def test_duplicate_step_id_fixture_has_supported_autofix() -> None:
    fixture = _get_fixture("duplicate_step_id")
    result = load_fixture_manifest(fixture, _GALLERY_DIR)
    assert result["ok"]
    guidance = explain_manifest_failure(manifest=result["manifest"])
    ids = {f["id"] for f in guidance["findings"]}
    assert "duplicate_step_id" in ids
    fix_result = propose_manifest_fixes(result["manifest"], guidance=guidance)
    proposals = [p for p in fix_result["proposals"] if p["finding_id"] == "duplicate_step_id"]
    assert any(p["status"] == "PROPOSED" and p["risk"] == "low" for p in proposals)
    supported = next(p for p in proposals if p["status"] == "PROPOSED")
    # Should rename duplicate step to read_data_2
    patch = supported["patches"][0]
    assert patch["op"] == "replace"
    assert patch["old_value"] == "read_data"
    assert patch["new_value"] == "read_data_2"


def test_unsafe_live_execution_fixture_has_supported_autofix() -> None:
    fixture = _get_fixture("unsafe_live_execution")
    result = load_fixture_manifest(fixture, _GALLERY_DIR)
    assert result["ok"]
    guidance = explain_manifest_failure(manifest=result["manifest"])
    ids = {f["id"] for f in guidance["findings"]}
    assert "live_execution_enabled" in ids
    critical = [f for f in guidance["findings"] if f["id"] == "live_execution_enabled"]
    assert critical[0]["severity"] == "critical"
    fix_result = propose_manifest_fixes(result["manifest"], guidance=guidance)
    proposals = [p for p in fix_result["proposals"] if p["finding_id"] == "live_execution_enabled"]
    assert any(p["status"] == "PROPOSED" and p["risk"] == "low" for p in proposals)
    supported = next(p for p in proposals if p["status"] == "PROPOSED")
    patch = supported["patches"][0]
    assert patch["op"] == "replace"
    assert patch["old_value"] is True
    assert patch["new_value"] is False


def test_missing_output_alias_fixture_is_not_supported_autofix() -> None:
    fixture = _get_fixture("missing_output_alias")
    result = load_fixture_manifest(fixture, _GALLERY_DIR)
    assert result["ok"]
    guidance = explain_manifest_failure(manifest=result["manifest"])
    ids = {f["id"] for f in guidance["findings"]}
    assert "step_missing_output_alias" in ids
    fix_result = propose_manifest_fixes(result["manifest"], guidance=guidance)
    # No proposal should be both PROPOSED and low risk
    applyable = [
        p for p in fix_result["proposals"]
        if p["status"] == "PROPOSED" and p["risk"] == "low"
    ]
    assert applyable == [], f"Expected no applyable proposals, got: {applyable}"


def test_side_effect_without_pending_expectation_fixture_is_not_supported_autofix() -> None:
    fixture = _get_fixture("side_effect_without_pending_expectation")
    result = load_fixture_manifest(fixture, _GALLERY_DIR)
    assert result["ok"]
    guidance = explain_manifest_failure(manifest=result["manifest"])
    ids = {f["id"] for f in guidance["findings"]}
    assert "side_effect_command_without_pending_expectation" in ids
    fix_result = propose_manifest_fixes(result["manifest"], guidance=guidance)
    proposals = [
        p for p in fix_result["proposals"]
        if p["finding_id"] == "side_effect_command_without_pending_expectation"
    ]
    assert proposals
    assert all(p["status"] == "NOT_SUPPORTED" for p in proposals)


def test_malformed_json_fixture_returns_invalid_json_guidance() -> None:
    fixture = _get_fixture("malformed_json")
    result = load_fixture_manifest(fixture, _GALLERY_DIR)
    assert not result["ok"], "Expected malformed_json to fail JSON parsing"
    assert result["exception"] is not None
    guidance = explain_manifest_failure(exception=result["exception"])
    assert guidance["status"] == "HAS_FINDINGS"
    ids = {f["id"] for f in guidance["findings"]}
    assert "json_parse_error" in ids


# ---------------------------------------------------------------------------
# Matrix tests (parametrised over whole gallery)
# ---------------------------------------------------------------------------


def test_every_gallery_fixture_produces_expected_findings() -> None:
    fixtures = iter_gallery_fixtures(_GALLERY_DIR)
    failures: list[str] = []

    for fixture in fixtures:
        load_result = load_fixture_manifest(fixture, _GALLERY_DIR)
        if load_result["ok"]:
            guidance = explain_manifest_failure(manifest=load_result["manifest"])
        else:
            guidance = explain_manifest_failure(exception=load_result["exception"])

        actual_ids = {f["id"] for f in guidance["findings"]}
        for expected_id in fixture["expected_findings"]:
            if expected_id not in actual_ids:
                failures.append(
                    f"[{fixture['id']}] Expected finding '{expected_id}' not found. "
                    f"Actual findings: {sorted(actual_ids)}"
                )

    assert not failures, "\n".join(failures)


def test_every_supported_autofix_preview_does_not_mutate_original() -> None:
    import copy

    fixtures = iter_gallery_fixtures(_GALLERY_DIR)
    for fixture in fixtures:
        load_result = load_fixture_manifest(fixture, _GALLERY_DIR)
        if not load_result["ok"]:
            continue  # malformed JSON — skip

        manifest = load_result["manifest"]
        original = copy.deepcopy(manifest)
        guidance = explain_manifest_failure(manifest=manifest)
        fix_result = propose_manifest_fixes(manifest, guidance=guidance)

        for proposal in fix_result["proposals"]:
            if proposal["status"] != "PROPOSED" or proposal["risk"] != "low":
                continue
            preview = apply_manifest_fix_preview(manifest, proposal)
            assert preview["ok"], (
                f"[{fixture['id']}] Preview failed for proposal {proposal['fix_id']}: "
                f"{preview.get('error', 'unknown')}"
            )
            assert manifest == original, (
                f"[{fixture['id']}] Original manifest was mutated during preview of {proposal['fix_id']}"
            )


def test_every_supported_autofix_preview_produces_valid_json() -> None:
    fixtures = iter_gallery_fixtures(_GALLERY_DIR)
    for fixture in fixtures:
        load_result = load_fixture_manifest(fixture, _GALLERY_DIR)
        if not load_result["ok"]:
            continue

        manifest = load_result["manifest"]
        guidance = explain_manifest_failure(manifest=manifest)
        fix_result = propose_manifest_fixes(manifest, guidance=guidance)

        for proposal in fix_result["proposals"]:
            if proposal["status"] != "PROPOSED" or proposal["risk"] != "low":
                continue
            preview = apply_manifest_fix_preview(manifest, proposal)
            assert preview["ok"], f"[{fixture['id']}] Preview failed: {preview.get('error')}"
            # Verify after_json is valid JSON
            try:
                parsed = json.loads(preview["after_json"])
            except Exception as exc:
                pytest.fail(
                    f"[{fixture['id']}] after_json is not valid JSON for proposal "
                    f"{proposal['fix_id']}: {exc}"
                )
            assert isinstance(parsed, dict), f"[{fixture['id']}] Patched manifest is not a dict"


def test_supported_autofixes_reduce_or_remove_target_finding() -> None:
    fixtures = iter_gallery_fixtures(_GALLERY_DIR)
    failures: list[str] = []

    for fixture in fixtures:
        if not fixture["expected_autofix"].get("supported"):
            continue
        load_result = load_fixture_manifest(fixture, _GALLERY_DIR)
        if not load_result["ok"]:
            continue

        manifest = load_result["manifest"]
        guidance = explain_manifest_failure(manifest=manifest)
        fix_result = propose_manifest_fixes(manifest, guidance=guidance)

        target_finding_id = fixture["expected_autofix"]["finding_id"]
        proposals = [
            p for p in fix_result["proposals"]
            if p["finding_id"] == target_finding_id and p["status"] == "PROPOSED"
        ]
        if not proposals:
            failures.append(f"[{fixture['id']}] No PROPOSED fix for '{target_finding_id}'")
            continue

        proposal = proposals[0]
        preview = apply_manifest_fix_preview(manifest, proposal)
        if not preview["ok"]:
            failures.append(
                f"[{fixture['id']}] Preview failed for '{target_finding_id}': {preview.get('error')}"
            )
            continue

        patched = preview["manifest"]
        after_guidance = explain_manifest_failure(manifest=patched)
        after_ids = {f["id"] for f in after_guidance["findings"]}

        # The target finding should be gone or reduced
        before_count = sum(1 for f in guidance["findings"] if f["id"] == target_finding_id)
        after_count = sum(1 for f in after_guidance["findings"] if f["id"] == target_finding_id)

        if after_count >= before_count and after_count > 0:
            failures.append(
                f"[{fixture['id']}] Target finding '{target_finding_id}' not reduced after fix "
                f"(before={before_count}, after={after_count})"
            )

    assert not failures, "\n".join(failures)


def test_unsupported_fixtures_do_not_generate_low_risk_applyable_patch() -> None:
    fixtures = iter_gallery_fixtures(_GALLERY_DIR)
    failures: list[str] = []

    for fixture in fixtures:
        if fixture["expected_autofix"].get("supported"):
            continue  # only checking unsupported fixtures

        load_result = load_fixture_manifest(fixture, _GALLERY_DIR)

        if load_result["ok"]:
            manifest = load_result["manifest"]
            guidance = explain_manifest_failure(manifest=manifest)
        else:
            # For malformed JSON fixtures, inject the json_parse_error finding
            guidance = explain_manifest_failure(exception=load_result["exception"])
            manifest = {}

        fix_result = propose_manifest_fixes(manifest, guidance=guidance)
        applyable = [
            p for p in fix_result["proposals"]
            if p["status"] == "PROPOSED" and p["risk"] == "low"
        ]

        if applyable:
            failures.append(
                f"[{fixture['id']}] Expected no applyable proposals, "
                f"got: {[p['finding_id'] for p in applyable]}"
            )

    assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------------
# Loader-specific tests
# ---------------------------------------------------------------------------


def test_manifest_regression_gallery_loader_index() -> None:
    index = load_gallery_index(_GALLERY_DIR)
    assert "version" in index
    assert "fixtures" in index
    fixture_ids = {f["id"] for f in index["fixtures"]}
    required_ids = {
        "completion_output_missing",
        "validation_output_missing",
        "unknown_tool",
        "invalid_command",
        "input_used_but_not_declared",
        "input_declared_but_not_used",
        "duplicate_step_id",
        "unsafe_live_execution",
        "missing_output_alias",
        "side_effect_without_pending_expectation",
        "malformed_json",
    }
    missing = required_ids - fixture_ids
    assert not missing, f"Gallery index missing required fixture IDs: {missing}"


def test_manifest_regression_gallery_loader_fixture_load() -> None:
    fixtures = iter_gallery_fixtures(_GALLERY_DIR)
    loaded_count = 0
    for fixture in fixtures:
        result = load_fixture_manifest(fixture, _GALLERY_DIR)
        assert "ok" in result
        assert "path" in result
        if result["ok"]:
            assert isinstance(result["manifest"], dict)
            assert result["exception"] is None
            loaded_count += 1
        else:
            assert result["exception"] is not None
    assert loaded_count >= 10, f"Expected at least 10 loadable fixtures, got {loaded_count}"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_fixture(fixture_id: str) -> dict:
    fixtures = iter_gallery_fixtures(_GALLERY_DIR)
    match = next((f for f in fixtures if f["id"] == fixture_id), None)
    assert match is not None, f"Fixture '{fixture_id}' not found in gallery index"
    return match
