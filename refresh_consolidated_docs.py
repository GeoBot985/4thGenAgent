from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
DOCS_DIR = ROOT / "docs"
OUTPUT_PATH = DOCS_DIR / "consolidated_docs_for_llm.md"

TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".mmd",
    ".svg",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".py",
}

SKIP_NAMES = {OUTPUT_PATH.name}

def main() -> int:
    files = collect_docs_files()
    text_files = [path for path in files if is_text_file(path)]
    binary_files = [path for path in files if not is_text_file(path)]

    lines: list[str] = []
    lines.extend(
        [
            "# Consolidated Docs Bundle",
            "",
            "This file inlines the text-based files under `docs/` and lists binary assets separately.",
            "It is intended to be shared with an LLM as a single reference document.",
            "",
            "## Inventory",
            "",
            f"- Text files included: {len(text_files)}",
            f"- Binary assets listed: {len(binary_files)}",
            f"- Source directory: `{DOCS_DIR.as_posix()}`",
            "",
            "## Text Files",
            "",
        ]
    )

    for path in text_files:
        rel = path.relative_to(ROOT).as_posix()
        lines.append(f"### {rel}")
        lines.append("")
        lines.extend(path.read_text(encoding="utf-8").rstrip().splitlines())
        lines.append("")
        lines.append("")

    lines.extend(
        [
            "## Binary Assets",
            "",
            "The following files are present in `docs/` but are binary or image assets, so their raw bytes are not inlined here.",
            "",
            "| File | Size (bytes) |",
            "|---|---:|",
        ]
    )
    for path in binary_files:
        rel = path.relative_to(ROOT).as_posix()
        lines.append(f"| `{rel}` | {path.stat().st_size} |")

    OUTPUT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"text files: {len(text_files)}")
    print(f"binary assets: {len(binary_files)}")
    return 0


def collect_docs_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(DOCS_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.name in SKIP_NAMES:
            continue
        files.append(path)
    return files


def is_text_file(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return True
    try:
        sample = path.read_bytes()[:1024]
    except Exception:
        return False
    return b"\x00" not in sample


if __name__ == "__main__":
    raise SystemExit(main())
