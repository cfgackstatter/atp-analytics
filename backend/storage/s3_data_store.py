# backend/storage/s3_data_store.py
"""Data storage utilities with S3 backend."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

import boto3
import polars as pl
from botocore.client import BaseClient

from backend.scraper.config import BIO_PRESENT_FIELDS

logger = logging.getLogger(__name__)

# Configuration
BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "atp-analytics-data")
USE_S3 = os.getenv("USE_S3", "true").lower() == "true"
LOCAL_DATA_DIR = Path("data")

_s3_client: Optional[BaseClient] = None


def _ensure_local_data_dir() -> Path:
    LOCAL_DATA_DIR.mkdir(exist_ok=True)
    return LOCAL_DATA_DIR


def _get_s3_client() -> BaseClient:
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _get_s3_key(filename: str) -> str:
    """Convert filename to S3 key."""
    return f"data/{filename}"


def save_data(df: pl.DataFrame, filename: str) -> None:
    """Save DataFrame to parquet (S3 or local)."""
    if USE_S3:
        client = _get_s3_client()
        buffer = BytesIO()
        df.write_parquet(buffer)
        buffer.seek(0)
        s3_key = _get_s3_key(filename)
        client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=buffer,
            ContentType="application/octet-stream",
        )
        logger.info(f"Saved {filename} to S3: s3://{BUCKET_NAME}/{s3_key}")
    else:
        path = _ensure_local_data_dir() / filename
        df.write_parquet(path)
        logger.info(f"Saved {filename} locally: {path}")


def load_data(filename: str) -> pl.DataFrame:
    """Load DataFrame from parquet (S3 or local)."""
    if USE_S3:
        client = _get_s3_client()
        s3_key = _get_s3_key(filename)
        try:
            response = client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            buffer = BytesIO(response["Body"].read())
            df = pl.read_parquet(buffer)
            logger.info(f"Loaded {filename} from S3")
            return df
        except client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"s3://{BUCKET_NAME}/{s3_key}") from None
    else:
        path = _ensure_local_data_dir() / filename
        if not path.exists():
            raise FileNotFoundError(str(path))
        return pl.read_parquet(path)


def load_data_or_empty(filename: str, schema: dict) -> pl.DataFrame:
    """Load DataFrame or return empty with schema."""
    try:
        return load_data(filename)
    except FileNotFoundError:
        return pl.DataFrame(schema=schema)


def upsert_data(
    new_df: pl.DataFrame,
    existing_df: pl.DataFrame,
    unique_cols: list[str],
) -> pl.DataFrame:
    """Combine and deduplicate data."""
    return pl.concat([existing_df, new_df]).unique(subset=unique_cols, keep="last")


def save_rankings(df: pl.DataFrame, ranking_type: str) -> None:
    """Save rankings data."""
    save_data(df, f"{ranking_type}_rankings.parquet")


def load_rankings(ranking_type: str, schema: dict | None = None) -> pl.DataFrame:
    """Load rankings data, optionally returning empty DataFrame with schema."""
    filename = f"{ranking_type}_rankings.parquet"
    if schema is not None:
        return load_data_or_empty(filename, schema)
    return load_data(filename)


def load_singles_rankings(schema: dict | None = None) -> pl.DataFrame:
    """Load singles rankings data."""
    return load_rankings("singles", schema)


def load_doubles_rankings(schema: dict | None = None) -> pl.DataFrame:
    """Load doubles rankings data."""
    return load_rankings("doubles", schema)


def save_players(df: pl.DataFrame) -> None:
    """Save players data."""
    save_data(df, "players.parquet")


def load_players(schema: dict | None = None) -> pl.DataFrame:
    """Load players data, optionally returning empty DataFrame with schema."""
    if schema is not None:
        return load_data_or_empty("players.parquet", schema)
    return load_data("players.parquet")


def save_tournaments(df: pl.DataFrame) -> None:
    """Save tournaments data."""
    save_data(df, "tournaments.parquet")


def load_tournaments(schema: dict | None = None) -> pl.DataFrame:
    """Load tournaments data, optionally returning empty DataFrame with schema."""
    if schema is not None:
        return load_data_or_empty("tournaments.parquet", schema)
    return load_data("tournaments.parquet")


def get_data_summary() -> dict:
    """Get summary statistics for all data files."""
    summary = {
        "bucket": BUCKET_NAME if USE_S3 else "local",
        "storage": "s3" if USE_S3 else "local",
        "use_s3": USE_S3,
    }

    try:
        df = load_data("singles_rankings.parquet")
        summary["rankings_singles"] = _ranking_summary(df)
    except FileNotFoundError:
        summary["rankings_singles"] = None

    try:
        df = load_data("doubles_rankings.parquet")
        summary["rankings_doubles"] = _ranking_summary(df)
    except FileNotFoundError:
        summary["rankings_doubles"] = None

    try:
        df = load_data("players.parquet")
        present = [f for f in BIO_PRESENT_FIELDS if f in df.columns]
        has_bio = (
            df.select(
                pl.any_horizontal([pl.col(field).is_not_null() for field in present])
            ).to_series()
            if present
            else pl.Series([], dtype=pl.Boolean)
        )

        with_bio = int(has_bio.sum()) if len(has_bio) > 0 else 0
        missing_bio = len(df) - with_bio

        countries = 0
        if "country" in df.columns:
            countries = df.select(pl.col("country").drop_nulls().n_unique()).item()

        with_birthdate = 0
        if "birthdate" in df.columns:
            with_birthdate = int(
                df.select(pl.col("birthdate").is_not_null().sum()).item()
            )

        summary["players"] = {
            "count": len(df),
            "with_bio": with_bio,
            "missing_bio": missing_bio,
            "bio_coverage_pct": round(100.0 * with_bio / len(df), 1) if len(df) else 0,
            "with_birthdate": with_birthdate,
            "missing_birthdate": len(df) - with_birthdate,
            "birthdate_coverage_pct": (
                round(100.0 * with_birthdate / len(df), 1) if len(df) else 0
            ),
            "countries": countries,
            "size": f"{df.estimated_size('mb'):.2f} MB",
        }
    except FileNotFoundError:
        summary["players"] = None
    except Exception as e:
        logger.error(f"Error processing players data: {e}")
        summary["players"] = {"error": str(e)}

    try:
        df = load_data("tournaments.parquet")

        year_range = None
        if "year" in df.columns:
            min_year = df.select(pl.col("year").min()).item()
            max_year = df.select(pl.col("year").max()).item()
            year_range = f"{min_year}-{max_year}"

        tournament_types = []
        counts_by_type: dict[str, int] = {}
        if "tournament_type" in df.columns:
            tournament_types = (
                df.select(pl.col("tournament_type").unique()).to_series().to_list()
            )
            for row in (
                df.group_by("tournament_type")
                .len()
                .sort("tournament_type")
                .iter_rows(named=True)
            ):
                counts_by_type[str(row["tournament_type"])] = int(row["len"])

        with_winners = 0
        if "singles_winner_name" in df.columns:
            with_winners = df.select(
                pl.col("singles_winner_name").is_not_null().sum()
            ).item()
        elif "singles_winner_id" in df.columns:
            with_winners = df.select(
                pl.col("singles_winner_id").is_not_null().sum()
            ).item()

        summary["tournaments"] = {
            "count": len(df),
            "year_range": year_range,
            "types": tournament_types,
            "counts_by_type": counts_by_type,
            "with_winners": with_winners,
            "winner_coverage_pct": (
                round(100.0 * with_winners / len(df), 1) if len(df) else 0
            ),
            "size": f"{df.estimated_size('mb'):.2f} MB",
        }
    except FileNotFoundError:
        summary["tournaments"] = None

    return summary


def _ranking_summary(df: pl.DataFrame) -> dict:
    min_date = df.select(pl.col("date").min()).item() if "date" in df.columns else None
    max_date = df.select(pl.col("date").max()).item() if "date" in df.columns else None
    unique_weeks = (
        df.select(pl.col("date").n_unique()).item() if "date" in df.columns else 0
    )
    unique_players = (
        df.select(pl.col("player_id").n_unique()).item()
        if "player_id" in df.columns
        else 0
    )
    stale_days = None
    if max_date:
        try:
            latest = datetime.strptime(str(max_date)[:10], "%Y-%m-%d").date()
            stale_days = (datetime.now(timezone.utc).date() - latest).days
        except ValueError:
            stale_days = None

    return {
        "count": len(df),
        "unique_players": unique_players,
        "unique_weeks": unique_weeks,
        "date_range": f"{min_date} to {max_date}" if min_date and max_date else None,
        "latest_date": max_date,
        "stale_days": stale_days,
        "size": f"{df.estimated_size('mb'):.2f} MB",
    }
