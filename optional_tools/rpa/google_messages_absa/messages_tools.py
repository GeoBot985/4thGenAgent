from __future__ import annotations

"""Browser-backed Google Messages read tool.

This is a read-only adapter for the paired Google Messages web session.
It intentionally avoids sending messages or mutating account state.
"""

from pathlib import Path
from typing import Any
import time
import re
import os

try:  # pragma: no cover - optional runtime dependency
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - dependency may not be installed in all environments
    async_playwright = None  # type: ignore[assignment]

MESSAGES_URL = "https://messages.google.com/web/conversations"
DEFAULT_BROWSER_USER_DATA_DIR = Path("runtime_data") / "absa_workflow_profile"
CHROME_EXECUTABLE_CANDIDATES = [
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe",
]


def safe_print(text: str) -> None:
    import sys

    sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


def get_profile_dir(runtime_root: str = "runtime_data") -> Path:
    profile_dir = Path(runtime_root) / "absa_workflow_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


async def launch_messages_context(
    playwright: Any,
    runtime_root: str = "runtime_data",
    slowmo: int = 100,
    browser_user_data_dir: str | None = None,
    browser_profile_dir: str = "Default",
    browser_cdp_url: str = "",
):
    if browser_cdp_url:
        browser = await playwright.chromium.connect_over_cdp(browser_cdp_url)
        if browser.contexts:
            return browser.contexts[0]
        return await browser.new_context(viewport={"width": 1400, "height": 900})

    user_data_dir = Path(browser_user_data_dir) if browser_user_data_dir else DEFAULT_BROWSER_USER_DATA_DIR
    executable_path = next((str(path) for path in CHROME_EXECUTABLE_CANDIDATES if path.is_file()), None)
    launch_kwargs = {
        "user_data_dir": str(user_data_dir),
        "headless": False,
        "slow_mo": slowmo,
        "viewport": {"width": 1400, "height": 900},
        "args": [f"--profile-directory={browser_profile_dir}"],
    }
    if executable_path:
        launch_kwargs["executable_path"] = executable_path
    return await playwright.chromium.launch_persistent_context(**launch_kwargs)


async def get_or_create_page(context: Any):
    if context.pages:
        return context.pages[0]
    return await context.new_page()


