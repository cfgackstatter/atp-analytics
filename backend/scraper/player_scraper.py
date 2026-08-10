# backend/scraper/player_scraper.py
"""Scrape ATP player biographical data."""

from __future__ import annotations

import logging
import re
import time

from playwright.async_api import Page as AsyncPage
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from backend.scraper.config import MAX_RETRIES, PLAYER_OVERVIEW_URL, RETRY_BACKOFF_BASE
from backend.scraper.http_utils import (
    async_goto_and_extract,
    goto_and_extract,
    playwright_session,
)
from backend.scraper.parallel import parallel_map

logger = logging.getLogger(__name__)

_BIO_ITEMS_JS = """
() => Array.from(
    document.querySelectorAll("div.pd_content li")
).map(li => {
    const spans = li.querySelectorAll(":scope > span");
    return spans.length >= 2
        ? { label: spans[0].textContent.trim(), value: spans[1].textContent.trim() }
        : null;
}).filter(Boolean)
"""

BIO_SELECTOR = "div.pd_content"


def player_overview_url(player_id: str, player_slug: str) -> str:
    return f"{PLAYER_OVERVIEW_URL}/{player_slug}/{player_id}/overview"


def _extract_date(text: str) -> str | None:
    if m := re.search(r"(\d{4})/(\d{2})/(\d{2})", text):
        return m.group(0)
    return None


def _extract_weight_kg(text: str) -> int | None:
    if m := re.search(r"\((\d+)kg\)", text):
        return int(m.group(1))
    if m := re.search(r"(\d+)\s*lbs", text):
        return round(int(m.group(1)) * 0.453592)
    return None


def _extract_height_cm(text: str) -> int | None:
    if m := re.search(r"\((\d+)cm\)", text):
        return int(m.group(1))
    if m := re.search(r"(\d+)'(\d+)\"", text):
        feet, inches = int(m.group(1)), int(m.group(2))
        return round((feet * 12 + inches) * 2.54)
    return None


def _parse_plays(text: str) -> tuple[str | None, str | None]:
    handedness = (
        "Right-Handed"
        if "Right-Handed" in text
        else "Left-Handed"
        if "Left-Handed" in text
        else None
    )
    backhand = (
        "Two-Handed"
        if "Two-Handed Backhand" in text
        else "One-Handed"
        if "One-Handed Backhand" in text
        else None
    )
    return handedness, backhand


def items_to_bio(items: list[dict]) -> dict:
    data: dict = {}
    for item in items or []:
        label, value = item["label"], item["value"]
        if label in ("Age", "DOB"):
            data["birthdate"] = _extract_date(value)
        elif label == "Weight":
            data["weight_kg"] = _extract_weight_kg(value)
        elif label == "Height":
            data["height_cm"] = _extract_height_cm(value)
        elif label == "Turned pro":
            data["turned_pro"] = int(value) if value.isdigit() else None
        elif label == "Country":
            data["country"] = value.split("\n")[0].strip() or None
        elif label == "Birthplace":
            data["birthplace"] = value or None
        elif label == "Plays":
            data["handedness"], data["backhand"] = _parse_plays(value)
        elif label == "Coach":
            data["coach"] = value or None
    return data


def _scrape_player(page: Page, player_id: str, player_slug: str) -> dict:
    """Scrape one player using an existing Playwright page."""
    url = player_overview_url(player_id, player_slug)
    items = goto_and_extract(
        page,
        url,
        selector=BIO_SELECTOR,
        js=_BIO_ITEMS_JS,
        max_retries=1,
    )
    data = items_to_bio(items or [])
    logger.info("Scraped player %s: %s", player_id, data)
    return data


async def async_scrape_player(
    page: AsyncPage,
    player_id: str,
    player_slug: str,
) -> dict:
    url = player_overview_url(player_id, player_slug)
    items = await async_goto_and_extract(
        page,
        url,
        selector=BIO_SELECTOR,
        js=_BIO_ITEMS_JS,
    )
    data = items_to_bio(items or [])
    logger.info("Scraped player %s: %s", player_id, data)
    return data


def scrape_players_batch(
    players: list[tuple[str, str]],
    max_retries: int = MAX_RETRIES,
    context=None,
    *,
    parallel: bool = True,
) -> dict[str, dict]:
    """
    Scrape multiple players.

    When ``parallel`` is True (default), uses a small pool of pages.
    ``context`` is only used for the sequential fallback path.
    """
    if not players:
        return {}

    if parallel:
        return _scrape_players_parallel(players)

    results: dict[str, dict] = {}

    def _run(ctx) -> dict[str, dict]:
        page = ctx.new_page()
        try:
            for player_id, player_slug in players:
                for attempt in range(max_retries):
                    try:
                        data = _scrape_player(page, player_id, player_slug)
                        if data:
                            results[player_id] = data
                        break
                    except PlaywrightTimeoutError:
                        logger.warning(
                            "Timeout scraping %s, attempt %s/%s",
                            player_id,
                            attempt + 1,
                            max_retries,
                        )
                        if attempt >= max_retries - 1:
                            logger.error(
                                "Failed to scrape player %s after %s attempts",
                                player_id,
                                max_retries,
                            )
                        else:
                            time.sleep(RETRY_BACKOFF_BASE ** attempt)
                    except Exception as e:
                        logger.error(
                            "Error scraping %s: %s: %s",
                            player_id,
                            type(e).__name__,
                            e,
                            exc_info=True,
                        )
                        break
        finally:
            page.close()
        return results

    if context is not None:
        return _run(context)
    with playwright_session() as ctx:
        return _run(ctx)


def _scrape_players_parallel(players: list[tuple[str, str]]) -> dict[str, dict]:
    async def worker(page, item: tuple[str, str]) -> tuple[str, dict]:
        player_id, player_slug = item
        data = await async_scrape_player(page, player_id, player_slug)
        return player_id, data

    outcomes = parallel_map(players, worker)
    results: dict[str, dict] = {}
    for item, outcome in zip(players, outcomes):
        player_id = item[0]
        if isinstance(outcome, BaseException):
            logger.error("Failed to scrape player %s: %s", player_id, outcome)
            continue
        pid, data = outcome
        if data:
            results[pid] = data
    return results
