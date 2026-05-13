from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile


def file_read_json(path: str, runtime_root: str = "runtime_data") -> dict:
    target = _resolve_runtime_path(path, runtime_root)
    data = json.loads(target.read_text(encoding="utf-8"))
    return {"ok": True, "path": str(target), "data": data}


def file_write_json(path: str, data: object, runtime_root: str = "runtime_data") -> dict:
    target = _resolve_runtime_path(path, runtime_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
    return {"ok": True, "path": str(target)}


def file_list(path: str = "", runtime_root: str = "runtime_data") -> dict:
    target = _resolve_runtime_path(path or ".", runtime_root)
    if target.is_file():
        entries = [target.name]
    else:
        entries = sorted(entry.name for entry in target.iterdir())
    return {"ok": True, "path": str(target), "entries": entries}


def file_exists(path: str, runtime_root: str = "runtime_data") -> dict:
    target = _resolve_runtime_path(path, runtime_root)
    return {"ok": True, "path": str(target), "exists": target.exists()}


def _resolve_runtime_path(path: str, runtime_root: str) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string.")
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Path is outside runtime_data.")
    root = Path(runtime_root).resolve()
    target = (root / candidate).resolve()
    target.relative_to(root)
    return target
