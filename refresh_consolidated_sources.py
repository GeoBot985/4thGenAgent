from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT_PREFIX = "consolidated_sources"
LINES_PER_FILE = 7500

JSON_ALLOWLIST = {
    Path("config/event_routes.json"),
    Path("config/manifests/customer_message_status_check.json"),
    Path("config/manifests/event_mock_ping.json"),
    Path("runtime_data/events/event_index.json"),
    Path("runtime_data/business/customers.json"),
    Path("runtime_data/business/orders.json"),
    Path("runtime_data/business/order_items.json"),
    Path("runtime_data/business/payments.json"),
    Path("runtime_data/business/shipments.json"),
    Path("runtime_data/business/inventory.json"),
    Path("runtime_data/business/suppliers.json"),
    Path("runtime_data/business/purchase_orders.json"),
}


def collect_sources() -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for path in sorted(ROOT.rglob("*.py")):
        if "__pycache__" in path.parts or "bits" in path.parts or path.name.startswith("."):
            continue
        items.append((relative_display(path), path.read_text(encoding="utf-8")))
    for rel in sorted(JSON_ALLOWLIST):
        path = ROOT / rel
        if path.is_file():
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


def main() -> int:
    items = collect_sources()
    lines = render_blocks(items)
    outputs = write_split_files(lines)
    total_lines = len(lines)
    print(f"wrote {len(outputs)} files from {len(items)} sources")
    print(f"total lines: {total_lines}")
    for path in outputs:
        print(path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
