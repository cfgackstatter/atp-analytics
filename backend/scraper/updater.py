# backend/scraper/updater.py
"""Update logic for rankings, tournaments, and player biographical data."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import polars as pl

from backend.scraper.config import (
    BIO_COLUMNS,
    PLAYER_SCRAPE_COOLDOWN_DAYS,
    RANKING_CHECKPOINT_WEEKS,
    VALID_TOURNAMENT_TYPES,
)
from backend.scraper.http_utils import playwright_session
from backend.scraper.parallel import parallel_map
from backend.scraper.player_scraper import scrape_players_batch
from backend.scraper.player_utils import slug_for_player
from backend.scraper.ranking_scraper import async_scrape_ranking, get_ranking_dates
from backend.scraper.schemas import PLAYERS_SCHEMA, RANKINGS_SCHEMA, TOURNAMENTS_SCHEMA
from backend.scraper.tournament_scraper import (
    async_scrape_tournaments,
    year_type_already_complete,
)
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


def _chunked(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _merge_players_from_rankings(
    existing_players: pl.DataFrame,
    new_players: pl.DataFrame,
) -> pl.DataFrame:
    """Append new players and fill missing slugs from ranking hrefs."""
    existing_players = _ensure_schema_columns(existing_players, PLAYERS_SCHEMA)
    new_players = _ensure_schema_columns(new_players, PLAYERS_SCHEMA)

    slug_updates = new_players.select(["player_id", "player_slug"]).filter(
        pl.col("player_slug").is_not_null()
    )
    if len(slug_updates) > 0 and "player_slug" in existing_players.columns:
        joined = existing_players.join(
            slug_updates, on="player_id", how="left", suffix="_new"
        )
        existing_players = joined.with_columns(
            pl.coalesce([pl.col("player_slug"), pl.col("player_slug_new")]).alias(
                "player_slug"
            )
        ).drop("player_slug_new")

    existing_ids = set(existing_players["player_id"].to_list())
    truly_new = new_players.filter(~pl.col("player_id").is_in(existing_ids))
    if len(truly_new) == 0:
        return existing_players

    logger.info("Adding %s new players to players table", len(truly_new))
    return pl.concat([existing_players, truly_new])


def _merge_rankings_checkpoint(
    ranking_type: str,
    ranking_frames: list[pl.DataFrame],
    player_frames: list[pl.DataFrame],
) -> int:
    """Upsert a batch of scraped weeks under the write lock. Returns week count."""
    if not ranking_frames:
        return 0

    new_rankings = pl.concat(ranking_frames)
    new_players = (
        pl.concat(player_frames).unique(subset=PLAYERS_UNIQUE_COLS, keep="last")
        if player_frames
        else pl.DataFrame(schema=PLAYERS_SCHEMA)
    )
    new_players = _ensure_schema_columns(new_players, PLAYERS_SCHEMA)
    weeks = new_rankings.select("date").n_unique()

    with data_write_lock():
        existing = load_rankings(ranking_type, schema=RANKINGS_SCHEMA)
        combined_rankings = upsert_data(
            new_rankings, existing, RANKINGS_UNIQUE_COLS
        )
        save_rankings(combined_rankings, ranking_type)

        existing_players = load_players(schema=PLAYERS_SCHEMA)
        combined_players = _merge_players_from_rankings(existing_players, new_players)
        save_players(combined_players)

    logger.info("Checkpoint saved: %s ranking weeks for %s", weeks, ranking_type)
    return int(weeks)


def update_rankings(ranking_type: str, max_weeks: int | None = None) -> int:
    """
    Scrape missing rankings and merge into storage.

    Uses a cached week list, parallel page scrapes, and checkpointed saves.
    """
    with playwright_session(single_process=True) as ctx:
        page = ctx.new_page()
        try:
            all_dates = get_ranking_dates(ranking_type, page=page, use_cache=True)
        finally:
            page.close()

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
        "Scraping %s weeks for %s (checkpoint every %s)...",
        len(dates_to_scrape),
        ranking_type,
        RANKING_CHECKPOINT_WEEKS,
    )

    total_weeks = 0
    for chunk_idx, chunk in enumerate(
        _chunked(dates_to_scrape, RANKING_CHECKPOINT_WEEKS), start=1
    ):
        logger.info(
            "Rankings chunk %s: %s weeks (%s … %s)",
            chunk_idx,
            len(chunk),
            chunk[0],
            chunk[-1],
        )

        async def worker(page, date: str):
            return await async_scrape_ranking(page, ranking_type, date)

        outcomes = parallel_map(chunk, worker)
        ranking_frames: list[pl.DataFrame] = []
        player_frames: list[pl.DataFrame] = []

        for date, outcome in zip(chunk, outcomes):
            if isinstance(outcome, BaseException):
                logger.warning("Failed ranking week %s: %s", date, outcome)
                continue
            rankings_df, players_df = outcome
            if len(rankings_df) > 0:
                ranking_frames.append(rankings_df)
            if len(players_df) > 0:
                player_frames.append(players_df)

        total_weeks += _merge_rankings_checkpoint(
            ranking_type, ranking_frames, player_frames
        )

    if total_weeks == 0:
        logger.warning("No ranking data was successfully scraped")
        return 0

    logger.info("Successfully scraped %s weeks", total_weeks)
    return total_weeks


def update_tournaments(
    start_year: int,
    end_year: int,
    types: list[str],
) -> dict[str, int]:
    """
    Scrape tournaments for year/type ranges and upsert into storage.

    Skips past years/types that already look complete; always refreshes
    the current calendar year. Scrapes remaining units in parallel.
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

    existing_df = load_tournaments(schema=TOURNAMENTS_SCHEMA)
    current_year = datetime.now().year

    jobs: list[tuple[int, str]] = []
    skipped = 0
    for year in range(start_year, end_year + 1):
        for t_type in types:
            if year_type_already_complete(
                existing_df, year, t_type, current_year=current_year
            ):
                logger.info("Skipping %s %s (already complete)", t_type, year)
                skipped += 1
                continue
            jobs.append((year, t_type))

    if not jobs:
        logger.info(
            "Nothing to scrape (%s year/type combos already complete)",
            skipped,
        )
        return {
            "tournaments_scraped": 0,
            "total_tournaments": len(existing_df),
            "skipped": skipped,
        }

    logger.info(
        "Scraping %s tournament year/type jobs (%s skipped)...",
        len(jobs),
        skipped,
    )

    async def worker(page, job: tuple[int, str]):
        year, t_type = job
        return await async_scrape_tournaments(page, year, t_type)

    outcomes = parallel_map(jobs, worker)
    frames: list[pl.DataFrame] = []
    for job, outcome in zip(jobs, outcomes):
        if isinstance(outcome, BaseException):
            logger.warning("Failed tournaments %s %s: %s", job[1], job[0], outcome)
            continue
        if len(outcome) > 0:
            frames.append(outcome)

    if not frames:
        return {
            "tournaments_scraped": 0,
            "total_tournaments": len(existing_df),
            "skipped": skipped,
        }

    new_df = pl.concat(frames)

    with data_write_lock():
        latest_existing = load_tournaments(schema=TOURNAMENTS_SCHEMA)
        combined_df = upsert_data(new_df, latest_existing, TOURNAMENTS_UNIQUE_COLS)
        save_tournaments(combined_df)
        total = len(combined_df)

    return {
        "tournaments_scraped": len(new_df),
        "total_tournaments": total,
        "skipped": skipped,
    }


