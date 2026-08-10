# backend/scraper/player_utils.py
"""Player-related utility functions."""

from __future__ import annotations

import re
import unicodedata


_PLAYER_HREF_RE = re.compile(r"/players/([^/]+)/([^/]+)/")


def generate_player_slug(player_name: str) -> str:
    """
    Generate a URL slug from a player name.

    Accented characters are ASCII-folded so names like "Alcaraz Garfia"
    / "Müller" produce ATP-like slugs.
    """
    normalized = unicodedata.normalize("NFKD", player_name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = ascii_name.lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9-]", "", slug)


def extract_player_id(href: str | list | None) -> str | None:
    """Extract player ID from an ATP Tour player URL."""
    if not isinstance(href, str):
        return None
    match = _PLAYER_HREF_RE.search(href)
    return match.group(2) if match else None


def extract_player_slug(href: str | list | None) -> str | None:
    """Extract the URL slug segment from an ATP Tour player URL."""
    if not isinstance(href, str):
        return None
    match = _PLAYER_HREF_RE.search(href)
    return match.group(1) if match else None


def slug_for_player(
    player_name: str | None,
    *,
    stored_slug: str | None = None,
    href: str | None = None,
) -> str:
    """Prefer slug from href, then stored slug, then generated from name."""
    from_href = extract_player_slug(href)
    if from_href:
        return from_href
    if stored_slug:
        return stored_slug
    return generate_player_slug(player_name or "")
