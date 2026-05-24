from __future__ import annotations

import json
import pytest
from src.taskframe_cli import main


def _run(argv: list[str]) -> tuple[int, str]:
    import io
    import sys
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        code = main(argv)
    except SystemExit as exc:
        code = int(exc.code or 0)
    finally:
        sys.stdout = old_stdout
    return code, buf.getvalue()


def test_live_read_status_exits_zero():
    code, _ = _run(["live-read", "status", "--profile", "controlled_live_read", "--json"])
    assert code == 0


def test_live_read_status_valid_json():
    code, output = _run(["live-read", "status", "--profile", "controlled_live_read", "--json"])
    assert code == 0
    data = json.loads(output)
    assert isinstance(data, dict)
    assert "profile" in data


def test_live_read_status_profile_field():
    _, output = _run(["live-read", "status", "--profile", "controlled_live_read", "--json"])
    data = json.loads(output)
    assert data.get("profile") == "controlled_live_read"


def test_live_read_proof_no_live_probes_exits_zero():
    code, _ = _run([
        "live-read", "proof",
        "--profile", "controlled_live_read",
        "--no-live-probes",
        "--json",
    ])
    assert code == 0


def test_live_read_proof_no_live_probes_valid_json():
    code, output = _run([
        "live-read", "proof",
        "--profile", "controlled_live_read",
        "--no-live-probes",
        "--json",
    ])
    data = json.loads(output)
    assert isinstance(data, dict)
    assert "ok" in data


def test_live_read_proof_no_live_probes_ok_true():
    _, output = _run([
        "live-read", "proof",
        "--profile", "controlled_live_read",
        "--no-live-probes",
        "--json",
    ])
    data = json.loads(output)
    assert data.get("ok") is True


def test_live_read_proof_no_side_effects_performed():
    _, output = _run([
        "live-read", "proof",
        "--profile", "controlled_live_read",
        "--no-live-probes",
        "--json",
    ])
    data = json.loads(output)
    assert data.get("live_side_effects_performed") is False


def test_live_read_proof_rpa_blocked():
    _, output = _run([
        "live-read", "proof",
        "--profile", "controlled_live_read",
        "--no-live-probes",
        "--json",
    ])
    data = json.loads(output)
    assert data.get("rpa_blocked") is True


def test_live_read_proof_write_report(tmp_path):
    code, output = _run([
        "live-read", "proof",
        "--profile", "controlled_live_read",
        "--no-live-probes",
        "--write-report",
        "--runtime-data-dir", str(tmp_path),
        "--json",
    ])
    assert code == 0
    data = json.loads(output)
    paths = data.get("report_paths", {})
    from pathlib import Path
    assert Path(paths.get("live_read_proof_json", "missing")).is_file()
    assert Path(paths.get("live_read_proof_md", "missing")).is_file()


def test_live_read_blocked_side_effects_exits_zero():
    code, _ = _run([
        "live-read", "blocked-side-effects",
        "--profile", "controlled_live_read",
        "--json",
    ])
    assert code == 0


def test_live_read_blocked_side_effects_valid_json():
    code, output = _run([
        "live-read", "blocked-side-effects",
        "--profile", "controlled_live_read",
        "--json",
    ])
    data = json.loads(output)
    assert isinstance(data, dict)
    assert "ok" in data


def test_live_read_blocked_side_effects_ok_true():
    _, output = _run([
        "live-read", "blocked-side-effects",
        "--profile", "controlled_live_read",
        "--json",
    ])
    data = json.loads(output)
    assert data.get("ok") is True


def test_live_read_blocked_side_effects_not_performed():
    _, output = _run([
        "live-read", "blocked-side-effects",
        "--profile", "controlled_live_read",
        "--json",
    ])
    data = json.loads(output)
    assert data.get("live_side_effects_performed") is False


def test_live_read_blocked_side_effects_rpa_blocked():
    _, output = _run([
        "live-read", "blocked-side-effects",
        "--profile", "controlled_live_read",
        "--json",
    ])
    data = json.loads(output)
    assert data.get("rpa_blocked") is True
