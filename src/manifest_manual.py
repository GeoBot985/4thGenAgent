from __future__ import annotations

import os
import webbrowser
from pathlib import Path


def manifest_manual_path() -> Path:
    return Path(__file__).resolve().parents[1] / "docs" / "manifest_building_manual.md"


def open_manifest_manual() -> dict:
    md_path = manifest_manual_path()
    html_path = md_path.with_suffix(".html")
    target = html_path if html_path.is_file() else md_path
    if not target.is_file():
        return {"ok": False, "path": str(target), "error": "Manifest manual not found."}
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(target))  # type: ignore[attr-defined]
        else:
            webbrowser.open(target.resolve().as_uri())
        return {"ok": True, "path": str(target), "error": ""}
    except Exception as exc:
        return {"ok": False, "path": str(target), "error": str(exc)}
