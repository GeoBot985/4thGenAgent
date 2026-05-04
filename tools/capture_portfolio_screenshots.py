from __future__ import annotations

from pathlib import Path


def main() -> int:
    print("Capture the following portfolio screenshots from the real app:")
    print("1. operator_ui_main.png")
    print("2. customer_workflow_completed.png")
    print("3. procurement_workflow_completed.png")
    print("4. accounting_workflow_completed.png")
    print("5. pending_approval_view.png")
    print("6. report_example.png")
    print("7. cross_workflow_demo_completed.png")
    print("8. architecture_diagram.png")
    print()
    print("Suggested output folder:")
    print(str(Path("docs") / "screenshots"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
