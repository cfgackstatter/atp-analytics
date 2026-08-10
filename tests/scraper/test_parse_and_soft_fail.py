import logging

import polars as pl

from backend.scraper.parse_utils import parse_int
from backend.scraper.player_scraper import items_to_bio
from backend.scraper.ranking_scraper import rows_to_dataframes
from backend.scraper.soft_fail import soft_fail
from backend.scraper.updater import _apply_bio_updates
from backend.scraper.schemas import PLAYERS_SCHEMA


def test_parse_int_variants():
    assert parse_int("1,234") == 1234
    assert parse_int("T5") == 5
    assert parse_int("+12") == 12
    assert parse_int("-") is None
    assert parse_int(None) is None


def test_soft_fail_returns_empty_factory_result():
    log = logging.getLogger("test")
    result = soft_fail(log, "unit", RuntimeError("boom"), list)
    assert result == []


def test_items_to_bio_extracts_fields():
    items = [
        {"label": "Age", "value": "36 (1987/05/22)"},
        {"label": "Weight", "value": "170 lbs (77kg)"},
        {"label": "Height", "value": "6'2\" (188cm)"},
        {"label": "Country", "value": "Serbia\nextra"},
        {"label": "Plays", "value": "Right-Handed, Two-Handed Backhand"},
    ]
    data = items_to_bio(items)
    assert data["birthdate"] == "1987/05/22"
    assert data["weight_kg"] == 77
    assert data["height_cm"] == 188
    assert data["country"] == "Serbia"
    assert data["handedness"] == "Right-Handed"
    assert data["backhand"] == "Two-Handed"


def test_rows_to_dataframes_uses_href_for_id_and_slug():
    rows = [
        {
            "rank": "1",
            "player_href": "https://www.atptour.com/en/players/jannik-sinner/s0ag/overview",
            "player_name": "Jannik Sinner",
            "points": "10,000",
            "points_move": "+10",
            "tourns": "18",
            "drop": "0",
            "best": "0",
        }
    ]
    rankings_df, players_df = rows_to_dataframes(rows, "singles", "2024-01-01")
    assert rankings_df["player_id"][0] == "s0ag"
    assert players_df["player_slug"][0] == "jannik-sinner"


def test_apply_bio_updates_fills_nulls_only_and_records_attempt():
    players = pl.DataFrame(
        {
            "player_id": ["p1"],
            "player_name": ["Test"],
            "country": ["USA"],
            "height_cm": [None],
            "scrape_attempted_at": [None],
        }
    )
    # Ensure full schema
    for col, dtype in PLAYERS_SCHEMA.items():
        if col not in players.columns:
            players = players.with_columns(pl.lit(None).cast(dtype).alias(col))
    players = players.select(list(PLAYERS_SCHEMA.keys()))

    updates = [
        {
            "player_id": "p1",
            "country": "ESP",
            "height_cm": 180,
            "scrape_attempted_at": "2026-01-01T00:00:00",
        }
    ]
    out = _apply_bio_updates(players, updates)
    row = out.to_dicts()[0]
    assert row["country"] == "USA"  # not overwritten
    assert row["height_cm"] == 180
    assert row["scrape_attempted_at"] == "2026-01-01T00:00:00"
