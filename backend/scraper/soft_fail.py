"""Uniform soft-fail policy for scrapers after retries are exhausted."""

from __future__ import annotations

import logging
from typing import Callable, TypeVar

from playwright.async_api import TimeoutError as AsyncPlaywrightTimeoutError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

T = TypeVar("T")

TimeoutTypes = (PlaywrightTimeoutError, AsyncPlaywrightTimeoutError)


def soft_fail(
    logger: logging.Logger,
    label: str,
    exc: BaseException,
    empty: Callable[[], T],
) -> T:
    """
    Log a scrape failure and return an empty result.

    Policy: after ``goto_and_extract`` retries are exhausted, scrapers return
    empty data and continue the job (never crash the whole run).
    """
    if isinstance(exc, TimeoutTypes):
        logger.warning("Timeout %s: %s", label, exc)
    else:
        logger.warning("Skipping %s due to error: %s", label, exc)
    return empty()
