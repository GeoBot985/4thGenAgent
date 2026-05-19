from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .tool_result_contract import build_tool_evidence

_TOOL = "invoiceops/read_invoice_file"
_RESULT_TYPE = "invoiceops_raw_invoice_text"
_SUPPORTED_EXTENSIONS = frozenset({".txt", ".pdf"})

DEFAULT_RUNTIME_ROOT = "runtime_data"


def invoiceops_read_invoice_file(path: str, runtime_root: str = DEFAULT_RUNTIME_ROOT) -> dict:
    resolved = _resolve_path(path, runtime_root)
    ext = Path(resolved).suffix.lower()

    if ext not in _SUPPORTED_EXTENSIONS:
        return _error_result("UNSUPPORTED_INVOICE_FILE_TYPE", path)

    if not os.path.isfile(resolved):
        return _error_result("INVOICE_FILE_NOT_FOUND", path)

    if ext == ".txt":
        source_type = "text"
        text, read_error = _read_txt(resolved)
    else:
        source_type = "pdf"
        text, read_error = _read_pdf(resolved)

    if read_error:
        return _error_result(read_error, path)

    if not text or not text.strip():
        return _error_result("INVOICE_TEXT_EMPTY", path)

    evidence = build_tool_evidence(
        tool=_TOOL,
        mode="dry_run",
        source="builtin",
        operation="read",
        input_refs=[f"path={path}"],
        output_ref=_RESULT_TYPE,
    )

    return {
        "ok": True,
        "type": _RESULT_TYPE,
        "data": {
            "source_path": resolved,
            "source_type": source_type,
            "text": text,
            "char_count": len(text),
            "line_count": len(text.splitlines()),
        },
        "evidence": evidence,
        "error": "",
        "metadata": {"fixture_mode": _is_fixture_path(resolved)},
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_path(path: str, runtime_root: str) -> str:
    p = Path(path)
    if p.is_absolute():
        return str(p)
    cwd_candidate = Path(os.getcwd()) / p
    if cwd_candidate.exists():
        return str(cwd_candidate)
    root_candidate = Path(runtime_root) / p
    if root_candidate.exists():
        return str(root_candidate)
    # Return CWD-relative resolution so callers get a stable absolute path in errors.
    return str(cwd_candidate)


def _is_fixture_path(resolved: str) -> bool:
    parts = Path(resolved).parts
    return any(part in {"fixtures", "invoiceops"} for part in parts)


def _read_txt(path: str) -> tuple[str, str]:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read(), ""
    except OSError as exc:
        return "", "INVOICE_FILE_READ_FAILED"


def _read_pdf(path: str) -> tuple[str, str]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "", "INVOICE_FILE_READ_FAILED"

    try:
        doc = fitz.open(path)
        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages), ""
    except Exception:
        return "", "INVOICE_FILE_READ_FAILED"


def _error_result(error_code: str, path: str) -> dict:
    return {
        "ok": False,
        "type": _RESULT_TYPE,
        "data": {},
        "evidence": {},
        "error": error_code,
        "metadata": {},
    }
