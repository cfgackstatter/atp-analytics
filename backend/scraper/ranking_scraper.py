# backend/scraper/ranking_scraper.py
"""Scrape ATP rankings data."""

from __future__ import annotations

import logging

import polars as pl
from playwright.async_api import Page as AsyncPage
from playwright.sync_api import Page

from backend.scraper.config import RANKINGS_URLS
from backend.scraper.date_cache import load_ranking_dates, save_ranking_dates
from backend.scraper.http_utils import (
    async_goto_and_extract,
    goto_and_extract,
    owned_page,
)
from backend.scraper.parse_utils import parse_int
from backend.scraper.player_utils import extract_player_id, extract_player_slug
from backend.scraper.schemas import PLAYERS_SCHEMA, RANKINGS_SCHEMA
from backend.scraper.soft_fail import soft_fail

logger = logging.getLogger(__name__)

_DATES_JS = """
() => Array.from(
    document.querySelectorAll("select#dateWeek-filter option")
).map(o => ({ value: o.value, text: o.textContent.trim() }))
"""

_ROWS_JS = """
() => Array.from(
    document.querySelectorAll("table.desktop-table tbody tr.lower-row")
).map(row => ({
    rank:        row.querySelector(".rank")?.textContent.trim(),
    player_href: row.querySelector(".player a")?.href || null,
    player_name: row.querySelector(".player a span")?.textContent.trim(),
    points:      row.querySelector(".points")?.textContent.trim(),
    points_move: row.querySelector(".pointsMove")?.textContent.trim(),
    tourns:      row.querySelector(".tourns")?.textContent.trim(),
    drop:        row.querySelector(".drop")?.textContent.trim(),
    best:        row.querySelector(".best")?.textContent.trim(),
}))
"""

RANKINGS_ROW_SELECTOR = "table.desktop-table tbody tr.lower-row"


def ranking_page_url(ranking_type: str, date: str) -> str:
    return f"{RANKINGS_URLS[ranking_type]}?rankRange=0-5000&dateWeek={date}"


def _empty_frames() -> tuple[pl.DataFrame, pl.DataFrame]:
    return pl.DataFrame(schema=RANKINGS_SCHEMA), pl.DataFrame(schema=PLAYERS_SCHEMA)


def _options_to_dates(options: list[dict]) -> list[str]:
    dates: list[str] = []
    for opt in options:
        value = opt.get("value", "")
        if value == "Current Week":
            dates.append(opt.get("text", "").replace(".", "-"))
        elif value:
            dates.append(value)
    return dates


def rows_to_dataframes(
    rows: list[dict],
    ranking_type: str,
    date: str,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Convert evaluated ranking rows into rankings + players DataFrames."""
    if not rows:
        return _empty_frames()

    rankings_data = []
    players_data = []
    for row in rows:
        rank_text = (row.get("rank") or "").replace("T", "")
        href = row.get("player_href")
        player_id = extract_player_id(href)
        player_name = row.get("player_name") or None
        player_slug = extract_player_slug(href)

        rankings_data.append(
            {
                "rank": int(rank_text) if rank_text.isdigit() else None,
                "player_id": player_id,
                "points": parse_int(row.get("points")),
                "points_move": parse_int(row.get("points_move")),
                "tournaments_played": parse_int(row.get("tourns")),
                "dropping": parse_int(row.get("drop")),
                "next_best": parse_int(row.get("best")),
                "date": date,
                "type": ranking_type,
            }
        )
        if player_id and player_name:
            players_data.append(
                {
                    "player_id": player_id,
                    "player_name": player_name,
                    "player_slug": player_slug,
                }
            )

    return (
        pl.DataFrame(rankings_data, schema=RANKINGS_SCHEMA),
        pl.DataFrame(players_data, schema=PLAYERS_SCHEMA),
    )


def get_ranking_dates(
    ranking_type: str,
    context=None,
    page: Page | None = None,
    *,
    use_cache: bool = True,
) -> list[str]:
    """Extract all available ranking dates from dropdown (cached on disk)."""
    if use_cache:
        cached = load_ranking_dates(ranking_type)
        if cached is not None:
            return cached

    url = f"{RANKINGS_URLS[ranking_type]}?rankRange=0-5000"

    try:
        with owned_page(context, page) as p:
            options = goto_and_extract(
                p,
                url,
                selector="select#dateWeek-filter option",
                js=_DATES_JS,
            )
    except Exception as exc:
        return soft_fail(logger, f"ranking dates for {ranking_type}", exc, list)

    if not options:
        logger.warning("Dropdown not found for %s", ranking_type)
        return []

    dates = _options_to_dates(options)
    if dates and use_cache:
        save_ranking_dates(ranking_type, dates)
    return dates


def scrape_ranking(
    ranking_type: str,
    date: str,
    context=None,
    page: Page | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Scrape rankings for a specific date. Soft-fails to empty frames."""
    url = ranking_page_url(ranking_type, date)

    try:
        with owned_page(context, page) as p:
            rows = goto_and_extract(
                p,
                url,
                selector=RANKINGS_ROW_SELECTOR,
                js=_ROWS_JS,
            )
    except Exception as exc:
        return soft_fail(
            logger,
            f"{ranking_type} rankings for {date}",
            exc,
            _empty_frames,
        )

    rankings_df, players_df = rows_to_dataframes(rows or [], ranking_type, date)
    if len(rankings_df) == 0:
        logger.warning("No ranking rows found for %s", date)
    else:
        logger.info("Scraped %s rows for %s %s", len(rankings_df), ranking_type, date)
    return rankings_df, players_df


async def async_scrape_ranking(
    page: AsyncPage,
    ranking_type: str,
    date: str,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Async ranking scrape for a single week; soft-fails to empty frames."""
    url = ranking_page_url(ranking_type, date)
    try:
        rows = await async_goto_and_extract(
            page,
            url,
            selector=RANKINGS_ROW_SELECTOR,
            js=_ROWS_JS,
        )
    except Exception as exc:
        return soft_fail(
            logger,
            f"{ranking_type} rankings for {date}",
            exc,
            _empty_frames,
        )

    rankings_df, players_df = rows_to_dataframes(rows or [], ranking_type, date)
    if len(rankings_df) == 0:
        logger.warning("No ranking rows found for %s", date)
    else:
        logger.info("Scraped %s rows for %s %s", len(rankings_df), ranking_type, date)
    return rankings_df, players_df
