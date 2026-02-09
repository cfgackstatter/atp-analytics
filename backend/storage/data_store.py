# backend/storage/data_store.py
"""Data storage utilities with schema-aware loading."""

import polars as pl
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def save_data(df: pl.DataFrame, filename: str) -> None:
    """Save DataFrame to parquet."""
    df.write_parquet(DATA_DIR / filename)


def load_data(filename: str) -> pl.DataFrame:
    """Load DataFrame from parquet."""
    return pl.read_parquet(DATA_DIR / filename)


def load_data_or_empty(filename: str, schema: dict) -> pl.DataFrame:
    """Load DataFrame or return empty with schema."""
    path = DATA_DIR / filename
    return pl.read_parquet(path) if path.exists() else pl.DataFrame(schema=schema)


def upsert_data(
    new_df: pl.DataFrame,
    existing_df: pl.DataFrame,
    unique_cols: list[str]
) -> pl.DataFrame:
    """Combine and deduplicate data."""
    return pl.concat([existing_df, new_df]).unique(subset=unique_cols, keep="last")


# Rankings
def save_rankings(df: pl.DataFrame, ranking_type: str) -> None:
    """Save rankings data."""
    save_data(df, f"{ranking_type}_rankings.parquet")


def load_rankings(ranking_type: str, schema: dict | None = None) -> pl.DataFrame:
    """Load rankings data, optionally returning empty DataFrame with schema."""
    filename = f"{ranking_type}_rankings.parquet"
    if schema is not None:
        return load_data_or_empty(filename, schema)
    return load_data(filename)


# Players
def save_players(df: pl.DataFrame) -> None:
    """Save players data."""
    save_data(df, "players.parquet")


def load_players(schema: dict | None = None) -> pl.DataFrame:
    """Load players data, optionally returning empty DataFrame with schema."""
    if schema is not None:
        return load_data_or_empty("players.parquet", schema)
    return load_data("players.parquet")


# Tournaments
def save_tournaments(df: pl.DataFrame) -> None:
    """Save tournaments data."""
    save_data(df, "tournaments.parquet")


def load_tournaments(schema: dict | None = None) -> pl.DataFrame:
    """Load tournaments data, optionally returning empty DataFrame with schema."""
    if schema is not None:
        return load_data_or_empty("tournaments.parquet", schema)
    return load_data("tournaments.parquet")