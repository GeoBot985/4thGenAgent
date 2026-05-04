from runtime.google_sheet_tools import load_accounting_sheet_config, sheet_prepare_write_rows, sheet_read_range, sheet_write_rows
from runtime.tool_registry import TOOL_REGISTRY


def test_sheet_config_loads():
    config = load_accounting_sheet_config()
    assert "tabs" in config


def test_sheet_config_missing_spreadsheet_id_fails_workflow_validation():
    result = sheet_read_range("", "Payments!A:I")
    assert result["ok"] is False
    assert result["error"] == "SPREADSHEET_ID_REQUIRED"


def test_sheet_read_range_returns_rows(monkeypatch):
    monkeypatch.setattr("runtime.google_sheet_tools.read_sheet_entries", lambda spreadsheet_id, range_name: [["a", "b"], ["1", "2"]])
    result = sheet_read_range("sheet-1", "Payments!A:I")
    assert result["ok"] is True
    assert result["row_count"] == 2


def test_sheet_prepare_write_rows_returns_pending_payload():
    result = sheet_prepare_write_rows("sheet-1", "ReconRuns!A:J", [["x"]], mode="append")
    assert result["tool"] == "sheet/write_rows"
    assert result["row_count"] == 1


def test_sheet_write_rows_dry_run_does_not_call_google_api(monkeypatch):
    called = {"value": False}
    monkeypatch.setattr("runtime.google_sheet_tools.write_sheet_entries", lambda *args, **kwargs: called.update(value=True))
    result = sheet_write_rows("sheet-1", "ReconRuns!A:J", [["x"]], mode="append", dry_run=True)
    assert result["ok"] is True
    assert result["written"] is False
    assert called["value"] is False


def test_sheet_write_rows_live_calls_google_writer(monkeypatch):
    monkeypatch.setattr(
        "runtime.google_sheet_tools.write_sheet_entries",
        lambda spreadsheet_id, range_name, values, mode="append": {
            "updates": {"updatedRange": range_name, "updatedRows": len(values)}
        },
    )
    result = sheet_write_rows("sheet-1", "ReconRuns!A:J", [["x"]], mode="append", dry_run=False)
    assert result["ok"] is True
    assert result["written"] is True
    assert result["row_count"] == 1
