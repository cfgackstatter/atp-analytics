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
    """Get comprehensive summary statistics for all data files."""
    from datetime import datetime
    from typing import Any, Dict, Optional

    summary: Dict[str, Any] = {
        "storage": "s3" if USE_S3 else "local",
        "timestamp": datetime.now().isoformat()
    }

    # Helper function to format file size
    def format_file_size(filename: str) -> str:
        """Get file size in human-readable format."""
        if USE_S3:
            # Check if s3_client is available
            if s3_client is None:
                return "N/A"

            try:
                s3_key = _get_s3_key(filename)
                response = s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
                size_bytes = response['ContentLength']
            except Exception:
                return "N/A"
        else:
            path = LOCAL_DATA_DIR / filename
            if not path.exists():
                return "N/A"
            size_bytes = path.stat().st_size

        # Convert to human-readable format
        size_float = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_float < 1024.0:
                return f"{size_float:.1f} {unit}"
            size_float /= 1024.0
        return f"{size_float:.1f} TB"

    # === PLAYERS ===
    try:
        players_df = load_players()

        # Count players with bio data (those with birthdate)
        has_bio = players_df.filter(pl.col("birthdate").is_not_null())
        missing_bio = len(players_df) - len(has_bio)

        # Count unique countries
        countries = players_df.filter(
            pl.col("country_code").is_not_null()
        )["country_code"].n_unique()

        summary["players"] = {
            "count": len(players_df),
            "with_bio": len(has_bio),
            "missing_bio": missing_bio,
            "countries": countries,
            "size": format_file_size("players.parquet")
        }
    except FileNotFoundError:
        summary["players"] = None
    except Exception as e:
        logger.error(f"Error loading players data: {e}")
        summary["players"] = None

    # === SINGLES RANKINGS ===
    try:
        singles_df = load_data("singles_rankings.parquet")

        min_date = singles_df.select(pl.col("date").min()).item()
        max_date = singles_df.select(pl.col("date").max()).item()
        unique_players = singles_df["player_id"].n_unique()

        summary["rankings_singles"] = {
            "count": len(singles_df),
            "unique_players": unique_players,
            "date_range": f"{min_date} to {max_date}",
            "latest_date": str(max_date),
            "size": format_file_size("singles_rankings.parquet")
        }
    except FileNotFoundError:
        summary["rankings_singles"] = None
    except Exception as e:
        logger.error(f"Error loading singles rankings: {e}")
        summary["rankings_singles"] = None

    # === DOUBLES RANKINGS ===
    try:
        doubles_df = load_data("doubles_rankings.parquet")

        min_date = doubles_df.select(pl.col("date").min()).item()
        max_date = doubles_df.select(pl.col("date").max()).item()
        unique_players = doubles_df["player_id"].n_unique()

        summary["rankings_doubles"] = {
            "count": len(doubles_df),
            "unique_players": unique_players,
            "date_range": f"{min_date} to {max_date}",
            "latest_date": str(max_date),
            "size": format_file_size("doubles_rankings.parquet")
        }
    except FileNotFoundError:
        summary["rankings_doubles"] = None
    except Exception as e:
        logger.error(f"Error loading doubles rankings: {e}")
        summary["rankings_doubles"] = None

    # === TOURNAMENTS ===
    try:
        tournaments_df = load_tournaments()

        # Get year range
        min_year = tournaments_df.select(pl.col("year").min()).item()
        max_year = tournaments_df.select(pl.col("year").max()).item()

        # Get unique tournament types
        types = tournaments_df["tournament_type"].unique().sort().to_list()

        # Count tournaments with winners
        has_singles_winner = "singles_winner_id" in tournaments_df.columns
        has_doubles_winner = "doubles_winner_ids" in tournaments_df.columns

        if has_singles_winner and has_doubles_winner:
            with_winners = tournaments_df.filter(
                (pl.col("singles_winner_id").is_not_null()) |
                (pl.col("doubles_winner_ids").is_not_null())
            )
        elif has_singles_winner:
            with_winners = tournaments_df.filter(
                pl.col("singles_winner_id").is_not_null()
            )
        elif has_doubles_winner:
            with_winners = tournaments_df.filter(
                pl.col("doubles_winner_ids").is_not_null()
            )
        else:
            with_winners = pl.DataFrame()

        summary["tournaments"] = {
            "count": len(tournaments_df),
            "year_range": f"{min_year}-{max_year}",
            "types": types,
            "with_winners": len(with_winners),
            "size": format_file_size("tournaments.parquet")
        }
    except FileNotFoundError:
        summary["tournaments"] = None
    except Exception as e:
        logger.error(f"Error loading tournaments: {e}")
        summary["tournaments"] = None

    return summary