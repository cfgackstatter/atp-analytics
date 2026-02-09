#!/usr/bin/env python3
"""Update ATP tournament data."""

import sys
import logging

sys.path.append('.')

from backend.scraper.tournament_scraper import scrape_tournaments
from backend.scraper.config import VALID_TOURNAMENT_TYPES
from backend.scraper.schemas import TOURNAMENTS_SCHEMA
from backend.storage.data_store import load_tournaments, save_tournaments, upsert_data
import polars as pl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python scripts/update_tournaments.py START_YEAR END_YEAR [TYPES]")
        print(f"Valid types: {', '.join(VALID_TOURNAMENT_TYPES)}")
        print("Example: python scripts/update_tournaments.py 2020 2025 atp,gs")
        sys.exit(1)

    start_year = int(sys.argv[1])
    end_year = int(sys.argv[2])
    types = sys.argv[3].split(',') if len(sys.argv) > 3 else ['atp']

    # Validate types
    invalid_types = [t for t in types if t not in VALID_TOURNAMENT_TYPES]
    if invalid_types:
        print(f"Error: Invalid tournament types: {', '.join(invalid_types)}")
        print(f"Valid types are: {', '.join(VALID_TOURNAMENT_TYPES)}")
        sys.exit(1)

    # Scrape tournaments
    new_tournaments = []
    for year in range(start_year, end_year + 1):
        for t_type in types:
            logger.info(f"Scraping {t_type} {year}...")
            new_tournaments.append(scrape_tournaments(year, t_type))

    if not new_tournaments:
        logger.warning("No tournaments scraped")
        return

    new_df = pl.concat(new_tournaments)

    # Load existing and merge
    existing_df = load_tournaments(schema=TOURNAMENTS_SCHEMA)

    # Deduplicate by (year, type, name, start_date)
    combined_df = upsert_data(
        new_df,
        existing_df,
        ['year', 'tournament_type', 'tournament_name', 'start_date']
    )

    save_tournaments(combined_df)
    logger.info(f"Scraped {len(new_df)} tournaments, total: {len(combined_df)}")
    print(f"\nCompleted: {len(new_df)} new tournaments, {len(combined_df)} total")


if __name__ == "__main__":
    main()