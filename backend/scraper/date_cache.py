"""Disk cache for ranking week-dropdown lists."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from backend.scraper.config import RANKING_DATE_CACHE_TTL_HOURS

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(os.getenv("RANKING_DATE_CACHE_DIR", "/tmp/atp-analytics-cache"))


def _cache_path(ranking_type: str) -> Path:
    return _CACHE_DIR / f"ranking_dates_{ranking_type}.json"


def load_ranking_dates(ranking_type: str) -> list[str] | None:
    """Return cached dates if present and fresh; otherwise None."""
    path = _cache_path(ranking_type)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None

    fetched_at = payload.get("fetched_at")
    dates = payload.get("dates")
    if not isinstance(fetched_at, (int, float)) or not isinstance(dates, list):
        return None

    age_hours = (time.time() - fetched_at) / 3600.0
    if age_hours > RANKING_DATE_CACHE_TTL_HOURS:
        logger.info(
            "Ranking date cache expired for %s (%.1fh old)",
            ranking_type,
            age_hours,
        )
        return None

    logger.info(
        "Using cached ranking dates for %s (%s weeks, %.1fh old)",
        ranking_type,
        len(dates),
        age_hours,
    )
    return [str(d) for d in dates]


def save_ranking_dates(ranking_type: str, dates: list[str]) -> None:
    """Persist ranking dates for later jobs."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(ranking_type)
    payload = {"fetched_at": time.time(), "dates": dates}
    path.write_text(json.dumps(payload), encoding="utf-8")
    logger.info("Cached %s ranking dates for %s", len(dates), ranking_type)
