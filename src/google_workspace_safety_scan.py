from __future__ import annotations

from pathlib import Path
from typing import Any


FORBIDDEN_TERMS = (
    ".send(",
    ".insert(",
    ".update(",
    ".patch(",
    ".delete(",
    ".trash(",
    ".modify(",
    ".batchUpdate(",
    ".append(",
    ".clear(",
    ".permissions(",
)


def scan_google_workspace_pack_for_forbidden_calls(
    path: str | Path = "tool_packs/google_workspace",
) -> dict[str, Any]:
    pack_path = Path(path)
    scanned_files: list[str] = []
    forbidden_hits: list[dict[str, str]] = []
    if not pack_path.exists():
        return {"ok": False, "forbidden_hits": [], "scanned_files": []}

    for file_path in sorted(pack_path.rglob("*.py")):
        if "__pycache__" in file_path.parts:
            continue
        if "tests" in file_path.parts and file_path.name != "__init__.py":
            # Pack-local tests are not part of the executable surface area.
            continue
        scanned_files.append(_display_path(file_path))
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        lower = text.lower()
        for term in FORBIDDEN_TERMS:
            if term.lower() in lower:
                forbidden_hits.append({"path": _display_path(file_path), "term": term})

    return {
        "ok": not forbidden_hits,
        "forbidden_hits": forbidden_hits,
        "scanned_files": scanned_files,
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path(__file__).resolve().parents[1]))
    except Exception:
        return str(path)
