"""Tests for tournament date-range parsing."""

from backend.scraper.tournament_scraper import _parse_date_range


def test_parse_same_month_range():
    assert _parse_date_range("10 - 16 January, 2024") == ("2024-01-10", "2024-01-16")


def test_parse_cross_month_range():
    assert _parse_date_range("28 January - 3 February, 2024") == (
        "2024-01-28",
        "2024-02-03",
    )


def test_parse_cross_year_range():
    assert _parse_date_range("30 December, 2023 - 5 January, 2024") == (
        "2023-12-30",
        "2024-01-05",
    )


def test_parse_empty():
    assert _parse_date_range("") == (None, None)
