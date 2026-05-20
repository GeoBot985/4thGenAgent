from __future__ import annotations

import json
from pathlib import Path

from runtime.recovery import generate_recovery_report
from runtime.persistence import save_taskframe

from tests.recovery_test_utils import seed_recovery_runtime, write_recovery_manifest


def test_recovery_report_writes_json_and_markdown(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    manifest_dir = tmp_path / "manifests"
    manifest_path = write_recovery_manifest(manifest_dir)
    frame = seed_recovery_runtime(runtime_root, manifest_path)
    frame.state = "FAILED_EXECUTION"
    frame.steps[0].status = "FAILED"
    frame.steps[0].last_error = "temporary failure"
    frame.pending_actions.append(
        {
            "action_id": "action_1",
            "step_id": frame.steps[0].step_id,
            "tool": "g/check",
            "namespace": "g",
            "action": "check",
            "action_type": "read_mail",
            "output_alias": "unread_mail",
            "business_ref": "mailbox",
            "status": "APPROVED",
            "side_effect_performed": False,
            "idempotency_key": f"{frame.manifest_id}:{frame.frame_id}:{frame.steps[0].step_id}:read_mail:mailbox",
        }
    )
    save_taskframe(frame, runtime_root)

    report = generate_recovery_report(frame, runtime_data_dir=runtime_root, manifest_dir=manifest_dir)

    json_path = Path(report["json_path"])
    md_path = Path(report["markdown_path"])
    assert json_path.is_file()
    assert md_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["assessment"]["side_effect_risk"] == "staged"
    assert payload["assessment"]["idempotency_keys"]
    markdown = md_path.read_text(encoding="utf-8")
    assert "Recovery Assessment" in markdown
    assert "Side-effect Risk" in markdown
