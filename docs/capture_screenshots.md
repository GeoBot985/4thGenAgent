# Capture Screenshots

These portfolio screenshots are captured from the live operator console and the generated release/report artifacts.

## Start The Console

```powershell
python -m src.operator_ui
```

## Generate The Demo Artifacts First

```powershell
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

## Current Screenshot Set

The current portfolio set is:

- `docs/screenshots/01_operator_home.png`
- `docs/screenshots/02_demo_customer_happy_path.png`
- `docs/screenshots/03_demo_customer_pending_approval.png`
- `docs/screenshots/04_run_report_step_outcomes.png`
- `docs/screenshots/05_demo_customer_failed_validation.png`
- `docs/screenshots/06_report_generation_demo.png`
- `docs/screenshots/07_business_report_visible_path.png`
- `docs/screenshots/08_tool_status_panel.png`
- `docs/screenshots/09_release_verification.png`

## Capture Notes

- Capture the operator UI after the clean demo and tool health state is loaded.
- Use the default portfolio workflows only.
- Show the business-readable Demo View for the customer and report-generation scenarios.
- Include the run report step-outcome view for the audit artifact.
- Do not include ABSA, Google Messages, or any personal/private RPA workflow in the main demo path.
- For report and verification screenshots, capture the generated markdown or artifact viewer output, not live external systems.
