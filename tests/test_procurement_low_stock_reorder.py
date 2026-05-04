from __future__ import annotations

import json
from pathlib import Path

from runtime.business_data import reset_business_dataset
from src.operator_scenario_runner import run_scenario


def _run_procurement(runtime_root: str = "runtime_data"):
    if runtime_root != "runtime_data":
        reset_business_dataset(runtime_root)
    return run_scenario("procurement_low_stock_happy_path", runtime_data_dir=runtime_root, reset_dataset=False)


def test_procurement_happy_path_reaches_waiting_for_execute(tmp_path):
    result = _run_procurement()
    assert result["state"] == "WAITING_FOR_EXECUTE"


def test_procurement_outputs_required_artifacts(tmp_path):
    result = _run_procurement()
    outputs = result["snapshot"]["outputs"]
    for key in ("low_stock_items", "reorder_candidates", "duplicate_po_check", "selected_supplier", "draft_po", "po_validation", "supplier_message", "supplier_message_send"):
        assert key in outputs
    assert outputs["po_validation"]["ok"] is True


def test_procurement_stages_one_pending_supplier_action(tmp_path):
    result = _run_procurement()
    assert len(result["snapshot"]["pending_actions"]) == 1
    assert len(result["snapshot"]["executed_actions"]) == 0


def test_procurement_po_total_matches_line_sum(tmp_path):
    result = _run_procurement()
    draft_po = result["snapshot"]["outputs"]["draft_po"]
    total = round(sum(line["line_total"] for line in draft_po["lines"]), 2)
    assert round(draft_po["total"], 2) == total


def test_procurement_llm_call_is_recorded(tmp_path):
    result = _run_procurement()
    llm_calls = result["snapshot"]["llm_calls"]
    assert any(call.get("action") == "draft_supplier_reorder_message" for call in llm_calls)


def test_procurement_no_live_send_occurs(tmp_path):
    result = _run_procurement()
    assert result["snapshot"]["executed_actions"] == []


def test_duplicate_open_po_excludes_candidate_but_continues_with_remaining(tmp_path):
    result = _run_procurement()
    assert result["state"] == "WAITING_FOR_EXECUTE"
    duplicates = result["snapshot"]["outputs"]["duplicate_po_check"]["duplicates"]
    valid_candidates = result["snapshot"]["outputs"]["duplicate_po_check"]["valid_candidates"]
    assert any(item["sku"] == "SKU-1001" for item in duplicates)
    assert any(item["sku"] == "SKU-1002" for item in valid_candidates)
    assert any(line["sku"] == "SKU-1002" for line in result["snapshot"]["outputs"]["draft_po"]["lines"])


def test_bad_supplier_message_blocks_pending_action(tmp_path):
    runtime_root = str(tmp_path)
    reset_business_dataset(runtime_root)
    result = run_scenario("procurement_low_stock_bad_llm_message", runtime_data_dir=runtime_root, reset_dataset=False)
    assert result["state"].startswith("FAILED")
    assert result["snapshot"]["pending_actions"] == []
