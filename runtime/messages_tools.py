from __future__ import annotations

"""Browser-backed Google Messages read tool.

This is a read-only adapter for the paired Google Messages web session.
It intentionally avoids sending messages or mutating account state.
"""

from pathlib import Path
from typing import Any
import time
import os

try:  # pragma: no cover - optional runtime dependency
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - dependency may not be installed in all environments
    async_playwright = None  # type: ignore[assignment]

MESSAGES_URL = "https://messages.google.com/web/conversations"
DEFAULT_BROWSER_USER_DATA_DIR = Path("runtime_data") / "google_messages_profile"
CHROME_EXECUTABLE_CANDIDATES = [
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe",
]


def safe_print(text: str) -> None:
    import sys

    sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


def get_profile_dir(runtime_root: str = "runtime_data") -> Path:
    profile_dir = Path(runtime_root) / "google_messages_profile"
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


def messages_extract_absa_transactions(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from optional_tools.rpa.google_messages_absa.messages_tools import messages_extract_absa_transactions as _messages_extract_absa_transactions

    return _messages_extract_absa_transactions(*args, **kwargs)


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
