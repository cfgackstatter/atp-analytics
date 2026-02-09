#!/usr/bin/env python3
"""Update ATP player biographical data."""

import sys
import logging

sys.path.append('.')

from backend.scraper.updater import update_player_bio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)


def main():
    """Main entry point."""
    num = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    scraped = update_player_bio(num)
    print(f"\nCompleted: Scraped {scraped} players")


if __name__ == "__main__":
    main()