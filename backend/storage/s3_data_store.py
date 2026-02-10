# backend/storage/s3_data_store.py
"""Data storage utilities with S3 backend."""

import polars as pl
import boto3
import os
from pathlib import Path
from io import BytesIO
import logging
from botocore.client import BaseClient
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration
BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "atp-analytics-data")
USE_S3 = os.getenv("USE_S3", "true").lower() == "true"
LOCAL_DATA_DIR = Path("data")
LOCAL_DATA_DIR.mkdir(exist_ok=True)

# Initialize S3 client (only if using S3)
s3_client: Optional[BaseClient] = boto3.client("s3") if USE_S3 else None


def _get_s3_key(filename: str) -> str:
    """Convert filename to S3 key."""
    return f"data/{filename}"


def save_data(df: pl.DataFrame, filename: str) -> None:
    """Save DataFrame to parquet (S3 or local)."""
    if USE_S3:
        assert s3_client is not None

        # Write to bytes buffer
        buffer = BytesIO()
        df.write_parquet(buffer)
        buffer.seek(0)

        # Upload to S3
        s3_key = _get_s3_key(filename)
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=buffer.getvalue(),
            ContentType="application/octet-stream"
        )
        logger.info(f"Saved {filename} to S3: s3://{BUCKET_NAME}/{s3_key}")
    else:
        # Save locally
        path = LOCAL_DATA_DIR / filename
        df.write_parquet(path)
        logger.info(f"Saved {filename} locally: {path}")


def load_data(filename: str) -> pl.DataFrame:
    """Load DataFrame from parquet (S3 or local)."""
    if USE_S3:
        assert s3_client is not None

        s3_key = _get_s3_key(filename)
        try:
            # Download from S3
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            buffer = BytesIO(response["Body"].read())
            df = pl.read_parquet(buffer)
            logger.info(f"Loaded {filename} from S3")
            return df
        except s3_client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"s3://{BUCKET_NAME}/{s3_key}")
    else:
        # Load locally
        path = LOCAL_DATA_DIR / filename
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
    unique_cols: list[str]
) -> pl.DataFrame:
    """Combine and deduplicate data."""
    return pl.concat([existing_df, new_df]).unique(subset=unique_cols, keep="last")


# Convenience functions for specific data types
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

    # Singles Rankings
    try:
        df = load_data("singles_rankings.parquet")
        min_date = df.select(pl.col("date").min()).item() if "date" in df.columns else None
        max_date = df.select(pl.col("date").max()).item() if "date" in df.columns else None
        summary["rankings_singles"] = {
            "count": len(df),
            "unique_players": df.select(pl.col("player_id").n_unique()).item() if "player_id" in df.columns else 0,
            "date_range": f"{min_date} to {max_date}" if min_date and max_date else None,
            "latest_date": max_date,
            "size": f"{df.estimated_size('mb'):.2f} MB"
        }
    except FileNotFoundError:
        summary["rankings_singles"] = None

    # Doubles Rankings
    try:
        df = load_data("doubles_rankings.parquet")
        min_date = df.select(pl.col("date").min()).item() if "date" in df.columns else None
        max_date = df.select(pl.col("date").max()).item() if "date" in df.columns else None
        summary["rankings_doubles"] = {
            "count": len(df),
            "unique_players": df.select(pl.col("player_id").n_unique()).item() if "player_id" in df.columns else 0,
            "date_range": f"{min_date} to {max_date}" if min_date and max_date else None,
            "latest_date": max_date,
            "size": f"{df.estimated_size('mb'):.2f} MB"
        }
    except FileNotFoundError:
        summary["rankings_doubles"] = None

    # Players
    try:
        df = load_data("players.parquet")

        # Count players with bio data (at least one bio field filled)
        bio_fields = ["birthdate", "weight_kg", "height_cm", "country", "handedness"]
        has_bio = df.select(
            pl.any_horizontal([pl.col(field).is_not_null() for field in bio_fields if field in df.columns])
        ).to_series()

        with_bio = has_bio.sum() if len(has_bio) > 0 else 0
        missing_bio = len(df) - with_bio

        # Count unique countries (use "country" column, not "country_code")
        countries = 0
        if "country" in df.columns:
            countries = df.select(pl.col("country").n_unique()).item()

        summary["players"] = {
            "count": len(df),
            "with_bio": int(with_bio),
            "missing_bio": int(missing_bio),
            "countries": countries,
            "size": f"{df.estimated_size('mb'):.2f} MB"
        }
    except FileNotFoundError:
        summary["players"] = None
    except Exception as e:
        logger.error(f"Error processing players data: {e}")
        summary["players"] = {"error": str(e)}

    # Tournaments
    try:
        df = load_data("tournaments.parquet")

        year_range = None
        if "year" in df.columns:
            min_year = df.select(pl.col("year").min()).item()
            max_year = df.select(pl.col("year").max()).item()
            year_range = f"{min_year}-{max_year}"

        tournament_types = []
        if "tournament_type" in df.columns:
            tournament_types = df.select(pl.col("tournament_type").unique()).to_series().to_list()

        with_winners = 0
        if "winner_name" in df.columns:
            with_winners = df.select(pl.col("winner_name").is_not_null().sum()).item()

        summary["tournaments"] = {
            "count": len(df),
            "year_range": year_range,
            "types": tournament_types,
            "with_winners": with_winners,
            "size": f"{df.estimated_size('mb'):.2f} MB"
        }
    except FileNotFoundError:
        summary["tournaments"] = None

    return summary