def _apply_bio_updates(
    players_df: pl.DataFrame,
    updates: list[dict],
) -> pl.DataFrame:
    """
    Fill only NULL bio fields from scraped updates (never overwrite existing).

    Always updates ``scrape_attempted_at`` (and slug when provided).
    """
    if not updates:
        return players_df

    players_df = _ensure_schema_columns(players_df, PLAYERS_SCHEMA)
    updates_df = _ensure_schema_columns(pl.DataFrame(updates), PLAYERS_SCHEMA)
    update_cols = ["player_id", *BIO_COLUMNS, "player_slug", "scrape_attempted_at"]
    updates_df = updates_df.select([c for c in update_cols if c in updates_df.columns])

    joined = players_df.join(updates_df, on="player_id", how="left", suffix="_new")

    coalesced: list[pl.Expr] = []
    drop_cols: list[str] = []
    for col in BIO_COLUMNS + ["player_slug"]:
        new_col = f"{col}_new"
        if new_col in joined.columns:
            coalesced.append(pl.coalesce([pl.col(col), pl.col(new_col)]).alias(col))
            drop_cols.append(new_col)

    if "scrape_attempted_at_new" in joined.columns:
        # Prefer the new attempt timestamp when present.
        coalesced.append(
            pl.coalesce(
                [pl.col("scrape_attempted_at_new"), pl.col("scrape_attempted_at")]
            ).alias("scrape_attempted_at")
        )
        drop_cols.append("scrape_attempted_at_new")

    if coalesced:
        joined = joined.with_columns(coalesced)
    if drop_cols:
        joined = joined.drop(drop_cols)

    return _ensure_schema_columns(joined, PLAYERS_SCHEMA)


def update_player_bio(num_players: int = 10) -> int:
    """
    Scrape biographical data for players missing info.

    Skips players attempted within PLAYER_SCRAPE_COOLDOWN_DAYS (including
    empty/failed pages). Prefers ATP slugs stored from ranking hrefs.
    """
    players_df = _ensure_schema_columns(
        load_players(schema=PLAYERS_SCHEMA), PLAYERS_SCHEMA
    )
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

    if PLAYER_SCRAPE_COOLDOWN_DAYS > 0:
        cutoff = (
            datetime.now() - timedelta(days=PLAYER_SCRAPE_COOLDOWN_DAYS)
        ).isoformat()
        missing = missing.filter(
            pl.col("scrape_attempted_at").is_null()
            | (pl.col("scrape_attempted_at") < cutoff)
        )

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
        slug = slug_for_player(name, stored_slug=row.get("player_slug"))
        players_to_scrape.append((pid, slug))
        player_name_map[pid] = name

    outcomes = scrape_players_batch(players_to_scrape, parallel=True)
    attempted_at = datetime.now().isoformat()

    updates: list[dict] = []
    ok_count = 0
    for outcome in outcomes:
        row = {
            "player_id": outcome.player_id,
            "player_name": player_name_map.get(outcome.player_id, outcome.player_id),
            "scrape_attempted_at": attempted_at,
            **outcome.data,
        }
        updates.append(row)
        if outcome.status == "ok":
            ok_count += 1

    if not updates:
        logger.warning("No player scrape outcomes to record")
        return 0

    with data_write_lock():
        players_df = load_players(schema=PLAYERS_SCHEMA)
        players_df = _ensure_schema_columns(players_df, PLAYERS_SCHEMA)
        players_df = _apply_bio_updates(players_df, updates)
        save_players(players_df)

    logger.info(
        "Player bio scrape done: %s ok, %s empty/failed (all attempts recorded)",
        ok_count,
        len(updates) - ok_count,
    )
    return ok_count
