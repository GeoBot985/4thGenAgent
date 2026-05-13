from __future__ import annotations



def build_failure_summary(frame: dict) -> dict:
    if not isinstance(frame, dict):
        frame = {}
    errors = _as_list(frame.get("errors"))
    validations = _as_list(frame.get("validations"))
    state = str(frame.get("state", "") or "")
    if not state.startswith("FAILED"):
        return {
            "ok": True,
            "frame_id": frame.get("frame_id", ""),
            "manifest_id": frame.get("manifest_id", ""),
            "state": state,
            "failed_step_id": "",
            "failure_type": "",
            "failure_message": "",
            "blocking_errors": [],
            "failed_validations": [],
            "pending_action_count": len(_as_list(frame.get("pending_actions"))),
            "executed_action_count": len(_as_list(frame.get("executed_actions"))),
            "safe_to_retry": True,
            "operator_explanation": "",
        }
    failed_validations = [item for item in validations if isinstance(item, dict) and item.get("ok") is False]
    if not failed_validations:
        failed_validations = [
            {
                "validation_id": item.get("validation_id", ""),
                "type": item.get("type", ""),
                "ok": False,
                "message": item.get("message", "") or item.get("error", ""),
                "data": item.get("data", {}),
            }
            for item in errors
            if isinstance(item, dict) and (item.get("type") or item.get("message") or item.get("data"))
        ]
    failed_step = _find_failed_step(frame)
    failure_message = _failure_message(frame, failed_step, errors, failed_validations)
    return {
        "ok": True,
        "frame_id": frame.get("frame_id", ""),
        "manifest_id": frame.get("manifest_id", ""),
        "state": state,
        "failed_step_id": failed_step,
        "failure_type": _failure_type(frame, failed_step, failed_validations),
        "failure_message": failure_message,
        "blocking_errors": errors,
        "failed_validations": failed_validations,
        "pending_action_count": len(_as_list(frame.get("pending_actions"))),
        "executed_action_count": len(_as_list(frame.get("executed_actions"))),
        "safe_to_retry": state not in {"FAILED_EXECUTION", "FAILED_VALIDATION", "FAILED_COMPLETION"},
        "operator_explanation": _operator_explanation(state, failure_message),
    }


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _find_failed_step(frame: dict) -> str:
    for key in ("steps", "manifest_steps"):
        for step in _as_list(frame.get(key)):
            if isinstance(step, dict) and str(step.get("status", "")).upper().startswith("FAILED"):
                return str(step.get("step_id") or step.get("id") or "")
    return str(frame.get("current_step_id", "") or "")


def _failure_type(frame: dict, failed_step: str, failed_validations: list[dict]) -> str:
    if _as_list(frame.get("errors")):
        return "validation_failed" if frame.get("state") == "FAILED_VALIDATION" else "execution_failed"
    if failed_validations:
        return "validation_failed"
    return "failed"


def _failure_message(frame: dict, failed_step: str, errors: list[dict], failed_validations: list[dict]) -> str:
    if errors:
        for error in errors:
            if isinstance(error, dict) and error.get("message"):
                return str(error.get("message"))
            if isinstance(error, dict) and error.get("data"):
                return str(error.get("data"))
    if failed_validations:
        first = failed_validations[0]
        return str(first.get("message") or first.get("validation_id") or "Validation failed.")
    if failed_step:
        return f"Step failed: {failed_step}"
    return ""


def _operator_explanation(state: str, failure_message: str) -> str:
    if not failure_message:
        return ""
    if state == "FAILED_VALIDATION":
        return f"The runtime blocked the reply because {failure_message.lower()}"
    if state == "FAILED_EXECUTION":
        return f"The runtime stopped during execution because {failure_message.lower()}"
    return failure_message
