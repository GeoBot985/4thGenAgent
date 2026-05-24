"""Spec 156 — InvoiceOps live posting manifest tests."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

MANIFEST_PATH = Path(__file__).parent.parent / "manifests" / "invoiceops_live_sheet_posting_pilot.manifest.json"


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_file_exists():
    assert MANIFEST_PATH.is_file()


def test_manifest_is_valid_json(manifest):
    assert isinstance(manifest, dict)


def test_manifest_has_manifest_id(manifest):
    assert manifest.get("manifest_id")


def test_manifest_manifest_id_contains_invoiceops(manifest):
    assert "invoiceops" in manifest["manifest_id"]


def test_manifest_stops_at_waiting_for_execute(manifest):
    assert manifest["completion"]["success_state"] == "WAITING_FOR_EXECUTE"


def test_manifest_live_side_effects_not_allowed(manifest):
    policy = manifest.get("side_effect_policy", {})
    assert policy.get("live_side_effects_allowed") is False


def test_manifest_has_side_effects_false(manifest):
    policy = manifest.get("side_effect_policy", {})
    assert policy.get("has_side_effects") is False


def test_manifest_has_steps(manifest):
    assert manifest.get("steps")
    assert len(manifest["steps"]) >= 1


def test_manifest_includes_build_posting_plan_step(manifest):
    step_ids = [s.get("id") for s in manifest.get("steps", [])]
    assert "build_posting_plan" in step_ids


def test_manifest_pending_actions_min_is_1(manifest):
    assert manifest["completion"].get("pending_actions_min", 0) >= 1


def test_manifest_allows_pending_approval(manifest):
    assert manifest["completion"].get("allow_pending_approval") is True


def test_manifest_has_inputs(manifest):
    assert manifest.get("inputs")


def test_manifest_inputs_include_frame_id(manifest):
    assert "frame_id" in manifest["inputs"]


def test_manifest_outputs_include_posting_plan(manifest):
    outputs = manifest.get("outputs", {})
    assert "posting_plan" in outputs
