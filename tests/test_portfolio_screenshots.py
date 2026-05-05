from pathlib import Path


def test_portfolio_screenshots_exist():
    base = Path("docs/screenshots")
    required = [
        "01_operator_home.png",
        "02_scenario_pack.png",
        "03_taskframe_detail.png",
        "04_step_playback.png",
        "05_pending_approval.png",
        "06_tool_status_panel.png",
        "07_tool_health_details.png",
        "08_report_output.png",
        "09_release_verification.png",
    ]
    for name in required:
        assert (base / name).is_file(), name
