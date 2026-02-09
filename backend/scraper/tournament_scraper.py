# backend/scraper/tournament_scraper.py
"""Scrape ATP tournament data."""

import logging
import re
from bs4 import BeautifulSoup
import polars as pl

from backend.scraper.config import (
    VALID_TOURNAMENT_TYPES,
    MONTH_MAP,
    RESULTS_ARCHIVE_URL
)
from backend.scraper.schemas import TOURNAMENTS_SCHEMA
from backend.scraper.http_utils import fetch_with_retry
from backend.scraper.player_utils import extract_player_id

logger = logging.getLogger(__name__)


def _parse_date_range(date_str: str) -> tuple[str | None, str | None]:
    """Parse tournament date range into start/end dates."""
    if not date_str:
        return None, None

    # Normalize spaces
    date_str = " ".join(date_str.split())

    # Single month: "3 - 9 January, 2022"
    if m := re.match(r'(\d+)\s*-\s*(\d+)\s+([A-Za-z]+),?\s+(\d{4})', date_str):
        start_day, end_day, month, year = m.groups()
        month_num = MONTH_MAP.get(month, '01')
        return (
            f"{year}-{month_num}-{start_day.zfill(2)}",
            f"{year}-{month_num}-{end_day.zfill(2)}",
        )

    # Cross-month, year only at end: "27 October - 2 November, 2025"
    if m := re.match(r'(\d+)\s+([A-Za-z]+)\s*-\s*(\d+)\s+([A-Za-z]+),?\s+(\d{4})', date_str):
        start_day, start_month, end_day, end_month, year = m.groups()
        start_month_num = MONTH_MAP.get(start_month, '01')
        end_month_num = MONTH_MAP.get(end_month, '01')
        return (
            f"{year}-{start_month_num}-{start_day.zfill(2)}",
            f"{year}-{end_month_num}-{end_day.zfill(2)}",
        )

    # Cross-month, years on both ends: "23 December, 2024 - 5 January, 2025"
    if m := re.match(
        r'(\d+)\s+([A-Za-z]+),?\s+(\d{4})\s*-\s*(\d+)\s+([A-Za-z]+),?\s+(\d{4})',
        date_str,
    ):
        start_day, start_month, start_year, end_day, end_month, end_year = m.groups()
        start_month_num = MONTH_MAP.get(start_month, '01')
        end_month_num = MONTH_MAP.get(end_month, '01')
        return (
            f"{start_year}-{start_month_num}-{start_day.zfill(2)}",
            f"{end_year}-{end_month_num}-{end_day.zfill(2)}",
        )

    return None, None


def scrape_tournaments(year: int, tournament_type: str = 'atp') -> pl.DataFrame:
    """
    Scrape tournaments for specific year and type.

    Args:
        year: Tournament year
        tournament_type: One of 'gs', 'atp', 'ch', 'fu'

    Returns:
        DataFrame of tournaments, empty on failure
    """
    if tournament_type not in VALID_TOURNAMENT_TYPES:
        raise ValueError(
            f"Invalid tournament type: {tournament_type}. "
            f"Must be one of {VALID_TOURNAMENT_TYPES}"
        )

    url = f"{RESULTS_ARCHIVE_URL}?year={year}&tournamentType={tournament_type}"
    response = fetch_with_retry(url)

    if response is None:
        logger.warning(f"Skipping {tournament_type} {year} due to connection issues")
        return pl.DataFrame(schema=TOURNAMENTS_SCHEMA)

    soup = BeautifulSoup(response.text, "html.parser")
    tournaments_data = []

    for events_list in soup.find_all('ul', class_='events'):
        for li in events_list.find_all('li', recursive=False):
            tournament_info = li.find('div', class_='tournament-info')
            if not tournament_info:
                continue

            # Extract basic info
            name_span = tournament_info.find('span', class_='name')
            tournament_name = name_span.text.strip() if name_span else None

            # Extract country code
            country_code = None
            if flag_svg := tournament_info.find('svg', class_='atp-flag'):
                if use_tag := flag_svg.find('use'):
                    if href := use_tag.get('href'):
                        if isinstance(href, str):
                            if match := re.search(r'#flag-([a-z]+)', href):
                                country_code = match.group(1).upper()

            # Extract venue and dates
            venue_span = tournament_info.find('span', class_='venue')
            venue = venue_span.text.strip().rstrip(' |').strip() if venue_span else None

            date_span = tournament_info.find('span', class_='Date')
            date_str = date_span.text.strip() if date_span else None
            start_date, end_date = _parse_date_range(date_str) if date_str else (None, None)

            # Extract winners
            singles_winner_id = None
            singles_winner_name = None
            doubles_winner_ids = []
            doubles_winner_names = []

            if cta_holder := li.find('div', class_='cta-holder'):
                for dl in cta_holder.find_all('dl', class_='winner'):
                    dt = dl.find('dt')
                    if not dt:
                        continue

                    if 'Singles' in dt.text:
                        if singles_link := dl.find('a'):
                            singles_winner_name = singles_link.text.strip()
                            singles_winner_id = extract_player_id(singles_link.get('href'))
                    elif 'Doubles' in dt.text:
                        for link in dl.find_all('a'):
                            doubles_winner_names.append(link.text.strip())
                            if player_id := extract_player_id(link.get('href')):
                                doubles_winner_ids.append(player_id)

            # Skip tournaments without winners (not completed yet)
            if not singles_winner_id and not doubles_winner_ids:
                continue

            tournaments_data.append({
                'year': year,
                'tournament_type': tournament_type,
                'tournament_name': tournament_name,
                'venue': venue,
                'country_code': country_code,
                'start_date': start_date,
                'end_date': end_date,
                'singles_winner_id': singles_winner_id,
                'singles_winner_name': singles_winner_name,
                'doubles_winner_ids': ','.join(doubles_winner_ids) if doubles_winner_ids else None,
                'doubles_winner_names': ','.join(doubles_winner_names) if doubles_winner_names else None,
            })

    return pl.DataFrame(tournaments_data, schema=TOURNAMENTS_SCHEMA)