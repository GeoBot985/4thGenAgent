from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollablePanel(ttk.Frame):
    def __init__(self, parent: tk.Widget, title: str, *, body_padding: int = 0, body_bg: str | None = None):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.title_label = ttk.Label(self, text=title, style="Section.TLabel")
        self.title_label.grid(row=0, column=0, sticky="w")

        container = ttk.Frame(self)
        container.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(container, highlightthickness=0, borderwidth=0, bg=body_bg or "#f7f8fa")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.body = ttk.Frame(self.canvas, padding=body_padding)
        self._body_window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.body.bind("<Enter>", self._bind_mousewheel)
        self.body.bind("<Leave>", self._unbind_mousewheel)

    def _on_body_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._body_window, width=event.width)

    def _bind_mousewheel(self, _event: tk.Event) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: tk.Event) -> None:
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        delta = 0
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        elif getattr(event, "delta", 0):
            delta = -1 if event.delta > 0 else 1
        if delta:
            self.canvas.yview_scroll(delta, "units")


def create_scrolled_text_widget(parent: tk.Widget, *, height: int = 8, bg: str = "#f7f8fa", fg: str = "#1f2937", font: tuple[str, int] = ("Segoe UI", 10)) -> tuple[tk.Text, ttk.Scrollbar]:
    frame = ttk.Frame(parent)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    text = tk.Text(
        frame,
        wrap="word",
        height=height,
        bg=bg,
        fg=fg,
        relief="flat",
        highlightthickness=0,
        borderwidth=0,
        font=font,
        padx=8,
        pady=8,
    )
    text.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    text.configure(yscrollcommand=scrollbar.set)
    text.scrolled_container = frame  # type: ignore[attr-defined]
    return text, scrollbar
