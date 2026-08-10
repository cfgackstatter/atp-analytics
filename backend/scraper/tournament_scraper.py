# backend/scraper/tournament_scraper.py
"""Scrape ATP tournament data."""

from __future__ import annotations

import logging
import re
from datetime import datetime

import polars as pl
from playwright.async_api import Page as AsyncPage
from playwright.sync_api import Page

from backend.scraper.config import MONTH_MAP, RESULTS_ARCHIVE_URL, VALID_TOURNAMENT_TYPES
from backend.scraper.http_utils import (
    async_goto_and_extract,
    goto_and_extract,
    owned_page,
)
from backend.scraper.player_utils import extract_player_id
from backend.scraper.schemas import TOURNAMENTS_SCHEMA
from backend.scraper.soft_fail import soft_fail

logger = logging.getLogger(__name__)

_EVENTS_JS = """
() => Array.from(document.querySelectorAll("ul.events li")).map(li => {
    const info = li.querySelector(".tournament-info");
    if (!info) return null;
    const flagUse = info.querySelector("svg.atp-flag use");
    const flagHref = flagUse?.getAttribute("href") || "";
    const flagMatch = flagHref.match(/#flag-([a-z]+)/);
    const winners = {};
    li.querySelectorAll(".cta-holder dl.winner").forEach(dl => {
        const label = dl.querySelector("dt")?.textContent || "";
        const links = Array.from(dl.querySelectorAll("a"));
        if (label.includes("Singles") && links[0]) {
            winners.singles_name = links[0].textContent.trim();
            winners.singles_href = links[0].href;
        } else if (label.includes("Doubles")) {
            winners.doubles_names = links.map(a => a.textContent.trim());
            winners.doubles_hrefs = links.map(a => a.href);
        }
    });
    return {
        name: info.querySelector(".name")?.textContent.trim(),
        venue: info.querySelector(".venue")?.textContent.trim().replace(/\\s*\\|\\s*$/, ""),
        date_str: info.querySelector(".Date")?.textContent.trim(),
        country_code: flagMatch ? flagMatch[1].toUpperCase() : null,
        ...winners,
    };
}).filter(Boolean)
"""

EVENTS_SELECTOR = "ul.events li"


def tournament_archive_url(year: int, tournament_type: str) -> str:
    return f"{RESULTS_ARCHIVE_URL}?year={year}&tournamentType={tournament_type}"


def _parse_date_range(date_str: str) -> tuple[str | None, str | None]:
    """Parse tournament date range into start/end dates."""
    if not date_str:
        return None, None
    date_str = " ".join(date_str.split())
    if m := re.match(r"(\d+)\s*-\s*(\d+)\s+([A-Za-z]+),?\s+(\d{4})", date_str):
        start_day, end_day, month, year = m.groups()
        month_num = MONTH_MAP.get(month, "01")
        return (
            f"{year}-{month_num}-{start_day.zfill(2)}",
            f"{year}-{month_num}-{end_day.zfill(2)}",
        )
    if m := re.match(
        r"(\d+)\s+([A-Za-z]+)\s*-\s*(\d+)\s+([A-Za-z]+),?\s+(\d{4})", date_str
    ):
        sd, sm, ed, em, year = m.groups()
        return (
            f"{year}-{MONTH_MAP.get(sm, '01')}-{sd.zfill(2)}",
            f"{year}-{MONTH_MAP.get(em, '01')}-{ed.zfill(2)}",
        )
    if m := re.match(
        r"(\d+)\s+([A-Za-z]+),?\s+(\d{4})\s*-\s*(\d+)\s+([A-Za-z]+),?\s+(\d{4})",
        date_str,
    ):
        sd, sm, sy, ed, em, ey = m.groups()
        return (
            f"{sy}-{MONTH_MAP.get(sm, '01')}-{sd.zfill(2)}",
            f"{ey}-{MONTH_MAP.get(em, '01')}-{ed.zfill(2)}",
        )
    return None, None


def rows_to_dataframe(rows: list[dict], year: int, tournament_type: str) -> pl.DataFrame:
    data = []
    for row in rows or []:
        singles_id = extract_player_id(row.get("singles_href"))
        if not singles_id and not row.get("doubles_hrefs"):
            continue
        doubles_hrefs = row.get("doubles_hrefs") or []
        doubles_ids = [pid for h in doubles_hrefs if (pid := extract_player_id(h))]
        start_date, end_date = _parse_date_range(row.get("date_str"))
        data.append(
            {
                "year": year,
                "tournament_type": tournament_type,
                "tournament_name": row.get("name"),
                "venue": row.get("venue"),
                "country_code": row.get("country_code"),
                "start_date": start_date,
                "end_date": end_date,
                "singles_winner_id": singles_id,
                "singles_winner_name": row.get("singles_name"),
                "doubles_winner_ids": ",".join(doubles_ids) or None,
                "doubles_winner_names": ",".join(row.get("doubles_names") or []) or None,
            }
        )
    return pl.DataFrame(data, schema=TOURNAMENTS_SCHEMA)


def year_type_already_complete(
    existing: pl.DataFrame,
    year: int,
    tournament_type: str,
    *,
    current_year: int | None = None,
) -> bool:
    """
    True when a past year/type can be skipped.

    Current calendar year is always refreshed. Past years are skipped if we
    already store at least one tournament with a singles winner.
    """
    now_year = current_year if current_year is not None else datetime.now().year
    if year >= now_year:
        return False
    if existing is None or len(existing) == 0:
        return False

    subset = existing.filter(
        (pl.col("year") == year) & (pl.col("tournament_type") == tournament_type)
    )
    if len(subset) == 0:
        return False
    winners = subset.filter(pl.col("singles_winner_id").is_not_null())
    return len(winners) > 0


def scrape_tournaments(
    year: int,
    tournament_type: str = "atp",
    context=None,
    page: Page | None = None,
) -> pl.DataFrame:
    """Scrape tournaments for a specific year and type. Soft-fails to empty."""
    if tournament_type not in VALID_TOURNAMENT_TYPES:
        raise ValueError(
            f"Invalid tournament type: {tournament_type}. "
            f"Must be one of {VALID_TOURNAMENT_TYPES}"
        )

    url = tournament_archive_url(year, tournament_type)

    try:
        with owned_page(context, page) as p:
            rows = goto_and_extract(
                p,
                url,
                selector=EVENTS_SELECTOR,
                js=_EVENTS_JS,
            )
    except Exception as exc:
        return soft_fail(
            logger,
            f"tournaments {tournament_type} {year}",
            exc,
            lambda: pl.DataFrame(schema=TOURNAMENTS_SCHEMA),
        )

    df = rows_to_dataframe(rows or [], year, tournament_type)
    logger.info("Scraped %s tournaments for %s %s", len(df), tournament_type, year)
    return df


async def async_scrape_tournaments(
    page: AsyncPage,
    year: int,
    tournament_type: str,
) -> pl.DataFrame:
    """Async tournament scrape; soft-fails to empty."""
    url = tournament_archive_url(year, tournament_type)
    try:
        rows = await async_goto_and_extract(
            page,
            url,
            selector=EVENTS_SELECTOR,
            js=_EVENTS_JS,
        )
    except Exception as exc:
        return soft_fail(
            logger,
            f"tournaments {tournament_type} {year}",
            exc,
            lambda: pl.DataFrame(schema=TOURNAMENTS_SCHEMA),
        )

    df = rows_to_dataframe(rows or [], year, tournament_type)
    logger.info("Scraped %s tournaments for %s %s", len(df), tournament_type, year)
    return df
