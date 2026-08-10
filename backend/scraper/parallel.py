"""Run scrape units concurrently with a small pool of Playwright pages."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

from backend.scraper.config import SCRAPE_CONCURRENCY
from backend.scraper.http_utils import async_playwright_session

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")

AsyncWorker = Callable[[object, T], Awaitable[R]]


async def _parallel_map_async(
    items: Sequence[T],
    worker: AsyncWorker[T, R],
    *,
    concurrency: int,
) -> list[R | BaseException]:
    if not items:
        return []

    # Multi-page needs a normal Chromium process model.
    single_process = concurrency <= 1
    async with async_playwright_session(single_process=single_process) as ctx:
        sem = asyncio.Semaphore(concurrency)

        async def run_one(item: T) -> R:
            async with sem:
                page = await ctx.new_page()
                try:
                    return await worker(page, item)
                finally:
                    await page.close()

        return list(await asyncio.gather(*(run_one(i) for i in items), return_exceptions=True))


def parallel_map(
    items: Sequence[T],
    worker: AsyncWorker[T, R],
    *,
    concurrency: int | None = None,
) -> list[R | BaseException]:
    """
    Run ``worker(page, item)`` over items with up to ``concurrency`` pages.

    Returns results in the same order as ``items``; failures are Exception values.
    """
    workers = concurrency if concurrency is not None else SCRAPE_CONCURRENCY
    workers = max(1, workers)
    logger.info("Parallel scrape: %s items, concurrency=%s", len(items), workers)
    return asyncio.run(_parallel_map_async(items, worker, concurrency=workers))
