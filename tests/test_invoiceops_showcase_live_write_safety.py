from __future__ import annotations

from runtime.invoiceops_showcase_demo import (
    run_showcase_invoice_batch,
    execute_showcase_live_posting,
    build_showcase_posting_plan,
    REQUIRED_PROFILE,
    CONFIRMATION_TEMPLATE,
)


def test_live_mode_requires_correct_profile() -> None:
    result = run_showcase_invoice_batch(
        live_mode=True,
        profile="service",
        spreadsheet_id="SHEET123",
        confirm=CONFIRMATION_TEMPLATE.format(spreadsheet_id="SHEET123"),
    )
    assert not result["ok"]
    assert any("profile_required" in b for b in result["blockers"])


def test_live_mode_requires_spreadsheet_id() -> None:
    result = run_showcase_invoice_batch(
        live_mode=True,
        profile=REQUIRED_PROFILE,
        spreadsheet_id="",
        confirm="",
    )
    assert not result["ok"]
    assert any("spreadsheet_id" in b for b in result["blockers"])


def test_live_mode_requires_typed_confirmation() -> None:
    result = run_showcase_invoice_batch(
        live_mode=True,
        profile=REQUIRED_PROFILE,
        spreadsheet_id="SHEET123",
        confirm="wrong confirmation",
    )
    assert not result["ok"]
    assert any("confirmation_required" in b for b in result["blockers"])


def test_live_mode_blocked_without_any_confirm() -> None:
    result = run_showcase_invoice_batch(
        live_mode=True,
        profile=REQUIRED_PROFILE,
        spreadsheet_id="SHEET123",
        confirm="",
    )
    assert not result["ok"]
    assert result["live_side_effects_performed"] is False


def test_execute_showcase_posting_wrong_profile() -> None:
    posting_plan = build_showcase_posting_plan(run_id="TEST-001", invoice_results=[])
    result = execute_showcase_live_posting(
        posting_plan=posting_plan,
        spreadsheet_id="SHEET123",
        profile="service",
        confirm=CONFIRMATION_TEMPLATE.format(spreadsheet_id="SHEET123"),
    )
    assert not result["ok"]
    assert "profile_required" in result.get("error", "")


def test_execute_showcase_posting_wrong_confirmation() -> None:
    posting_plan = build_showcase_posting_plan(run_id="TEST-001", invoice_results=[])
    result = execute_showcase_live_posting(
        posting_plan=posting_plan,
        spreadsheet_id="SHEET123",
        profile=REQUIRED_PROFILE,
        confirm="WRONG PHRASE",
    )
    assert not result["ok"]
    assert result["error"] == "CONFIRMATION_REQUIRED"


def test_execute_showcase_posting_correct_inputs() -> None:
    posting_plan = build_showcase_posting_plan(run_id="TEST-001", invoice_results=[])
    confirm = CONFIRMATION_TEMPLATE.format(spreadsheet_id="SHEET123")
    result = execute_showcase_live_posting(
        posting_plan=posting_plan,
        spreadsheet_id="SHEET123",
        profile=REQUIRED_PROFILE,
        confirm=confirm,
    )
    assert result["ok"]
    assert result["confirmed"] is True


def test_non_demo_spreadsheet_blocked_by_missing_confirmation() -> None:
    result = run_showcase_invoice_batch(
        live_mode=True,
        profile=REQUIRED_PROFILE,
        spreadsheet_id="OTHER_SHEET_999",
        confirm=CONFIRMATION_TEMPLATE.format(spreadsheet_id="SHEET123"),
    )
    assert not result["ok"]
    assert any("confirmation_required" in b for b in result["blockers"])


def test_idempotency_keys_are_unique_across_batch() -> None:
    result = run_showcase_invoice_batch(live_mode=False)
    keys: list[str] = []
    for inv in result["invoice_results"]:
        for pw in inv.get("prepared_writes", []):
            keys.append(pw["idempotency_key"])
    assert len(keys) == len(set(keys)), "Idempotency key collision detected"
