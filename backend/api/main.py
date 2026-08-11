# backend/api/main.py
"""FastAPI application for ATP Analytics."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import polars as pl
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.admin import router as admin_router
from backend.api.errors import http_internal_error
from backend.api.https_redirect import HTTPSRedirectMiddleware
from backend.api.settings import cors_origins, docs_enabled
from backend.scraper.config import BIO_PRESENT_FIELDS
from backend.scraper.schemas import PLAYERS_SCHEMA, RANKINGS_SCHEMA, TOURNAMENTS_SCHEMA
from backend.storage.s3_data_store import (
    load_doubles_rankings,
    load_players,
    load_singles_rankings,
    load_tournaments,
)

logger = logging.getLogger(__name__)

_enable_docs = docs_enabled()

app = FastAPI(
    title="ATP Analytics API",
    version="1.0.0",
    docs_url="/docs" if _enable_docs else None,
    redoc_url="/redoc" if _enable_docs else None,
    openapi_url="/openapi.json" if _enable_docs else None,
)

# Outer middleware runs last-added first; HTTPS redirect should wrap the stack.
_origins = cors_origins()
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
app.add_middleware(HTTPSRedirectMiddleware)

app.include_router(admin_router, prefix="/admin", tags=["admin"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unexpected errors; never leak internals to clients."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "storage": os.getenv("USE_S3", "false"),
    }


@app.get("/players/search")
def search_players(q: str = Query(..., min_length=1)):
    """Search for players by name."""
    try:
        players_df = load_players(schema=PLAYERS_SCHEMA)
        if len(players_df) == 0:
            return []

        mask = players_df["player_name"].str.to_lowercase().str.contains(q.lower())
        results = players_df.filter(mask)
        return results.to_dicts()
    except Exception as e:
        raise http_internal_error(logger, e, public_message="Failed to search players") from e


@app.get("/rankings/stored")
def get_stored_rankings(
    ranking_type: str = Query(default="singles", pattern="^(singles|doubles)$"),
    player_ids: Optional[str] = Query(default=None),
    limit: int = Query(default=1000, le=5000),
    latest_only: bool = Query(default=False),
):
    """Get stored ranking history."""
    try:
        if ranking_type == "singles":
            df = load_singles_rankings(schema=RANKINGS_SCHEMA)
        else:
            df = load_doubles_rankings(schema=RANKINGS_SCHEMA)

        if len(df) == 0:
            return []

        if player_ids:
            player_id_list = [pid.strip() for pid in player_ids.split(",")]
            df = df.filter(df["player_id"].is_in(player_id_list))
            return df.sort("date").to_dicts()

        if latest_only:
            df = df.sort("date", descending=True).group_by("player_id").head(1)
            if "rank" in df.columns:
                df = df.sort("rank")
        else:
            df = df.sort("date")

        df = df.head(limit)
        return df.to_dicts()
    except Exception as e:
        raise http_internal_error(logger, e, public_message="Failed to load rankings") from e


@app.get("/tournaments")
def get_tournaments(
    year: Optional[int] = None,
    tournament_type: Optional[str] = None,
):
    """Get tournament data."""
    try:
        df = load_tournaments(schema=TOURNAMENTS_SCHEMA)
        if len(df) == 0:
            return []

        if year:
            df = df.filter(df["year"] == year)

        if tournament_type:
            df = df.filter(df["tournament_type"] == tournament_type)

        return df.to_dicts()
    except Exception as e:
        raise http_internal_error(logger, e, public_message="Failed to load tournaments") from e


@app.get("/players")
def get_players(
    country: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    has_bio: Optional[bool] = None,
):
    """Get all players with optional filtering."""
    try:
        players_df = load_players(schema=PLAYERS_SCHEMA)
        if len(players_df) == 0:
            return []

        if country:
            mask = players_df["country"].str.to_lowercase().str.contains(country.lower())
            players_df = players_df.filter(mask)

        if has_bio is not None:
            present = [f for f in BIO_PRESENT_FIELDS if f in players_df.columns]
            if present:
                if has_bio:
                    mask = pl.any_horizontal(
                        [pl.col(field).is_not_null() for field in present]
                    )
                else:
                    mask = pl.all_horizontal(
                        [pl.col(field).is_null() for field in present]
                    )
                players_df = players_df.filter(mask)

        players_df = players_df.head(limit)
        return players_df.to_dicts()
    except Exception as e:
        raise http_internal_error(logger, e, public_message="Failed to load players") from e


# === FRONTEND SERVING ===

STATIC_DIR = Path(__file__).parent.parent / "static"

if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/favicon.ico")
    @app.head("/favicon.ico")
    def serve_favicon_ico():
        favicon_path = STATIC_DIR / "favicon.ico"
        if favicon_path.exists():
            return FileResponse(favicon_path, media_type="image/x-icon")
        raise HTTPException(status_code=404)

    @app.get("/favicon.png")
    @app.head("/favicon.png")
    def serve_favicon_png():
        favicon_path = STATIC_DIR / "favicon.png"
        if favicon_path.exists():
            return FileResponse(favicon_path, media_type="image/png")
        raise HTTPException(status_code=404)

    @app.get("/logo.png")
    @app.head("/logo.png")
    def serve_logo_png():
        logo_path = STATIC_DIR / "logo.png"
        if logo_path.exists():
            return FileResponse(logo_path, media_type="image/png")
        raise HTTPException(status_code=404)

    @app.get("/logo.svg")
    @app.head("/logo.svg")
    def serve_logo_svg():
        logo_path = STATIC_DIR / "logo.svg"
        if logo_path.exists():
            return FileResponse(logo_path, media_type="image/svg+xml")
        raise HTTPException(status_code=404)

    @app.get("/vite.svg")
    @app.head("/vite.svg")
    def serve_vite_svg():
        svg_path = STATIC_DIR / "vite.svg"
        if svg_path.exists():
            return FileResponse(svg_path)
        raise HTTPException(status_code=404)


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the React frontend index.html."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    payload = {
        "name": "ATP Analytics API",
        "version": "1.0.0",
        "message": "Frontend not found. Build frontend and copy to backend/static/",
    }
    if _enable_docs:
        payload["docs"] = "/docs"
    return payload


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    """Catch-all for SPA routes; do not intercept API / docs paths."""
    # Always reserve these paths so disabled docs cannot fall through to index.html.
    api_exact = {
        "health",
        "tournaments",
        "players",
        "docs",
        "redoc",
        "openapi.json",
    }
    api_prefixes = (
        "api/",
        "admin/",
        "players/",
        "rankings/",
        "tournaments/",
        "docs/",
        "redoc/",
    )

    if full_path in api_exact or full_path.startswith(api_prefixes):
        raise HTTPException(status_code=404)

    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404)
