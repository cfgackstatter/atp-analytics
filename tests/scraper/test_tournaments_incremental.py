import polars as pl

from backend.scraper.tournament_scraper import year_type_already_complete


def test_year_type_complete_skips_past_with_winners_only():
    existing = pl.DataFrame(
        {
            "year": [2020, 2020],
            "tournament_type": ["atp", "atp"],
            "singles_winner_id": ["p1", None],
        }
    )
    assert year_type_already_complete(existing, 2020, "atp", current_year=2026)
    assert not year_type_already_complete(existing, 2020, "gs", current_year=2026)
    assert not year_type_already_complete(existing, 2026, "atp", current_year=2026)
