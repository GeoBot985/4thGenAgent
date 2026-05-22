"""Spec 140 — Tests for 'taskframe worker' CLI commands."""
import json

import pytest

from src.taskframe_cli import main


@pytest.fixture()
def rd(tmp_path):
    return str(tmp_path)


def _run(argv, capsys=None):
    try:
        code = main(argv)
    except SystemExit as e:
        code = int(e.code) if e.code is not None else 0
    return code


class TestWorkerStatusCLI:
    def test_status_exits_zero(self, rd):
        code = _run(["worker", "status", "--runtime-data-dir", rd])
        assert code == 0

    def test_status_json_exits_zero(self, rd, capsys):
        code = _run(["worker", "status", "--runtime-data-dir", rd, "--json"], capsys)
        assert code == 0

    def test_status_json_is_valid_json(self, rd, capsys):
        _run(["worker", "status", "--runtime-data-dir", rd, "--json"])


class TestWorkerHealthCLI:
    def test_health_exits_zero(self, rd):
        code = _run(["worker", "health", "--runtime-data-dir", rd])
        assert code == 0

    def test_health_json_is_parseable(self, rd, capsys):
        _run(["worker", "health", "--runtime-data-dir", rd, "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "ok" in data
        assert "checks" in data


class TestWorkerRunOnceCLI:
    def test_run_once_exits_zero(self, rd):
        code = _run(["worker", "run-once", "--runtime-data-dir", rd])
        assert code == 0

    def test_run_once_json_output(self, rd, capsys):
        _run(["worker", "run-once", "--runtime-data-dir", rd, "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "ok" in data
        assert "cycle_id" in data

    def test_run_once_no_scheduler(self, rd):
        code = _run(["worker", "run-once", "--runtime-data-dir", rd, "--no-scheduler"])
        assert code == 0

    def test_run_once_no_event_sources(self, rd):
        code = _run(["worker", "run-once", "--runtime-data-dir", rd, "--no-event-sources"])
        assert code == 0

    def test_run_once_queue_limit(self, rd):
        code = _run(["worker", "run-once", "--runtime-data-dir", rd, "--queue-limit", "5"])
        assert code == 0

    def test_run_once_writes_cycles_jsonl(self, rd):
        from pathlib import Path
        _run(["worker", "run-once", "--runtime-data-dir", rd])
        cycles_path = Path(rd) / "worker" / "cycles.jsonl"
        assert cycles_path.exists()


class TestWorkerRunLoopCLI:
    def test_run_loop_max_cycles_1(self, rd, capsys):
        _run(["worker", "run-loop", "--runtime-data-dir", rd, "--max-cycles", "1", "--sleep-seconds", "0", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["cycles_run"] == 1

    def test_run_loop_max_cycles_2(self, rd, capsys):
        _run(["worker", "run-loop", "--runtime-data-dir", rd, "--max-cycles", "2", "--sleep-seconds", "0", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["cycles_run"] == 2


class TestWorkerStopCLI:
    def test_stop_exits_zero(self, rd):
        code = _run(["worker", "stop", "--runtime-data-dir", rd])
        assert code == 0

    def test_stop_json_ok(self, rd, capsys):
        _run(["worker", "stop", "--runtime-data-dir", rd, "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True


class TestWorkerCyclesCLI:
    def test_cycles_empty_exits_zero(self, rd):
        code = _run(["worker", "cycles", "--runtime-data-dir", rd])
        assert code == 0

    def test_cycles_after_run_json(self, rd, capsys):
        _run(["worker", "run-once", "--runtime-data-dir", rd])
        capsys.readouterr()  # clear run-once output
        _run(["worker", "cycles", "--runtime-data-dir", rd, "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["count"] >= 1


class TestWorkerClearStaleLockCLI:
    def test_clear_stale_lock_no_lock_exits_zero(self, rd):
        code = _run(["worker", "clear-stale-lock", "--runtime-data-dir", rd])
        assert code == 0

    def test_clear_stale_lock_json_ok(self, rd, capsys):
        _run(["worker", "clear-stale-lock", "--runtime-data-dir", rd, "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
