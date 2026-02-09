# backend/api/main.py
"""FastAPI application for ATP Analytics."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, datetime
import polars as pl

from backend.scraper.updater import update_rankings
from backend.scraper.tournament_scraper import scrape_tournaments
from backend.scraper.schemas import TOURNAMENTS_SCHEMA
from backend.storage.data_store import (
    load_rankings,
    load_players,
    load_tournaments,
    save_tournaments,
    upsert_data
)

app = FastAPI(title="ATP Analytics API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/players/search")
def search_players(q: str = Query("", min_length=0)):
    """
    Search players by name.

    Args:
        q: Search query string

    Returns:
        List of up to 10 matching players
    """
    try:
        players = load_players()
    except FileNotFoundError:
        return []

    if not q:
        return []

    filtered = players.filter(
        pl.col("player_name").str.to_lowercase().str.contains(q.lower())
    )

    return filtered.head(10).to_dicts()


@app.get("/tournaments")
def get_tournaments():
    """
    Get all tournaments.

    Returns:
        List of all tournaments with winners
    """
    try:
        df = load_tournaments()
        return df.to_dicts()
    except FileNotFoundError:
        return []


@app.get("/rankings/stored")
def get_stored_rankings(
    ranking_type: str = Query("singles", pattern="^(singles|doubles)$"),
    player_ids: str = Query(""),
    ranking_date: date | None = None,
):
    """
    Read rankings from Parquet and filter by player_ids and/or date.

    Args:
        ranking_type: 'singles' or 'doubles'
        player_ids: Comma-separated player IDs
        ranking_date: Optional date filter (YYYY-MM-DD)

    Returns:
        List of ranking records matching filters
    """
    try:
        df = load_rankings(ranking_type)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="No data found. Run update first."
        )

    if player_ids:
        ids = [id.strip() for id in player_ids.split(",") if id.strip()]
        df = df.filter(pl.col("player_id").is_in(ids))

    if ranking_date:
        df = df.filter(pl.col("date") == ranking_date.isoformat())

    return df.to_dicts()


@app.post("/admin/update-rankings")
def trigger_update(
    ranking_type: str = Query("singles", pattern="^(singles|doubles)$"),
    max_weeks: int | None = Query(None, ge=1, le=100)
):
    """
    Manually trigger rankings update (admin endpoint).

    Args:
        ranking_type: 'singles' or 'doubles'
        max_weeks: Maximum number of weeks to scrape (optional)

    Returns:
        Update summary with count of weeks scraped
    """
    count = update_rankings(ranking_type, max_weeks)
    return {
        "ranking_type": ranking_type,
        "weeks_updated": count,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/tasks/update-weekly")
def scheduled_weekly_update():
    """
    Scheduled task to update rankings and tournaments (called by cron).

    Updates:
    - Last 5 weeks of singles rankings
    - Last 5 weeks of doubles rankings
    - Current year ATP tournaments

    Returns:
        Summary of updates performed
    """
    # Update last 5 weeks of rankings
    singles_count = update_rankings("singles", max_weeks=5)
    doubles_count = update_rankings("doubles", max_weeks=5)

    # Update current year tournaments
    current_year = datetime.now().year
    new_tournaments = scrape_tournaments(current_year, 'atp')

    existing_tournaments = load_tournaments(schema=TOURNAMENTS_SCHEMA)
    combined_tournaments = upsert_data(
        new_tournaments,
        existing_tournaments,
        ['year', 'tournament_type', 'tournament_name']
    )
    save_tournaments(combined_tournaments)

    return {
        "singles_weeks_updated": singles_count,
        "doubles_weeks_updated": doubles_count,
        "tournaments_updated": len(new_tournaments),
        "timestamp": datetime.now().isoformat(),
        "message": "Weekly update completed"
    }