from __future__ import annotations

import json
import shutil
import sys
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.llm_adapter import FakeLLMAdapter
from src.operator_scenarios import get_scenario as load_scenario
from src.operator_scenario_runner import run_scenario


OUTPUTS_ROOT = ROOT / "runtime_data" / "outputs"
RUNTIME_ROOT = OUTPUTS_ROOT / "runtime"
REPORTS_DIR = OUTPUTS_ROOT / "reports"
AUDIT_DIR = OUTPUTS_ROOT / "audit"


ACCOUNTING_FIXTURES: dict[str, list[list[str]]] = {
    "Payments!A:I": [
        ["payment_id", "payment_ref", "order_ref", "customer_id", "amount", "currency", "payment_date", "status", "source"],
        ["PAY-1001", "EFT-9001", "ORD-10042", "CUST-1001", "1250.00", "ZAR", "2026-05-04", "received", "bank"],
        ["PAY-1002", "EFT-9002", "ORD-10043", "CUST-1002", "450.00", "ZAR", "2026-05-04", "received", "bank"],
        ["PAY-1003", "EFT-9003", "ORD-10044", "CUST-1003", "300.00", "ZAR", "2026-05-04", "received", "bank"],
        ["PAY-1004", "EFT-9005", "ORD-10045", "CUST-1004", "500.00", "ZAR", "2026-05-04", "received", "bank"],
        ["PAY-1005", "EFT-9005", "ORD-10046", "CUST-1005", "250.00", "ZAR", "2026-05-04", "received", "bank"],
    ],
    "Orders!A:F": [
        ["order_ref", "customer_id", "order_total", "currency", "order_status", "invoice_id"],
        ["ORD-10042", "CUST-1001", "1250.00", "ZAR", "invoiced", "INV-10042"],
        ["ORD-10043", "CUST-1002", "500.00", "ZAR", "invoiced", "INV-10043"],
        ["ORD-10044", "CUST-1003", "300.00", "ZAR", "invoiced", "INV-10044"],
        ["ORD-10045", "CUST-1004", "500.00", "ZAR", "invoiced", "INV-10045"],
        ["ORD-10046", "CUST-1005", "250.00", "ZAR", "invoiced", "INV-10046"],
    ],
    "CustomerInvoices!A:H": [
        ["invoice_id", "order_ref", "customer_id", "invoice_total", "currency", "invoice_status", "issued_date", "due_date"],
        ["INV-10042", "ORD-10042", "CUST-1001", "1250.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
        ["INV-10043", "ORD-10043", "CUST-1002", "500.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
        ["INV-10044", "ORD-10044", "CUST-1003", "300.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
        ["INV-10045", "ORD-10045", "CUST-1004", "500.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
        ["INV-10046", "ORD-10046", "CUST-1005", "250.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
    ],
    "Ledger!A:I": [
        ["ledger_entry_id", "source_type", "source_ref", "debit_account", "credit_account", "amount", "currency", "posted_date", "status"],
        ["LED-1001", "payment", "EFT-9001", "bank", "revenue", "1250.00", "ZAR", "2026-05-04", "posted"],
    ],
}


WORKFLOWS: list[dict[str, str]] = [
    {
        "workflow_key": "customer_workflow",
        "label": "Customer Order-Status Workflow",
        "scenario_id": "customer_status_approve_execute_dry_run",
        "expected_state": "COMPLETED",
    },
    {
        "workflow_key": "procurement_workflow",
        "label": "Procurement Low-Stock Workflow",
        "scenario_id": "procurement_low_stock_approve_execute_dry_run",
        "expected_state": "COMPLETED",
    },
    {
        "workflow_key": "accounting_workflow",
        "label": "Accounting Reconciliation Workflow",
        "scenario_id": "accounting_payment_reconciliation_approve_execute_dry_run",
        "expected_state": "COMPLETED",
    },
]


def main() -> int:
    _prepare_directories()
    started_at = _now()
    workflow_results: list[dict[str, Any]] = []
    failures: list[str] = []

    adapter = FakeLLMAdapter()
    with ExitStack() as stack:
        stack.enter_context(patch("runtime.google_sheet_tools.sheet_read_range", side_effect=_fake_sheet_read_range))
        stack.enter_context(patch("src.operator_scenario_runner.get_scenario", side_effect=_patched_get_scenario))

        for workflow in WORKFLOWS:
            result = run_scenario(
                workflow["scenario_id"],
                runtime_data_dir=str(RUNTIME_ROOT),
                use_local_llm=False,
                reset_dataset=True,
                generate_report=True,
                llm_adapter=adapter,
                allow_test_fake_llm=True,
            )
            copied_artifacts = _copy_scenario_artifacts(workflow["workflow_key"], result)
            workflow_result = _build_workflow_result(workflow, result, copied_artifacts)
            workflow_results.append(workflow_result)
            if workflow_result["status"] != "PASS":
                failures.append(f"{workflow['workflow_key']}: {workflow_result['error']}")

    ended_at = _now()
    summary = _summarize(workflow_results, started_at, ended_at, failures)
    report_paths = _write_top_level_report(summary, workflow_results)
    audit_paths = _write_audit(summary, workflow_results, report_paths)
    artifacts = {**report_paths, **audit_paths}
    summary["artifacts"] = artifacts
    _write_json(AUDIT_DIR / "golden_demo_audit.json", {
        "report_type": "golden_demo_verification",
        "generated_at": ended_at,
        "started_at": started_at,
        "ended_at": ended_at,
        "verdict": summary["verdict"],
        "checks": summary["checks"],
        "summary": {
            "workflow_count": summary["workflow_count"],
            "pass_count": summary["pass_count"],
            "fail_count": summary["fail_count"],
            "duration_ms": summary["duration_ms"],
        },
        "workflow_results": workflow_results,
        "known_limitations": summary["known_limitations"],
        "artifacts": artifacts,
    })
    print(_render_console_summary(summary, workflow_results))
    return 0 if not failures else 1


def _prepare_directories() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)


def _patched_get_scenario(scenario_id: str) -> dict[str, Any]:
    scenario = deepcopy(load_scenario(scenario_id))
    if scenario_id.startswith("accounting_payment_reconciliation"):
        payload = scenario.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        payload["spreadsheet_id"] = "demo-sheet-local"
        scenario["payload"] = payload
    return scenario


def _fake_sheet_read_range(spreadsheet_id: str, range_name: str) -> dict[str, Any]:
    rows = ACCOUNTING_FIXTURES.get(range_name)
    if rows is None:
        return {
            "ok": False,
            "spreadsheet_id": spreadsheet_id,
            "range_name": range_name,
            "rows": [],
            "row_count": 0,
            "error": f"UNKNOWN_RANGE:{range_name}",
        }
    return {
        "ok": True,
        "spreadsheet_id": spreadsheet_id,
        "range_name": range_name,
        "rows": rows,
        "row_count": len(rows),
        "error": "",
    }


def _copy_scenario_artifacts(workflow_key: str, result: dict[str, Any]) -> dict[str, str]:
    report_result = result.get("report_result", {}) if isinstance(result, dict) else {}
    copied: dict[str, str] = {}
    mapping = {
        "markdown_path": REPORTS_DIR / f"{workflow_key}_report.md",
        "html_path": REPORTS_DIR / f"{workflow_key}_report.html",
        "evidence_bundle_path": AUDIT_DIR / f"{workflow_key}_audit.json",
    }
    for source_key, target_path in mapping.items():
        source_path = Path(str(report_result.get(source_key, "")))
        if not source_path.is_file():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied[source_key] = str(target_path)
    return copied


def _build_workflow_result(workflow: dict[str, str], result: dict[str, Any], copied_artifacts: dict[str, str]) -> dict[str, Any]:
    approval_pack = result.get("approval_pack", {}) if isinstance(result, dict) else {}
    snapshot = result.get("snapshot", {}) if isinstance(result, dict) else {}
    pending_actions = _list_value(snapshot, "pending_actions")
    executed_actions = _list_value(snapshot, "executed_actions")
    tool_calls = _list_value(snapshot, "tool_calls")
    outputs = snapshot.get("outputs", {}) if isinstance(snapshot, dict) else {}
    report_result = result.get("report_result", {}) if isinstance(result, dict) else {}
    status = "PASS"
    error = ""
    expected_state = workflow["expected_state"]
    actual_state = str(result.get("state", ""))
    if not result.get("ok"):
        status = "FAIL"
        error = str(result.get("error", "")) or "Scenario failed."
    elif actual_state != expected_state:
        status = "FAIL"
        error = f"Expected state {expected_state}, got {actual_state}."
    elif not report_result.get("ok"):
        status = "FAIL"
        error = "Scenario report generation failed."
    elif not copied_artifacts:
        status = "FAIL"
        error = "Scenario artifacts were not copied to runtime_data/outputs."

    checks = _build_acceptance_checks(workflow["workflow_key"], result, snapshot, approval_pack)
    if status == "PASS" and any(value != "PASS" for value in checks.values()):
        status = "FAIL"
        failed = [name for name, value in checks.items() if value != "PASS"]
        error = f"Acceptance checks failed: {', '.join(failed)}"

    return {
        "workflow_key": workflow["workflow_key"],
        "label": workflow["label"],
        "scenario_id": workflow["scenario_id"],
        "status": status,
        "state": actual_state,
        "frame_id": result.get("frame_id", ""),
        "manifest_id": result.get("manifest_id", ""),
        "pending_action_count": len(pending_actions),
        "executed_action_count": len(executed_actions),
        "approval_pack_pending_count": approval_pack.get("pending_action_count", 0) if isinstance(approval_pack, dict) else 0,
        "report_result": report_result,
        "artifacts": copied_artifacts,
        "checks": checks,
        "error": error,
    }


def _build_acceptance_checks(workflow_key: str, result: dict[str, Any], snapshot: dict[str, Any], approval_pack: dict[str, Any]) -> dict[str, str]:
    outputs = snapshot.get("outputs", {}) if isinstance(snapshot, dict) else {}
    pending_actions = _list_value(snapshot, "pending_actions")
    executed_actions = _list_value(snapshot, "executed_actions")
    tool_calls = _list_value(snapshot, "tool_calls")
    if workflow_key == "customer_workflow":
        return {
            "customer_input_accepted": _bool_status(result.get("ok") and result.get("state") in {"WAITING_FOR_EXECUTE", "COMPLETED"}),
            "order_reference_available": _bool_status(bool(outputs.get("order_id")) or bool(_nested_value(outputs, "order.order_ref"))),
            "order_lookup_executed": _bool_status(_has_tool_call(tool_calls, {"customer/order_context", "order/read", "customer/build_status_context"})),
            "ownership_validated": _bool_status(bool(_nested_value(outputs, "ownership_check.ok")) if isinstance(outputs.get("ownership_check"), dict) else bool(outputs.get("ownership_check"))),
            "reply_drafted": _bool_status(bool(_nested_value(outputs, "draft_reply.body")) if isinstance(outputs.get("draft_reply"), dict) else False),
            "dry_run_only": _bool_status(_all_tool_calls_dry_run(tool_calls) and _all_executed_actions_dry_run(executed_actions)),
            "approval_gate": _bool_status(bool(pending_actions) and int(approval_pack.get("pending_action_count", 0) or 0) >= 1),
        }
    if workflow_key == "procurement_workflow":
        return {
            "low_stock_identified": _bool_status(bool(outputs.get("low_stock_items")) or bool(outputs.get("reorder_candidates"))),
            "reorder_calculated": _bool_status(bool(outputs.get("draft_po"))),
            "supplier_selected": _bool_status(bool(outputs.get("selected_supplier"))),
            "purchase_order_staged": _bool_status(bool(pending_actions) and _has_tool_call(tool_calls, {"supplier/prepare_message_action", "supplier/send_message"})),
            "dry_run_only": _bool_status(_all_tool_calls_dry_run(tool_calls) and _all_executed_actions_dry_run(executed_actions)),
            "approval_gate": _bool_status(int(approval_pack.get("pending_action_count", 0) or 0) >= 1),
        }
    if workflow_key == "accounting_workflow":
        required_outputs = ("payments_sheet", "orders_sheet", "invoices_sheet", "ledger_sheet", "reconciliation_result", "reconciliation_validation", "exception_summary")
        return {
            "reconciliation_data_loaded": _bool_status(all(key in outputs for key in required_outputs)),
            "matched_or_unmatched_identified": _bool_status(bool(_nested_value(outputs, "reconciliation_result.matched")) or bool(_nested_value(outputs, "reconciliation_result.exceptions"))),
            "exception_report_created": _bool_status(bool(outputs.get("exception_summary")) and bool(result.get("report_result", {}).get("ok"))),
            "ledger_validation_ran": _bool_status(bool(_nested_value(outputs, "reconciliation_validation.ok")) if isinstance(outputs.get("reconciliation_validation"), dict) else bool(outputs.get("reconciliation_validation"))),
            "dry_run_only": _bool_status(_all_tool_calls_dry_run(tool_calls) and _all_executed_actions_dry_run(executed_actions)),
            "approval_gate": _bool_status(bool(pending_actions) and int(approval_pack.get("pending_action_count", 0) or 0) == 2),
        }
    return {
        "approval_gate": _bool_status(bool(pending_actions) and int(approval_pack.get("pending_action_count", 0) or 0) > 0),
        "dry_run_only": _bool_status(_all_tool_calls_dry_run(tool_calls) and _all_executed_actions_dry_run(executed_actions)),
        "taskframe_completed": _bool_status(str(result.get("state", "")) == "COMPLETED"),
    }


def _summarize(workflow_results: list[dict[str, Any]], started_at: str, ended_at: str, failures: list[str]) -> dict[str, Any]:
    pass_count = sum(1 for item in workflow_results if item["status"] == "PASS")
    fail_count = sum(1 for item in workflow_results if item["status"] != "PASS")
    approval_gate_ok = all(item["pending_action_count"] > 0 and item["executed_action_count"] > 0 for item in workflow_results)
    report_ok = all(bool(item["report_result"].get("ok")) for item in workflow_results)
    audit_ok = all(all(path in item["artifacts"] for path in ("markdown_path", "html_path", "evidence_bundle_path")) for item in workflow_results)
    verdict = "READY" if not failures and fail_count == 0 else "FAILED"
    return {
        "generated_at": ended_at,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": _duration_ms(started_at, ended_at),
        "workflow_count": len(workflow_results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "verdict": verdict,
        "checks": {
            "customer": "PASS" if _workflow_status(workflow_results, "customer_workflow") else "FAIL",
            "procurement": "PASS" if _workflow_status(workflow_results, "procurement_workflow") else "FAIL",
            "accounting": "PASS" if _workflow_status(workflow_results, "accounting_workflow") else "FAIL",
            "approval_gate": "PASS" if approval_gate_ok else "FAIL",
            "report_audit": "PASS" if report_ok and audit_ok else "FAIL",
        },
        "known_limitations": [],
        "failures": failures,
    }


def _write_top_level_report(summary: dict[str, Any], workflow_results: list[dict[str, Any]]) -> dict[str, str]:
    markdown_path = REPORTS_DIR / "golden_demo_report.md"
    html_path = REPORTS_DIR / "golden_demo_report.html"
    markdown = _render_markdown(summary, workflow_results)
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>Golden Demo Report</title></head><body><pre>{_escape(markdown)}</pre></body></html>"
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return {"golden_demo_report_md": str(markdown_path), "golden_demo_report_html": str(html_path)}


def _write_audit(summary: dict[str, Any], workflow_results: list[dict[str, Any]], report_paths: dict[str, str]) -> dict[str, str]:
    audit_path = AUDIT_DIR / "golden_demo_audit.json"
    audit = {
        "verdict": summary.get("verdict", "FAILED"),
        "checks": summary.get("checks", {}),
        "workflow_results": workflow_results,
        "summary": {
            "workflow_count": summary.get("workflow_count", 0),
            "pass_count": summary.get("pass_count", 0),
            "fail_count": summary.get("fail_count", 0),
            "duration_ms": summary.get("duration_ms", 0),
        },
        "known_limitations": summary.get("known_limitations", []),
        "artifacts": report_paths,
    }
    _write_json(audit_path, audit)
    return {"golden_demo_audit_json": str(audit_path)}


def _render_markdown(summary: dict[str, Any], workflow_results: list[dict[str, Any]]) -> str:
    lines = [
        "# Golden Demo Report",
        "",
        "## Overview",
        "",
        "- TaskFrame-centered manifest-driven business automation runtime",
        "- Clean-clone release-candidate path",
        "- Optional RPA excluded from the default demo path",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "|---|---|",
    ]
    for key, status in summary.get("checks", {}).items():
        lines.append(f"| {key} | {status} |")
    lines.extend([
        "",
        "## Workflow Results",
        "",
        "| Workflow | Scenario | State | Pending | Executed | Report | Audit |",
        "|---|---|---:|---:|---:|---|---|",
    ])
    for item in workflow_results:
        lines.append(
            f"| {item['workflow_key']} | {item['scenario_id']} | {item['state']} | {item['pending_action_count']} | {item['executed_action_count']} | {item['artifacts'].get('markdown_path', '')} | {item['artifacts'].get('evidence_bundle_path', '')} |"
        )
    lines.extend([
        "",
        "## Verdict",
        "",
        f"- {summary.get('verdict', 'FAILED')}",
        "",
        "## Known Limitations",
        "",
    ])
    if summary.get("known_limitations"):
        lines.extend([f"- {item}" for item in summary["known_limitations"]])
    else:
        lines.append("- None")
    return "\n".join(lines)


def _render_console_summary(summary: dict[str, Any], workflow_results: list[dict[str, Any]]) -> str:
    lines = [
        "GOLDEN DEMO",
        f"Verdict: {summary.get('verdict', 'FAILED')}",
        f"Workflows: {summary.get('pass_count', 0)}/{summary.get('workflow_count', 0)} passed",
    ]
    for item in workflow_results:
        lines.append(f"- {item['workflow_key']}: {item['status']} ({item['state']})")
    lines.append(f"Report: {REPORTS_DIR / 'golden_demo_report.md'}")
    lines.append(f"Audit: {AUDIT_DIR / 'golden_demo_audit.json'}")
    return "\n".join(lines)


def _list_value(data: dict[str, Any], path: str) -> list[Any]:
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return []
    return current if isinstance(current, list) else []


def _nested_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _has_tool_call(tool_calls: list[Any], tool_names: set[str]) -> bool:
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        if str(call.get("tool", "")) in tool_names:
            return True
    return False


def _all_tool_calls_dry_run(tool_calls: list[Any]) -> bool:
    relevant = [call for call in tool_calls if isinstance(call, dict) and call.get("tool")]
    if not relevant:
        return False
    return all(call.get("live") is False for call in relevant)


def _all_executed_actions_dry_run(executed_actions: list[Any]) -> bool:
    relevant = [action for action in executed_actions if isinstance(action, dict)]
    if not relevant:
        return False
    return all(action.get("dry_run") is True for action in relevant)


def _bool_status(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _workflow_status(workflow_results: list[dict[str, Any]], workflow_key: str) -> bool:
    item = next((result for result in workflow_results if result["workflow_key"] == workflow_key), None)
    return bool(item and item["status"] == "PASS")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _duration_ms(started_at: str, ended_at: str) -> int:
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        return int((end - start).total_seconds() * 1000)
    except Exception:
        return 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


if __name__ == "__main__":
    raise SystemExit(main())
