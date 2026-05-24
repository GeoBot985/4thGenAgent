from __future__ import annotations

import importlib
import time
import tkinter as tk


def test_supplier_invoice_scenario_button_path_is_nonblocking(monkeypatch):
    module = importlib.import_module("src.operator_ui")

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        import pytest

        pytest.skip(f"Tk unavailable: {exc}")

    try:
        root.withdraw()
        module.build_operator_ui(root)
        console = root.operator_console

        monkeypatch.setattr(
            module,
            "run_scenario",
            lambda *args, **kwargs: {
                "ok": True,
                "scenario_id": "supplier_invoice_match_happy_path",
                "label": "Supplier Invoice - Three-Way Match",
                "category": "accounting",
                "frame_id": "frame-test-1",
                "state": "WAITING_FOR_EXECUTE",
                "snapshot": {
                    "active_frame": {
                        "frame_id": "frame-test-1",
                        "manifest_id": "supplier.invoice.match",
                        "state": "WAITING_FOR_EXECUTE",
                    },
                    "pending_actions": [],
                    "executed_actions": [],
                    "outputs": {},
                },
                "timeline": [],
                "report_result": {},
                "approval_pack": {},
            },
        )

        console.scenario_var.set("Supplier Invoice - Three-Way Match")
        start = time.time()
        console.on_run_scenario()
        elapsed = time.time() - start

        assert elapsed < 1.0
        assert console.scenario_result["state"] == "WAITING_FOR_EXECUTE"
        assert console.recovery_snapshot["recovery_status"] == "not_run"
    finally:
        root.destroy()
