from __future__ import annotations

import importlib
import tkinter as tk
import unittest


def _build_console():
    module = importlib.import_module("src.operator_ui")
    root = tk.Tk()
    root.withdraw()
    module.build_operator_ui(root)
    console = getattr(root, "operator_console", None)
    return root, console


class OperatorDemoModeUITests(unittest.TestCase):
    def test_demo_mode_uses_compact_header_only(self):
        try:
            root, console = _build_console()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")

        try:
            self.assertIsNotNone(console)
            self.assertEqual(root.title(), "Autonomous Business Worker Demo")
            self.assertEqual(console.view_mode_var.get(), "Demo")
            self.assertEqual(console.demo_action_bar.winfo_manager(), "grid")
            self.assertEqual(console.demo_main_area.winfo_manager(), "grid")
            self.assertEqual(console.demo_action_bar.grid_info()["row"], 0)
            self.assertEqual(console.current_run_panel.grid_info()["row"], 2)
            self.assertIn("Current:", console.current_step_label.cget("text"))
            self.assertIn("Next:", console.current_step_label.cget("text"))
            self.assertIn("Run selected demo", console.demo_run_button.cget("text"))
            self.assertTrue(hasattr(console.demo_request_text, "scrolled_container"))
            self.assertTrue(hasattr(console.demo_worker_steps_text, "scrolled_container"))
            self.assertTrue(hasattr(console.demo_result_text, "scrolled_container"))
            self.assertTrue(hasattr(console.demo_evidence_text, "scrolled_container"))
        finally:
            root.destroy()

    def test_demo_mode_has_persistent_action_bar_near_top(self):
        try:
            root, console = _build_console()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")

        try:
            self.assertIsNotNone(console)
            self.assertEqual(console.demo_action_bar.grid_info()["row"], 0)
            self.assertIn("Demo:", console.demo_selector.master.winfo_children()[0].cget("text"))
            self.assertIn("Browse demo catalog", console.demo_browse_button.cget("text"))
            self.assertTrue(console.demo_run_button.instate(["!disabled"]))
            self.assertTrue(console.demo_generate_evidence_button.instate(["disabled"]))
            self.assertTrue(console.demo_open_evidence_button.instate(["disabled"]))
        finally:
            root.destroy()

    def test_demo_catalog_is_collapsed_by_default(self):
        try:
            root, console = _build_console()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")

        try:
            self.assertIsNotNone(console)
            self.assertIsNone(getattr(console, "demo_catalog_dialog", None))
            self.assertTrue(hasattr(console, "demo_browse_button"))
            self.assertEqual(console.demo_browse_button.winfo_manager(), "pack")
        finally:
            root.destroy()

    def test_empty_tabs_not_visible_before_first_run(self):
        try:
            root, console = _build_console()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")

        try:
            self.assertIsNotNone(console)
            self.assertTrue(hasattr(console, "demo_main_tabs"))
            self.assertEqual(console.demo_main_tabs.winfo_manager(), "")
            self.assertEqual(console.demo_result_card.winfo_manager(), "")
            self.assertEqual(console.demo_approval_card.winfo_manager(), "")
        finally:
            root.destroy()

    def test_current_run_is_compact_status_strip(self):
        try:
            root, console = _build_console()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")

        try:
            self.assertIsNotNone(console)
            self.assertLessEqual(int(console.demo_current_run_text.cget("height")), 2)
            text = console.demo_current_run_text.get("1.0", "end")
            self.assertIn("Current run:", text)
            self.assertIn("Status:", text)
        finally:
            root.destroy()

    def test_mode_switch_keeps_frames_alive_and_guided_controls(self):
        try:
            root, console = _build_console()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")

        try:
            self.assertIsNotNone(console)
            console._record_active_run(
                {
                    "frame_id": "frame-demo-123",
                    "scenario_id": "customer_status_happy_path",
                    "state": "WAITING_FOR_EXECUTE",
                    "snapshot": {
                        "active_event": {
                            "event_id": "evt-demo-1",
                            "source": "callcenter",
                            "event_type": "customer_message",
                            "payload": {"customer_id": "CUST-001", "message": "Where is my order ORD-10042?"},
                        },
                        "active_frame": {
                            "frame_id": "frame-demo-123",
                            "state": "WAITING_FOR_EXECUTE",
                            "manifest_id": "customer.message_status_check",
                            "inputs": {"customer_id": "CUST-001", "message": "Where is my order ORD-10042?"},
                            "outputs": {"order_id": "ORD-10042", "draft_reply": {"body": "Your order ORD-10042 has shipped."}},
                            "pending_actions": [
                                {
                                    "action_type": "send_customer_message",
                                    "status": "PENDING_APPROVAL",
                                    "customer_id": "CUST-001",
                                }
                            ],
                            "steps": [{"step_id": "validate_input"}, {"step_id": "extract_order_id"}],
                        },
                        "outputs": {"order_id": "ORD-10042"},
                        "validations": [{"step_id": "validate_customer_owns_order", "ok": True}],
                        "pending_actions": [
                            {
                                "action_type": "send_customer_message",
                                "status": "PENDING_APPROVAL",
                                "customer_id": "CUST-001",
                            }
                        ],
                    },
                    "timeline": [],
                    "report_result": {},
                }
            )
            console._load_result_frame(
                {
                    "frame_id": "frame-demo-123",
                    "scenario_id": "customer_status_happy_path",
                    "state": "WAITING_FOR_EXECUTE",
                    "snapshot": console.current_run["snapshot"],
                    "timeline": [],
                    "report_result": {},
                }
            )
            console._render_current_view()
            self.assertIn("frame-demo-1", console.demo_current_run_text.get("1.0", "end"))
            self.assertIn("Waiting for approval", console.current_step_label.cget("text"))
            self.assertEqual(console.demo_result_card.winfo_manager(), "grid")
            self.assertEqual(console.demo_approval_card.winfo_manager(), "grid")
            self.assertTrue(console.demo_request_text.cget("yscrollcommand"))
            self.assertTrue(console.demo_worker_steps_text.cget("yscrollcommand"))
            self.assertTrue(console.demo_result_text.cget("yscrollcommand"))
            self.assertTrue(console.demo_approve_button.instate(["!disabled"]))
            self.assertTrue(console.demo_reject_button.instate(["!disabled"]))
            self.assertTrue(console.demo_generate_evidence_button.instate(["!disabled"]))

            console.view_mode_var.set("Inspector")
            console._switch_view_mode()
            self.assertEqual(console.inspector_view_frame.winfo_manager(), "grid")
            self.assertTrue(hasattr(console, "trace_text"))

            console.view_mode_var.set("Demo")
            console._switch_view_mode()
            self.assertEqual(console.demo_view_frame.winfo_manager(), "grid")
            self.assertEqual(console.inspector_view_frame.winfo_manager(), "")
            self.assertTrue(hasattr(console, "trace_text"))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
