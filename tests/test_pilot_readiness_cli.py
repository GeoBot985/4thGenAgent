from __future__ import annotations

import json
import sys

import pytest


def _run_cli(args: list[str]) -> tuple[int, str]:
    from io import StringIO
    from contextlib import redirect_stdout
    from src.taskframe_cli import main

    buf = StringIO()
    with redirect_stdout(buf):
        try:
            rc = main(args)
        except SystemExit as e:
            rc = int(e.code) if e.code is not None else 0
    return rc, buf.getvalue()


@pytest.fixture(scope="module")
def cli_json_output():
    rc, output = _run_cli(["pilot-readiness", "--json"])
    return rc, output, json.loads(output)


def test_pilot_readiness_cli_returns_zero_by_default(cli_json_output):
    rc, _, _ = cli_json_output
    assert rc == 0


def test_pilot_readiness_cli_json_flag_outputs_valid_json(cli_json_output):
    rc, _, payload = cli_json_output
    assert rc == 0
    assert "ok" in payload
    assert "overall_score" in payload
    assert "status" in payload
    assert "threshold" in payload
    assert "claim" in payload


def test_pilot_readiness_cli_json_threshold_is_80(cli_json_output):
    _, _, payload = cli_json_output
    assert payload["threshold"] == 80


def test_pilot_readiness_cli_strict_flag_exits_nonzero_on_fail(monkeypatch):
    import src.pilot_readiness as pr

    monkeypatch.setattr(pr, "build_pilot_readiness_scorecard", lambda **kw: {
        "ok": False,
        "status": "FAIL",
        "overall_score": 40,
        "threshold": 80,
        "mandatory_failures": ["test forced failure"],
        "claim": "Controlled pilot readiness only.",
        "generated_at": "2026-01-01T00:00:00Z",
    })
    rc, _ = _run_cli(["pilot-readiness", "--strict"])
    assert rc != 0


def test_pilot_readiness_cli_write_pack_flag_accepted():
    rc, output = _run_cli(["pilot-readiness", "--json", "--write-pack"])
    assert rc == 0
    payload = json.loads(output)
    assert "pack_dir" in payload


def test_pilot_readiness_cli_output_mentions_claim(cli_json_output):
    _, output, _ = cli_json_output
    assert "pilot" in output.lower() or "controlled" in output.lower()


def test_pilot_readiness_command_exists_in_parser():
    from src.taskframe_cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["pilot-readiness"])
    assert args.command == "pilot-readiness"


def test_pilot_readiness_parser_has_write_pack_arg():
    from src.taskframe_cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["pilot-readiness", "--write-pack"])
    assert args.write_pack is True


def test_pilot_readiness_parser_has_json_arg():
    from src.taskframe_cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["pilot-readiness", "--json"])
    assert args.json is True


def test_pilot_readiness_parser_has_strict_arg():
    from src.taskframe_cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["pilot-readiness", "--strict"])
    assert args.strict is True
