#!/usr/bin/env python3
"""Update ATP tournament data."""

import logging
import sys

sys.path.append(".")

from backend.scraper.config import VALID_TOURNAMENT_TYPES
from backend.scraper.updater import update_tournaments

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/update_tournaments.py START_YEAR END_YEAR [TYPES]")
        print(f"Valid types: {', '.join(VALID_TOURNAMENT_TYPES)}")
        print("Example: python scripts/update_tournaments.py 2020 2025 atp,gs")
        sys.exit(1)

    start_year = int(sys.argv[1])
    end_year = int(sys.argv[2])
    types = sys.argv[3].split(",") if len(sys.argv) > 3 else ["atp"]

    invalid_types = [t for t in types if t not in VALID_TOURNAMENT_TYPES]
    if invalid_types:
        print(f"Error: Invalid tournament types: {', '.join(invalid_types)}")
        print(f"Valid types are: {', '.join(VALID_TOURNAMENT_TYPES)}")
        sys.exit(1)

    result = update_tournaments(start_year, end_year, types)
    print(
        f"\nCompleted: {result['tournaments_scraped']} scraped, "
        f"{result['total_tournaments']} total"
    )


if __name__ == "__main__":
    main()
