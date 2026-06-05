# backend/scraper/http_utils.py
"""HTTP utilities with retry logic."""

import httpx
import time
import logging
from typing import Optional

from backend.scraper.config import REQUEST_TIMEOUT, MAX_RETRIES, RETRY_BACKOFF_BASE
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


def fetch_with_retry(
    url: str,
    max_retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT
) -> Optional[httpx.Response]:
    """
    Fetch URL with retry logic and exponential backoff.

    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds

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


def fetch_with_playwright(
    url: str,
    wait_for_selector: str | None = None,
    timeout: int = 20000,
    extra_wait_ms: int = 2000,
) -> str | None:
    """
    Fetch a JS-rendered page using Playwright/Chromium.
    Use for pages protected by Cloudflare or requiring JS rendering.

    Returns:
        Page HTML string or None on failure
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--disable-extensions",
                    "--single-process",
                    "--no-zygote",
                ],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )

            def handle_route(route, request):
                if request.resource_type in {"image", "stylesheet", "font", "media"}:
                    route.abort()
                else:
                    route.continue_()

            context.route("**/*", handle_route)

            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)

            if wait_for_selector:
                page.wait_for_selector(wait_for_selector, timeout=timeout)
            else:
                page.wait_for_timeout(extra_wait_ms)

            content = page.content()
            browser.close()
            return content

    except PlaywrightTimeoutError:
        logger.error(f"Playwright timeout fetching: {url}")
        return None
    except Exception as e:
        logger.error(f"Playwright error fetching {url}: {type(e).__name__}: {e}")
        return None