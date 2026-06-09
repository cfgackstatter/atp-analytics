# backend/scraper/http_utils.py
"""Shared Playwright browser session for all scrapers."""

import logging
from contextlib import contextmanager
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

_BROWSER_ARGS = [
    "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
    "--disable-gpu", "--disable-software-rasterizer", "--disable-extensions",
    "--single-process", "--no-zygote",
]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_ABORT_TYPES = {"image", "stylesheet", "font", "media", "ping", "other"}

_ABORT_URL_FRAGMENTS = {
    "googletag", "googletagmanager", "exponea", "cookielaw",
    "cloudflareinsights", "riddle.com", "googlesyndication",
    "challenge-platform", "cdn-cgi", "globalnav", "navigationtop",
    "footernavigation", "relatedmedia", "StatsLeaderboard", "livematches",
    "players/profile/widget", "partners/footer", "webxp/projects",
}

def _handle_route(route, request) -> None:
    rtype = request.resource_type
    if rtype in _ABORT_TYPES:
        route.abort()
        return
    if rtype in {"xhr", "fetch", "script"} and any(f in request.url for f in _ABORT_URL_FRAGMENTS):
        route.abort()
        return
    route.continue_()

@contextmanager
def playwright_session():
    """Shared browser context for all scrapers. Use as: with playwright_session() as ctx."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=_BROWSER_ARGS)
        try:
            ctx = browser.new_context(user_agent=_USER_AGENT)
            ctx.route("**/*", _handle_route)
            yield ctx
        finally:
            browser.close()