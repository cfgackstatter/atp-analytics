# backend/scraper/player_scraper.py
"""Scrape ATP player biographical data."""

import logging
import re
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from backend.scraper.config import PLAYER_OVERVIEW_URL, MAX_RETRIES
from backend.scraper.http_utils import playwright_session

logger = logging.getLogger(__name__)


def _extract_date(text: str) -> str | None:
    if m := re.search(r'(\d{4})/(\d{2})/(\d{2})', text):
        return m.group(0)
    return None

def _extract_weight_kg(text: str) -> int | None:
    if m := re.search(r'\((\d+)kg\)', text):
        return int(m.group(1))
    if m := re.search(r'(\d+)\s*lbs', text):
        return round(int(m.group(1)) * 0.453592)
    return None

def _extract_height_cm(text: str) -> int | None:
    if m := re.search(r'\((\d+)cm\)', text):
        return int(m.group(1))
    if m := re.search(r"(\d+)'(\d+)\"", text):
        feet, inches = int(m.group(1)), int(m.group(2))
        return round((feet * 12 + inches) * 2.54)
    return None

def _parse_plays(text: str) -> tuple[str | None, str | None]:
    handedness = "Right-Handed" if "Right-Handed" in text else "Left-Handed" if "Left-Handed" in text else None
    backhand = "Two-Handed" if "Two-Handed Backhand" in text else "One-Handed" if "One-Handed Backhand" in text else None
    return handedness, backhand


def _scrape_player(page, player_id: str, player_slug: str) -> dict:
    """Scrape one player using an existing Playwright page."""
    url = f"{PLAYER_OVERVIEW_URL}/{player_slug}/{player_id}/overview"
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_selector("div.pd_content", timeout=15000)

    items = page.evaluate("""
        () => Array.from(
            document.querySelectorAll("div.pd_content li")
        ).map(li => {
            const spans = li.querySelectorAll(":scope > span");
            return spans.length >= 2
                ? { label: spans[0].textContent.trim(), value: spans[1].textContent.trim() }
                : null;
        }).filter(Boolean)
    """)

    data: dict = {}
    for item in items:
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

    logger.info(f"Scraped player {player_id}: {data}")
    return data


def scrape_players_batch(players: list[tuple[str, str]], max_retries: int = MAX_RETRIES) -> dict[str, dict]:
    """
    Scrape multiple players using a single shared browser session.

    Args:
        players: list of (player_id, player_slug)
    Returns:
        Mapping of player_id -> scraped data dict
    """
    results: dict[str, dict] = {}

    with playwright_session() as ctx:
        for player_id, player_slug in players:
            for attempt in range(max_retries):
                page = ctx.new_page()
                try:
                    data = _scrape_player(page, player_id, player_slug)
                    if data:
                        results[player_id] = data
                    break
                except PlaywrightTimeoutError:
                    logger.warning(f"Timeout scraping {player_id}, attempt {attempt + 1}/{max_retries}")
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to scrape player {player_id} after {max_retries} attempts")
                except Exception as e:
                    logger.error(f"Error scraping {player_id}: {type(e).__name__}: {e}", exc_info=True)
                    break
                finally:
                    page.close()

    return results