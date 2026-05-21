from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.portfolio_evidence_pack import build_portfolio_evidence_pack

pytestmark = pytest.mark.slow


def _seed_latest_story_pack(runtime_root: Path) -> None:
    story_pack_dir = runtime_root / "demo_packs" / "cross_workflow_business_demo_v2_demo" / "story_pack"
    story_pack_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "pack_id": "cross_workflow_business_demo_v2",
        "pack_run_id": "cross_workflow_business_demo_v2_demo",
        "story_title": "Order Fulfilment Exception",
        "ok": True,
        "dry_run_only": True,
        "live_side_effects_performed": False,
        "started_at": "2026-05-19T08:30:00+00:00",
        "ended_at": "2026-05-19T08:31:00+00:00",
        "duration_ms": 60000,
        "summary": {
            "workflow_count": 3,
            "completed_count": 3,
            "failed_count": 0,
            "total_pending_actions": 4,
            "total_executed_actions": 4,
            "total_llm_calls": 6,
            "total_tool_calls": 12,
            "reports_generated": 3,
            "evidence_bundles_generated": 3,
        },
        "workflow_results": [],
    }
    _write_json(story_pack_dir / "summary.json", summary)
    _write_json(
        story_pack_dir / "workflow_timeline.json",
        {
            "pack_run_id": summary["pack_run_id"],
            "timeline": [
                {
                    "sequence": 1,
                    "lane": "customer_support",
                    "scenario_id": "customer_status_approve_execute_dry_run",
                    "frame_id": "frame-1",
                    "manifest_id": "customer_status_llm_e2e",
                    "state": "COMPLETED",
                    "pending_action_count": 1,
                    "executed_action_count": 1,
                    "llm_call_count": 2,
                    "tool_call_count": 4,
                    "report_path": str(story_pack_dir / "customer.md"),
                    "evidence_bundle_path": str(story_pack_dir / "customer_evidence.json"),
                },
                {
                    "sequence": 2,
                    "lane": "procurement",
                    "scenario_id": "procurement_low_stock_approve_execute_dry_run",
                    "frame_id": "frame-2",
                    "manifest_id": "procurement_low_stock",
                    "state": "COMPLETED",
                    "pending_action_count": 1,
                    "executed_action_count": 1,
                    "llm_call_count": 2,
                    "tool_call_count": 4,
                    "report_path": str(story_pack_dir / "procurement.md"),
                    "evidence_bundle_path": str(story_pack_dir / "procurement_evidence.json"),
                },
                {
                    "sequence": 3,
                    "lane": "accounting",
                    "scenario_id": "accounting_payment_reconciliation_approve_execute_dry_run",
                    "frame_id": "frame-3",
                    "manifest_id": "accounting_payment_reconciliation",
                    "state": "COMPLETED",
                    "pending_action_count": 2,
                    "executed_action_count": 2,
                    "llm_call_count": 2,
                    "tool_call_count": 4,
                    "report_path": str(story_pack_dir / "accounting.md"),
                    "evidence_bundle_path": str(story_pack_dir / "accounting_evidence.json"),
                },
            ],
        },
    )
    (story_pack_dir / "index.md").write_text("# Story\n", encoding="utf-8")
    (story_pack_dir / "index.html").write_text("<!doctype html><html><body>Story</body></html>", encoding="utf-8")
    _write_json(story_pack_dir / "evidence_manifest.json", {"pack_run_id": summary["pack_run_id"], "artifacts": []})


