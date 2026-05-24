from __future__ import annotations

import json
from pathlib import Path

from runtime.invoiceops_showcase_demo import (
    run_showcase_invoice_batch,
    write_showcase_demo_report,
    render_showcase_demo_markdown,
)


def test_write_report_creates_expected_files(tmp_path: Path) -> None:
    batch = run_showcase_invoice_batch(live_mode=False)
    paths = write_showcase_demo_report(batch, runtime_data_dir=tmp_path)
    assert Path(paths["json_latest"]).is_file()
    assert Path(paths["markdown_latest"]).is_file()
    assert Path(paths["json_run"]).is_file()
    assert Path(paths["markdown_run"]).is_file()
    assert Path(paths["invoice_results"]).is_file()
    assert Path(paths["live_write_summary"]).is_file()


def test_json_latest_is_valid_json(tmp_path: Path) -> None:
    batch = run_showcase_invoice_batch(live_mode=False)
    paths = write_showcase_demo_report(batch, runtime_data_dir=tmp_path)
    data = json.loads(Path(paths["json_latest"]).read_text(encoding="utf-8"))
    assert data["demo_run_id"] == batch["demo_run_id"]
    assert data["invoice_count"] == 8


def test_invoice_results_file_contains_all_invoices(tmp_path: Path) -> None:
    batch = run_showcase_invoice_batch(live_mode=False)
    paths = write_showcase_demo_report(batch, runtime_data_dir=tmp_path)
    data = json.loads(Path(paths["invoice_results"]).read_text(encoding="utf-8"))
    assert len(data["invoice_results"]) == 8


def test_live_write_summary_file_structure(tmp_path: Path) -> None:
    batch = run_showcase_invoice_batch(live_mode=False)
    paths = write_showcase_demo_report(batch, runtime_data_dir=tmp_path)
    data = json.loads(Path(paths["live_write_summary"]).read_text(encoding="utf-8"))
    assert "live_writes" in data
    assert "total" in data
    assert isinstance(data["live_writes"], list)


def test_markdown_report_contains_required_sections() -> None:
    batch = run_showcase_invoice_batch(live_mode=False)
    md = render_showcase_demo_markdown(batch)
    assert "InvoiceOps Live Bookkeeping Showcase Demo" in md
    assert "Demo Run ID" in md
    assert "Summary" in md
    assert "Invoice Scenario Results" in md
    assert "Exception Summary" in md
    assert "Live Write Safety Statement" in md
    assert "Talking Points" in md


def test_markdown_report_contains_all_invoice_numbers() -> None:
    batch = run_showcase_invoice_batch(live_mode=False)
    md = render_showcase_demo_markdown(batch)
    for i in range(1, 9):
        assert f"INV-00{i}" in md


def test_write_report_idempotent_latest_file(tmp_path: Path) -> None:
    batch1 = run_showcase_invoice_batch(live_mode=False)
    paths1 = write_showcase_demo_report(batch1, runtime_data_dir=tmp_path)
    batch2 = run_showcase_invoice_batch(live_mode=False)
    paths2 = write_showcase_demo_report(batch2, runtime_data_dir=tmp_path)
    data = json.loads(Path(paths2["json_latest"]).read_text(encoding="utf-8"))
    assert data["demo_run_id"] == batch2["demo_run_id"]


def test_run_with_write_report_flag_populates_reports_key(tmp_path: Path) -> None:
    result = run_showcase_invoice_batch(live_mode=False, write_report=True, runtime_data_dir=str(tmp_path))
    assert result["ok"]
    assert result["reports"].get("json_latest")
    assert result["reports"].get("markdown_latest")
