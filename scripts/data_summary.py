#!/usr/bin/env python3
"""
Data Summary Script
Prints comprehensive statistics and summaries of all stored data.
"""

import sys
sys.path.append('.')

from pathlib import Path
import polars as pl
from backend.storage.data_store import DATA_DIR, load_rankings, load_players, load_tournaments

def print_header(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 80}")
    print(f"{title:^80}")
    print('=' * 80)

def print_subheader(title: str):
    """Print a formatted subsection header."""
    print(f"\n{'-' * 80}")
    print(f"{title}")
    print('-' * 80)

def summarize_rankings():
    """Summarize rankings data."""
    print_header("RANKINGS DATA SUMMARY")

    for ranking_type in ['singles', 'doubles']:
        try:
            df = load_rankings(ranking_type)

            print_subheader(f"{ranking_type.upper()} Rankings")

            # Basic stats
            print(f"Total records: {len(df):,}")
            print(f"Unique players: {df['player_id'].n_unique():,}")
            print(f"Unique dates: {df['date'].n_unique():,}")

            # Date range
            dates = df['date'].sort()
            print(f"\nDate range:")
            print(f"  Earliest: {dates.min()}")
            print(f"  Latest:   {dates.max()}")

            # Rank statistics
            print(f"\nRank statistics:")
            print(f"  Min rank: {df['rank'].min()}")
            print(f"  Max rank: {df['rank'].max()}")
            print(f"  Average rank: {df['rank'].mean():.1f}")

            # Points statistics
            print(f"\nPoints statistics:")
            print(f"  Min points: {df['points'].min():,}")
            print(f"  Max points: {df['points'].max():,}")
            print(f"  Average points: {df['points'].mean():.0f}")

            # Top 10 players by max points
            top_players = (df
                .group_by('player_id')
                .agg(pl.col('points').max().alias('max_points'))
                .sort('max_points', descending=True)
                .head(10)
            )

            print(f"\nTop 10 players by max points:")
            for i, row in enumerate(top_players.iter_rows(named=True), 1):
                print(f"  {i:2d}. Player ID {row['player_id']}: {row['max_points']:,} points")

            # Data completeness
            print(f"\nData completeness:")
            for col in ['points_move', 'tournaments_played', 'dropping', 'next_best']:
                null_pct = (df[col].null_count() / len(df)) * 100
                print(f"  {col}: {100 - null_pct:.1f}% complete")

        except FileNotFoundError:
            print_subheader(f"{ranking_type.upper()} Rankings")
            print(f"⚠️  No {ranking_type} rankings data found")

def summarize_players():
    """Summarize player data."""
    print_header("PLAYERS DATA SUMMARY")

    try:
        df = load_players()

        print(f"Total players: {len(df):,}")

        # Bio data completeness
        bio_cols = ['birthdate', 'weight_kg', 'height_cm', 'turned_pro', 
                    'country', 'birthplace', 'handedness', 'backhand', 'coach']

        print(f"\nBiographical data completeness:")
        for col in bio_cols:
            if col in df.columns:
                filled = df[col].drop_nulls().len()
                pct = (filled / len(df)) * 100
                print(f"  {col:20s}: {filled:5,} / {len(df):5,} ({pct:5.1f}%)")
            else:
                print(f"  {col:20s}: Column not found")

        # Country distribution (top 10)
        if 'country' in df.columns:
            country_counts = (df
                .filter(pl.col('country').is_not_null())
                .group_by('country')
                .agg(pl.count().alias('count'))
                .sort('count', descending=True)
                .head(10)
            )

            print(f"\nTop 10 countries by player count:")
            for i, row in enumerate(country_counts.iter_rows(named=True), 1):
                print(f"  {i:2d}. {row['country']:20s}: {row['count']:4,} players")

        # Handedness distribution
        if 'handedness' in df.columns:
            handedness = df.filter(pl.col('handedness').is_not_null())['handedness'].value_counts()
            print(f"\nHandedness distribution:")
            for row in handedness.iter_rows(named=True):
                print(f"  {row['handedness']:15s}: {row['count']:4,} players")

        # Backhand distribution
        if 'backhand' in df.columns:
            backhand = df.filter(pl.col('backhand').is_not_null())['backhand'].value_counts()
            print(f"\nBackhand distribution:")
            for row in backhand.iter_rows(named=True):
                print(f"  {row['backhand']:20s}: {row['count']:4,} players")

        # Height statistics
        if 'height_cm' in df.columns:
            heights = df.filter(pl.col('height_cm').is_not_null())['height_cm']
            if len(heights) > 0:
                print(f"\nHeight statistics (cm):")
                print(f"  Min:     {heights.min()}")
                print(f"  Max:     {heights.max()}")
                print(f"  Average: {heights.mean():.1f}")
                print(f"  Median:  {heights.median():.1f}")

        # Weight statistics
        if 'weight_kg' in df.columns:
            weights = df.filter(pl.col('weight_kg').is_not_null())['weight_kg']
            if len(weights) > 0:
                print(f"\nWeight statistics (kg):")
                print(f"  Min:     {weights.min()}")
                print(f"  Max:     {weights.max()}")
                print(f"  Average: {weights.mean():.1f}")
                print(f"  Median:  {weights.median():.1f}")

    except FileNotFoundError:
        print("⚠️  No players data found")

