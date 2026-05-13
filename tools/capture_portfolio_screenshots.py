from __future__ import annotations

from pathlib import Path


def main() -> int:
    print("Capture the following portfolio screenshots from the real app:")
    print("1. 01_operator_home.png")
    print("2. 02_demo_customer_happy_path.png")
    print("3. 03_demo_customer_pending_approval.png")
    print("4. 04_run_report_step_outcomes.png")
    print("5. 05_demo_customer_failed_validation.png")
    print("6. 06_report_generation_demo.png")
    print("7. 07_business_report_visible_path.png")
    print("8. 08_tool_status_panel.png")
    print("9. 09_release_verification.png")
    print()
    print("Suggested output folder:")
    print(str(Path("docs") / "screenshots"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
