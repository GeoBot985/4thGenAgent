from __future__ import annotations

from dataclasses import replace

from .tool_capabilities import ToolCapability


_CAPABILITIES: tuple[ToolCapability, ...] = (
    ToolCapability(
        tool_id="business_context",
        display_name="Business Context",
        category="business_context",
        description="Loads demo business context from the local runtime_data/business fixtures.",
        core_or_optional="core",
        side_effect_level="read_only",
        auth_required=False,
        auth_type=None,
        setup_available=True,
        setup_action="Seed or validate the demo business dataset.",
        rpa_live_probe_required=False,
        limitations=["Uses local demo business fixtures only."],
    ),
    ToolCapability(
        tool_id="business_database",
        display_name="Demo Business Database",
        category="database",
        description="Reads the local demo business data store used by the portfolio workflows.",
        core_or_optional="core",
        side_effect_level="read_only",
        auth_required=False,
        auth_type=None,
        setup_available=True,
        setup_action="Create or seed the local demo business dataset.",
        rpa_live_probe_required=False,
        limitations=["Backed by JSON fixtures instead of a live database server."],
    ),
    ToolCapability(
        tool_id="gmail",
        display_name="Gmail",
        category="gmail",
        description="Read-only Gmail adapter for operator checks and message retrieval.",
        core_or_optional="optional",
        side_effect_level="read_only",
        auth_required=True,
        auth_type="google_oauth",
        setup_available=True,
        setup_action="Add Google OAuth credentials and token files.",
        rpa_live_probe_required=False,
        limitations=["Requires Google account authorization for live access."],
    ),
    ToolCapability(
        tool_id="google_sheets",
        display_name="Google Sheets",
        category="google_sheets",
        description="Read-only Sheets checks plus approval-gated write preparation.",
        core_or_optional="optional",
        side_effect_level="prepare_only",
        auth_required=True,
        auth_type="google_oauth",
        setup_available=True,
        setup_action="Add Google OAuth credentials and select a spreadsheet ID.",
        rpa_live_probe_required=False,
        limitations=["Live reads depend on credentials and a configured spreadsheet ID."],
    ),
    ToolCapability(
        tool_id="google_calendar",
        display_name="Google Calendar",
        category="google_calendar",
        description="Read-only calendar visibility and next-event checks.",
        core_or_optional="optional",
        side_effect_level="read_only",
        auth_required=True,
        auth_type="google_oauth",
        setup_available=True,
        setup_action="Add Google OAuth credentials and authorize Calendar access.",
        rpa_live_probe_required=False,
        limitations=["Live reads depend on calendar authorization."],
    ),
    ToolCapability(
        tool_id="llm_ollama",
        display_name="Ollama LLM",
        category="llm",
        description="Bounded local LLM adapter used for drafting and extraction when configured.",
        core_or_optional="optional",
        side_effect_level="read_only",
        auth_required=False,
        auth_type=None,
        setup_available=True,
        setup_action="Start Ollama locally or use the fake provider for clean-clone demos.",
        rpa_live_probe_required=False,
        limitations=["Availability depends on a local Ollama endpoint or a mocked provider."],
    ),
    ToolCapability(
        tool_id="memory_store",
        display_name="Memory Store",
        category="memory",
        description="Local persistent memory store used by manifest validations and operator flows.",
        core_or_optional="core",
        side_effect_level="read_only",
        auth_required=False,
        auth_type=None,
        setup_available=True,
        setup_action="Create the local memory store file if missing.",
        rpa_live_probe_required=False,
        limitations=["Only local runtime persistence is used."],
    ),
    ToolCapability(
        tool_id="report_generator",
        display_name="Report Generator",
        category="reporting",
        description="Generates local TaskFrame and operator demo reports.",
        core_or_optional="core",
        side_effect_level="read_only",
        auth_required=False,
        auth_type=None,
        setup_available=True,
        setup_action="Create the local report output directories.",
        rpa_live_probe_required=False,
        limitations=["Generates local artifacts only."],
    ),
    ToolCapability(
        tool_id="rpa_google_messages",
        display_name="Google Messages RPA",
        category="rpa",
        description="Optional browser-backed Google Messages probe for personal automation experiments.",
        core_or_optional="optional",
        side_effect_level="high_risk",
        auth_required=True,
        auth_type="browser_profile",
        setup_available=True,
        setup_action="Install Playwright, pair Google Messages manually, and provide a browser profile.",
        rpa_live_probe_required=True,
        excluded_from_default_release=True,
        limitations=[
            "Requires local browser state and authenticated Google Messages pairing.",
            "Excluded from clean-clone release verification.",
        ],
    ),
)

_CAPABILITY_BY_ID = {item.tool_id: item for item in _CAPABILITIES}


def list_tool_capabilities() -> list[ToolCapability]:
    return [replace(item) for item in _CAPABILITIES]


def get_tool_capability(tool_id: str) -> ToolCapability:
    try:
        return replace(_CAPABILITY_BY_ID[tool_id])
    except KeyError as exc:
        raise KeyError(f"Unknown tool capability: {tool_id}") from exc
