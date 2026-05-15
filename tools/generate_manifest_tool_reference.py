"""
Generate docs/manifest_tool_reference.md from the default runtime tool registry.

Run:
    python tools/generate_manifest_tool_reference.py
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runtime.tool_registry import TOOL_REGISTRY

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "manifest_tool_reference.md"

HEADER = """\
# Manifest Tool Reference

> **This file is generated from the runtime tool registry.**
> Do not edit it manually. To update, run:
> ```
> python tools/generate_manifest_tool_reference.py
> ```
> See [manifest_command_reference.md](manifest_command_reference.md) for command syntax.

---

"""

SAFETY_NOTE = (
    "> **Safety note:** This tool stages or performs a side effect "
    "and must be approval-gated before execution."
)


def bool_str(value: bool) -> str:
    return "true" if value else "false"


def build_command_example(tool_key: str, info: dict) -> str:
    req = info.get("required_args", [])
    args = " ".join(f"{a}=$inputs.{a}" for a in req)
    parts = [f"[t:{tool_key} -> output_name]"]
    if args:
        parts.append(args)
    return " ".join(parts)


def render_tool(tool_key: str, info: dict) -> str:
    ns = info.get("namespace", "")
    action = info.get("action", "")
    side_effect = info.get("side_effect", False)
    requires_approval = info.get("requires_approval", False)
    output_type = info.get("output_type", "")
    required_args = info.get("required_args", [])
    optional_args = info.get("optional_args", [])
    arg_types = info.get("arg_types", {})

    lines = [f"## {tool_key}", ""]

    table_rows = [
        ("Namespace", ns),
        ("Action", action),
        ("Side effect", bool_str(side_effect)),
        ("Requires approval", bool_str(requires_approval)),
        ("Output type", f"`{output_type}`" if output_type else "—"),
    ]
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    for field, val in table_rows:
        lines.append(f"| {field} | {val} |")
    lines.append("")

    if side_effect:
        lines.append(SAFETY_NOTE)
        lines.append("")

    lines.append("### Command form")
    lines.append("")
    lines.append("```text")
    lines.append(build_command_example(tool_key, info))
    lines.append("```")
    lines.append("")

    if required_args:
        lines.append("### Required arguments")
        lines.append("")
        for arg in required_args:
            type_hint = arg_types.get(arg, "str")
            lines.append(f"- `{arg}` ({type_hint})")
        lines.append("")

    if optional_args:
        lines.append("### Optional arguments")
        lines.append("")
        for arg in optional_args:
            type_hint = arg_types.get(arg, "str")
            lines.append(f"- `{arg}` ({type_hint})")
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def generate() -> str:
    sorted_keys = sorted(
        TOOL_REGISTRY.keys(),
        key=lambda k: (TOOL_REGISTRY[k].get("namespace", ""), TOOL_REGISTRY[k].get("action", ""), k),
    )

    sections = [HEADER]
    for key in sorted_keys:
        sections.append(render_tool(key, TOOL_REGISTRY[key]))

    return "".join(sections)


def main() -> None:
    content = generate()
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Written: {OUTPUT_PATH}")
    print(f"Tools documented: {len(TOOL_REGISTRY)}")


if __name__ == "__main__":
    main()
