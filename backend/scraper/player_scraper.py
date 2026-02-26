# backend/scraper/player_scraper.py
"""Scrape ATP player biographical data."""

import logging
import re
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Route, Request
from bs4 import BeautifulSoup

from backend.scraper.config import PLAYER_OVERVIEW_URL, MAX_RETRIES

logger = logging.getLogger(__name__)


def _extract_date(text: str) -> str | None:
    """Extract YYYY/MM/DD date."""
    if match := re.search(r'(\d{4})/(\d{2})/(\d{2})', text):
        return match.group(0)
    return None


def _extract_weight_kg(text: str) -> int | None:
    """Extract weight in kg, converting from lbs if needed."""
    if match := re.search(r'\((\d+)kg\)', text):
        return int(match.group(1))
    if match := re.search(r'(\d+)\s*lbs', text):
        return round(int(match.group(1)) * 0.453592)
    return None


def _extract_height_cm(text: str) -> int | None:
    """Extract height in cm, converting from ft/in if needed."""
    if match := re.search(r'\((\d+)cm\)', text):
        return int(match.group(1))
    if match := re.search(r"(\d+)'(\d+)\"", text):
        feet, inches = int(match.group(1)), int(match.group(2))
        return round((feet * 12 + inches) * 2.54)
    return None


def _parse_plays(text: str) -> tuple[str | None, str | None]:
    """Extract handedness and backhand type."""
    handedness = (
        'Right-Handed' if 'Right-Handed' in text else
        'Left-Handed' if 'Left-Handed' in text else None
    )
    backhand = (
        'Two-Handed' if 'Two-Handed Backhand' in text else
        'One-Handed' if 'One-Handed Backhand' in text else None
    )
    return handedness, backhand


def _scrape_player_with_page(
    page,
    player_id: str,
    player_slug: str,
) -> dict:
    """Scrape player bio data using an existing Playwright page."""
    url = f"{PLAYER_OVERVIEW_URL}/{player_slug}/{player_id}/overview"

    logger.info(f"Navigating to {url} for player {player_id}")
    page.goto(url, wait_until="networkidle", timeout=30000)
    content = page.content()
    logger.info(f"Page loaded successfully for player {player_id}")

    soup = BeautifulSoup(content, "html.parser")
    pd_content = soup.find("div", class_="pd_content")

    if not pd_content:
        logger.warning(f"No bio content found for player {player_id}")
        return {}

    data: dict[str, object] = {}
    for li in pd_content.find_all("li"):
        spans = li.find_all("span", recursive=False)
        if len(spans) < 2:
            continue

        label = spans[0].get_text(strip=True)
        value = spans[1].get_text(strip=True)

        if label in ["Age", "DOB"]:
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

    logger.info(f"Successfully scraped player {player_id}: {data}")
    return data


def scrape_players_batch(players: list[tuple[str, str]], max_retries: int = MAX_RETRIES) -> dict[str, dict]:
    """
    Scrape multiple players using a single browser/context.

    Args:
        players: list of (player_id, player_slug)
        max_retries: retries per player

    Returns:
        Mapping player_id -> scraped data dict
    """
    results: dict[str, dict] = {}

    with sync_playwright() as p:
        logger.info(f"Launching shared Chromium browser for {len(players)} players")
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-extensions",
            ],
        )
        try:
            context = browser.new_context()

            # Reuse your resource blocking
            def handle_route(route, request):
                rtype = request.resource_type
                if rtype in {"image", "stylesheet", "font", "media"}:
                    route.abort()
                else:
                    route.continue_()

            # For performance, register the route once per context
            context.route("**/*", handle_route)

            for player_id, player_slug in players:
                for attempt in range(max_retries):
                    page = context.new_page()
                    try:
                        logger.info(
                            f"Batch scraping player {player_id} (attempt {attempt + 1}/{max_retries})"
                        )
                        data = _scrape_player_with_page(page, player_id, player_slug)
                        if data:
                            results[player_id] = data
                        break  # success, stop retry loop for this player
                    except PlaywrightTimeoutError:
                        logger.warning(
                            f"Timeout scraping player {player_id} in batch, "
                            f"attempt {attempt + 1}/{max_retries}"
                        )
                        if attempt == max_retries - 1:
                            logger.error(
                                f"Failed to scrape player {player_id} after {max_retries} attempts (batch)"
                            )
                    except Exception as e:
                        logger.error(
                            f"Unexpected error scraping player {player_id} in batch: "
                            f"{type(e).__name__}: {e}",
                            exc_info=True,
                        )
                        if attempt == max_retries - 1:
                            logger.error(
                                f"Giving up on player {player_id} after {max_retries} attempts (batch)"
                            )
                    finally:
                        page.close()

        finally:
            browser.close()

    return results