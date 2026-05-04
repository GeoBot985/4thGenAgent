from __future__ import annotations

import json
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.event_store import intake_and_run_event
from runtime.taskframe_reload import load_taskframe


def build_event_demo_summary(result: dict, event_data: dict, frame: object | None = None) -> str:
    lines: list[str] = ["EVENT WORKFLOW DEMO", ""]
    lines.append(f"Status: {result.get('status', '')}")
    lines.append("")
    lines.append("Event:")
    lines.append(f"  event_id: {event_data.get('event_id', '')}")
    lines.append(f"  source: {event_data.get('source', '')}")
    lines.append(f"  event_type: {event_data.get('event_type', '')}")
    lines.append("")
    lines.append("Route:")
    lines.append(f"  route_id: {result.get('route_id', '')}")
    lines.append(f"  manifest_id: {result.get('manifest_id', '')}")
    lines.append("")
    lines.append("TaskFrame:")
    lines.append(f"  frame_id: {result.get('frame_id', '')}")
    lines.append(f"  state: {result.get('status', '')}")
    lines.append("")
    outputs = result.get("outputs", {}) or {}
    lines.append("Outputs:")
    lines.append(f"  order_id: {outputs.get('order_id', '')}")
    order = outputs.get("order", {}) or {}
    lines.append(f"  order_status: {order.get('status', '')}")
    draft = outputs.get("draft_reply", {}) or {}
    lines.append(f"  draft_reply: {draft.get('body', '')}")
    lines.append("")
    lines.append("Pending Actions:")
    pending_actions = []
    if frame is not None:
        pending_actions = getattr(frame, "pending_actions", [])
    for action in pending_actions:
        lines.append(f"  - action_type: {action.get('action_type', '')}")
        lines.append(f"    status: {action.get('status', '')}")
        lines.append(f"    customer_id: {action.get('customer_id', '')}")
        lines.append(f"    channel: {action.get('channel', '')}")
    lines.append("")
    lines.append(f"Result: {'PASS' if result.get('status') == 'WAITING_FOR_EXECUTE' else 'FAIL'}")
    if result.get("status") != "WAITING_FOR_EXECUTE" and result.get("errors"):
        lines.append("Errors:")
        for error in result.get("errors", []):
            lines.append(f"  - {error}")
    return "\n".join(lines)


def main() -> int:
    demo_path = ROOT / "demo" / "customer_message_event.json"
    event_data = json.loads(demo_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as runtime_dir:
        runtime_path = Path(runtime_dir)
        result = intake_and_run_event(event_data, runtime_data_dir=runtime_path, manifest_dir="manifests")
        frame = None
        frame_id = result.get("frame_id")
        if frame_id:
            try:
                frame = load_taskframe(frame_id, runtime_path)
            except Exception:
                frame = None

        summary = build_event_demo_summary(result, event_data, frame)
        print(summary)
        return 0 if result.get("status") == "WAITING_FOR_EXECUTE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
