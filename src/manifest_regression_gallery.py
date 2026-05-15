from __future__ import annotations

import json
from pathlib import Path


_DEFAULT_BASE_DIR = Path("tests/fixtures/broken_manifests")


def load_gallery_index(
    base_dir: str | Path = _DEFAULT_BASE_DIR,
) -> dict:
    """Load and return the gallery_index.json as a dict."""
    index_path = Path(base_dir) / "gallery_index.json"
    return json.loads(index_path.read_text(encoding="utf-8"))


def iter_gallery_fixtures(
    base_dir: str | Path = _DEFAULT_BASE_DIR,
) -> list[dict]:
    """Return the list of fixture metadata dicts from gallery_index.json."""
    index = load_gallery_index(base_dir)
    return list(index.get("fixtures") or [])


def load_fixture_manifest(
    fixture: dict,
    base_dir: str | Path = _DEFAULT_BASE_DIR,
) -> dict:
    """
    Load a fixture file and attempt to parse it as JSON.

    Returns a result dict:
    {
        "ok": bool,
        "manifest": dict | None,
        "text": str,
        "path": str,
        "exception": Exception | None,
    }

    ok=False and exception set means the file contains invalid JSON.
    ok=True means manifest is a valid parsed dict.
    """
    path = Path(base_dir) / fixture["path"]
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "ok": False,
            "manifest": None,
            "text": "",
            "path": str(path),
            "exception": exc,
        }

    try:
        manifest = json.loads(text)
        return {
            "ok": True,
            "manifest": manifest,
            "text": text,
            "path": str(path),
            "exception": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "manifest": None,
            "text": text,
            "path": str(path),
            "exception": exc,
        }