async def open_messages(page: Any) -> None:
    await page.goto(MESSAGES_URL, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(2500)


async def is_logged_in(page: Any) -> bool:
    checks = [
        page.get_by_text("Messages", exact=False),
        page.get_by_text("Search messages", exact=False),
        page.get_by_text("Start chat", exact=False),
        page.locator("[aria-label='Search messages']"),
        page.locator("[aria-label='New conversation']"),
        page.locator("[role='main']"),
    ]

    for locator in checks:
        try:
            if await locator.first.is_visible(timeout=1500):
                return True
        except Exception:
            continue
    return False


async def is_login_screen(page: Any) -> bool:
    checks = [
        page.get_by_text("Use Messages on your computer", exact=False),
        page.get_by_text("Pair with QR code", exact=False),
        page.get_by_text("Link with Google", exact=False),
        page.get_by_text("Google Messages for web", exact=False),
        page.locator("canvas"),
    ]
    for locator in checks:
        try:
            if await locator.first.is_visible(timeout=1500):
                return True
        except Exception:
            continue
    return False


async def wait_for_login(page: Any, timeout_ms: int = 120000) -> bool:
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        if await is_logged_in(page):
            return True
        await page.wait_for_timeout(1000)
    return False


async def require_login(page: Any, timeout_ms: int = 120000) -> None:
    if await is_logged_in(page):
        return

    if await is_login_screen(page):
        safe_print("Complete Google Messages pairing in the phone app, then leave the browser open.")

    if await wait_for_login(page, timeout_ms=timeout_ms):
        return

    raise RuntimeError(
        "Google Messages web is not authenticated. "
        "Pair messages.google.com/web/conversations with the phone app first."
    )


async def _clear_search_box(page: Any) -> None:
    candidates = [
        page.locator("[aria-label='Search messages']"),
        page.get_by_role("textbox", name="Search messages"),
        page.get_by_role("textbox").first,
    ]
    for locator in candidates:
        try:
            candidate = locator.first
            if await candidate.is_visible(timeout=2000):
                await candidate.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                return
        except Exception:
            continue
    raise RuntimeError("Could not find Google Messages search box.")


async def _fill_search_query(page: Any, search_query: str) -> bool:
    if not search_query:
        return False
    candidates = [
        page.locator("[aria-label='Search messages']"),
        page.get_by_role("textbox", name="Search messages"),
        page.get_by_role("textbox").first,
    ]
    for locator in candidates:
        try:
            candidate = locator.first
            if await candidate.is_visible(timeout=2000):
                await candidate.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await candidate.fill(search_query)
                await page.wait_for_timeout(2500)
                return True
        except Exception:
            continue
    return False


def _thread_candidates(thread_name: str) -> list[str]:
    values = [thread_name.strip()]
    if "/" in thread_name:
        values.append(thread_name.replace("/", " ").strip())
        values.append(thread_name.replace("/", "").strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(value.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


async def find_thread(page: Any, thread_name: str, timeout_ms: int = 30000) -> bool:
    deadline = time.monotonic() + (timeout_ms / 1000)
    candidates = _thread_candidates(thread_name)

    while time.monotonic() < deadline:
        try:
            await _clear_search_box(page)
            search_box = page.locator("[aria-label='Search messages']").first
            if not await search_box.is_visible(timeout=1500):
                search_box = page.get_by_role("textbox").first
            await search_box.fill(candidates[0])
            await page.wait_for_timeout(1000)
        except Exception:
            pass

        for candidate in candidates:
            locators = [
                page.get_by_text(candidate, exact=True),
                page.get_by_text(candidate, exact=False),
                page.get_by_title(candidate, exact=False),
            ]
            for locator in locators:
                try:
                    item = locator.first
                    if await item.is_visible(timeout=1000):
                        await item.click()
                        await page.wait_for_timeout(1000)
                        return True
                except Exception:
                    continue

        await page.wait_for_timeout(1000)

    return False


def _normalize_message_text(value: str) -> str:
    return " ".join((value or "").split())


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


async def read_visible_messages(page: Any, limit: int = 20) -> list[dict[str, str]]:
    candidates = [
        "[data-message-text]",
        "[data-text]",
        "[dir='auto']",
        "article",
        "li",
        "div",
    ]
    messages: list[dict[str, str]] = []
    seen: set[str] = set()

    for selector in candidates:
        try:
            nodes = page.locator(selector)
            count = min(await nodes.count(), max(limit * 4, limit))
            for idx in range(count):
                node = nodes.nth(idx)
                try:
                    if not await node.is_visible(timeout=1000):
                        continue
                    raw = await node.inner_text(timeout=1000)
                except Exception:
                    continue
                text = _normalize_message_text(raw)
                if not text or len(text) < 2:
                    continue
                if text in seen:
                    continue
                seen.add(text)
                messages.append({"direction": "unknown", "type": "text", "text": text})
                if len(messages) >= limit:
                    return messages
        except Exception:
            continue

    return messages


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

        # If repeated scroll attempts no longer advance the surface and no new
        # ABSA candidates are appearing, abort instead of continuing to burn
        # through the rest of the scan budget.
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


async def messages_read_recent(
    thread_name: str,
    limit: int = 20,
    runtime_root: str = "runtime_data",
    slowmo: int = 100,
    keep_open: bool = False,
    browser_user_data_dir: str = "",
    browser_profile_dir: str = "Default",
    browser_cdp_url: str = "",
) -> dict[str, Any]:
    if async_playwright is None:  # pragma: no cover - dependency issue
        return {"ok": False, "thread_name": thread_name, "count": 0, "messages": [], "error": "Playwright unavailable."}

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

            found = await find_thread(page, thread_name)
            if not found:
                return {"ok": False, "thread_name": thread_name, "count": 0, "messages": [], "error": "THREAD_NOT_FOUND"}

            await page.wait_for_timeout(1500)
            messages = await read_visible_messages(page, limit=limit)
            result = {
                "ok": True,
                "thread_name": thread_name,
                "count": len(messages),
                "messages": messages,
                "error": "",
            }
            if keep_open:
                safe_print("Browser left open. Close it manually when done.")
                await page.wait_for_timeout(24 * 60 * 60 * 1000)
            return result
        finally:
            if not keep_open:
                await context.close()
