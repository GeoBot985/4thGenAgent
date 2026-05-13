from __future__ import annotations

import re
from typing import Any

from runtime.messages_tools import (
    _fill_search_query,
    _normalize_message_text,
    async_playwright,
    get_or_create_page,
    launch_messages_context,
    open_messages,
    require_login,
)


def _parse_absa_transaction(text: str, year: int = 2026) -> dict[str, Any] | None:
    normalized = _normalize_message_text(text)
    lower = normalized.lower()
    if "absa" not in lower:
        return None
    if not any(keyword in lower for keyword in ("debit", "debi", "settlement", "direct debit", "spring", "spr")):
        return None

    date_match = re.search(r"\b(\d{2}/\d{2}/(\d{2}|\d{4}))\b", normalized)
    if not date_match:
        return None
    date_text = date_match.group(1)
    date_year = date_match.group(2)
    if len(date_year) == 2:
        resolved_year = 2000 + int(date_year)
    else:
        resolved_year = int(date_year)
    if resolved_year != year:
        return None

    amount_match = re.search(r"R-?\d[\d,]*\.\d{2}", normalized)
    balance_match = re.search(r"(?:Beskikbaar|Available|Balance|Saldo)\s+R?(\d[\d,]*\.\d{2})", normalized, re.IGNORECASE)
    merchant_match = re.search(r"SPR\s+\d+\s*,\s*([^,]+)", normalized, re.IGNORECASE)
    account_ref_match = re.search(r"\b(?:SETTLEMENT/C|DEBIET|DEBIT ORDER|DIRECT DEBIT|DIREC)", normalized, re.IGNORECASE)

    return {
        "source_text": normalized,
        "date": date_text,
        "year": resolved_year,
        "amount": amount_match.group(0) if amount_match else "",
        "available_balance": balance_match.group(1) if balance_match else "",
        "merchant": merchant_match.group(1).strip() if merchant_match else "",
        "category": "absa_debit_order" if account_ref_match else "absa_transaction",
    }


def _extract_absa_candidate_texts(body_text: str) -> list[str]:
    normalized = _normalize_message_text(body_text)
    if not normalized:
        return []
    candidates = [
        _normalize_message_text(match.group(0))
        for match in re.finditer(r"Absa:\s+.*?(?:CONRAGR015|CONRAGRO15|CONRAGR0?15)", normalized, flags=re.IGNORECASE)
    ]
    if candidates:
        return candidates
    return [
        _normalize_message_text(part)
        for part in re.split(r"\s+\+\d{10,15}\s+", normalized)
        if "absa:" in part.lower()
    ]


