from __future__ import annotations

import json
import pytest
from pathlib import Path
from runtime.live_read_proof import (
    build_live_read_proof_plan,
    run_live_read_proof_pack,
    validate_live_read_boundary,
    write_live_read_proof_report,
    render_live_read_proof_markdown,
)


def test_plan_returns_dict():
    plan = build_live_read_proof_plan()
    assert isinstance(plan, dict)


def test_plan_profile():
    plan = build_live_read_proof_plan(profile="controlled_live_read")
    assert plan.get("profile") == "controlled_live_read"


def test_plan_no_live_probes_empty_list():
    plan = build_live_read_proof_plan(no_live_probes=True)
    assert plan.get("live_probes_planned") == []


def test_plan_live_probes_present_without_flag():
    plan = build_live_read_proof_plan(no_live_probes=False)
    probes = plan.get("live_probes_planned", [])
    assert len(probes) > 0
    assert "google_auth_status" in probes


def test_pack_no_live_probes_passes(tmp_path):
    result = run_live_read_proof_pack(
        no_live_probes=True,
        runtime_data_dir=str(tmp_path),
    )
    assert isinstance(result, dict)
    assert result.get("ok") is True


def test_pack_no_live_probes_no_side_effects(tmp_path):
    result = run_live_read_proof_pack(
        no_live_probes=True,
        runtime_data_dir=str(tmp_path),
    )
    assert result.get("live_side_effects_performed") is False


def test_pack_no_live_probes_rpa_blocked(tmp_path):
    result = run_live_read_proof_pack(
        no_live_probes=True,
        runtime_data_dir=str(tmp_path),
    )
    assert result.get("rpa_blocked") is True


def test_pack_no_live_probes_has_blocked_checks(tmp_path):
    result = run_live_read_proof_pack(
        no_live_probes=True,
        runtime_data_dir=str(tmp_path),
    )
    blocked = result.get("blocked_side_effect_checks", [])
    assert len(blocked) > 0


def test_pack_missing_credentials_skips_probes(tmp_path):
    result = run_live_read_proof_pack(
        no_live_probes=False,
        runtime_data_dir=str(tmp_path),
        credentials_path="/nonexistent/credentials.json",
        token_path="/nonexistent/token.json",
    )
    assert result.get("live_reads_attempted") is False
    probes = result.get("probes", [])
    for p in probes:
        assert p.get("status") == "SKIPPED"


def test_pack_profile_field(tmp_path):
    result = run_live_read_proof_pack(
        no_live_probes=True,
        runtime_data_dir=str(tmp_path),
        profile="controlled_live_read",
    )
    assert result.get("profile") == "controlled_live_read"


def test_pack_invalid_profile_has_blockers(tmp_path):
    result = run_live_read_proof_pack(
        no_live_probes=True,
        runtime_data_dir=str(tmp_path),
        profile="unknown_profile_xyz",
    )
    assert result.get("ok") is False
    assert len(result.get("blockers", [])) > 0


def test_pack_credential_check_redacted(tmp_path):
    result = run_live_read_proof_pack(
        no_live_probes=True,
        runtime_data_dir=str(tmp_path),
    )
    cred = result.get("credential_check", {})
    assert "access_token" not in cred or cred.get("access_token") == "[REDACTED]"
    assert "refresh_token" not in cred or cred.get("refresh_token") == "[REDACTED]"


def test_write_report_creates_files(tmp_path):
    result = run_live_read_proof_pack(
        no_live_probes=True,
        runtime_data_dir=str(tmp_path),
    )
    report = write_live_read_proof_report(result, runtime_data_dir=str(tmp_path))
    assert report.get("ok") is True
    paths = report.get("paths", {})
    assert Path(paths["live_read_proof_json"]).is_file()
    assert Path(paths["live_read_proof_md"]).is_file()
    assert Path(paths["blocked_side_effects_json"]).is_file()
    assert Path(paths["blocked_side_effects_md"]).is_file()


def test_write_report_json_valid(tmp_path):
    result = run_live_read_proof_pack(
        no_live_probes=True,
        runtime_data_dir=str(tmp_path),
    )
    report = write_live_read_proof_report(result, runtime_data_dir=str(tmp_path))
    paths = report.get("paths", {})
    data = json.loads(Path(paths["live_read_proof_json"]).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "ok" in data


def test_render_markdown_contains_profile():
    result = run_live_read_proof_pack(no_live_probes=True)
    md = render_live_read_proof_markdown(result)
    assert "controlled_live_read" in md


def test_render_markdown_safety_statement():
    result = run_live_read_proof_pack(no_live_probes=True)
    md = render_live_read_proof_markdown(result)
    assert "No live side effects were performed" in md


def test_render_markdown_conclusion_pass():
    result = run_live_read_proof_pack(no_live_probes=True)
    md = render_live_read_proof_markdown(result)
    assert "PASS" in md