def _seed_latest_readiness_scorecard(runtime_root: Path) -> None:
    readiness_dir = runtime_root / "readiness"
    readiness_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": True,
        "status": "PASS",
        "threshold": 90,
        "overall_score": 100,
        "generated_at": "2026-05-19T08:31:00+00:00",
        "areas": {},
        "blocking_areas": [],
        "warnings": [],
        "errors": [],
        "report_paths": {
            "json_path": str(readiness_dir / "readiness_scorecard.json"),
            "markdown_path": str(readiness_dir / "readiness_scorecard.md"),
            "html_path": str(readiness_dir / "readiness_scorecard.html"),
        },
    }
    _write_json(readiness_dir / "readiness_scorecard.json", payload)
    (readiness_dir / "readiness_scorecard.md").write_text("# Ready\n", encoding="utf-8")
    (readiness_dir / "readiness_scorecard.html").write_text("<!doctype html><html><body>Ready</body></html>", encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def test_portfolio_pack_module_imports():
    import src.portfolio_evidence_pack as module

    assert hasattr(module, "build_portfolio_evidence_pack")


def test_portfolio_pack_generates_required_files(tmp_path):
    runtime_root = tmp_path / "runtime_data"
    _seed_latest_story_pack(runtime_root)
    _seed_latest_readiness_scorecard(runtime_root)

    result = build_portfolio_evidence_pack(runtime_data_dir=runtime_root)

    assert result["ok"] is True
    for key in (
        "index_markdown_path",
        "index_html_path",
        "summary_json_path",
        "architecture_path",
        "demo_script_path",
        "tool_inventory_path",
        "workflow_proof_path",
        "screenshot_checklist_path",
    ):
        assert Path(result[key]).is_file(), key
    assert any("latest_story_pack_link" in str(item.get("artifact_id", "")) for item in result["linked_artifacts"])
    assert any("latest_readiness_scorecard_link" in str(item.get("artifact_id", "")) for item in result["linked_artifacts"])


def test_portfolio_summary_has_required_shape(tmp_path):
    runtime_root = tmp_path / "runtime_data"
    _seed_latest_story_pack(runtime_root)
    _seed_latest_readiness_scorecard(runtime_root)

    result = build_portfolio_evidence_pack(runtime_data_dir=runtime_root)
    summary = json.loads(Path(result["summary_json_path"]).read_text(encoding="utf-8"))

    assert summary["pack_id"] == "portfolio_evidence_pack_v1"
    assert summary["ok"] is True
    assert summary["project_name"] == "TaskFrame Runtime"
    assert summary["project_type"] == "controlled_business_automation_runtime"
    assert summary["live_side_effects_claimed"] is False
    assert summary["production_readiness_claimed"] is False
    assert summary["included_story_pack"] is True
    assert summary["included_readiness_scorecard"] is True
    assert summary["workflow_count"] >= 3
    assert summary["tool_count"] > 0
    assert isinstance(summary["evidence_links"], list)
    assert isinstance(summary["known_limitations"], list)


def test_portfolio_pack_includes_architecture_summary(tmp_path):
    runtime_root = tmp_path / "runtime_data"
    result = build_portfolio_evidence_pack(runtime_data_dir=runtime_root)
    text = Path(result["architecture_path"]).read_text(encoding="utf-8")

    assert "Command / Event" in text
    assert "LLM is a bounded helper" in text
    assert "LLM is not the controller" in text
    assert "Approval Gate" in text


def test_portfolio_pack_includes_tool_inventory(tmp_path):
    runtime_root = tmp_path / "runtime_data"
    result = build_portfolio_evidence_pack(runtime_data_dir=runtime_root)
    text = Path(result["tool_inventory_path"]).read_text(encoding="utf-8")

    assert "| Tool ID | Display Name | Category | Core/Optional | Side Effect Level | Auth Required | Enabled | Limitations |" in text
    assert "business_context" in text


def test_portfolio_pack_includes_workflow_proof(tmp_path):
    runtime_root = tmp_path / "runtime_data"
    _seed_latest_story_pack(runtime_root)
    result = build_portfolio_evidence_pack(runtime_data_dir=runtime_root)
    text = Path(result["workflow_proof_path"]).read_text(encoding="utf-8")

    assert "customer_support" in text
    assert "procurement" in text
    assert "accounting" in text
    assert "cross_workflow_story" in text


def test_portfolio_pack_includes_known_limitations(tmp_path):
    runtime_root = tmp_path / "runtime_data"
    result = build_portfolio_evidence_pack(runtime_data_dir=runtime_root)
    text = Path(result["screenshot_checklist_path"]).read_text(encoding="utf-8")
    limitations = Path(result["pack_dir"]) / "known_limitations.md"
    limitations_text = limitations.read_text(encoding="utf-8")

    assert "controlled portfolio/demo runtime" in limitations_text.lower()
    assert "live side effects are blocked or approval-staged" in limitations_text.lower()
    assert "portfolio pack" in text.lower()


def test_portfolio_pack_does_not_claim_production_readiness(tmp_path):
    runtime_root = tmp_path / "runtime_data"
    result = build_portfolio_evidence_pack(runtime_data_dir=runtime_root)
    summary = json.loads(Path(result["summary_json_path"]).read_text(encoding="utf-8"))
    index_text = Path(result["index_markdown_path"]).read_text(encoding="utf-8")

    assert summary["production_readiness_claimed"] is False
    assert "not proof of production deployment readiness" in index_text.lower()


def test_cli_portfolio_pack_command_exists():
    from src.taskframe_cli import build_parser

    parser = build_parser()
    help_text = parser.format_help()

    assert "portfolio-pack" in help_text
    assert "readiness" in help_text


def test_release_verifier_includes_portfolio_pack_check():
    from tools.run_release_candidate_verification import _check_portfolio_evidence_pack_v1

    result = _check_portfolio_evidence_pack_v1()

    assert result["name"] == "portfolio_evidence_pack_v1"
    assert result["status"] == "PASS"


def test_operator_ui_mentions_portfolio_pack_actions():
    text = Path("src/operator_ui.py").read_text(encoding="utf-8")

    assert "Generate Portfolio Evidence Pack" in text
    assert "Open Portfolio HTML" in text
    assert "on_generate_portfolio_evidence_pack" in text
