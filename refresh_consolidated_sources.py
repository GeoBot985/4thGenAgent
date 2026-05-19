from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT_PREFIX = "consolidated_sources"
LINES_PER_FILE = 7500

SUMMARY_OUTPUT = "consolidated_validation_testing_summary.txt"


def collect_sources() -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for path in sorted(ROOT.rglob("*.py")):
        if not _include_py_source(path):
            continue
        items.append((relative_display(path), path.read_text(encoding="utf-8")))
    return items


def relative_display(path: Path) -> str:
    return path.relative_to(ROOT).as_posix().replace("/", "\\")


def render_blocks(items: list[tuple[str, str]]) -> list[str]:
    lines: list[str] = []
    for rel_path, content in items:
        lines.append(f"### {rel_path}")
        lines.append("")
        lines.extend(content.splitlines())
        lines.append("")
        lines.append("")
    return lines


def write_split_files(lines: list[str]) -> list[Path]:
    existing = sorted(ROOT.glob(f"{OUTPUT_PREFIX}_part_*.txt"))
    for path in existing:
        path.unlink()

    outputs: list[Path] = []
    for index, start in enumerate(range(0, len(lines), LINES_PER_FILE), start=1):
        chunk = lines[start : start + LINES_PER_FILE]
        output = ROOT / f"{OUTPUT_PREFIX}_part_{index:02d}.txt"
        output.write_text("\n".join(chunk).rstrip() + "\n", encoding="utf-8")
        outputs.append(output)
    return outputs


def build_validation_testing_summary() -> str:
    lines = [
        "# Validation and Testing Coverage Summary",
        "",
        "## What this repository validates",
        "",
        "- Manifest parsing, normalization, and strict contract checks",
        "- Manifest health checks and regression gallery coverage",
        "- Event route alignment and source contracts",
        "- Tool result contracts and evidence enforcement",
        "- Tool governance, lifecycle, and health gates",
        "- Readiness scorecard generation and release gating",
        "- Cross-workflow story pack generation",
        "- Supplier invoice matching workflow validation",
        "- Portfolio evidence pack generation",
        "",
        "## Test surfaces present",
        "",
        "- Unit tests for runtime helpers, CLI commands, UI hooks, and report builders",
        "- Scenario tests for customer, procurement, accounting, order management, and supplier invoice flows",
        "- Manifest strict-contract tests and regression gallery tests",
        "- Toolpack contract, governance, lifecycle, and health tests",
        "- Release-verifier checks that exercise the clean-clone path",
        "",
        "## JSON shapes that explain the app",
        "",
        "### ToolResult",
        "```json",
        "{",
        '  "ok": true,',
        '  "type": "string",',
        '  "data": {},',
        '  "evidence": {',
        '    "tool": "namespace/action",',
        '    "mode": "dry_run|live|local_static_check",',
        '    "source": "builtin|migrated_toolpack|external_toolpack",',
        '    "operation": "read|prepare|side_effect|health|validation",',
        '    "input_refs": [],',
        '    "output_ref": ""',
        "  },",
        '  "error": "",',
        '  "metadata": {}',
        "}",
        "```",
        "",
        "### Strict Manifest Contract",
        "```json",
        "{",
        '  "manifest_id": "string",',
        '  "name": "string",',
        '  "version": "string",',
        '  "trigger": {},',
        '  "inputs": {"required": [], "optional": []},',
        '  "steps": [],',
        '  "validations": [],',
        '  "completion": {},',
        '  "side_effect_policy": {}',
        "}",
        "```",
        "",
        "### Readiness Scorecard",
        "```json",
        "{",
        '  "ok": true,',
        '  "status": "PASS",',
        '  "threshold": 90,',
        '  "overall_score": 100.0,',
        '  "areas": {',
        '    "tooling": {',
        '      "area_id": "tooling",',
        '      "label": "Tooling",',
        '      "score": 100.0,',
        '      "status": "PASS"',
        "    }",
        "  }",
        "}",
        "```",
        "",
        "### Story Pack Summary",
        "```json",
        "{",
        '  "pack_id": "cross_workflow_business_demo_v2",',
        '  "pack_run_id": "string",',
        '  "ok": true,',
        '  "dry_run_only": true,',
        '  "live_side_effects_performed": false,',
        '  "workflow_results": []',
        "}",
        "```",
        "",
        "### Portfolio Evidence Pack Summary",
        "```json",
        "{",
        '  "pack_id": "portfolio_evidence_pack_v1",',
        '  "pack_run_id": "string",',
        '  "project_name": "TaskFrame Runtime",',
        '  "project_type": "controlled_business_automation_runtime",',
        '  "live_side_effects_claimed": false,',
        '  "production_readiness_claimed": false,',
        '  "included_story_pack": true,',
        '  "included_readiness_scorecard": true',
        "}",
        "```",
        "",
        "## Validation and testing code locations",
        "",
        "- `tests/test_manifest_contract_strict.py`",
        "- `tests/test_manifest_regression_gallery_*.py`",
        "- `tests/test_toolpack_contract_runner.py`",
        "- `tests/test_toolpack_lifecycle.py`",
        "- `tests/test_readiness_scorecard.py`",
        "- `tests/test_cross_workflow_demo_story_v2.py`",
        "- `tests/test_supplier_invoice_*.py`",
        "- `tests/test_portfolio_evidence_pack.py`",
        "- `tools/run_release_candidate_verification.py`",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    items = collect_sources()
    lines = render_blocks(items)
    outputs = write_split_files(lines)
    summary_path = ROOT / SUMMARY_OUTPUT
    summary_path.write_text(build_validation_testing_summary(), encoding="utf-8")
    total_lines = len(lines)
    print(f"wrote {len(outputs)} files from {len(items)} sources")
    print(f"total lines: {total_lines}")
    print(summary_path.name)
    for path in outputs:
        print(path.name)
    return 0


def _include_py_source(path: Path) -> bool:
    if "__pycache__" in path.parts:
        return False
    if any(part.startswith(".") for part in path.parts):
        return False
    if "tests" in path.parts:
        return False
    if path.name.startswith("test_") or path.name.endswith("_test.py"):
        return False
    if "worktrees" in path.parts:
        return False
    if "bits" in path.parts:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
