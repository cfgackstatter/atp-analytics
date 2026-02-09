# backend/scraper/player_utils.py
"""Player-related utility functions."""

import re


def generate_player_slug(player_name: str) -> str:
    """
    Generate URL slug from player name.

    Args:
        player_name: Player's full name

    Returns:
        URL-safe slug
    """
    return re.sub(r'[^a-z0-9-]', '', player_name.lower().replace(' ', '-'))


def extract_player_id(href: str | list | None) -> str | None:
    """
    Extract player ID from ATP Tour URL href.

    Args:
        href: URL or href attribute

    Returns:
        Player ID or None
    """
    if not isinstance(href, str):
        return None
    match = re.search(r'/players/[^/]+/([^/]+)/', href)
    return match.group(1) if match else None