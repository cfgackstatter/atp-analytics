# backend/scraper/http_utils.py
"""Shared Playwright browser session and navigation helpers for all scrapers."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from backend.scraper.config import MAX_RETRIES, REQUEST_TIMEOUT, RETRY_BACKOFF_BASE

logger = logging.getLogger(__name__)

BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-extensions",
    # Helps low-memory EB instances; keep concurrency at 1 page per session.
    "--single-process",
    "--no-zygote",
]

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
    "googlesyndication",
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


def _timeout_ms() -> int:
    return int(REQUEST_TIMEOUT * 1000)


def _handle_route(route, request) -> None:
    rtype = request.resource_type
    if rtype in _ABORT_TYPES:
        route.abort()
        return
    if rtype in {"xhr", "fetch", "script"} and any(
        fragment in request.url for fragment in _ABORT_URL_FRAGMENTS
    ):
        route.abort()
        return
    route.continue_()


@contextmanager
def playwright_session() -> Iterator[Any]:
    """Yield a shared BrowserContext with route filtering enabled."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=BROWSER_ARGS)
        try:
            ctx = browser.new_context(user_agent=_USER_AGENT)
            ctx.route("**/*", _handle_route)
            yield ctx
        finally:
            browser.close()


def goto_and_extract(
    page: Page,
    url: str,
    *,
    selector: str,
    js: str,
    timeout_ms: int | None = None,
    max_retries: int | None = None,
) -> Any:
    """
    Navigate with ``commit`` + wait for ``selector`` (attached), then ``evaluate``.

    Retries timeouts with exponential backoff from config.
    """
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
