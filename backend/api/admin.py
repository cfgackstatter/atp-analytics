"""Admin endpoints for manual data updates and monitoring."""

from __future__ import annotations

import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from backend.api.auth import require_admin
from backend.api.rate_limit import rate_limit_admin
from backend.scraper.config import VALID_TOURNAMENT_TYPES
from backend.scraper.schemas import TOURNAMENTS_SCHEMA
from backend.scraper.tournament_scraper import scrape_tournaments
from backend.scraper.updater import update_player_bio, update_rankings
from backend.storage.s3_data_store import (
    get_data_summary,
    load_tournaments,
    save_tournaments,
    upsert_data,
)

logger = logging.getLogger(__name__)

# Public HTML only; API routes use auth + rate limit below.
router = APIRouter()

# Protected admin API (Authorization: Bearer + per-IP rate limit).
api_router = APIRouter(
    dependencies=[Depends(rate_limit_admin), Depends(require_admin)],
)

# In-memory job tracking (use Redis/DB for production)
active_jobs: dict[str, dict[str, Any]] = {}
completed_jobs: list[dict[str, Any]] = []


def _now_iso() -> str:
    return datetime.now().isoformat()


def _start_job(job_id: str, **meta: Any) -> None:
    active_jobs[job_id] = {"status": "running", "started": _now_iso(), **meta}


def _finish_job(job_id: str, **meta: Any) -> None:
    """Move a job from active → completed (success or failure)."""
    active = active_jobs.pop(job_id, {})
    completed_jobs.append(
        {
            "job_id": job_id,
            "type": active.get("type"),
            "started": active.get("started"),
            "completed": _now_iso(),
            **meta,
        }
    )


def _fail_job(job_id: str, error: Exception) -> None:
    logger.exception("Admin job %s failed", job_id)
    _finish_job(job_id, status="failed", error=str(error))


@router.get("/dashboard")
def serve_admin_dashboard():
    """Serve the admin dashboard HTML page (auth happens on API calls)."""
    candidates = [
        Path(__file__).parent.parent / "templates" / "admin.html",
        Path(__file__).parent.parent / "static" / "admin.html",
    ]
    for path in candidates:
        if path.is_file():
            return FileResponse(path, media_type="text/html")
    raise HTTPException(status_code=404, detail="admin.html not found")


@api_router.get("/data-summary")
def get_summary():
    """Return record counts, date ranges, and file sizes for all datasets."""
    try:
        summary = get_data_summary()
        summary["timestamp"] = _now_iso()
        return summary
    except Exception as e:
        logger.exception("Error getting data summary")
        raise HTTPException(status_code=500, detail="Failed to load data summary") from e


@api_router.post("/update-rankings")
def manual_update_rankings(
    background_tasks: BackgroundTasks,
    ranking_type: str = Query("singles", pattern="^(singles|doubles)$"),
    max_weeks: int = Query(10, ge=1, le=500),
):
    """Manually trigger a rankings scrape."""
    job_id = f"rankings_{ranking_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def run_update() -> None:
        _start_job(
            job_id,
            type="rankings",
            ranking_type=ranking_type,
            max_weeks=max_weeks,
        )
        try:
            count = update_rankings(ranking_type, max_weeks)
            _finish_job(
                job_id,
                status="completed",
                ranking_type=ranking_type,
                weeks_scraped=count,
            )
        except Exception as e:
            _fail_job(job_id, e)

    background_tasks.add_task(run_update)
    return {
        "job_id": job_id,
        "status": "started",
        "ranking_type": ranking_type,
        "max_weeks": max_weeks,
        "message": f"Started scraping {max_weeks} weeks of {ranking_type} rankings",
    }


@api_router.post("/update-tournaments")
def manual_update_tournaments(
    background_tasks: BackgroundTasks,
    start_year: int = Query(..., ge=1990, le=2030),
    end_year: int = Query(..., ge=1990, le=2030),
    types: str = Query("atp"),
):
    """Manually trigger a tournament scrape."""
    type_list = [t.strip() for t in types.split(",") if t.strip()]
    invalid = [t for t in type_list if t not in VALID_TOURNAMENT_TYPES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tournament types: {invalid}. Valid: {VALID_TOURNAMENT_TYPES}",
        )
    if not type_list:
        raise HTTPException(status_code=400, detail="At least one tournament type is required")
    if start_year > end_year:
        raise HTTPException(status_code=400, detail="start_year must be <= end_year")

    job_id = f"tournaments_{start_year}_{end_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def run_update() -> None:
        _start_job(
            job_id,
            type="tournaments",
            start_year=start_year,
            end_year=end_year,
            tournament_types=type_list,
        )
        try:
            frames = [
                scrape_tournaments(year, t_type)
                for year in range(start_year, end_year + 1)
                for t_type in type_list
            ]
            if not frames:
                _finish_job(job_id, status="completed", tournaments_scraped=0, total_tournaments=0)
                return

            new_df = pl.concat(frames)
            existing_df = load_tournaments(schema=TOURNAMENTS_SCHEMA)
            combined_df = upsert_data(
                new_df,
                existing_df,
                ["year", "tournament_type", "tournament_name", "start_date"],
            )
            save_tournaments(combined_df)
            _finish_job(
                job_id,
                status="completed",
                tournament_types=type_list,
                tournaments_scraped=len(new_df),
                total_tournaments=len(combined_df),
            )
        except Exception as e:
            _fail_job(job_id, e)

    background_tasks.add_task(run_update)
    return {
        "job_id": job_id,
        "status": "started",
        "start_year": start_year,
        "end_year": end_year,
        "types": type_list,
        "message": (
            f"Started scraping {len(type_list)} tournament types "
            f"from {start_year}-{end_year}"
        ),
    }


@api_router.post("/update-players")
def manual_update_players(
    background_tasks: BackgroundTasks,
    num_players: int = Query(10, ge=1, le=500),
):
    """Manually trigger a player bio scrape."""
    job_id = f"players_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def run_update() -> None:
        _start_job(job_id, type="players", num_players=num_players)
        try:
            count = update_player_bio(num_players)
            _finish_job(
                job_id,
                status="completed",
                num_players=num_players,
                players_updated=count,
            )
        except Exception as e:
            _fail_job(job_id, e)

    background_tasks.add_task(run_update)
    return {
        "job_id": job_id,
        "status": "started",
        "num_players": num_players,
        "message": f"Started scraping top {num_players} players",
    }


@api_router.get("/jobs")
def get_jobs():
    """Return active jobs and the most recent completed jobs."""
    return {
        "active": list(active_jobs.values()),
        "completed": completed_jobs[-20:],
    }


@api_router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Return status for a specific job."""
    if job_id in active_jobs:
        return active_jobs[job_id]
    for job in completed_jobs:
        if job.get("job_id") == job_id:
            return job
    raise HTTPException(status_code=404, detail="Job not found")


@api_router.get("/test-playwright")
def test_playwright():
    """Smoke-test Playwright on this host."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--single-process",
                    "--no-zygote",
                ],
            )
            page = browser.new_page()
            page.goto("https://example.com", wait_until="commit", timeout=15000)
            title = page.title()
            browser.close()
        return {"status": "ok", "title": title}
    except Exception as e:
        logger.exception("Playwright smoke test failed")
        return {
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc(),
        }


# Mount protected routes on the public admin router (same /admin prefix).
router.include_router(api_router)
