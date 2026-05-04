from __future__ import annotations

from .errors import PendingActionError
from .models import TaskFrame
from .pending_actions import (
    get_pending_action,
    list_pending_actions,
    mark_pending_action_approved,
    mark_pending_action_rejected,
)
from .taskframe import add_audit_event


def approve_action(
    frame: TaskFrame,
    action_id: str,
    approved_by: str = "system",
    reason: str = "",
) -> TaskFrame:
    action = get_pending_action(frame, action_id)
    if action.get("status") != "PENDING_APPROVAL":
        raise PendingActionError(f"Cannot approve action in status: {action.get('status')}")
    mark_pending_action_approved(frame, action_id, approved_by, reason)
    add_audit_event(
        frame,
        "PENDING_ACTION_APPROVED",
        "Pending action approved.",
        {
            "action_id": action_id,
            "tool": action.get("tool"),
            "output_alias": action.get("output_alias"),
        },
    )
    return frame


def reject_action(
    frame: TaskFrame,
    action_id: str,
    rejected_by: str = "system",
    reason: str = "",
) -> TaskFrame:
    action = get_pending_action(frame, action_id)
    if action.get("status") != "PENDING_APPROVAL":
        raise PendingActionError(f"Cannot reject action in status: {action.get('status')}")
    mark_pending_action_rejected(frame, action_id, rejected_by, reason)
    add_audit_event(
        frame,
        "PENDING_ACTION_REJECTED",
        "Pending action rejected.",
        {
            "action_id": action_id,
            "tool": action.get("tool"),
            "output_alias": action.get("output_alias"),
        },
    )
    return frame


def approve_all_pending_actions(
    frame: TaskFrame,
    approved_by: str = "system",
    reason: str = "",
) -> TaskFrame:
    for action in list_pending_actions(frame, "PENDING_APPROVAL"):
        approve_action(frame, action["action_id"], approved_by=approved_by, reason=reason)
    return frame


def reject_all_pending_actions(
    frame: TaskFrame,
    rejected_by: str = "system",
    reason: str = "",
) -> TaskFrame:
    for action in list_pending_actions(frame, "PENDING_APPROVAL"):
        reject_action(frame, action["action_id"], rejected_by=rejected_by, reason=reason)
    return frame

