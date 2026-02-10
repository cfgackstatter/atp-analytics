# backend/api/admin.py
"""Admin endpoints for manual data updates and monitoring."""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from datetime import datetime
import os
import logging
from typing import Optional
from pathlib import Path

from backend.scraper.updater import update_rankings, update_player_bio
from backend.scraper.tournament_scraper import scrape_tournaments
from backend.scraper.schemas import TOURNAMENTS_SCHEMA
from backend.scraper.config import VALID_TOURNAMENT_TYPES
from backend.storage.s3_data_store import (
    load_tournaments, save_tournaments, upsert_data, get_data_summary
)

import polars as pl

router = APIRouter()

logger = logging.getLogger(__name__)

# Simple password auth from environment
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme123")

# In-memory job tracking (use Redis/DB for production)
active_jobs = {}
completed_jobs = []


def verify_password(password: str | None) -> None:
    """Verify admin password."""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")


@router.get("/dashboard")
def serve_admin_dashboard():
    """Serve the admin dashboard HTML page."""
    # Look for admin.html in backend/templates or backend/static
    admin_html_paths = [
        Path(__file__).parent.parent / "templates" / "admin.html",
        Path(__file__).parent.parent / "static" / "admin.html",
        Path(__file__).parent.parent / "admin.html",
    ]

    for admin_path in admin_html_paths:
        if admin_path.exists():
            return FileResponse(admin_path, media_type="text/html")

    # If not found, return error with instructions
    raise HTTPException(
        status_code=404, 
        detail="admin.html not found. Place it in backend/templates/ or backend/static/"
    )


@router.get("/data-summary")
def get_summary(password: str = Query(...)):
    """
    Get comprehensive data summary.

    Returns record counts, date ranges, file sizes for all datasets.
    """
    verify_password(password)

    try:
        summary = get_data_summary()
        summary["timestamp"] = datetime.now().isoformat()
        return summary
    except Exception as e:
        logger.error(f"Error getting data summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-rankings")
def manual_update_rankings(
    background_tasks: BackgroundTasks,
    ranking_type: str = Query("singles", pattern="^(singles|doubles)$"),
    max_weeks: int = Query(10, ge=1, le=500),
    password: str = Query(...)
):
    """
    Manually trigger rankings update.

    Args:
        ranking_type: 'singles' or 'doubles'
        max_weeks: Number of weeks to scrape (default: 10, max: 500)
        password: Admin password
    """
    verify_password(password)

    job_id = f"rankings_{ranking_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def run_update():
        try:
            active_jobs[job_id] = {
                "status": "running",
                "type": "rankings",
                "ranking_type": ranking_type,
                "max_weeks": max_weeks,
                "started": datetime.now().isoformat()
            }

            count = update_rankings(ranking_type, max_weeks)

            completed_jobs.append({
                "job_id": job_id,
                "status": "completed",
                "type": "rankings",
                "ranking_type": ranking_type,
                "weeks_scraped": count,
                "completed": datetime.now().isoformat()
            })

            del active_jobs[job_id]

        except Exception as e:
            logger.error(f"Rankings update failed: {e}")
            active_jobs[job_id]["status"] = "failed"
            active_jobs[job_id]["error"] = str(e)

    # Run in background
    background_tasks.add_task(run_update)

    return {
        "job_id": job_id,
        "status": "started",
        "ranking_type": ranking_type,
        "max_weeks": max_weeks,
        "message": f"Started scraping {max_weeks} weeks of {ranking_type} rankings"
    }


