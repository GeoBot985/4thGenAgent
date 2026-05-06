from __future__ import annotations

import importlib
import tkinter as tk
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "operator_ui.py"
DATA_SOURCE = ROOT / "src" / "operator_data.py"
SCRIPT = ROOT / "scripts" / "run_operator_ui.py"


class OperatorFrontendShellTests(unittest.TestCase):
    def test_ui_module_imports(self):
        module = importlib.import_module("src.operator_ui")
        data_module = importlib.import_module("src.operator_data")

        self.assertTrue(hasattr(module, "main"))
        self.assertTrue(hasattr(module, "build_operator_ui") or hasattr(module, "OperatorConsole"))
        self.assertTrue(hasattr(data_module, "build_operator_snapshot"))

    def test_script_exists(self):
        self.assertTrue(SCRIPT.exists())

    def test_required_labels_exist_in_source(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in (
            "Autonomous Business Worker Demo",
            "Demo:",
            "Horizontal Demo Flow",
            "Current run:",
            "Incoming Request",
            "Automation Progress",
            "Business Result",
            "Run selected demo",
            "Browse demo catalog",
            "Generate evidence for this run",
            "Open evidence for this run",
            "Advanced settings",
            "No evidence pack has been generated for this run yet",
            "Approval / Evidence",
            "Technical Inspector",
            "View Mode",
            "Demo",
            "Operator",
            "Inspector",
        ):
            self.assertIn(text, source)

    def test_run_selected_demo_not_only_inside_scenario_card_area(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertLess(source.index("Demo:"), source.index("Run selected demo"))
        self.assertLess(source.index("Run selected demo"), source.index("Current run:"))

    def test_no_forbidden_runtime_calls(self):
        for path in (SOURCE, DATA_SOURCE):
            source = path.read_text(encoding="utf-8")
            for text in (
                "intake_event(",
                "intake_and_run_event(",
                "execute_pending",
                "send_customer_message",
                "gmail",
                "whatsapp",
            ):
                self.assertNotIn(text, source)

    def test_build_operator_ui_creates_withdrawn_root(self):
        module = importlib.import_module("src.operator_ui")
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")

        try:
            root.withdraw()
            built = module.build_operator_ui(root)
            self.assertIs(built, root)
            self.assertEqual(root.title(), "Autonomous Business Worker Demo")
            console = getattr(root, "operator_console", None)
            self.assertIsNotNone(console)
            self.assertTrue(hasattr(console, "tool_health_tree"))
            self.assertTrue(hasattr(console, "tool_health_details"))
            self.assertTrue(hasattr(console, "view_mode_var"))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
