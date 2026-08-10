# backend/scraper/updater.py
"""Update logic for rankings, tournaments, and player biographical data."""

from __future__ import annotations

import logging

import polars as pl

from backend.scraper.config import BIO_COLUMNS, VALID_TOURNAMENT_TYPES
from backend.scraper.http_utils import playwright_session
from backend.scraper.player_scraper import scrape_players_batch
from backend.scraper.player_utils import generate_player_slug
from backend.scraper.ranking_scraper import get_ranking_dates, scrape_ranking
from backend.scraper.schemas import PLAYERS_SCHEMA, RANKINGS_SCHEMA, TOURNAMENTS_SCHEMA
from backend.scraper.tournament_scraper import scrape_tournaments
from backend.storage.s3_data_store import (
    load_players,
    load_rankings,
    load_tournaments,
    save_players,
    save_rankings,
    save_tournaments,
    upsert_data,
)
from backend.storage.write_lock import data_write_lock

logger = logging.getLogger(__name__)

RANKINGS_UNIQUE_COLS = ["player_id", "date"]
PLAYERS_UNIQUE_COLS = ["player_id"]
TOURNAMENTS_UNIQUE_COLS = [
    "year",
    "tournament_type",
    "tournament_name",
    "start_date",
]


def _ensure_schema_columns(df: pl.DataFrame, schema: dict) -> pl.DataFrame:
    """Ensure DataFrame has all schema columns; select canonical column order."""
    for col, dtype in schema.items():
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).cast(dtype).alias(col))
    return df.select(list(schema.keys()))


def update_rankings(ranking_type: str, max_weeks: int | None = None) -> int:
    """
    Scrape missing rankings and merge into storage.

    Scraping runs without the write lock; the final load/merge/save is locked
    so concurrent jobs cannot clobber each other.
    """
    ranking_frames: list[pl.DataFrame] = []
    player_frames: list[pl.DataFrame] = []

    with playwright_session() as ctx:
        page = ctx.new_page()
        try:
            all_dates = get_ranking_dates(ranking_type, page=page)

            existing = load_rankings(ranking_type, schema=RANKINGS_SCHEMA)
            scraped_dates = set(existing["date"].unique())
            missing = sorted(
                (d for d in all_dates if d not in scraped_dates),
                reverse=True,
            )

            if not missing:
                logger.info("No missing %s rankings to scrape", ranking_type)
                return 0

            dates_to_scrape = missing[:max_weeks] if max_weeks else missing
            logger.info(
                "Scraping %s weeks for %s...",
                len(dates_to_scrape),
                ranking_type,
            )

            for i, date in enumerate(dates_to_scrape, 1):
                logger.info("  %s/%s: %s", i, len(dates_to_scrape), date)
                rankings_df, players_df = scrape_ranking(
                    ranking_type, date, page=page
                )
                if len(rankings_df) > 0:
                    ranking_frames.append(rankings_df)
                if len(players_df) > 0:
                    player_frames.append(players_df)
        finally:
            page.close()

    if not ranking_frames:
        logger.warning("No ranking data was successfully scraped")
        return 0

    new_rankings = pl.concat(ranking_frames)
    new_players = (
        pl.concat(player_frames).unique(subset=PLAYERS_UNIQUE_COLS, keep="last")
        if player_frames
        else pl.DataFrame(schema=PLAYERS_SCHEMA)
    )
    new_players = _ensure_schema_columns(new_players, PLAYERS_SCHEMA)

    with data_write_lock():
        existing = load_rankings(ranking_type, schema=RANKINGS_SCHEMA)
        combined_rankings = upsert_data(
            new_rankings, existing, RANKINGS_UNIQUE_COLS
        )
        save_rankings(combined_rankings, ranking_type)

        existing_players = _ensure_schema_columns(
            load_players(schema=PLAYERS_SCHEMA),
            PLAYERS_SCHEMA,
        )
        existing_ids = set(existing_players["player_id"].to_list())
        truly_new = new_players.filter(~pl.col("player_id").is_in(existing_ids))

        if len(truly_new) > 0:
            combined_players = pl.concat([existing_players, truly_new])
            logger.info("Adding %s new players to players table", len(truly_new))
            save_players(combined_players)
        else:
            logger.info("No new players to add")

    logger.info("Successfully scraped %s weeks", len(ranking_frames))
    return len(ranking_frames)


