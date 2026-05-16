from __future__ import annotations

GOOGLE_WORKSPACE_TOOLPACK_ID = "google_workspace"
GOOGLE_WORKSPACE_NAME = "Google Workspace Read-Only Tool Pack"
GOOGLE_WORKSPACE_VERSION = "1.0.0"
GOOGLE_WORKSPACE_RISK_CLASS = "external_auth_read_only"
GOOGLE_WORKSPACE_SERVICE_NAMES = ("gmail", "calendar", "sheets")
GOOGLE_AUTH_STATUS_TYPE = "google_auth_status"
GMAIL_MESSAGE_METADATA_LIST_TYPE = "gmail_message_metadata_list"
GMAIL_MESSAGE_METADATA_TYPE = "gmail_message_metadata"
CALENDAR_ENTRY_LIST_TYPE = "calendar_entry_list"
SHEETS_RANGE_VALUES_TYPE = "sheets_range_values"

DEFAULT_TOOL_RESULT_ERROR = ""
DEFAULT_LIVE_GUARDRAIL = "read_only_google_workspace"

REDACT_KEYS = {
    "token",
    "password",
    "secret",
    "authorization",
    "api_key",
    "credential",
    "credentials",
    "cookie",
}
