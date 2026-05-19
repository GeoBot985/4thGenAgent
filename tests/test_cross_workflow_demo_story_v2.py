from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.operator_cross_workflow_demo import get_demo_pack, run_cross_workflow_demo_pack
from tools.run_release_candidate_verification import _check_cross_workflow_story_v2


def _run_v2_demo(tmp_path: Path) -> dict:
    result = run_cross_workflow_demo_pack(
        pack_id="cross_workflow_business_demo_v2",
        runtime_data_dir=str(tmp_path),
        reset_dataset=True,
        generate_reports=True,
        use_real_llm=False,
        allow_test_fake_llm=True,
        skip_llm_preflight=True,
    )
    assert result.get("ok") is True, result.get("error", "")
    story = result.get("story_pack_result", {})
    assert story.get("ok") is True, story.get("errors", [])
    return result


def test_v2_demo_pack_is_registered():
    pack = get_demo_pack("cross_workflow_business_demo_v2")
    assert pack["id"] == "cross_workflow_business_demo_v2"
    assert pack["story_title"] == "Order Fulfilment Exception"
    assert pack.get("generate_story_pack") is True


def test_story_pack_builder_creates_required_files(tmp_path: Path):
    result = _run_v2_demo(tmp_path)
    story = result["story_pack_result"]
    assert Path(story["story_pack_dir"]).is_dir()
    for key in ("index_markdown_path", "index_html_path", "summary_json_path", "evidence_manifest_path"):
        assert Path(story[key]).is_file(), story[key]
    assert Path(story["story_pack_dir"]).joinpath("screenshots_checklist.md").is_file()
    assert Path(story["story_pack_dir"]).joinpath("README.md").is_file()
    assert Path(story["story_pack_dir"]).joinpath("workflow_timeline.json").is_file()


def test_story_pack_summary_has_required_shape(tmp_path: Path):
    result = _run_v2_demo(tmp_path)
    summary = json.loads(Path(result["story_pack_result"]["summary_json_path"]).read_text(encoding="utf-8"))
    assert summary["pack_id"] == "cross_workflow_business_demo_v2"
    assert summary["story_title"] == "Order Fulfilment Exception"
    assert summary["ok"] is True
    assert summary["dry_run_only"] is True
    assert summary["live_side_effects_performed"] is False
    assert summary["workflow_count"] >= 3
    assert summary["reports_generated"] >= 1
    assert summary["evidence_bundles_generated"] >= 1


def test_story_pack_evidence_manifest_lists_existing_artifacts(tmp_path: Path):
    result = _run_v2_demo(tmp_path)
    story = result["story_pack_result"]
    manifest = json.loads(Path(story["evidence_manifest_path"]).read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts", [])
    assert isinstance(artifacts, list) and artifacts
    for artifact in artifacts:
        assert artifact["exists"] is True
        assert Path(artifact["path"]).is_file()


def test_story_pack_timeline_contains_each_workflow_lane(tmp_path: Path):
    result = _run_v2_demo(tmp_path)
    timeline = json.loads(Path(result["story_pack_result"]["story_pack_dir"]).joinpath("workflow_timeline.json").read_text(encoding="utf-8"))
    lanes = {item.get("lane", "") for item in timeline.get("timeline", []) if isinstance(item, dict)}
    assert {"customer_support", "procurement", "accounting"}.issubset(lanes)


def test_story_pack_declares_no_live_side_effects(tmp_path: Path):
    result = _run_v2_demo(tmp_path)
    summary = json.loads(Path(result["story_pack_result"]["summary_json_path"]).read_text(encoding="utf-8"))
    assert summary["dry_run_only"] is True
    assert summary["live_side_effects_performed"] is False


def test_story_pack_does_not_link_stale_pack_run_artifacts(tmp_path: Path):
    result = _run_v2_demo(tmp_path)
    story = result["story_pack_result"]
    manifest = json.loads(Path(story["evidence_manifest_path"]).read_text(encoding="utf-8"))
    workflow_frame_ids = {item.get("frame_id", "") for item in result.get("workflow_results", []) if isinstance(item, dict)}
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        if artifact.get("workflow_lane") == "story_pack":
            continue
        assert artifact.get("frame_id", "") in workflow_frame_ids
        assert str(result["pack_run_id"]) in story["story_pack_dir"]


def test_cli_cross_workflow_v2_command_exists(tmp_path: Path):
    command = [
        sys.executable,
        "-m",
        "src.taskframe_cli",
        "demo",
        "cross-workflow-v2",
        "--runtime-data-dir",
        str(tmp_path),
        "--reset-dataset",
        "--json",
    ]
    completed = subprocess.run(command, cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["pack_id"] == "cross_workflow_business_demo_v2"
    assert payload["story_pack_result"]["ok"] is True


def test_operator_ui_mentions_story_pack_actions():
    ui_source = Path("src/operator_ui.py").read_text(encoding="utf-8")
    assert "Run full business workflow demo v2" in ui_source
    assert "Open story evidence pack" in ui_source
    assert "Open story HTML" in ui_source
    assert "Open story folder" in ui_source


def test_release_verifier_includes_cross_workflow_story_v2_check(tmp_path: Path):
    result = _check_cross_workflow_story_v2()
    assert result["status"] == "PASS", result
    assert result["name"] == "cross_workflow_story_v2"
    assert Path(result["story_pack_dir"]).is_dir()
    assert Path(result["story_markdown_path"]).is_file()
    assert Path(result["story_html_path"]).is_file()
    assert Path(result["evidence_manifest_path"]).is_file()
    assert Path(result["summary_json_path"]).is_file()
