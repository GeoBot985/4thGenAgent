from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from runtime.tool_capabilities import ToolHealthResult

from runtime.messages_tools import (
    async_playwright,
    get_or_create_page,
    is_login_screen,
    is_logged_in,
    launch_messages_context,
    open_messages,
)


async def live_probe_google_messages(config: dict[str, Any]) -> ToolHealthResult:
    checked_at = _utc_now()
    runtime_root = str(config.get("runtime_root", "runtime_data"))
    browser_user_data_dir = str(config.get("browser_user_data_dir", "") or "")
    browser_profile_dir = str(config.get("browser_profile_dir", "Default"))
    browser_cdp_url = str(config.get("browser_cdp_url", "") or "")
    slowmo = int(config.get("slowmo", 0) or 0)
    search_query = str(config.get("search_query", "") or "").strip()

    if async_playwright is None:
        return ToolHealthResult(
            tool_id="rpa_google_messages",
            ok=False,
            status="missing_dependency",
            severity="error",
            message="Playwright is not installed.",
            can_auto_resolve=False,
            recommended_action="Install Playwright before running the live Google Messages probe.",
            checked_at=checked_at,
            details={"runtime_root": runtime_root},
        )

    if browser_user_data_dir:
        user_data_path = Path(browser_user_data_dir)
        if not user_data_path.exists():
            return ToolHealthResult(
                tool_id="rpa_google_messages",
                ok=False,
                status="misconfigured",
                severity="error",
                message="Browser profile path is missing or invalid.",
                can_auto_resolve=False,
                recommended_action="Provide a valid browser_user_data_dir path.",
                checked_at=checked_at,
                details={"browser_user_data_dir": browser_user_data_dir, "runtime_root": runtime_root},
            )

    async with async_playwright() as playwright:
        context = await launch_messages_context(
            playwright,
            runtime_root=runtime_root,
            slowmo=slowmo,
            browser_user_data_dir=browser_user_data_dir or None,
            browser_profile_dir=browser_profile_dir,
            browser_cdp_url=browser_cdp_url,
        )
        launched_locally = not browser_cdp_url
        try:
            page = await get_or_create_page(context)
            await open_messages(page)
            logged_in = await is_logged_in(page)
            login_screen = await is_login_screen(page)
            if not logged_in:
                if login_screen:
                    return ToolHealthResult(
                        tool_id="rpa_google_messages",
                        ok=False,
                        status="needs_auth",
                        severity="warning",
                        message="Google Messages opened but no authenticated session was detected.",
                        can_auto_resolve=False,
                        recommended_action="Open setup and pair Google Messages manually.",
                        checked_at=checked_at,
                        details={"runtime_root": runtime_root, "login_screen": True},
                    )
                return ToolHealthResult(
                    tool_id="rpa_google_messages",
                    ok=False,
                    status="needs_auth",
                    severity="warning",
                    message="Google Messages did not reach an authenticated session.",
                    can_auto_resolve=False,
                    recommended_action="Pair Google Messages manually and retry the live probe.",
                    checked_at=checked_at,
                    details={"runtime_root": runtime_root, "login_screen": False},
                )

            search_box_found = await _search_box_present(page)
            scroll_surface_found = await _scroll_surface_present(page)
            if search_query:
                await _run_read_only_search(page, search_query)
            if search_box_found and scroll_surface_found:
                return ToolHealthResult(
                    tool_id="rpa_google_messages",
                    ok=True,
                    status="live_verified",
                    severity="info",
                    message="Google Messages opened, authenticated session detected, search box found, scroll surface detected.",
                    can_auto_resolve=False,
                    recommended_action=None,
                    checked_at=checked_at,
                    details={
                        "runtime_root": runtime_root,
                        "search_box_found": search_box_found,
                        "scroll_surface_found": scroll_surface_found,
                        "search_query": search_query,
                    },
                )
            return ToolHealthResult(
                tool_id="rpa_google_messages",
                ok=False,
                status="failing",
                severity="error",
                message="Google Messages opened but a search box or scroll surface could not be confirmed.",
                can_auto_resolve=False,
                recommended_action="Check the Google Messages web session and retry.",
                checked_at=checked_at,
                details={
                    "runtime_root": runtime_root,
                    "search_box_found": search_box_found,
                    "scroll_surface_found": scroll_surface_found,
                    "search_query": search_query,
                },
            )
        finally:
            if launched_locally:
                await context.close()


async def _search_box_present(page: Any) -> bool:
    candidates = [
        page.locator("[aria-label='Search messages']"),
        page.get_by_role("textbox", name="Search messages"),
        page.get_by_role("textbox"),
    ]
    for locator in candidates:
        try:
            if await locator.first.is_visible(timeout=2000):
                return True
        except Exception:
            continue
    return False


async def _scroll_surface_present(page: Any) -> bool:
    candidates = [
        page.locator("[role='main']"),
        page.locator("main"),
        page.locator("body"),
    ]
    for locator in candidates:
        try:
            if await locator.first.is_visible(timeout=2000):
                return True
        except Exception:
            continue
    return False


async def _run_read_only_search(page: Any, search_query: str) -> None:
    candidates = [
        page.locator("[aria-label='Search messages']"),
        page.get_by_role("textbox", name="Search messages"),
        page.get_by_role("textbox"),
    ]
    for locator in candidates:
        try:
            candidate = locator.first
            if await candidate.is_visible(timeout=1500):
                await candidate.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await candidate.fill(search_query)
                await page.wait_for_timeout(1000)
                return
        except Exception:
            continue


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def main() -> int:
    result = await live_probe_google_messages({})
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
