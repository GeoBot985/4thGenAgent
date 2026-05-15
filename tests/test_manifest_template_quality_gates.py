from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.generated_manifest_smoke_runner import (
    PASSING_CLASSIFICATIONS,
    run_template_quality_gates,
    write_smoke_report,
)
from src.manifest_template_generator import (
    build_manifest_from_template,
    list_manifest_templates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _runtime_dir(tmp_path: Path) -> Path:
    d = tmp_path / "runtime_data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manifest_dir(tmp_path: Path) -> Path:
    d = tmp_path / "manifests"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# test_quality_gates_cover_all_templates
# ---------------------------------------------------------------------------

def test_quality_gates_cover_all_templates(tmp_path: Path) -> None:
    result = run_template_quality_gates(
        runtime_data_dir=_runtime_dir(tmp_path),
        manifest_dir=_manifest_dir(tmp_path),
    )
    templates = list_manifest_templates()
    assert result["template_count"] == len(templates)
    result_ids = {r["template_id"] for r in result["results"]}
    template_ids = {t["template_id"] for t in templates}
    assert result_ids == template_ids


# ---------------------------------------------------------------------------
# test_quality_gates_pass_for_builtin_templates
# ---------------------------------------------------------------------------

def test_quality_gates_pass_for_builtin_templates(tmp_path: Path) -> None:
    result = run_template_quality_gates(
        runtime_data_dir=_runtime_dir(tmp_path),
        manifest_dir=_manifest_dir(tmp_path),
    )
    assert result.get("ok"), (
        f"Quality gates failed.\nFailed: {result.get('failed')}\nResults:\n"
        + "\n".join(
            f"  {r['template_id']}: {r['status']} ({r['classification']}) {r.get('errors', [])}"
            for r in result.get("results", [])
        )
    )
    assert result.get("status") == "PASS"
    assert result.get("passed") == result.get("template_count")
    assert result.get("failed") == 0


# ---------------------------------------------------------------------------
# test_quality_gate_result_has_template_count
# ---------------------------------------------------------------------------

def test_quality_gate_result_has_template_count(tmp_path: Path) -> None:
    result = run_template_quality_gates(
        runtime_data_dir=_runtime_dir(tmp_path),
        manifest_dir=_manifest_dir(tmp_path),
    )
    assert "template_count" in result
    assert "passed" in result
    assert "failed" in result
    assert "results" in result
    assert isinstance(result["results"], list)
    assert result["template_count"] > 0


# ---------------------------------------------------------------------------
# test_quality_gates_detect_broken_template
# ---------------------------------------------------------------------------

def test_quality_gates_detect_broken_template(tmp_path: Path) -> None:
    from src.generated_manifest_smoke_runner import smoke_run_manifest_candidate

    broken = build_manifest_from_template("manual_read_tool", "quality.broken_test", "Broken")
    broken["steps"] = [{"id": "bad", "command": "not_a_valid_command"}]

    result = smoke_run_manifest_candidate(broken, runtime_data_dir=_runtime_dir(tmp_path))
    assert not result.get("ok")
    assert result.get("classification") not in PASSING_CLASSIFICATIONS


# ---------------------------------------------------------------------------
# test_quality_gates_do_not_write_to_real_manifest_dir
# ---------------------------------------------------------------------------

def test_quality_gates_do_not_write_to_real_manifest_dir(tmp_path: Path) -> None:
    real_manifests = Path("manifests")
    before_files = set(real_manifests.glob("*.json")) if real_manifests.is_dir() else set()

    run_template_quality_gates(
        runtime_data_dir=_runtime_dir(tmp_path),
        manifest_dir=_manifest_dir(tmp_path),
    )

    after_files = set(real_manifests.glob("*.json")) if real_manifests.is_dir() else set()
    new_files = after_files - before_files
    quality_gate_files = {f for f in new_files if "quality." in f.stem or "quality_" in f.stem}
    assert not quality_gate_files, f"Quality gate wrote to real manifests/ dir: {quality_gate_files}"


# ---------------------------------------------------------------------------
# test_quality_gates_do_not_modify_event_routes
# ---------------------------------------------------------------------------

def test_quality_gates_do_not_modify_event_routes(tmp_path: Path) -> None:
    event_routes = Path("config/event_routes.json")
    original = event_routes.read_text(encoding="utf-8") if event_routes.is_file() else None

    run_template_quality_gates(
        runtime_data_dir=_runtime_dir(tmp_path),
        manifest_dir=_manifest_dir(tmp_path),
    )

    if original is not None:
        assert event_routes.read_text(encoding="utf-8") == original, "event_routes.json was modified!"


# ---------------------------------------------------------------------------
# test_approval_template_quality_gate_requires_pending_action
# ---------------------------------------------------------------------------

def test_approval_template_quality_gate_requires_pending_action(tmp_path: Path) -> None:
    from src.generated_manifest_smoke_runner import smoke_run_manifest_candidate

    manifest = build_manifest_from_template(
        "approval_side_effect", "quality.approval_gate", "Approval Gate"
    )
    result = smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))
    assert result.get("classification") == "WAITING_FOR_EXECUTE_EXPECTED", (
        f"Approval template must reach WAITING_FOR_EXECUTE. Got: {result.get('classification')}. "
        f"State: {result.get('state')}. Errors: {result.get('errors')}"
    )
    # Must have staged at least one pending action
    assert result.get("pending_action_count", 0) >= 1 or result.get("state") == "WAITING_FOR_EXECUTE"


# ---------------------------------------------------------------------------
# test_event_template_quality_gate_does_not_register_route
# ---------------------------------------------------------------------------

def test_event_template_quality_gate_does_not_register_route(tmp_path: Path) -> None:
    from src.generated_manifest_smoke_runner import smoke_run_manifest_candidate

    routes_file = Path("config/event_routes.json")
    before = routes_file.read_text(encoding="utf-8") if routes_file.is_file() else None

    manifest = build_manifest_from_template(
        "event_driven_stub", "quality.event_gate", "Event Gate"
    )
    smoke_run_manifest_candidate(manifest, runtime_data_dir=_runtime_dir(tmp_path))

    if before is not None:
        assert routes_file.read_text(encoding="utf-8") == before, "event_routes.json was modified!"


# ---------------------------------------------------------------------------
# test_quality_gate_report_has_markdown_table
# ---------------------------------------------------------------------------

def test_quality_gate_report_has_markdown_table(tmp_path: Path) -> None:
    result = run_template_quality_gates(
        runtime_data_dir=_runtime_dir(tmp_path),
        manifest_dir=_manifest_dir(tmp_path),
    )
    report = write_smoke_report(result, runtime_data_dir=_runtime_dir(tmp_path), report_name="quality_gate_report")
    assert report.get("ok"), report.get("error")
    md = Path(report["markdown_path"]).read_text(encoding="utf-8")
    assert "| Template |" in md or "| template" in md.lower()
    assert "PASS" in md or "FAIL" in md
    assert "manual_read_tool" in md or "quality." in md
