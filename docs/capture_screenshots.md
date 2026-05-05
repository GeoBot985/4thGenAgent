# Capture Screenshots

These portfolio screenshots are captured from the live operator console and the generated release/report artifacts.

## Start the console
```powershell
python -m src.operator_ui
```

## Generate the demo artifacts first
```powershell
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

## Screenshot targets
- `docs/screenshots/01_operator_home.png`
- `docs/screenshots/02_scenario_pack.png`
- `docs/screenshots/03_taskframe_detail.png`
- `docs/screenshots/04_step_playback.png`
- `docs/screenshots/05_pending_approval.png`
- `docs/screenshots/06_tool_status_panel.png`
- `docs/screenshots/07_tool_health_details.png`
- `docs/screenshots/08_report_output.png`
- `docs/screenshots/09_release_verification.png`

## Capture notes
- Capture the operator UI after the clean demo and tool health state is loaded.
- Use the default portfolio workflows only.
- Do not include ABSA, Google Messages, or any personal/private RPA workflow in the main demo path.
- For report and verification screenshots, capture the generated markdown or artifact viewer output, not live external systems.
