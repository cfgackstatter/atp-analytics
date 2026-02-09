# backend/scraper/http_utils.py
"""HTTP utilities with retry logic."""

import httpx
import time
import logging
from typing import Optional

from backend.scraper.config import REQUEST_TIMEOUT, MAX_RETRIES, RETRY_BACKOFF_BASE

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