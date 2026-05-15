from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "operator_ui.py"


class Operator1080pUsabilityTests(unittest.TestCase):
    def test_demo_view_has_single_primary_action_button(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("_primary_demo_action", "_apply_primary_demo_action", "primary_demo_action_button"):
            self.assertIn(text, source)

    def test_advanced_actions_are_collapsible(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("advanced_actions_visible_var", source)
        self.assertIn("Advanced actions", source)

    def test_variable_demo_cards_use_scrolled_text_widgets(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("create_scroll_card("), 4)
        self.assertIn("create_scrolled_text_widget", source)

    def test_primary_action_appears_before_current_run_panel(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertLess(source.index("primary_demo_action_button"), source.index("current_run_panel"))

    def test_demo_view_preserves_required_labels(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in (
            "Incoming Request",
            "Automation Progress",
            "Business Result",
            "Approval / Evidence",
            "Technical Inspector",
            "Current run:",
            "Next:",
        ):
            self.assertIn(text, source)


if __name__ == "__main__":
    unittest.main()
