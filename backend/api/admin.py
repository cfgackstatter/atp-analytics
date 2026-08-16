"""Admin endpoints for manual data updates and monitoring."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from backend.api.auth import require_admin
from backend.api.job_manager import get_job, is_busy, list_jobs, submit_job
from backend.api.rate_limit import rate_limit_admin
from backend.scraper.config import (
    PLAYER_SCRAPE_COOLDOWN_DAYS,
    SCRAPE_CONCURRENCY,
    VALID_TOURNAMENT_TYPES,
    playwright_single_process,
)
from backend.storage.s3_data_store import get_data_summary

logger = logging.getLogger(__name__)

router = APIRouter()

api_router = APIRouter(
    dependencies=[Depends(rate_limit_admin), Depends(require_admin)],
)


def _now_iso() -> str:
    return datetime.now().isoformat()


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
        summary["system"] = {
            "scrape_concurrency": SCRAPE_CONCURRENCY,
            "playwright_single_process": playwright_single_process(),
            "player_scrape_cooldown_days": PLAYER_SCRAPE_COOLDOWN_DAYS,
            "scrape_busy": is_busy(),
        }
        return summary
    except Exception as e:
        logger.exception("Error getting data summary")
        raise HTTPException(status_code=500, detail="Failed to load data summary") from e


@api_router.post("/update-rankings")
def manual_update_rankings(
    ranking_type: str = Query("singles", pattern="^(singles|doubles)$"),
    max_weeks: int = Query(10, ge=1, le=500),
):
    """Start a rankings scrape in a dedicated subprocess."""
    job_id = submit_job(
        "rankings",
        {"ranking_type": ranking_type, "max_weeks": max_weeks},
        ranking_type=ranking_type,
        max_weeks=max_weeks,
    )
    return {
        "job_id": job_id,
        "status": "started",
        "ranking_type": ranking_type,
        "max_weeks": max_weeks,
        "message": (
            f"Started scraping {max_weeks} weeks of {ranking_type} rankings "
            "(subprocess; site stays responsive)"
        ),
    }


@api_router.post("/update-tournaments")
def manual_update_tournaments(
    start_year: int = Query(..., ge=1990, le=2030),
    end_year: int = Query(..., ge=1990, le=2030),
    types: str = Query("atp"),
):
    """Start a tournament scrape in a dedicated subprocess."""
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

    job_id = submit_job(
        "tournaments",
        {
            "start_year": start_year,
            "end_year": end_year,
            "types": type_list,
        },
        start_year=start_year,
        end_year=end_year,
        tournament_types=type_list,
    )
    return {
        "job_id": job_id,
        "status": "started",
        "start_year": start_year,
        "end_year": end_year,
        "types": type_list,
        "message": (
            f"Started scraping {len(type_list)} tournament types "
            f"from {start_year}-{end_year} (subprocess; site stays responsive)"
        ),
    }


@api_router.post("/update-players")
def manual_update_players(
    num_players: int = Query(10, ge=1, le=500),
):
    """Start a player bio scrape in a dedicated subprocess."""
    job_id = submit_job(
        "players",
        {"num_players": num_players},
        num_players=num_players,
    )
    return {
        "job_id": job_id,
        "status": "started",
        "num_players": num_players,
        "message": (
            f"Started scraping top {num_players} players "
            "(subprocess; site stays responsive)"
        ),
    }


@api_router.get("/jobs")
def get_jobs():
    """Return active jobs and the most recent completed jobs."""
    return list_jobs()


@api_router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Return status for a specific job."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@api_router.get("/test-playwright")
def test_playwright():
    """Smoke-test Playwright on this host (short, in-process)."""
    try:
        from backend.scraper.http_utils import goto_and_extract, playwright_session

        with playwright_session() as ctx:
            page = ctx.new_page()
            try:
                title = goto_and_extract(
                    page,
                    "https://example.com",
                    selector="body",
                    js="() => document.title",
                    max_retries=1,
                )
            finally:
                page.close()
        return {"status": "ok", "title": title}
    except Exception as e:
        logger.exception("Playwright smoke test failed")
        return {
            "status": "error",
            "error": str(e),
        }


router.include_router(api_router)
