"""Tests for storage helpers and summary metrics."""

import polars as pl

from backend.storage.s3_data_store import get_data_summary, upsert_data


def test_upsert_keeps_last_on_keys():
    existing = pl.DataFrame(
        {"player_id": ["a", "b"], "rank": [1, 2], "date": ["2024-01-01", "2024-01-01"]}
    )
    new = pl.DataFrame(
        {"player_id": ["a"], "rank": [5], "date": ["2024-01-01"]}
    )
    out = upsert_data(new, existing, ["player_id", "date"]).sort("player_id")
    assert out.to_dicts() == [
        {"player_id": "a", "rank": 5, "date": "2024-01-01"},
        {"player_id": "b", "rank": 2, "date": "2024-01-01"},
    ]


def test_tournament_summary_counts_singles_winner_name(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.storage.s3_data_store.USE_S3", False)
    monkeypatch.setattr("backend.storage.s3_data_store.LOCAL_DATA_DIR", tmp_path)

    tournaments = pl.DataFrame(
        {
            "year": [2024, 2024],
            "tournament_type": ["gs", "atp"],
            "tournament_name": ["AO", "IW"],
            "singles_winner_name": ["A Player", None],
            "singles_winner_id": ["a1", None],
        }
    )
    tournaments.write_parquet(tmp_path / "tournaments.parquet")

    summary = get_data_summary()
    assert summary["tournaments"] is not None
    assert summary["tournaments"]["with_winners"] == 1
