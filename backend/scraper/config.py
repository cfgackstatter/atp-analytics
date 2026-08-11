# backend/scraper/config.py
"""Configuration and constants for scraping."""

from __future__ import annotations

import os

# Playwright navigation / selector waits (seconds → ms in http_utils)
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # Exponential backoff: 1s, 2s, 4s

# Parallel page navigations within one browser (2–3 is the sweet spot).
# Default 2 balances speed vs memory on small EB instances; raise locally if desired.
SCRAPE_CONCURRENCY = max(1, int(os.getenv("SCRAPE_CONCURRENCY", "2")))

# Persist ranking week dropdowns to avoid an extra navigation every job.
RANKING_DATE_CACHE_TTL_HOURS = float(os.getenv("RANKING_DATE_CACHE_TTL_HOURS", "12"))

# Merge/save rankings to storage after this many successful week scrapes.
RANKING_CHECKPOINT_WEEKS = max(1, int(os.getenv("RANKING_CHECKPOINT_WEEKS", "5")))

# Don't re-queue player bio scrapes for this many days after an attempt
# (including empty/failed pages), so broken slugs aren't hammered forever.
PLAYER_SCRAPE_COOLDOWN_DAYS = max(
    0, int(os.getenv("PLAYER_SCRAPE_COOLDOWN_DAYS", "7"))
)

# --single-process helps tiny hosts but breaks multi-page concurrency.
# Default: on when concurrency is 1, off when concurrency > 1. Override with env.
_SINGLE_PROCESS_ENV = os.getenv("PLAYWRIGHT_SINGLE_PROCESS", "").strip().lower()


def playwright_single_process() -> bool:
    if _SINGLE_PROCESS_ENV in {"1", "true", "yes", "on"}:
        return True
    if _SINGLE_PROCESS_ENV in {"0", "false", "no", "off"}:
        return False
    return SCRAPE_CONCURRENCY <= 1


# ATP Tour URLs
ATP_BASE_URL = "https://www.atptour.com"
RANKINGS_URLS = {
    "singles": f"{ATP_BASE_URL}/en/rankings/singles",
    "doubles": f"{ATP_BASE_URL}/en/rankings/doubles",
}
RESULTS_ARCHIVE_URL = f"{ATP_BASE_URL}/en/scores/results-archive"
PLAYER_OVERVIEW_URL = f"{ATP_BASE_URL}/en/players"

# Tournament Types
VALID_TOURNAMENT_TYPES = {"gs", "atp", "ch", "fu"}

# Month Mapping
MONTH_MAP = {
    "January": "01",
    "February": "02",
    "March": "03",
    "April": "04",
    "May": "05",
    "June": "06",
    "July": "07",
    "August": "08",
    "September": "09",
    "October": "10",
    "November": "11",
    "December": "12",
}

# Bio Data Columns
BIO_COLUMNS = [
    "birthdate",
    "weight_kg",
    "height_cm",
    "turned_pro",
    "country",
    "birthplace",
    "handedness",
    "backhand",
    "coach",
]

# Fields used to decide whether a player "has bio" / needs a scrape.
BIO_PRESENT_FIELDS = [
    "birthdate",
    "weight_kg",
    "height_cm",
    "country",
    "handedness",
]
