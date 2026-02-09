# backend/scraper/schemas.py
"""Centralized schema definitions."""

import polars as pl

# Rankings Schema
RANKINGS_SCHEMA = {
    "rank": pl.Int64,
    "player_id": pl.String,
    "points": pl.Int64,
    "points_move": pl.Int64,
    "tournaments_played": pl.Int64,
    "dropping": pl.Int64,
    "next_best": pl.Int64,
    "date": pl.String,
    "type": pl.String,
}

# Players Schema (including bio fields)
PLAYERS_SCHEMA = {
    "player_id": pl.String,
    "player_name": pl.String,
    "birthdate": pl.String,
    "weight_kg": pl.Int64,
    "height_cm": pl.Int64,
    "turned_pro": pl.Int64,
    "country": pl.String,
    "birthplace": pl.String,
    "handedness": pl.String,
    "backhand": pl.String,
    "coach": pl.String,
}

# Tournaments Schema
TOURNAMENTS_SCHEMA = {
    "year": pl.Int64,
    "tournament_type": pl.String,
    "tournament_name": pl.String,
    "venue": pl.String,
    "country_code": pl.String,
    "start_date": pl.String,
    "end_date": pl.String,
    "singles_winner_id": pl.String,
    "singles_winner_name": pl.String,
    "doubles_winner_ids": pl.String,
    "doubles_winner_names": pl.String,
}