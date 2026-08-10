"""Shared parsing helpers for scraped text."""

from __future__ import annotations


def parse_int(text: str | None) -> int | None:
    """Parse integer from scraped text (commas, +/-, '-', 'T' prefix)."""
    if not text:
        return None
    cleaned = text.strip().replace(",", "").replace("T", "")
    if not cleaned or cleaned == "-":
        return None
    return int(cleaned) if cleaned.lstrip("-+").isdigit() else None
