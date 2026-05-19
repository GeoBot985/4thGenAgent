from __future__ import annotations

import ast

from .errors import CommandParseError
from .models import ParsedCommand


_KIND_ALIASES = {
    "t": "tool",
    "tool": "tool",
    "pending": "pending",
    "m": "memory",
    "memory": "memory",
    "q": "llm",
    "llm": "llm",
    "a": "approval",
    "approval": "approval",
    "i": "inspection",
    "inspection": "inspection",
    "c": "cleanup",
    "cleanup": "cleanup",
    "mt": "maintenance",
    "maintenance": "maintenance",
    "validate": "validate",
}

_LLM_ACTIONS = {"summarize", "extract", "classify", "draft", "compare", "extract_order_ref", "classify_customer_message", "summarize_customer_message", "summarize_business_context", "draft_customer_status_reply", "compare_reply_to_facts", "draft_supplier_reorder_message", "draft_reconciliation_exception_summary", "draft_supplier_invoice_exception_summary"}
_APPROVAL_ACTIONS = {"list_pending", "approve", "reject", "execute_approved", "execute_live_approved", "approve_and_execute"}
_APPROVAL_BLOCKED_ACTIONS = {"live_execute", "force_execute", "delete", "mutate", "resume_all", "approve_all", "reject_all"}
_INSPECTION_ACTIONS = {
    "list_runs",
    "summary",
    "taskframe",
    "outputs",
    "audit",
    "validations",
    "errors",
    "pending_actions",
    "executed_actions",
    "attempts",
    "tool_calls",
    "llm_calls",
    "cleanup_reports",
}
_INSPECTION_BLOCKED_ACTIONS = {"delete", "resume", "rerun", "approve", "execute"}
_CLEANUP_ACTIONS = {"plan", "execute", "reports_plan", "index_plan", "temp_plan"}
_CLEANUP_BLOCKED_ACTIONS = {"delete_all", "delete_runs", "purge", "wipe", "force"}
_MAINTENANCE_ACTIONS = {"index_rebuild", "cleanup_dry_run", "report_failed_runs", "report_pending_runs", "report_live_packs", "summary"}
_MAINTENANCE_BLOCKED_ACTIONS = {"delete", "execute", "approve", "live"}