def summarize_tournaments():
    """Summarize tournament data."""
    print_header("TOURNAMENTS DATA SUMMARY")

    try:
        df = load_tournaments()

        print(f"Total tournaments: {len(df):,}")

        # Year range
        print(f"\nYear range:")
        print(f"  Earliest: {df['year'].min()}")
        print(f"  Latest:   {df['year'].max()}")

        # Tournament types
        type_counts = df['tournament_type'].value_counts().sort('tournament_type')
        print(f"\nTournament types:")
        for row in type_counts.iter_rows(named=True):
            print(f"  {row['tournament_type']:10s}: {row['count']:4,} tournaments")

        # Tournaments by year (last 5 years)
        recent_years = sorted(df['year'].unique())[-5:]
        print(f"\nTournaments per year (recent):")
        for year in recent_years:
            count = df.filter(pl.col('year') == year).height
            print(f"  {year}: {count:3,} tournaments")

        # Country distribution (top 10)
        if 'country_code' in df.columns:
            country_counts = (df
                .filter(pl.col('country_code').is_not_null())
                .group_by('country_code')
                .agg(pl.count().alias('count'))
                .sort('count', descending=True)
                .head(10)
            )

            print(f"\nTop 10 countries by tournament count:")
            for i, row in enumerate(country_counts.iter_rows(named=True), 1):
                print(f"  {i:2d}. {row['country_code']:3s}: {row['count']:4,} tournaments")

        # Singles vs doubles winners
        singles_count = df.filter(pl.col('singles_winner_id').is_not_null()).height
        doubles_count = df.filter(pl.col('doubles_winner_ids').is_not_null()).height

        print(f"\nWinner data:")
        print(f"  Tournaments with singles winner: {singles_count:,} ({singles_count/len(df)*100:.1f}%)")
        print(f"  Tournaments with doubles winners: {doubles_count:,} ({doubles_count/len(df)*100:.1f}%)")

        # Most frequent winners (singles, top 10)
        if singles_count > 0:
            top_winners = (df
                .filter(pl.col('singles_winner_id').is_not_null())
                .group_by(['singles_winner_id', 'singles_winner_name'])
                .agg(pl.count().alias('wins'))
                .sort('wins', descending=True)
                .head(10)
            )

            print(f"\nTop 10 singles winners:")
            for i, row in enumerate(top_winners.iter_rows(named=True), 1):
                name = row['singles_winner_name'] or f"ID: {row['singles_winner_id']}"
                print(f"  {i:2d}. {name:30s}: {row['wins']:3,} titles")

        # Date completeness
        start_date_pct = (df['start_date'].drop_nulls().len() / len(df)) * 100
        end_date_pct = (df['end_date'].drop_nulls().len() / len(df)) * 100

        print(f"\nDate data completeness:")
        print(f"  Start dates: {start_date_pct:.1f}%")
        print(f"  End dates:   {end_date_pct:.1f}%")

    except FileNotFoundError:
        print("⚠️  No tournaments data found")

def summarize_files():
    """Summarize data files."""
    print_header("DATA FILES")

    print(f"Data directory: {DATA_DIR.absolute()}\n")

    if not DATA_DIR.exists():
        print("⚠️  Data directory does not exist")
        return

    files = sorted(DATA_DIR.glob("*.parquet"))

    if not files:
        print("⚠️  No data files found")
        return

    print(f"{'File':<30} {'Size':>15} {'Modified'}")
    print('-' * 80)

    for file in files:
        size = file.stat().st_size
        modified = file.stat().st_mtime
        from datetime import datetime
        mod_date = datetime.fromtimestamp(modified).strftime('%Y-%m-%d %H:%M:%S')

        # Format size
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 ** 2:
            size_str = f"{size / 1024:.1f} KB"
        elif size < 1024 ** 3:
            size_str = f"{size / (1024 ** 2):.1f} MB"
        else:
            size_str = f"{size / (1024 ** 3):.1f} GB"

        print(f"{file.name:<30} {size_str:>15} {mod_date}")

def main():
    """Run all summaries."""
    print("\n" + "█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "ATP TENNIS DATA SUMMARY".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80)

    summarize_files()
    summarize_rankings()
    summarize_players()
    summarize_tournaments()

    print("\n" + "=" * 80)
    print("Summary complete!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()