@router.post("/update-tournaments")
def manual_update_tournaments(
    background_tasks: BackgroundTasks,
    start_year: int = Query(..., ge=1990, le=2030),
    end_year: int = Query(..., ge=1990, le=2030),
    types: str = Query("atp"),
    password: str = Query(...)
):
    """
    Manually trigger tournament update.

    Args:
        start_year: Start year (inclusive)
        end_year: End year (inclusive)
        types: Comma-separated tournament types (atp,gs,ch,fu)
        password: Admin password
    """
    verify_password(password)

    # Validate tournament types
    type_list = [t.strip() for t in types.split(",")]
    invalid = [t for t in type_list if t not in VALID_TOURNAMENT_TYPES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tournament types: {invalid}. Valid: {VALID_TOURNAMENT_TYPES}"
        )

    if start_year > end_year:
        raise HTTPException(status_code=400, detail="start_year must be <= end_year")

    job_id = f"tournaments_{start_year}_{end_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def run_update():
        try:
            active_jobs[job_id] = {
                "status": "running",
                "type": "tournaments",
                "start_year": start_year,
                "end_year": end_year,
                "tournament_types": type_list,
                "started": datetime.now().isoformat()
            }

            new_tournaments = []
            for year in range(start_year, end_year + 1):
                for t_type in type_list:
                    logger.info(f"Scraping {t_type} {year}...")
                    new_tournaments.append(scrape_tournaments(year, t_type))

            if new_tournaments:
                new_df = pl.concat(new_tournaments)
                existing_df = load_tournaments(schema=TOURNAMENTS_SCHEMA)
                combined_df = upsert_data(
                    new_df, existing_df,
                    ['year', 'tournament_type', 'tournament_name', 'start_date']
                )
                save_tournaments(combined_df)

                completed_jobs.append({
                    "job_id": job_id,
                    "status": "completed",
                    "type": "tournaments",
                    "tournaments_scraped": len(new_df),
                    "total_tournaments": len(combined_df),
                    "completed": datetime.now().isoformat()
                })

            del active_jobs[job_id]

        except Exception as e:
            logger.error(f"Tournament update failed: {e}")
            active_jobs[job_id]["status"] = "failed"
            active_jobs[job_id]["error"] = str(e)

    background_tasks.add_task(run_update)

    return {
        "job_id": job_id,
        "status": "started",
        "start_year": start_year,
        "end_year": end_year,
        "types": type_list,
        "message": f"Started scraping {len(type_list)} tournament types from {start_year}-{end_year}"
    }


@router.post("/update-players")
def manual_update_players(
    background_tasks: BackgroundTasks,
    num_players: int = Query(10, ge=1, le=500),
    password: str = Query(...)
):
    """
    Manually trigger player bio update.

    Args:
        num_players: Number of top players to scrape (default: 10, max: 500)
        password: Admin password
    """
    verify_password(password)

    job_id = f"players_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def run_update():
        try:
            active_jobs[job_id] = {
                "status": "running",
                "type": "players",
                "num_players": num_players,
                "started": datetime.now().isoformat()
            }

            count = update_player_bio(num_players)

            completed_jobs.append({
                "job_id": job_id,
                "status": "completed",
                "type": "players",
                "players_updated": count,
                "completed": datetime.now().isoformat()
            })

            del active_jobs[job_id]

        except Exception as e:
            logger.error(f"Player update failed: {e}")
            active_jobs[job_id]["status"] = "failed"
            active_jobs[job_id]["error"] = str(e)

    background_tasks.add_task(run_update)

    return {
        "job_id": job_id,
        "status": "started",
        "num_players": num_players,
        "message": f"Started scraping top {num_players} players"
    }


@router.get("/jobs")
def get_jobs(password: str = Query(...)):
    """Get status of all jobs (active and recent completed)."""
    verify_password(password)

    return {
        "active": list(active_jobs.values()),
        "completed": completed_jobs[-20:]  # Last 20 completed jobs
    }


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, password: str = Query(...)):
    """Get status of specific job."""
    verify_password(password)

    if job_id in active_jobs:
        return active_jobs[job_id]

    for job in completed_jobs:
        if job["job_id"] == job_id:
            return job

    raise HTTPException(status_code=404, detail="Job not found")