"""Execute admin scrape jobs (intended to run in a dedicated subprocess)."""

from __future__ import annotations

import logging
from typing import Any, Callable

from backend.scraper.updater import (
    update_player_bio,
    update_rankings,
    update_tournaments,
)

logger = logging.getLogger(__name__)

JobHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _run_rankings(params: dict[str, Any]) -> dict[str, Any]:
    ranking_type = params["ranking_type"]
    max_weeks = params.get("max_weeks")
    weeks = update_rankings(ranking_type, max_weeks)
    return {
        "ranking_type": ranking_type,
        "weeks_scraped": weeks,
    }


def _run_tournaments(params: dict[str, Any]) -> dict[str, Any]:
    result = update_tournaments(
        start_year=params["start_year"],
        end_year=params["end_year"],
        types=params["types"],
    )
    return {
        "tournament_types": params["types"],
        **result,
    }


def _run_players(params: dict[str, Any]) -> dict[str, Any]:
    num_players = params["num_players"]
    updated = update_player_bio(num_players)
    return {
        "num_players": num_players,
        "players_updated": updated,
    }


HANDLERS: dict[str, JobHandler] = {
    "rankings": _run_rankings,
    "tournaments": _run_tournaments,
    "players": _run_players,
}


def run_job(job_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Run a scrape job and return a JSON-serializable result dict."""
    try:
        handler = HANDLERS[job_type]
    except KeyError as exc:
        raise ValueError(f"Unknown job type: {job_type!r}") from exc

    logger.info("Starting job type=%s params=%s", job_type, params)
    result = handler(params)
    logger.info("Finished job type=%s result=%s", job_type, result)
    return result