def parse_command(command: str) -> ParsedCommand:
    if not isinstance(command, str) or not command.strip():
        raise CommandParseError("Command must be a non-empty string.")

    raw = command.strip()
    if not raw.startswith("["):
        raise CommandParseError("Command must start with '['.")

    closing_index = raw.find("]")
    if closing_index == -1:
        raise CommandParseError("Command must contain a closing ']'.")

    header = raw[1:closing_index].strip()
    payload = raw[closing_index + 1 :].strip()

    if not header:
        raise CommandParseError("Command header cannot be empty.")

    if header == "validate_required_inputs" or header.startswith("validate_required_inputs:"):
        validation_action = "required_inputs"
        if ":" in header:
            validation_action = header.split(":", 1)[1].strip() or validation_action
        if payload:
            raise CommandParseError("Validation commands do not accept payloads.")
        return ParsedCommand(
            raw=raw,
            kind="validate_required_inputs",
            namespace=None,
            action=validation_action,
            output_alias=None,
            payload="",
            args={},
        )

    if header.startswith("validate:"):
        validation_id = header[len("validate:") :].strip()
        if not validation_id or any(ch.isspace() for ch in validation_id):
            raise CommandParseError("Validation command must include a validation id.")
        if payload:
            raise CommandParseError("Validation commands do not accept payloads.")
        return ParsedCommand(
            raw=raw,
            kind="validate",
            namespace=None,
            action=validation_id,
            output_alias=None,
            payload="",
            args={},
        )

    if header.startswith("i:"):
        inspection_body = header[len("i:") :].strip()
        if "->" not in inspection_body:
            raise CommandParseError("Inspection commands require an output alias with '->'.")
        inspection_action_raw, inspection_alias_raw = inspection_body.split("->", 1)
        inspection_action = inspection_action_raw.strip()
        inspection_output_alias = inspection_alias_raw.strip()
        if not inspection_action or any(ch.isspace() for ch in inspection_action):
            raise CommandParseError("Inspection command must include an action id.")
        if not inspection_output_alias:
            raise CommandParseError("Output alias cannot be empty.")
        if inspection_action in _INSPECTION_BLOCKED_ACTIONS:
            raise CommandParseError(f"Inspection action not allowed: {inspection_action}")
        if inspection_action not in _INSPECTION_ACTIONS:
            raise CommandParseError(f"Unsupported inspection action: {inspection_action}")

    if header.startswith("a:"):
        approval_body = header[len("a:") :].strip()
        if "->" not in approval_body:
            raise CommandParseError("Approval commands require an output alias with '->'.")
        approval_action_raw, approval_alias_raw = approval_body.split("->", 1)
        approval_action = approval_action_raw.strip()
        approval_output_alias = approval_alias_raw.strip()
        if not approval_action or any(ch.isspace() for ch in approval_action):
            raise CommandParseError("Approval command must include an action id.")
        if not approval_output_alias:
            raise CommandParseError("Output alias cannot be empty.")
        if approval_action in _APPROVAL_BLOCKED_ACTIONS:
            raise CommandParseError(f"Approval action not allowed: {approval_action}")
        if approval_action not in _APPROVAL_ACTIONS:
            raise CommandParseError(f"Unsupported approval action: {approval_action}")

    if ":" not in header:
        raise CommandParseError("Command header must contain a kind separator ':'.")

    kind_token, remainder = header.split(":", 1)
    kind = _normalize_kind(kind_token.strip())
    remainder = remainder.strip()
    if not remainder:
        raise CommandParseError("Command action is missing.")

    if "->" not in remainder:
        raise CommandParseError("Command must include an output alias with '->'.")

    left, right = remainder.split("->", 1)
    output_alias = right.strip()
    if not output_alias:
        raise CommandParseError("Output alias cannot be empty.")

    left = left.strip()
    if not left:
        raise CommandParseError("Command action is missing.")

    namespace: str | None = None
    if "/" in left:
        prefix, action = left.split("/", 1)
        namespace = prefix.strip()
        action = action.strip()
        if not namespace:
            raise CommandParseError("Namespace cannot be empty.")
    else:
        action = left
        if kind == "memory":
            namespace = "m"
        elif kind == "llm":
            namespace = "q"
        elif kind == "approval":
            namespace = "a"
        elif kind == "inspection":
            namespace = "i"
        elif kind == "cleanup":
            namespace = "c"
        elif kind == "maintenance":
            namespace = "mt"

    if not action:
        raise CommandParseError("Action cannot be empty.")
    if kind == "llm":
        if namespace == "":
            raise CommandParseError("Namespace cannot be empty.")
        if namespace != "q":
            raise CommandParseError("LLM commands must use namespace 'q'.")
        if action not in _LLM_ACTIONS:
            raise CommandParseError(f"Unsupported LLM action: {action}")
    if kind == "cleanup":
        if namespace == "":
            raise CommandParseError("Namespace cannot be empty.")
        if namespace != "c":
            raise CommandParseError("Cleanup commands must use namespace 'c'.")
        if action in _CLEANUP_BLOCKED_ACTIONS:
            raise CommandParseError(f"Cleanup action not allowed: {action}")
        if action not in _CLEANUP_ACTIONS:
            raise CommandParseError(f"Unsupported cleanup action: {action}")
    if kind == "maintenance":
        if namespace == "":
            raise CommandParseError("Namespace cannot be empty.")
        if namespace != "mt":
            raise CommandParseError("Maintenance commands must use namespace 'mt'.")
        if action in _MAINTENANCE_BLOCKED_ACTIONS:
            raise CommandParseError(f"Maintenance action not allowed: {action}")
        if action not in _MAINTENANCE_ACTIONS:
            raise CommandParseError(f"Unsupported maintenance action: {action}")
    if kind == "inspection":
        if namespace == "":
            raise CommandParseError("Namespace cannot be empty.")
        if namespace != "i":
            raise CommandParseError("Inspection commands must use namespace 'i'.")
        if action in _INSPECTION_BLOCKED_ACTIONS:
            raise CommandParseError(f"Inspection action not allowed: {action}")
        if action not in _INSPECTION_ACTIONS:
            raise CommandParseError(f"Unsupported inspection action: {action}")
    if kind == "approval":
        if namespace == "":
            raise CommandParseError("Namespace cannot be empty.")
        if namespace != "a":
            raise CommandParseError("Approval commands must use namespace 'a'.")
        if action in _APPROVAL_BLOCKED_ACTIONS:
            raise CommandParseError(f"Approval action not allowed: {action}")
        if action not in _APPROVAL_ACTIONS:
            raise CommandParseError(f"Unsupported approval action: {action}")

    args = _parse_args(payload)
    return ParsedCommand(
        raw=raw,
        kind=kind,
        namespace=namespace,
        action=action,
        output_alias=output_alias,
        payload=payload,
        args=args,
    )


def _normalize_kind(kind_token: str) -> str:
    try:
        return _KIND_ALIASES[kind_token]
    except KeyError as exc:
        raise CommandParseError(f"Unknown command kind: {kind_token}") from exc


def _parse_args(payload: str) -> dict[str, str]:
    if not payload:
        return {}

    segments = _split_unquoted(payload, ";")
    if not segments:
        return {}

    if any(_find_unquoted(segment, "=") is None for segment in segments):
        return {}

    args: dict[str, str] = {}
    for segment in segments:
        key, value = _split_first_unquoted(segment, "=")
        if key is None or value is None:
            return {}
        key = key.strip()
        value = value.strip()
        if not key:
            raise CommandParseError("Argument key cannot be empty.")
        args[key] = _unquote(value)
    return args


def _split_unquoted(text: str, separator: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    escape = False

    for char in text:
        if escape:
            current.append(char)
            escape = False
            continue

        if char == "\\":
            current.append(char)
            escape = True
            continue

        if char == "'" and not in_double:
            in_single = not in_single
            current.append(char)
            continue

        if char == '"' and not in_single:
            in_double = not in_double
            current.append(char)
            continue

        if char == separator and not in_single and not in_double:
            segment = "".join(current).strip()
            if segment:
                parts.append(segment)
            current = []
            continue

        current.append(char)

    segment = "".join(current).strip()
    if segment:
        parts.append(segment)

    return parts


def _find_unquoted(text: str, needle: str) -> int | None:
    in_single = False
    in_double = False
    escape = False

    for index, char in enumerate(text):
        if escape:
            escape = False
            continue

        if char == "\\":
            escape = True
            continue

        if char == "'" and not in_double:
            in_single = not in_single
            continue

        if char == '"' and not in_single:
            in_double = not in_double
            continue

        if char == needle and not in_single and not in_double:
            return index

    return None


def _split_first_unquoted(text: str, needle: str) -> tuple[str | None, str | None]:
    index = _find_unquoted(text, needle)
    if index is None:
        return None, None
    return text[:index], text[index + 1 :]


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        try:
            evaluated = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
        if isinstance(evaluated, str):
            return evaluated
    return value
