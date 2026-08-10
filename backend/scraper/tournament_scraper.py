# backend/scraper/tournament_scraper.py
"""Scrape ATP tournament data."""

from __future__ import annotations

import logging
import re

import polars as pl
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from backend.scraper.config import MONTH_MAP, RESULTS_ARCHIVE_URL, VALID_TOURNAMENT_TYPES
from backend.scraper.http_utils import goto_and_extract, playwright_session
from backend.scraper.player_utils import extract_player_id
from backend.scraper.schemas import TOURNAMENTS_SCHEMA

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


def scrape_tournaments(
    year: int,
    tournament_type: str = "atp",
    context=None,
    page: Page | None = None,
) -> pl.DataFrame:
    """Scrape tournaments for a specific year and type using Playwright."""
    if tournament_type not in VALID_TOURNAMENT_TYPES:
        raise ValueError(
            f"Invalid tournament type: {tournament_type}. "
            f"Must be one of {VALID_TOURNAMENT_TYPES}"
        )

    url = f"{RESULTS_ARCHIVE_URL}?year={year}&tournamentType={tournament_type}"

    def _fetch(p: Page):
        return goto_and_extract(
            p,
            url,
            selector="ul.events li",
            js=_EVENTS_JS,
        )

    try:
        if page is not None:
            rows = _fetch(page)
        elif context is not None:
            owned = context.new_page()
            try:
                rows = _fetch(owned)
            finally:
                owned.close()
        else:
            with playwright_session() as ctx:
                owned = ctx.new_page()
                try:
                    rows = _fetch(owned)
                finally:
                    owned.close()
    except PlaywrightTimeoutError:
        logger.warning("Timeout scraping %s %s", tournament_type, year)
        return pl.DataFrame(schema=TOURNAMENTS_SCHEMA)
    except Exception as e:
        logger.warning("Skipping %s %s: %s", tournament_type, year, e)
        return pl.DataFrame(schema=TOURNAMENTS_SCHEMA)

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

    logger.info("Scraped %s tournaments for %s %s", len(data), tournament_type, year)
    return pl.DataFrame(data, schema=TOURNAMENTS_SCHEMA)
