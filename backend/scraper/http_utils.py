# backend/scraper/http_utils.py
"""HTTP utilities with retry logic."""

import httpx
import time
import logging
from contextlib import contextmanager
from typing import Optional

from backend.scraper.config import REQUEST_TIMEOUT, MAX_RETRIES, RETRY_BACKOFF_BASE
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

_BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-extensions",
    "--single-process",
    "--no-zygote",
]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_ABORT_TYPES = {"image", "stylesheet", "font", "media", "ping", "other"}

_ABORT_URL_FRAGMENTS = {
    "googletag", "googletagmanager", "exponea", "cookielaw",
    "cloudflareinsights", "riddle.com", "googlesyndication",
    "challenge-platform", "cdn-cgi",
    "globalnav", "navigationtop", "footernavigation", "relatedmedia",
    "StatsLeaderboard", "livematches", "players/profile/widget",
    "partners/footer", "webxp/projects",
}


def _handle_route(route, request) -> None:
    rtype = request.resource_type
    url = request.url
    if rtype in _ABORT_TYPES:
        route.abort()
        return
    if rtype in {"xhr", "fetch", "script"} and any(f in url for f in _ABORT_URL_FRAGMENTS):
        route.abort()
        return
    route.continue_()


@contextmanager
def playwright_session():
    """
    Launch a single shared browser + context for multiple page fetches.
    Use this in updater.py to avoid re-launching Chromium on every call.

    Usage:
        with playwright_session() as ctx:
            html1 = fetch_with_playwright(url1, context=ctx)
            html2 = fetch_with_playwright(url2, context=ctx)
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=_BROWSER_ARGS)
        try:
            context = browser.new_context(user_agent=_USER_AGENT)
            context.route("**/*", _handle_route)
            yield context
        finally:
            browser.close()


def fetch_with_playwright(
    url: str,
    wait_for_selector: str | None = None,
    timeout: int = 20000,
    extra_wait_ms: int = 2000,
    context=None,
) -> str | None:
    """
    Fetch a JS-rendered page using Playwright/Chromium.

    Args:
        url: Page URL to fetch
        wait_for_selector: CSS selector to wait for (state="attached") before returning HTML.
                           Use None + extra_wait_ms for a fixed sleep instead.
        timeout: Timeout in ms for goto and wait_for_selector
        extra_wait_ms: Fixed sleep in ms when wait_for_selector is None
        context: An existing Playwright BrowserContext from playwright_session().
                 If provided, reuses the browser — much faster for multiple calls.
                 If None, spins up a one-shot browser (slower, for standalone use).

    Returns:
        Page HTML string or None on failure
    """
    def _fetch(ctx) -> str:
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="commit", timeout=timeout)
            if wait_for_selector:
                page.wait_for_selector(wait_for_selector, state="attached", timeout=timeout)
            else:
                page.wait_for_timeout(extra_wait_ms)
            return page.content()
        finally:
            page.close()

    try:
        if context is not None:
            return _fetch(context)
        # Fallback: one-shot browser when no shared context provided
        with playwright_session() as ctx:
            return _fetch(ctx)
    except PlaywrightTimeoutError:
        logger.error(f"Playwright timeout fetching: {url}")
        return None
    except Exception as e:
        logger.error(f"Playwright error fetching {url}: {type(e).__name__}: {e}")
        return None


def fetch_with_retry(
    url: str,
    max_retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT
) -> Optional[httpx.Response]:
    """
    Fetch URL with retry logic and exponential backoff.

    Returns:
        Response object or None if all retries failed
    """
    for attempt in range(max_retries):
        try:
            response = httpx.get(url, timeout=timeout, follow_redirects=True)
            response.raise_for_status()
            return response

        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            if attempt < max_retries - 1:
                wait_time = RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{max_retries}, "
                    f"retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Failed after {max_retries} attempts: timeout")
                return None

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {url}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None

    return None