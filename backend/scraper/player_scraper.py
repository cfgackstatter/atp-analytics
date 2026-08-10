# backend/scraper/player_scraper.py
"""Scrape ATP player biographical data."""

from __future__ import annotations

import logging
import re
import time

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from backend.scraper.config import MAX_RETRIES, PLAYER_OVERVIEW_URL, RETRY_BACKOFF_BASE
from backend.scraper.http_utils import goto_and_extract, playwright_session

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


def _scrape_player(page: Page, player_id: str, player_slug: str) -> dict:
    """Scrape one player using an existing Playwright page."""
    url = f"{PLAYER_OVERVIEW_URL}/{player_slug}/{player_id}/overview"
    items = goto_and_extract(
        page,
        url,
        selector="div.pd_content",
        js=_BIO_ITEMS_JS,
        max_retries=1,  # batch loop owns retries so we can log per player
    )

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

    logger.info("Scraped player %s: %s", player_id, data)
    return data


def scrape_players_batch(
    players: list[tuple[str, str]],
    max_retries: int = MAX_RETRIES,
    context=None,
) -> dict[str, dict]:
    """
    Scrape multiple players using a single shared browser page.

    Args:
        players: list of (player_id, player_slug)
        context: optional shared BrowserContext (reuses caller's session)
    Returns:
        Mapping of player_id -> scraped data dict
    """
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
