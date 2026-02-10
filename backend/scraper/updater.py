# backend/scraper/updater.py
"""Update logic for rankings and player biographical data."""

import logging
import polars as pl

from backend.scraper.ranking_scraper import get_ranking_dates, scrape_ranking
from backend.scraper.player_scraper import scrape_player
from backend.scraper.config import BIO_COLUMNS
from backend.scraper.schemas import RANKINGS_SCHEMA, PLAYERS_SCHEMA
from backend.scraper.player_utils import generate_player_slug
from backend.storage.s3_data_store import (
    load_rankings, save_rankings,
    load_players, save_players,
    upsert_data
)

logger = logging.getLogger(__name__)


def _ensure_schema_columns(df: pl.DataFrame, schema: dict) -> pl.DataFrame:
    """Ensure DataFrame has all schema columns with null values for missing ones."""
    for col, dtype in schema.items():
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).cast(dtype).alias(col))
    return df.select(list(schema.keys()))


def update_rankings(ranking_type: str, max_weeks: int | None = None) -> int:
    """
    Scrape missing rankings.

    Args:
        ranking_type: 'singles' or 'doubles'
        max_weeks: Maximum number of weeks to scrape (None = all missing)

    Returns:
        Number of weeks successfully scraped
    """
    all_dates = get_ranking_dates(ranking_type)

    # Get existing dates
    existing = load_rankings(ranking_type, schema=RANKINGS_SCHEMA)
    scraped_dates = set(existing["date"].unique())

    # Find missing dates
    missing = sorted([d for d in all_dates if d not in scraped_dates], reverse=True)

    if not missing:
        logger.info(f"No missing {ranking_type} rankings to scrape")
        return 0

    dates_to_scrape = missing[:max_weeks] if max_weeks else missing
    logger.info(f"Scraping {len(dates_to_scrape)} weeks for {ranking_type}...")

    # Scrape data
    ranking_frames = []
    player_frames = []

    for i, date in enumerate(dates_to_scrape, 1):
        logger.info(f"  {i}/{len(dates_to_scrape)}: {date}")
        rankings_df, players_df = scrape_ranking(ranking_type, date)

        if len(rankings_df) > 0:
            ranking_frames.append(rankings_df)
        if len(players_df) > 0:
            player_frames.append(players_df)

    # Check if we got any data
    if not ranking_frames:
        logger.warning("No ranking data was successfully scraped")
        return 0

    # Combine new data
    new_rankings = pl.concat(ranking_frames)
    new_players = (
        pl.concat(player_frames).unique(subset=["player_id"], keep="last")
        if player_frames else pl.DataFrame(schema=PLAYERS_SCHEMA)
    )

    # Save rankings
    combined_rankings = pl.concat([existing, new_rankings])
    save_rankings(combined_rankings, ranking_type)

    # Update players - ensure schemas match
    existing_players = load_players(schema=PLAYERS_SCHEMA)
    new_players = _ensure_schema_columns(new_players, PLAYERS_SCHEMA)
    existing_players = _ensure_schema_columns(existing_players, PLAYERS_SCHEMA)

    combined_players = upsert_data(new_players, existing_players, ["player_id"])
    save_players(combined_players)

    logger.info(f"Successfully scraped {len(ranking_frames)} weeks")
    return len(ranking_frames)


def update_player_bio(num_players: int = 10) -> int:
    """
    Scrape biographical data for players missing info.

    Args:
        num_players: Number of top players to scrape

    Returns:
        Number of players successfully scraped
    """
    players_df = load_players(schema=PLAYERS_SCHEMA)

    # Load rankings to determine priority
    singles_df = load_rankings("singles", schema=RANKINGS_SCHEMA)
    doubles_df = load_rankings("doubles", schema=RANKINGS_SCHEMA)

    # Get best ranks (only if data exists)
    best_singles = (
        singles_df.sort("rank").group_by("player_id").agg([
            pl.col("rank").min().alias("best_singles_rank"),
            pl.col("date").first().alias("best_singles_date")
        ])
        if len(singles_df) > 0
        else pl.DataFrame(schema={
            "player_id": pl.String,
            "best_singles_rank": pl.Int64,
            "best_singles_date": pl.String
        })
    )

    best_doubles = (
        doubles_df.sort("rank").group_by("player_id").agg([
            pl.col("rank").min().alias("best_doubles_rank"),
            pl.col("date").first().alias("best_doubles_date")
        ])
        if len(doubles_df) > 0
        else pl.DataFrame(schema={
            "player_id": pl.String,
            "best_doubles_rank": pl.Int64,
            "best_doubles_date": pl.String
        })
    )

    # Enrich with rankings
    enriched = (
        players_df
        .join(best_singles, on="player_id", how="left")
        .join(best_doubles, on="player_id", how="left")
        .with_columns([
            pl.coalesce(["best_singles_rank", "best_doubles_rank"]).alias("best_rank"),
            pl.coalesce(["best_singles_date", "best_doubles_date"]).alias("best_rank_date")
        ])
    )

    # Filter for missing bio data
    bio_check_cols = ["birthdate", "weight_kg", "height_cm", "country", "handedness"]
    conditions = [pl.col(col).is_null() for col in bio_check_cols]
    missing = enriched.filter(pl.any_horizontal(conditions)) if conditions else enriched

    # Select top players by rank
    to_scrape = missing.sort(
        ["best_rank", "best_rank_date"],
        descending=[False, True],
        nulls_last=True
    ).head(num_players)

    if len(to_scrape) == 0:
        logger.info("No players need bio data updates")
        return 0

    logger.info(f"Scraping {len(to_scrape)} players...")

    # Scrape player data and collect updates
    updates = []
    for i, row in enumerate(to_scrape.iter_rows(named=True), 1):
        logger.info(f"  {i}/{len(to_scrape)}: {row['player_name']}")
        slug = generate_player_slug(row['player_name'])
        data = scrape_player(row['player_id'], slug)

        if data:
            # ✅ FIX: Add player_id AND player_name to preserve name
            data['player_id'] = row['player_id']
            data['player_name'] = row['player_name']  # ⭐ CRITICAL: Preserve the name!
            updates.append(data)

    if not updates:
        logger.warning("No player data was successfully scraped")
        return 0

    # Create updates DataFrame with all columns
    updates_df = pl.DataFrame(updates)
    updates_df = _ensure_schema_columns(updates_df, PLAYERS_SCHEMA)

    # ✅ FIX: Merge using selective update - only update NULL bio fields
    # Get the subset of columns that were actually scraped (bio fields only)
    bio_field_updates = {row['player_id']: row for row in updates}

    # Update players_df by filling in bio fields without overwriting names
    for player_id, update_data in bio_field_updates.items():
        players_df = players_df.with_columns([
            pl.when(pl.col("player_id") == player_id)
            .then(pl.lit(update_data.get(col)))
            .otherwise(pl.col(col))
            .alias(col)
            for col in BIO_COLUMNS if col in update_data
        ])

    save_players(players_df)
    logger.info(f"Successfully updated {len(updates)} players")
    return len(updates)