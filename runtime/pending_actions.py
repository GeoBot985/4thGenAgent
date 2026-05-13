from __future__ import annotations


from .errors import PendingActionError
from .models import PENDING_ACTION_STATUSES, TaskFrame
from .taskframe import utc_now


def get_pending_action(frame: TaskFrame, action_id: str) -> dict:
    for action in frame.pending_actions:
        if action.get("action_id") == action_id:
            return action
    raise PendingActionError(f"Pending action not found: {action_id}")


def list_pending_actions(frame: TaskFrame, status: str | None = None) -> list[dict]:
    if status is None:
        return list(frame.pending_actions)
    return [action for action in frame.pending_actions if action.get("status") == status]


def transition_pending_action(
    action: dict,
    new_status: str,
) -> None:
    if new_status not in PENDING_ACTION_STATUSES:
        raise PendingActionError(f"Unknown pending action status: {new_status}")
    current_status = action.get("status")
    if current_status not in PENDING_ACTION_STATUSES:
        raise PendingActionError(f"Unknown pending action current status: {current_status}")
    if new_status not in PENDING_ACTION_TRANSITIONS.get(current_status, set()):
        raise PendingActionError(f"Invalid pending action transition: {current_status} -> {new_status}")
    action["status"] = new_status


def mark_pending_action_approved(
    frame: TaskFrame,
    action_id: str,
    approved_by: str,
    reason: str = "",
) -> dict:
    action = get_pending_action(frame, action_id)
    transition_pending_action(action, "APPROVED")
    action["approved_by"] = approved_by
    action["approved_at"] = utc_now()
    action["approval_reason"] = reason
    return action


def mark_pending_action_rejected(
    frame: TaskFrame,
    action_id: str,
    rejected_by: str,
    reason: str = "",
) -> dict:
    action = get_pending_action(frame, action_id)
    transition_pending_action(action, "REJECTED")
    action["rejected_by"] = rejected_by
    action["rejected_at"] = utc_now()
    action["rejection_reason"] = reason
    return action


PENDING_ACTION_TRANSITIONS = {
    "PENDING_APPROVAL": {"APPROVED", "REJECTED", "FAILED"},
    "APPROVED": {"EXECUTING", "FAILED"},
    "REJECTED": set(),
    "EXECUTING": {"EXECUTED", "FAILED"},
    "EXECUTED": set(),
    "FAILED": set(),
}

