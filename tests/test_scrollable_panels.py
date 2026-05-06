from __future__ import annotations

import tkinter as tk
import unittest

from src.operator_widgets import ScrollablePanel


class ScrollablePanelTests(unittest.TestCase):
    def test_scrollable_panel_constructs_header_body_and_scrollbar(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")

        try:
            root.withdraw()
            panel = ScrollablePanel(root, "Demo Panel")
            panel.pack(fill="both", expand=True)
            root.update_idletasks()
            self.assertEqual(panel.title_label.cget("text"), "Demo Panel")
            self.assertTrue(hasattr(panel, "body"))
            self.assertTrue(hasattr(panel, "scrollbar"))
            self.assertEqual(panel.title_label.winfo_manager(), "grid")
            self.assertGreaterEqual(len(panel.body.winfo_children()), 0)
        finally:
            root.destroy()

    def test_scrollable_panel_supports_vertical_overflow(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")

        try:
            root.geometry("320x180")
            panel = ScrollablePanel(root, "Overflow Demo")
            panel.pack(fill="both", expand=True)
            for index in range(40):
                tk.Label(panel.body, text=f"Line {index + 1}").pack(anchor="w")
            root.update_idletasks()
            bbox = panel.canvas.bbox("all")
            self.assertIsNotNone(bbox)
            self.assertGreater(bbox[3] - bbox[1], panel.canvas.winfo_height())
            self.assertGreaterEqual(panel.scrollbar.get()[1], 0.0)
        finally:
            root.destroy()

    def test_scrollable_panel_keeps_header_fixed(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")

        try:
            root.geometry("320x180")
            panel = ScrollablePanel(root, "Fixed Header")
            panel.pack(fill="both", expand=True)
            for index in range(30):
                tk.Label(panel.body, text=f"Row {index + 1}").pack(anchor="w")
            root.update_idletasks()
            header_before = panel.title_label.winfo_y()
            panel.canvas.yview_scroll(10, "units")
            root.update_idletasks()
            self.assertEqual(panel.title_label.winfo_y(), header_before)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
