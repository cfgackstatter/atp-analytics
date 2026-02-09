# backend/scraper/ranking_scraper.py
"""Scrape ATP rankings data."""

import logging
from bs4 import BeautifulSoup, Tag
import polars as pl

from backend.scraper.config import RANKINGS_URLS
from backend.scraper.schemas import RANKINGS_SCHEMA, PLAYERS_SCHEMA
from backend.scraper.http_utils import fetch_with_retry

logger = logging.getLogger(__name__)


def get_ranking_dates(ranking_type: str) -> list[str]:
    """Extract all available ranking dates from dropdown."""
    url = f"{RANKINGS_URLS[ranking_type]}?rankRange=0-5000"
    response = fetch_with_retry(url)

    if response is None:
        logger.warning(f"Could not fetch ranking dates for {ranking_type}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    dropdown = soup.find("select", {"id": "dateWeek-filter"})

    if not isinstance(dropdown, Tag):
        logger.warning(f"Dropdown not found for {ranking_type}")
        return []

    dates = []
    for option in dropdown.find_all("option"):
        value = option.get("value")
        if isinstance(value, str):
            if value == "Current Week":
                # Parse the visible text (e.g., "2024.10.28")
                dates.append(option.text.strip().replace(".", "-"))
            else:
                dates.append(value)

    return dates


def _extract_int(cell: Tag | None) -> int | None:
    """Extract integer from cell, handling commas, +/-, and '-'."""
    if not isinstance(cell, Tag):
        return None
    text = cell.text.strip().replace(",", "")
    if not text or text == "-":
        return None
    return int(text) if text.lstrip("-+").isdigit() else None


def _find_cell(row: Tag, class_name: str) -> Tag | None:
    """Find cell by class substring."""
    cell = row.find("td", class_=lambda x: bool(x and class_name in x.split()))
    return cell if isinstance(cell, Tag) else None


def scrape_ranking(ranking_type: str, date: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Scrape rankings for specific date.

    Args:
        ranking_type: 'singles' or 'doubles'
        date: Date string (YYYY-MM-DD format)

    Returns:
        Tuple of (rankings_df, players_df). Returns empty DataFrames on failure.
    """
    url = f"{RANKINGS_URLS[ranking_type]}?rankRange=0-5000&dateWeek={date}"
    response = fetch_with_retry(url)

    if response is None:
        logger.warning(f"Skipping {date} due to connection issues")
        return (
            pl.DataFrame(schema=RANKINGS_SCHEMA),
            pl.DataFrame(schema=PLAYERS_SCHEMA)
        )

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", class_="desktop-table")

    if not isinstance(table, Tag):
        logger.warning(f"No ranking table found for {date}")
        return (
            pl.DataFrame(schema=RANKINGS_SCHEMA),
            pl.DataFrame(schema=PLAYERS_SCHEMA)
        )

    tbody = table.find("tbody")
    if not isinstance(tbody, Tag):
        logger.warning(f"Table body not found for {date}")
        return (
            pl.DataFrame(schema=RANKINGS_SCHEMA),
            pl.DataFrame(schema=PLAYERS_SCHEMA)
        )

    rankings_data = []
    players_data = []

    for row in tbody.find_all("tr", class_="lower-row"):
        # Extract rank
        rank_cell = _find_cell(row, "rank")
        rank_text = rank_cell.text.strip().replace("T", "") if rank_cell else ""

        # Extract player info
        player_cell = _find_cell(row, "player")
        player_id = None
        player_name = None

        if player_cell:
            player_link = player_cell.find("a")
            if isinstance(player_link, Tag):
                href = player_link.get("href")
                if isinstance(href, str):
                    player_id = href.split("/")[-2]
                name_span = player_link.find("span")
                if isinstance(name_span, Tag):
                    player_name = name_span.text.strip()

        rankings_data.append({
            "rank": int(rank_text) if rank_text.isdigit() else None,
            "player_id": player_id,
            "points": _extract_int(_find_cell(row, "points")),
            "points_move": _extract_int(_find_cell(row, "pointsMove")),
            "tournaments_played": _extract_int(_find_cell(row, "tourns")),
            "dropping": _extract_int(_find_cell(row, "drop")),
            "next_best": _extract_int(_find_cell(row, "best")),
            "date": date,
            "type": ranking_type,
        })

        if player_id and player_name:
            players_data.append({"player_id": player_id, "player_name": player_name})

    if not rankings_data:
        logger.warning(f"No ranking data found for {date}")
        return (
            pl.DataFrame(schema=RANKINGS_SCHEMA),
            pl.DataFrame(schema=PLAYERS_SCHEMA)
        )

    return (
        pl.DataFrame(rankings_data, schema=RANKINGS_SCHEMA),
        pl.DataFrame(players_data, schema=PLAYERS_SCHEMA)
    )