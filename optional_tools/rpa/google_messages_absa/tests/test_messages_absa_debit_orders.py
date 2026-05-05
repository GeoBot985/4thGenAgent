from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


def test_absa_manifest_exists():
    assert Path("config/manifests/absa_debit_orders_2026.json").is_file()


def test_absa_scenario_exists():
    from src.operator_scenarios import get_scenario

    scenario = get_scenario("messages_absa_debit_orders_2026_capture")
    assert scenario["category"] == "messages"
    assert scenario["uses_llm"] is False
    assert scenario["event_type"] == "manual.messages_absa_debit_orders_2026"


def test_absa_transaction_parser_extracts_2026_debit_order():
    from runtime.messages_tools import _parse_absa_transaction

    text = (
        "Absa: SPR 8418, Aank, 03/05/26 SETTLEMENT/C - PREPAID DEBIET, "
        "ELECTRICITY: 07142323588, R-2,500.00, Beskikbaar R15,798.59. Hulp 0860008600; CONRAGR015"
    )

    parsed = _parse_absa_transaction(text, year=2026)

    assert parsed is not None
    assert parsed["year"] == 2026
    assert parsed["date"] == "03/05/26"
    assert parsed["amount"] == "R-2,500.00"
    assert parsed["category"] == "absa_debit_order"


@pytest.mark.asyncio
async def test_absa_scroll_collection_includes_debug_metadata(monkeypatch):
    import runtime.messages_tools as messages_tools

    body_texts = [
        "Messages | Loading conversation list",
        "Messages | Loading conversation list | Absa: SPR 8418, Aank, 03/05/26 SETTLEMENT/C - PREPAID DEBIET, ELECTRICITY: 07142323588, R-2,500.00, Beskikbaar R15,798.59. Hulp 0860008600; CONRAGR015",
    ]
    scrolls = [
        {"selector": "[role='main']", "moved": True, "before": {"scrollTop": 0, "clientHeight": 800}, "after": {"scrollTop": 800, "clientHeight": 800}},
        {"selector": "[role='main']", "moved": False, "before": {"scrollTop": 800, "clientHeight": 800}, "after": {"scrollTop": 800, "clientHeight": 800}},
        {"selector": "[role='main']", "moved": False, "before": {"scrollTop": 800, "clientHeight": 800}, "after": {"scrollTop": 800, "clientHeight": 800}},
        {"selector": "[role='main']", "moved": False, "before": {"scrollTop": 800, "clientHeight": 800}, "after": {"scrollTop": 800, "clientHeight": 800}},
    ]

    class FakeBodyLocator:
        def __init__(self):
            self.count = 0

        async def inner_text(self, timeout=5000):
            idx = min(self.count, len(body_texts) - 1)
            self.count += 1
            return body_texts[idx]

    class FakeLocator:
        def __init__(self):
            self.body = FakeBodyLocator()

        @property
        def first(self):
            return self

        async def is_visible(self, timeout=1000):
            return True

        async def evaluate(self, script, *args):
            payload = args[0] if args else None
            if "scrollTop" in script:
                return payload.get("before", {"scrollTop": 0, "clientHeight": 800})
            return {}

        async def inner_text(self, timeout=5000):
            return await self.body.inner_text(timeout=timeout)

    class FakePage:
        def __init__(self):
            self.body = FakeBodyLocator()

        def locator(self, selector):
            if selector == "body":
                return SimpleNamespace(inner_text=self.body.inner_text)
            return FakeLocator()

        class mouse:
            @staticmethod
            async def wheel(x, y):
                return None

        async def wait_for_timeout(self, ms):
            return None

    async def fake_scroll(page):
        return scrolls[min(fake_scroll.calls, len(scrolls) - 1)]

    fake_scroll.calls = 0

    async def counting_scroll(page):
        result = await fake_scroll(page)
        fake_scroll.calls += 1
        return result

    monkeypatch.setattr(messages_tools, "_scroll_active_messages_surface", counting_scroll)

    result = await messages_tools._collect_absa_body_text(FakePage(), max_scrolls=12)

    assert result["scroll_debug"]["body_chunks"] >= 1
    assert result["scroll_debug"]["scroll_rounds"] >= 1
    assert result["scroll_debug"]["stop_reason"] in {"stable_candidates_and_no_scroll_movement", "max_scrolls_reached"}
    assert "Absa:" in result["body_text"]
