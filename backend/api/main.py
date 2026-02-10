# backend/api/main.py
"""FastAPI application for ATP Analytics."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path
from typing import Optional, List

# Import storage functions
from backend.storage.s3_data_store import (
    load_players,
    load_singles_rankings,
    load_doubles_rankings,
    load_tournaments
)

# Import admin router
from backend.api.admin import router as admin_router

app = FastAPI(
    title="ATP Analytics API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include admin router
app.include_router(admin_router, prefix="/admin", tags=["admin"])

# === API ROUTES ===

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": "2026-02-10T02:00:00",
        "storage": os.getenv("USE_S3", "false")
    }

@app.get("/players/search")
def search_players(q: str = Query(..., min_length=1)):
    """Search for players by name."""
    try:
        players_df = load_players()

        if players_df is None or len(players_df) == 0:
            return []

        # Filter players by search query
        mask = players_df["player_name"].str.to_lowercase().str.contains(q.lower())
        results = players_df.filter(mask)

        return results.to_dicts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rankings/stored")
def get_stored_rankings(
    ranking_type: str = Query(..., pattern="^(singles|doubles)$"),
    player_ids: str = Query(..., description="Comma-separated player IDs")
):
    """Get stored ranking history for specified players."""
    try:
        player_id_list = [pid.strip() for pid in player_ids.split(",")]

        if ranking_type == "singles":
            df = load_singles_rankings()
        else:
            df = load_doubles_rankings()

        if df is None or len(df) == 0:
            return []

        # Filter by player IDs
        filtered = df.filter(df["player_id"].is_in(player_id_list))

        return filtered.to_dicts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tournaments")
def get_tournaments(
    year: Optional[int] = None,
    tournament_type: Optional[str] = None
):
    """Get tournament data."""
    try:
        df = load_tournaments()

        if df is None or len(df) == 0:
            return []

        # Apply filters
        if year:
            df = df.filter(df["year"] == year)

        if tournament_type:
            df = df.filter(df["tournament_type"] == tournament_type)

        return df.to_dicts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === TASK ENDPOINTS ===

@app.post("/tasks/update-weekly")
def update_weekly():
    """Weekly data update task (called by EventBridge)."""
    from backend.scraper.updater import update_rankings, update_player_bio

    try:
        # Run updates
        singles_weeks = update_rankings("singles", max_weeks=2)
        doubles_weeks = update_rankings("doubles", max_weeks=2)
        players_updated = update_player_bio(num_players=10)

        result = {
            "singles_weeks": singles_weeks,
            "doubles_weeks": doubles_weeks,
            "players_updated": players_updated
        }

        return {
            "status": "success",
            "message": "Weekly update completed",
            "timestamp": "2026-02-10T02:00:00",
            **result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": "2026-02-10T02:00:00"
        }

# === FRONTEND SERVING ===

# Get static directory path
STATIC_DIR = Path(__file__).parent.parent / "static"

# Mount static assets (CSS, JS, images)
if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/favicon.ico")
    @app.head("/favicon.ico")
    def serve_favicon_ico():
        """Serve favicon.ico."""
        favicon_path = STATIC_DIR / "favicon.ico"
        if favicon_path.exists():
            return FileResponse(favicon_path, media_type="image/x-icon")
        raise HTTPException(status_code=404)

    @app.get("/favicon.png")
    @app.head("/favicon.png")
    def serve_favicon_png():
        """Serve favicon.png."""
        favicon_path = STATIC_DIR / "favicon.png"
        if favicon_path.exists():
            return FileResponse(favicon_path, media_type="image/png")
        raise HTTPException(status_code=404)

    @app.get("/logo.png")
    @app.head("/logo.png")
    def serve_logo_png():
        """Serve logo.png."""
        logo_path = STATIC_DIR / "logo.png"
        if logo_path.exists():
            return FileResponse(logo_path, media_type="image/png")
        raise HTTPException(status_code=404)

    @app.get("/logo.svg")
    @app.head("/logo.svg")
    def serve_logo_svg():
        """Serve logo.svg."""
        logo_path = STATIC_DIR / "logo.svg"
        if logo_path.exists():
            return FileResponse(logo_path, media_type="image/svg+xml")
        raise HTTPException(status_code=404)

    @app.get("/vite.svg")
    @app.head("/vite.svg")
    def serve_vite_svg():
        """Serve vite.svg."""
        svg_path = STATIC_DIR / "vite.svg"
        if svg_path.exists():
            return FileResponse(svg_path)
        raise HTTPException(status_code=404)

# Serve React app at root (MUST BE LAST!)
@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the React frontend index.html."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    # Fallback if frontend not built
    return {
        "name": "ATP Analytics API",
        "version": "1.0.0",
        "docs": "/docs",
        "message": "Frontend not found. Build frontend and copy to backend/static/"
    }

# Catch-all route for React Router (SPA routing)
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    """
    Catch-all route for Single Page Application routing.
    Serves index.html for any non-API routes.
    """
    # Don't intercept API routes, docs, or admin
    if (full_path.startswith("api/") or 
        full_path.startswith("docs") or 
        full_path.startswith("redoc") or
        full_path.startswith("admin/") or
        full_path.startswith("tasks/") or
        full_path.startswith("health") or
        full_path.startswith("players/") or
        full_path.startswith("rankings/") or
        full_path.startswith("tournaments")):
        raise HTTPException(status_code=404)

    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404)