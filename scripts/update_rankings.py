#!/usr/bin/env python3
"""Update ATP rankings data."""

import sys
import logging

sys.path.append('.')

from backend.scraper.updater import update_rankings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_rankings.py RANKING_TYPE [MAX_WEEKS]")
        print("  RANKING_TYPE: singles or doubles")
        print("  MAX_WEEKS: optional, number of weeks to scrape")
        sys.exit(1)

    ranking_type = sys.argv[1]
    max_weeks = int(sys.argv[2]) if len(sys.argv) > 2 else None

    if ranking_type not in ['singles', 'doubles']:
        print("Error: RANKING_TYPE must be 'singles' or 'doubles'")
        sys.exit(1)

    scraped = update_rankings(ranking_type, max_weeks)
    print(f"\nCompleted: Scraped {scraped} weeks of {ranking_type} rankings")


if __name__ == "__main__":
    main()