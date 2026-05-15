from __future__ import annotations

from pathlib import Path


SOURCE = Path("src/operator_ui.py").read_text(encoding="utf-8")


def test_toolpack_buttons_exist_in_operator_ui_source() -> None:
    for text in ("Refresh Tool Packs", "Validate Tool Packs", "Open Tool Pack README"):
        assert text in SOURCE


def test_toolpack_status_columns_exist_in_operator_ui_source() -> None:
    for text in ("toolpack_discovery_snapshot", "registered", "enabled", "valid", "source", "path"):
        assert text in SOURCE