def update_tournaments(
    start_year: int,
    end_year: int,
    types: list[str],
) -> dict[str, int]:
    """
    Scrape tournaments for year/type ranges and upsert into storage.

    Returns counts: tournaments_scraped, total_tournaments.
    """
    invalid = [t for t in types if t not in VALID_TOURNAMENT_TYPES]
    if invalid:
        raise ValueError(
            f"Invalid tournament types: {invalid}. Valid: {VALID_TOURNAMENT_TYPES}"
        )
    if not types:
        raise ValueError("At least one tournament type is required")
    if start_year > end_year:
        raise ValueError("start_year must be <= end_year")

    frames: list[pl.DataFrame] = []
    with playwright_session() as ctx:
        page = ctx.new_page()
        try:
            for year in range(start_year, end_year + 1):
                for t_type in types:
                    logger.info("Scraping %s %s...", t_type, year)
                    frames.append(
                        scrape_tournaments(year, t_type, page=page)
                    )
        finally:
            page.close()

    if not frames:
        return {"tournaments_scraped": 0, "total_tournaments": 0}

    new_df = pl.concat(frames)

    with data_write_lock():
        existing_df = load_tournaments(schema=TOURNAMENTS_SCHEMA)
        combined_df = upsert_data(new_df, existing_df, TOURNAMENTS_UNIQUE_COLS)
        save_tournaments(combined_df)
        total = len(combined_df)

    return {
        "tournaments_scraped": len(new_df),
        "total_tournaments": total,
    }


def _apply_bio_updates(
    players_df: pl.DataFrame,
    updates: list[dict],
) -> pl.DataFrame:
    """Fill only NULL bio fields from scraped updates (never overwrite existing)."""
    for update_data in updates:
        player_id = update_data["player_id"]
        for col in BIO_COLUMNS:
            if col not in update_data:
                continue
            new_val = update_data.get(col)
            if new_val is None:
                continue
            players_df = players_df.with_columns(
                pl.when(
                    (pl.col("player_id") == player_id) & pl.col(col).is_null()
                )
                .then(pl.lit(new_val))
                .otherwise(pl.col(col))
                .alias(col)
            )
    return players_df


def update_player_bio(num_players: int = 10) -> int:
    """
    Scrape biographical data for players missing info.

    Returns number of players successfully scraped.
    """
    players_df = load_players(schema=PLAYERS_SCHEMA)
    singles_df = load_rankings("singles", schema=RANKINGS_SCHEMA)
    doubles_df = load_rankings("doubles", schema=RANKINGS_SCHEMA)

    best_singles = (
        singles_df.sort("rank")
        .group_by("player_id")
        .agg(
            [
                pl.col("rank").min().alias("best_singles_rank"),
                pl.col("date").first().alias("best_singles_date"),
            ]
        )
        if len(singles_df) > 0
        else pl.DataFrame(
            schema={
                "player_id": pl.String,
                "best_singles_rank": pl.Int64,
                "best_singles_date": pl.String,
            }
        )
    )

    best_doubles = (
        doubles_df.sort("rank")
        .group_by("player_id")
        .agg(
            [
                pl.col("rank").min().alias("best_doubles_rank"),
                pl.col("date").first().alias("best_doubles_date"),
            ]
        )
        if len(doubles_df) > 0
        else pl.DataFrame(
            schema={
                "player_id": pl.String,
                "best_doubles_rank": pl.Int64,
                "best_doubles_date": pl.String,
            }
        )
    )

    enriched = (
        players_df.join(best_singles, on="player_id", how="left")
        .join(best_doubles, on="player_id", how="left")
        .with_columns(
            [
                pl.coalesce(["best_singles_rank", "best_doubles_rank"]).alias(
                    "best_rank"
                ),
                pl.coalesce(["best_singles_date", "best_doubles_date"]).alias(
                    "best_rank_date"
                ),
            ]
        )
    )

    bio_check_cols = ["birthdate", "weight_kg", "height_cm", "country", "handedness"]
    conditions = [pl.col(col).is_null() for col in bio_check_cols]
    missing = enriched.filter(pl.any_horizontal(conditions)) if conditions else enriched

    to_scrape = missing.sort(
        ["best_rank", "best_rank_date"],
        descending=[False, True],
        nulls_last=True,
    ).head(num_players)

    if len(to_scrape) == 0:
        logger.info("No players need bio data updates")
        return 0

    logger.info("Scraping %s players...", len(to_scrape))

    players_to_scrape: list[tuple[str, str]] = []
    player_name_map: dict[str, str] = {}
    for row in to_scrape.iter_rows(named=True):
        pid = row["player_id"]
        name = row["player_name"]
        players_to_scrape.append((pid, generate_player_slug(name)))
        player_name_map[pid] = name

    with playwright_session() as ctx:
        batch_results = scrape_players_batch(players_to_scrape, context=ctx)

    updates: list[dict] = []
    for pid, data in batch_results.items():
        if data:
            data["player_id"] = pid
            data["player_name"] = player_name_map.get(pid, pid)
            updates.append(data)

    if not updates:
        logger.warning("No player data was successfully scraped")
        return 0

    with data_write_lock():
        players_df = load_players(schema=PLAYERS_SCHEMA)
        players_df = _ensure_schema_columns(players_df, PLAYERS_SCHEMA)
        players_df = _apply_bio_updates(players_df, updates)
        save_players(players_df)

    logger.info("Successfully updated %s players", len(updates))
    return len(updates)
