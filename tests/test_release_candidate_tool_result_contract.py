from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

import tools.run_release_candidate_verification as verifier

pytestmark = pytest.mark.release


def _run_check(active_override: bool) -> dict:
    script = textwrap.dedent(
        f"""
        import json
        from types import SimpleNamespace
        import tools.run_release_candidate_verification as verifier
        import runtime.manifest_loader as manifest_loader
        import runtime.taskframe as taskframe_module
        import runtime.tool_registry as tool_registry_module
        import runtime.tool_runner as tool_runner_module
        import src.toolpack_contract_runner as contract_runner_module
        import src.toolpack_loader as toolpack_loader_module

        class FakeToolRunner:
            def __init__(self, dry_run=True):
                self.dry_run = dry_run

            def run_step(self, frame, step):
                tool_call = {{
                    "tool": "g/check" if step.kind != "pending" else "wa/send",
                    "evidence_ref": "evidence_ref_1" if step.kind != "pending" else "evidence_ref_2",
                    "mode": "dry_run",
                    "source": "builtin",
                }}
                frame.tool_calls.append(tool_call)
                if step.kind == "pending":
                    frame.pending_actions.append(
                        {{
                            "action_id": "pa_1",
                            "tool": "wa/send",
                            "status": "PENDING_APPROVAL",
                            "output_alias": "sent_msg",
                        }}
                    )
                return SimpleNamespace(ok=True, evidence={{"tool": tool_call["tool"], "mode": "dry_run", "source": "builtin", "operation": "read", "input_refs": [], "output_ref": tool_call["evidence_ref"]}})

            def execute_pending_action(self, frame, pending_action):
                frame.tool_calls.append(
                    {{
                        "tool": pending_action.get("tool", ""),
                        "evidence_ref": "evidence_ref_3",
                        "mode": "dry_run",
                        "source": "builtin",
                    }}
                )
                return SimpleNamespace(ok=True, evidence={{"tool": "wa/send", "mode": "dry_run", "source": "builtin", "operation": "prepare", "input_refs": [], "output_ref": "evidence_ref_3"}})

        def fake_validate(result, expected_type, **kwargs):
            errors = []
            if not isinstance(result, dict):
                errors.append("Result must be a dict.")
            else:
                if not isinstance(result.get("ok"), bool):
                    errors.append("ok must be a bool.")
                if expected_type and str(result.get("type", "")) != expected_type:
                    errors.append("type mismatch")
                evidence = result.get("evidence")
                if not isinstance(evidence, dict):
                    errors.append("evidence must be a dict.")
                elif not evidence and not kwargs.get("allow_empty_evidence", False):
                    errors.append("evidence must not be empty.")
                if result.get("ok") is False and not str(result.get("error", "")).strip():
                    errors.append("error must be populated when ok is false.")
                if result.get("ok") is True and str(result.get("error", "")).strip():
                    errors.append("error must be empty when ok is true.")
            return {{"ok": not errors, "errors": errors}}

        contract_runner_module.run_toolpack_contract_tests = lambda *args, **kwargs: {{"ok": True, "errors": []}}
        contract_runner_module.validate_tool_result_shape = fake_validate
        tool_registry_module.build_tool_registry = lambda include_external=True: {{"g/check": {{"output_type": "gmail_check_result"}}, "wa/send": {{"output_type": "whatsapp_send_result"}}}}
        toolpack_loader_module.discover_toolpacks = lambda *, include_disabled=False: {{"toolpacks": [{{"toolpack_id": "release_pack" if {str(active_override)} else "demo_echo", "enabled": True, "allow_empty_evidence_for_contract_test": {str(active_override)}}}]}}
        manifest_loader.load_manifest = lambda path: SimpleNamespace(manifest_id=path, steps=[SimpleNamespace(kind="pending" if "whatsapp" in path else "tool", step_id="step_1", command="[t:g/check -> out]")])
        taskframe_module.create_taskframe = lambda manifest: SimpleNamespace(manifest_id=manifest.manifest_id, steps=list(manifest.steps), tool_calls=[], pending_actions=[], state="CREATED", outputs={{}})
        tool_runner_module.ToolRunner = FakeToolRunner
        print(json.dumps(verifier._check_tool_result_contract()))
        """
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_release_verifier_checks_tool_result_contract() -> None:
    result = _run_check(active_override=False)
    assert result["name"] == "tool_result_contract"
    assert result["status"] == "PASS"


def test_release_verifier_blocks_empty_evidence_override_in_release_pack() -> None:
    result = _run_check(active_override=True)
    assert result["name"] == "tool_result_contract"
    assert result["status"] == "FAIL"
    assert result["active_override_packs"] == ["release_pack"]
