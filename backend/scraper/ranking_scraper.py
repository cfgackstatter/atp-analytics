# backend/scraper/ranking_scraper.py
"""Scrape ATP rankings data."""

import logging
import polars as pl
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from backend.scraper.config import RANKINGS_URLS
from backend.scraper.schemas import RANKINGS_SCHEMA, PLAYERS_SCHEMA
from backend.scraper.http_utils import playwright_session

logger = logging.getLogger(__name__)


def _parse_int(text: str | None) -> int | None:
    """Parse integer from scraped text, handling commas, +/-, '-', and 'T' prefix."""
    if not text:
        return None
    text = text.strip().replace(",", "").replace("T", "")
    if not text or text == "-":
        return None
    return int(text) if text.lstrip("-+").isdigit() else None


def get_ranking_dates(ranking_type: str, context=None) -> list[str]:
    """Extract all available ranking dates from dropdown."""
    url = f"{RANKINGS_URLS[ranking_type]}?rankRange=0-5000"

    def _fetch(ctx):
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="commit", timeout=20000)
            page.wait_for_selector(
                "select#dateWeek-filter option", state="attached", timeout=20000
            )
            return page.evaluate("""
                () => Array.from(
                    document.querySelectorAll("select#dateWeek-filter option")
                ).map(o => ({ value: o.value, text: o.textContent.trim() }))
            """)
        finally:
            page.close()

    try:
        if context is not None:
            options = _fetch(context)
        else:
            with playwright_session() as ctx:
                options = _fetch(ctx)
    except PlaywrightTimeoutError:
        logger.warning(f"Timeout fetching ranking dates for {ranking_type}")
        return []
    except Exception as e:
        logger.warning(f"Could not fetch ranking dates for {ranking_type}: {e}")
        return []

    if not options:
        logger.warning(f"Dropdown not found for {ranking_type}")
        return []

    dates = []
    for opt in options:
        value = opt.get("value", "")
        if value == "Current Week":
            # Text is e.g. "2026.05.25" → "2026-05-25"
            dates.append(opt.get("text", "").replace(".", "-"))
        elif value:
            dates.append(value)

    return dates


def scrape_ranking(ranking_type: str, date: str, context=None) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Scrape rankings for a specific date.

    Args:
        ranking_type: 'singles' or 'doubles'
        date: Date string (YYYY-MM-DD format)

    Returns:
        Tuple of (rankings_df, players_df). Returns empty DataFrames on failure.
    """
    url = f"{RANKINGS_URLS[ranking_type]}?rankRange=0-5000&dateWeek={date}"

    def _fetch(ctx):
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="commit", timeout=20000)
            page.wait_for_selector(
                "table.desktop-table tbody tr.lower-row", state="attached", timeout=20000
            )
            return page.evaluate("""
                () => Array.from(
                    document.querySelectorAll("table.desktop-table tbody tr.lower-row")
                ).map(row => ({
                    rank:        row.querySelector(".rank")?.textContent.trim(),
                    player_id:   row.querySelector(".player a")?.href.split("/").slice(-2)[0],
                    player_name: row.querySelector(".player a span")?.textContent.trim(),
                    points:      row.querySelector(".points")?.textContent.trim(),
                    points_move: row.querySelector(".pointsMove")?.textContent.trim(),
                    tourns:      row.querySelector(".tourns")?.textContent.trim(),
                    drop:        row.querySelector(".drop")?.textContent.trim(),
                    best:        row.querySelector(".best")?.textContent.trim(),
                }))
            """)
        finally:
            page.close()

    try:
        if context is not None:
            rows = _fetch(context)
        else:
            with playwright_session() as ctx:
                rows = _fetch(ctx)
    except PlaywrightTimeoutError:
        logger.warning(f"Timeout scraping {ranking_type} rankings for {date}")
        return pl.DataFrame(schema=RANKINGS_SCHEMA), pl.DataFrame(schema=PLAYERS_SCHEMA)
    except Exception as e:
        logger.warning(f"Skipping {date} due to error: {e}")
        return pl.DataFrame(schema=RANKINGS_SCHEMA), pl.DataFrame(schema=PLAYERS_SCHEMA)

    if not rows:
        logger.warning(f"No ranking rows found for {date}")
        return pl.DataFrame(schema=RANKINGS_SCHEMA), pl.DataFrame(schema=PLAYERS_SCHEMA)

    rankings_data = []
    players_data = []

    for row in rows:
        rank_text = (row.get("rank") or "").replace("T", "")
        player_id = row.get("player_id") or None
        player_name = row.get("player_name") or None

        rankings_data.append({
            "rank":                int(rank_text) if rank_text.isdigit() else None,
            "player_id":           player_id,
            "points":              _parse_int(row.get("points")),
            "points_move":         _parse_int(row.get("points_move")),
            "tournaments_played":  _parse_int(row.get("tourns")),
            "dropping":            _parse_int(row.get("drop")),
            "next_best":           _parse_int(row.get("best")),
            "date":                date,
            "type":                ranking_type,
        })

        if player_id and player_name:
            players_data.append({"player_id": player_id, "player_name": player_name})

    logger.info(f"Scraped {len(rankings_data)} rows for {ranking_type} {date}")
    return (
        pl.DataFrame(rankings_data, schema=RANKINGS_SCHEMA),
        pl.DataFrame(players_data, schema=PLAYERS_SCHEMA),
    )