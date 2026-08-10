# backend/scraper/http_utils.py
"""Shared Playwright browser session and navigation helpers for all scrapers."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Iterator

from playwright.async_api import Page as AsyncPage
from playwright.async_api import TimeoutError as AsyncPlaywrightTimeoutError
from playwright.async_api import async_playwright
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from backend.scraper.config import (
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_BACKOFF_BASE,
    playwright_single_process,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_ABORT_TYPES = {
    "image",
    "stylesheet",
    "font",
    "media",
    "ping",
    "other",
    "manifest",
    "websocket",
    "eventsource",
    "texttrack",
}

_ABORT_URL_FRAGMENTS = {
    "googletag",
    "googletagmanager",
    "exponea",
    "cookielaw",
    "cloudflareinsights",
    "riddle.com",
    "googlesyndication",
    "challenge-platform",
    "cdn-cgi",
    "globalnav",
    "navigationtop",
    "footernavigation",
    "relatedmedia",
    "StatsLeaderboard",
    "livematches",
    "players/profile/widget",
    "partners/footer",
    "webxp/projects",
    "doubleclick",
    "google-analytics",
    "googleadservices",
    "facebook.net",
    "hotjar",
    "newrelic",
    "nr-data.net",
    "scorecardresearch",
    "adservice",
    "amazon-adsystem",
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "twitter.com",
    "linkedin.com",
    "segment.com",
    "segment.io",
}


def browser_launch_args(*, single_process: bool | None = None) -> list[str]:
    """Chromium flags; omit --single-process when using parallel pages."""
    args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--disable-extensions",
    ]
    use_single = (
        playwright_single_process() if single_process is None else single_process
    )
    if use_single:
        args.extend(["--single-process", "--no-zygote"])
    return args


# Back-compat alias used by older call sites / smoke tests.
BROWSER_ARGS = browser_launch_args()


def _timeout_ms() -> int:
    return int(REQUEST_TIMEOUT * 1000)


def _should_abort(rtype: str, url: str) -> bool:
    if rtype in _ABORT_TYPES:
        return True
    if rtype in {"xhr", "fetch", "script"} and any(
        fragment in url for fragment in _ABORT_URL_FRAGMENTS
    ):
        return True
    return False


async def _handle_route_async(route, request) -> None:
    if _should_abort(request.resource_type, request.url):
        await route.abort()
        return
    await route.continue_()


def _handle_route(route, request) -> None:
    if _should_abort(request.resource_type, request.url):
        route.abort()
        return
    route.continue_()


@contextmanager
def playwright_session(*, single_process: bool | None = None) -> Iterator[Any]:
    """Yield a shared sync BrowserContext with route filtering enabled."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=browser_launch_args(single_process=single_process),
        )
        try:
            ctx = browser.new_context(user_agent=_USER_AGENT)
            ctx.route("**/*", _handle_route)
            yield ctx
        finally:
            browser.close()


@contextmanager
def owned_page(context=None, page: Page | None = None) -> Iterator[Page]:
    """
    Yield a page for sync scrapers.

    Prefer an injected ``page``, else a temporary page on ``context``, else a
    short-lived self-launched session (fallback for scripts/tests only).
    """
    if page is not None:
        yield page
        return

    if context is not None:
        owned = context.new_page()
        try:
            yield owned
        finally:
            owned.close()
        return

    logger.debug("Scraper self-launching Playwright session (no page/context provided)")
    with playwright_session() as ctx:
        owned = ctx.new_page()
        try:
            yield owned
        finally:
            owned.close()


@asynccontextmanager
async def async_playwright_session(
    *,
    single_process: bool | None = None,
) -> AsyncIterator[Any]:
    """Yield a shared async BrowserContext with route filtering enabled."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=browser_launch_args(single_process=single_process),
        )
        try:
            ctx = await browser.new_context(user_agent=_USER_AGENT)
            await ctx.route("**/*", _handle_route_async)
            yield ctx
        finally:
            await browser.close()


def goto_and_extract(
    page: Page,
    url: str,
    *,
    selector: str,
    js: str,
    timeout_ms: int | None = None,
    max_retries: int | None = None,
) -> Any:
    """Sync navigate with ``commit`` + attached selector, then ``evaluate``."""
    timeout = timeout_ms if timeout_ms is not None else _timeout_ms()
    retries = MAX_RETRIES if max_retries is None else max_retries
    last_error: Exception | None = None

    for attempt in range(retries):
        try:
            page.goto(url, wait_until="commit", timeout=timeout)
            page.wait_for_selector(selector, state="attached", timeout=timeout)
            return page.evaluate(js)
        except PlaywrightTimeoutError as exc:
            last_error = exc
            if attempt >= retries - 1:
                break
            delay = RETRY_BACKOFF_BASE ** attempt
            logger.warning(
                "Timeout on %s (attempt %s/%s); retrying in %ss",
                url,
                attempt + 1,
                retries,
                delay,
            )
            time.sleep(delay)

    assert last_error is not None
    raise last_error


async def async_goto_and_extract(
    page: AsyncPage,
    url: str,
    *,
    selector: str,
    js: str,
    timeout_ms: int | None = None,
    max_retries: int | None = None,
) -> Any:
    """Async navigate with ``commit`` + attached selector, then ``evaluate``."""
    timeout = timeout_ms if timeout_ms is not None else _timeout_ms()
    retries = MAX_RETRIES if max_retries is None else max_retries
    last_error: Exception | None = None

    for attempt in range(retries):
        try:
            await page.goto(url, wait_until="commit", timeout=timeout)
            await page.wait_for_selector(selector, state="attached", timeout=timeout)
            return await page.evaluate(js)
        except AsyncPlaywrightTimeoutError as exc:
            last_error = exc
            if attempt >= retries - 1:
                break
            delay = RETRY_BACKOFF_BASE ** attempt
            logger.warning(
                "Timeout on %s (attempt %s/%s); retrying in %ss",
                url,
                attempt + 1,
                retries,
                delay,
            )
            await asyncio.sleep(delay)

    assert last_error is not None
    raise last_error