async def _scroll_active_messages_surface(page: Any) -> dict[str, Any]:
    selectors = [
        "nav.conversation-list",
        "[class*='conversation-list']",
        "[aria-label='Conversations list']",
        "[aria-label='Search results']",
        "[aria-label='Messages']",
        "[aria-label='Conversation']",
        "[role='main']",
        "main",
        "[role='list']",
        "mw-conversation-list",
        "body",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if not await locator.is_visible(timeout=1000):
                continue
            before = await locator.evaluate(
                """(el) => ({
                    scrollTop: el.scrollTop || 0,
                    scrollHeight: el.scrollHeight || 0,
                    clientHeight: el.clientHeight || 0
                })"""
            )
            delta = max(600, int((before.get("clientHeight") or 0) * 0.9))
            await locator.evaluate("(el, delta) => { el.scrollTop = (el.scrollTop || 0) + delta; }", delta)
            await page.wait_for_timeout(1500)
            after = await locator.evaluate(
                """(el) => ({
                    scrollTop: el.scrollTop || 0,
                    scrollHeight: el.scrollHeight || 0,
                    clientHeight: el.clientHeight || 0
                })"""
            )
            moved = int(after.get("scrollTop", 0)) > int(before.get("scrollTop", 0))
            if not moved:
                await page.mouse.wheel(0, delta)
                await page.wait_for_timeout(1000)
                after_wheel = await locator.evaluate(
                    """(el) => ({
                        scrollTop: el.scrollTop || 0,
                        scrollHeight: el.scrollHeight || 0,
                        clientHeight: el.clientHeight || 0
                    })"""
                )
                moved = int(after_wheel.get("scrollTop", 0)) > int(after.get("scrollTop", 0))
                if moved:
                    after = after_wheel
                    selector = f"{selector}+wheel"
            return {"selector": selector, "moved": moved, "before": before, "after": after}
        except Exception:
            continue
    await page.mouse.wheel(0, 1200)
    await page.wait_for_timeout(1500)
    return {
        "selector": "mouse_wheel",
        "moved": True,
        "before": {},
        "after": {},
    }


async def _collect_absa_body_text(page: Any, max_scrolls: int) -> dict[str, Any]:
    chunks: list[str] = []
    seen_bodies: set[str] = set()
    seen_candidates: set[str] = set()
    stable_candidate_rounds = 0
    no_scroll_move_rounds = 0
    scroll_debug: list[dict[str, Any]] = []
    stop_reason = "max_scrolls_reached"
    for _ in range(max(1, max_scrolls)):
        try:
            body_text = await page.locator("body").inner_text(timeout=5000)
        except Exception:
            body_text = ""
        normalized = _normalize_message_text(body_text)
        if normalized and normalized not in seen_bodies:
            chunks.append(body_text)
            seen_bodies.add(normalized)

        candidate_texts = _extract_absa_candidate_texts("\n".join(chunks))
        candidate_set = {text for text in candidate_texts if text}
        if candidate_set - seen_candidates:
            seen_candidates.update(candidate_set)
            stable_candidate_rounds = 0
        else:
            stable_candidate_rounds += 1

        scroll_result = await _scroll_active_messages_surface(page)
        scroll_debug.append(scroll_result)
        if not scroll_result.get("moved"):
            no_scroll_move_rounds += 1
        else:
            no_scroll_move_rounds = 0

        if stable_candidate_rounds >= 10 and no_scroll_move_rounds >= 5:
            stop_reason = "stable_candidates_and_no_scroll_movement"
            break

    else:
        stop_reason = "max_scrolls_reached"

    if not chunks:
        stop_reason = "no_body_text_collected"

    return {
        "body_text": "\n".join(chunks),
        "scroll_debug": {
            "max_scrolls": max_scrolls,
            "body_chunks": len(chunks),
            "candidate_count_before_parse": len(seen_candidates),
            "scroll_rounds": len(scroll_debug),
            "stable_candidate_rounds": stable_candidate_rounds,
            "no_scroll_move_rounds": no_scroll_move_rounds,
            "stop_reason": stop_reason,
            "last_scroll": scroll_debug[-1] if scroll_debug else {},
        },
    }


async def messages_extract_absa_transactions(
    year: int = 2026,
    search_query: str = "Absa",
    runtime_root: str = "runtime_data",
    slowmo: int = 100,
    limit: int = 200,
    max_scrolls: int = 240,
    browser_user_data_dir: str = "",
    browser_profile_dir: str = "Default",
    browser_cdp_url: str = "",
) -> dict[str, Any]:
    if async_playwright is None:  # pragma: no cover - dependency issue
        return {"ok": False, "year": year, "transactions": [], "rows": [], "count": 0, "error": "Playwright unavailable."}

    async with async_playwright() as p:
        context = await launch_messages_context(
            p,
            runtime_root=runtime_root,
            slowmo=slowmo,
            browser_user_data_dir=browser_user_data_dir or None,
            browser_profile_dir=browser_profile_dir,
            browser_cdp_url=browser_cdp_url,
        )
        try:
            page = await get_or_create_page(context)
            await open_messages(page)
            await require_login(page)

            if search_query:
                await _fill_search_query(page, search_query)

            collection = await _collect_absa_body_text(page, max_scrolls=max_scrolls)
            body_text = collection["body_text"]
            scroll_debug = collection["scroll_debug"]

            candidates: list[str] = _extract_absa_candidate_texts(body_text)
            for line in body_text.splitlines():
                text = _normalize_message_text(line)
                if not text:
                    continue
                lower = text.lower()
                if "absa" not in lower:
                    continue
                if not any(term in lower for term in ("debit", "debi", "settlement", "direct debit", "spr ", "spr")):
                    continue
                candidates.append(text)

            transactions: list[dict[str, Any]] = []
            seen: set[tuple[str, str, str]] = set()
            for text in candidates[:limit]:
                parsed = _parse_absa_transaction(text, year=year)
                if not parsed:
                    continue
                key = (parsed.get("date", ""), parsed.get("amount", ""), parsed.get("source_text", ""))
                if key in seen:
                    continue
                seen.add(key)
                transactions.append(parsed)

            if not transactions:
                return {
                    "ok": False,
                    "year": year,
                    "search_query": search_query,
                    "transactions": [],
                    "rows": [],
                    "count": 0,
                    "scroll_debug": scroll_debug,
                    "error": "NO_ABSA_TRANSACTIONS_FOUND",
                }

            rows = [
                [
                    "source_text",
                    "date",
                    "year",
                    "amount",
                    "available_balance",
                    "merchant",
                    "category",
                    "search_query",
                ]
            ]
            for item in transactions:
                rows.append(
                    [
                        item.get("source_text", ""),
                        item.get("date", ""),
                        item.get("year", ""),
                        item.get("amount", ""),
                        item.get("available_balance", ""),
                        item.get("merchant", ""),
                        item.get("category", ""),
                        search_query,
                    ]
                )

            return {
                "ok": True,
                "year": year,
                "search_query": search_query,
                "transactions": transactions,
                "rows": rows,
                "count": len(transactions),
                "scroll_debug": scroll_debug,
                "error": "",
            }
        finally:
            await context.close()
