from __future__ import annotations


def register_tools(registry: dict[str, dict]) -> None:
    registry["messages/extract_absa_transactions"] = {
        "namespace": "messages",
        "action": "extract_absa_transactions",
        "module": "optional_tools.rpa.google_messages_absa.messages_tools",
        "function": "messages_extract_absa_transactions",
        "side_effect": False,
        "requires_approval": False,
        "allow_live": True,
        "allow_live_side_effect": False,
        "live_guardrail": "blocked",
        "output_type": "messages_absa_transactions_result",
        "required_args": [],
        "optional_args": [
            "year",
            "search_query",
            "runtime_root",
            "slowmo",
            "limit",
            "max_scrolls",
            "browser_user_data_dir",
            "browser_profile_dir",
            "browser_cdp_url",
        ],
        "arg_types": {"year": "int", "slowmo": "int", "limit": "int", "max_scrolls": "int"},
    }
